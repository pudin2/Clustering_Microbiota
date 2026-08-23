import base64
import datetime as dt
import io
import json
import mimetypes
import os
import re
import shutil
import sys
import traceback
import uuid
from email.parser import BytesParser
from email.policy import default
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import unquote, urlparse

import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd

from modules.load import load_dataframe_from_path
from modules.characterization import distribution_plots_from_loaded, normality_tests_from_loaded
from modules.kde import kde_from_loaded
from modules.kruskal_wallis import kruskal_wallis_from_loaded
from modules.mann_whitney import mann_whitney_from_loaded
from modules.dbscan import dbscan_from_loaded
from modules.exploration import (
    dataset_profile_from_loaded,
    correlation_from_loaded,
    dimensionality_from_loaded,
    cluster_review_from_loaded,
)
from modules.visualizations import visualization_from_loaded
from modules.smart_assistant import OpenAssistantEngine

APP_ROOT = Path(__file__).resolve().parent
DATA_DIR = Path(os.getenv('MICROBIOTA_DATA_DIR', APP_ROOT / 'Datos'))
RUNS_DIR = Path(os.getenv('MICROBIOTA_RUNS_DIR', APP_ROOT / 'outputs' / 'web_runs'))
ANGULAR_DIST = Path(os.getenv('MICROBIOTA_ANGULAR_DIST', APP_ROOT.parent / 'microbiota-health-angular' / 'dist' / 'microbiota-health-workbench' / 'browser'))
DEFAULT_HOST = os.getenv('MICROBIOTA_HOST', '127.0.0.1')
DEFAULT_PORT = int(os.getenv('MICROBIOTA_PORT', '8765'))
SUPPORTED_EXTS = {'.csv', '.otus', '.txt', '.meta', '.taxonomy', '.tsv'}

DATA_DIR.mkdir(parents=True, exist_ok=True)
RUNS_DIR.mkdir(parents=True, exist_ok=True)


def json_safe(value, depth=0):
    if depth > 8:
        return str(value)
    if value is None or isinstance(value, (str, int, bool)):
        return value
    if isinstance(value, float):
        return value if np.isfinite(value) else None
    if isinstance(value, (np.integer,)):
        return int(value)
    if isinstance(value, (np.floating,)):
        v = float(value)
        return v if np.isfinite(v) else None
    if isinstance(value, (np.bool_,)):
        return bool(value)
    if isinstance(value, Path):
        return str(value)
    if isinstance(value, pd.DataFrame):
        return {
            'kind': 'table',
            'columns': [str(c) for c in value.columns],
            'rows': [json_safe(row, depth + 1) for row in value.replace({np.nan: None}).to_dict('records')],
            'rowCount': int(len(value)),
        }
    if isinstance(value, pd.Series):
        return {'kind': 'series', 'name': str(value.name or ''), 'values': json_safe(value.to_list(), depth + 1)}
    if isinstance(value, np.ndarray):
        return json_safe(value.tolist(), depth + 1)
    if isinstance(value, dict):
        return {str(k): json_safe(v, depth + 1) for k, v in value.items()}
    if isinstance(value, (list, tuple, set)):
        return [json_safe(v, depth + 1) for v in value]
    if hasattr(value, 'to_dict'):
        try:
            return json_safe(value.to_dict(), depth + 1)
        except Exception:
            pass
    return str(value)


def collect_tables(value, prefix='resultado', output=None):
    output = output if output is not None else []
    if isinstance(value, pd.DataFrame):
        frame = value.copy()
        preview = frame.head(1000).replace({np.nan: None})
        output.append({
            'name': prefix,
            'columns': [str(c) for c in preview.columns],
            'rows': json_safe(preview.to_dict('records')),
            'rowCount': int(len(frame)),
            'truncated': len(frame) > len(preview),
        })
        return output
    if isinstance(value, pd.Series):
        collect_tables(value.to_frame(), prefix, output)
        return output
    if isinstance(value, dict):
        for key, child in value.items():
            collect_tables(child, f'{prefix}.{key}', output)
    elif isinstance(value, (list, tuple)):
        for i, child in enumerate(value):
            collect_tables(child, f'{prefix}.{i + 1}', output)
    return output


def _parse_optional_float(value):
    return None if value in (None, '', []) else float(value)


def _parse_optional_int(value):
    return None if value in (None, '', []) else int(value)


def _list(value):
    if value in (None, ''):
        return None
    if isinstance(value, str):
        parts = [x.strip() for x in re.split(r'[,;]', value) if x.strip()]
        return parts or None
    return list(value) or None


def _dict(value):
    if value in (None, ''):
        return None
    if isinstance(value, dict):
        return value
    return json.loads(value)


def normalize_frontend_params(analysis, p):
    if analysis == 'exploration':
        return 'exploration', {
            'df_name': p.get('dataset'),
            'numeric_cols': _list(p.get('variables')),
            'max_category_values': int(p.get('maxCategoryValues', 12)),
            'verbose': bool(p.get('showSummary', True)),
        }
    if analysis == 'characterization':
        return analysis, {
            'df_name': p.get('dataset'), 'numeric_cols': _list(p.get('variables')),
            'analysis_mode': p.get('mode', 'both'), 'bins': int(p.get('bins', 80)),
            'plot_positive_hist': bool(p.get('positiveOnly', True)), 'verbose': bool(p.get('showSummary', True)),
        }
    if analysis == 'normality':
        return analysis, {
            'df_name': p.get('dataset'), 'numeric_cols': _list(p.get('variables')),
            'analysis_mode': p.get('mode', 'both'), 'value_mode': p.get('valueMode', 'both'),
            'test_method': p.get('testMethod', 'both'), 'alpha': float(p.get('alpha', .05)),
            'verbose': bool(p.get('showSummary', True)),
        }
    if analysis == 'correlation':
        return analysis, {
            'df_name': p.get('dataset'), 'numeric_cols': _list(p.get('variables')),
            'alpha': float(p.get('alpha', .05)), 'min_non_null': int(p.get('minNonNull', 3)),
            'max_plot_vars': int(p.get('maxPlotVariables', 20)), 'verbose': bool(p.get('showSummary', True)),
        }
    if analysis == 'visualization':
        y = p.get('yColumn') or None
        violin_vars = _list(p.get('violinVariables'))
        return analysis, {
            'df_name': p.get('dataset'), 'x_col': p.get('xColumn') or None, 'y_col': y,
            'hue_col': p.get('colorColumn') or None, 'group_col': p.get('violinGroup') or None,
            'violin_cols': violin_vars, 'rank_abundance': bool(p.get('rankAbundanceEnabled', False)),
            'abundance_cols': _list(p.get('abundanceColumns')), 'abundance_id_col': p.get('abundanceId') or 'ID',
            'top_n': _parse_optional_int(p.get('topN')), 'log_scale': bool(p.get('logScale', True)), 'verbose': True,
        }
    if analysis == 'kde':
        bws = p.get('kernelBandwidths')
        if isinstance(bws, str):
            parsed = []
            for item in _list(bws) or []:
                if ':' in item:
                    k, v = item.split(':', 1); parsed.append((k.strip(), float(v)))
            bws = parsed or None
        return analysis, {
            'data_df_name': p.get('dataset'), 'grid_size': int(p.get('gridSize', 1000)),
            'cv_subsample': int(p.get('cvSubsample', 1000)), 'cv_folds': int(p.get('cvFolds', 3)),
            'cv_bw_grid': int(p.get('cvBandwidthGrid', 8)), 'min_bandwidth': float(p.get('minBandwidth', 1)),
            'cv_max_expansions': int(p.get('maxExpansions', 4)), 'test_kernel_bandwidths': bws,
            'verbose': bool(p.get('showSummary', True)),
        }
    if analysis == 'kruskal':
        return analysis, {
            'alpha': float(p.get('alpha', .05)), 'group_df_name': p.get('groupsDataset'),
            'value_df_name': p.get('valuesDataset'), 'group_col': p.get('groupColumn'),
            'id_col_group': p.get('groupId'), 'id_col_value': p.get('valuesId'),
            'value_cols': _list(p.get('variables')), 'min_group_size': int(p.get('minGroupSize', 3)),
            'apply_fdr': bool(p.get('applyFdr', True)), 'verbose': bool(p.get('showSummary', True)),
        }
    if analysis == 'mann':
        groups = _list(p.get('groupsToCompare'))
        return 'mann_whitney', {
            'alpha': float(p.get('alpha', .05)), 'group_df_name': p.get('groupsDataset'),
            'value_df_name': p.get('valuesDataset'), 'group_col': p.get('groupColumn'),
            'groups_to_compare': tuple(groups) if groups else None, 'id_col_group': p.get('groupId'),
            'id_col_value': p.get('valuesId'), 'value_cols': _list(p.get('variables')),
            'min_group_size': int(p.get('minGroupSize', 3)), 'alternative': p.get('alternative', 'two-sided'),
            'apply_fdr': bool(p.get('applyFdr', True)), 'verbose': bool(p.get('showSummary', True)),
        }
    if analysis == 'reduction':
        thresholds = p.get('pcaThresholds') or [0.8, 0.9, 0.95]
        if isinstance(thresholds, str): thresholds = [float(x) for x in _list(thresholds) or []]
        return 'dimensionality', {
            'data_df_name': p.get('dataset'), 'id_col': p.get('idColumn') or None,
            'feature_cols': _list(p.get('features')), 'missing_strategy': p.get('missingStrategy', 'fill_zero'),
            'remove_zero_rows': bool(p.get('removeZeroRows', True)), 'min_prevalence': _parse_optional_float(p.get('minPrevalence')),
            'min_total_abundance': _parse_optional_float(p.get('minAbundance')), 'transform_method': p.get('transformMethod', 'none'),
            'pseudocount': float(p.get('pseudocount', 1)), 'scale': bool(p.get('scale', True)),
            'embedding_method': p.get('embeddingMethod', 'pca'), 'n_components': int(p.get('components', 2)),
            'random_state': int(p.get('randomState', 42)), 'embedding_kwargs': _dict(p.get('embeddingJson')),
            'variance_thresholds': tuple(float(x) for x in thresholds), 'verbose': bool(p.get('showSummary', True)),
        }
    if analysis == 'dbscan':
        return analysis, {
            'data_df_name': p.get('dataDataset'), 'id_col': p.get('dataId') or None, 'feature_cols': _list(p.get('features')),
            'meta_df_name': p.get('metaDataset') or None, 'meta_id_col': p.get('metaId') or None,
            'eps': float(p.get('eps', .5)), 'min_samples': int(p.get('minSamples', 5)),
            'calculate_k_distance': bool(p.get('calculateKDistance', True)), 'k_distance_min_samples': int(p.get('kDistanceMinSamples', 5)),
            'drop_non_numeric': bool(p.get('dropNonNumeric', True)), 'missing_strategy': p.get('missingStrategy', 'fill_zero'),
            'remove_zero_rows': bool(p.get('removeZeroRows', True)), 'min_prevalence': _parse_optional_float(p.get('minPrevalence')),
            'min_total_abundance': _parse_optional_float(p.get('minAbundance')), 'transform_method': p.get('transformMethod', 'none'),
            'pseudocount': float(p.get('pseudocount', 1)), 'scale': bool(p.get('scale', True)),
            'embedding_method': p.get('embeddingMethod', 'pca'), 'n_components': int(p.get('components', 2)),
            'random_state': int(p.get('randomState', 42)), 'embedding_kwargs': _dict(p.get('embeddingJson')),
            'plot_k_distance_graph': bool(p.get('saveKDistanceFigure', True)), 'plot_embedding_graph': bool(p.get('saveEmbeddingFigure', True)),
            'summary_numeric_cols': _list(p.get('numericSummary')), 'summary_categorical_cols': _list(p.get('categoricalSummary')),
            'summary_numeric_aggs': tuple(_list(p.get('aggregations')) or ['median']), 'verbose': bool(p.get('showSummary', True)),
        }
    if analysis == 'review':
        return 'cluster_review', {
            'df_name': p.get('dataset'), 'label_col': p.get('clusterColumn'), 'feature_cols': _list(p.get('features')),
            'ignore_noise': bool(p.get('ignoreNoise', True)), 'noise_label': str(p.get('noiseLabel', '-1')),
            'min_cluster_size': int(p.get('minClusters', 3)), 'verbose': bool(p.get('showSummary', True)),
        }
    raise ValueError(f'Análisis no soportado: {analysis}')


class WorkbenchState:
    def __init__(self):
        self.dfs = {}
        self.files = {}
        self.engine = OpenAssistantEngine(self.dfs)
        self.runs = []
        self.reload_datasets()
        self.load_saved_runs()

    def reload_datasets(self):
        self.dfs.clear(); self.files.clear()
        for path in sorted(DATA_DIR.iterdir()):
            if path.is_file() and path.suffix.lower() in SUPPORTED_EXTS:
                try:
                    key = path.stem
                    self.dfs[key] = load_dataframe_from_path(path)
                    self.files[key] = path
                except Exception as exc:
                    print(f'No se pudo cargar {path.name}: {exc}')
        self.engine.update_dfs(self.dfs)

    def dataset_metadata(self):
        items = []
        for idx, (key, df) in enumerate(self.dfs.items(), 1):
            numeric = []
            categorical = []
            categories = {}
            for col in df.columns:
                s = df[col]
                parsed = pd.to_numeric(s, errors='coerce')
                numeric_ratio = parsed.notna().sum() / max(s.notna().sum(), 1)
                if pd.api.types.is_numeric_dtype(s) or numeric_ratio >= .85:
                    numeric.append(str(col))
                else:
                    categorical.append(str(col))
                    unique = [json_safe(v) for v in s.dropna().unique().tolist()[:100]]
                    if len(unique) <= 100:
                        categories[str(col)] = unique
            path = self.files.get(key)
            items.append({
                'id': idx, 'key': key, 'name': path.name if path else key, 'rows': int(len(df)), 'columns': int(len(df.columns)),
                'status': 'Listo', 'type': path.suffix.lstrip('.').upper() if path else 'Dataset',
                'columnNames': [str(c) for c in df.columns], 'numericColumns': numeric,
                'categoricalColumns': categorical, 'categories': categories,
            })
        return items

    def save_upload(self, filename, content):
        safe_name = Path(filename).name
        suffix = Path(safe_name).suffix.lower()
        if suffix not in SUPPORTED_EXTS:
            raise ValueError(f'Formato no soportado: {suffix}. Usa CSV, TSV, TXT, OTUS, META o TAXONOMY.')
        target = DATA_DIR / safe_name
        target.write_bytes(content)
        self.reload_datasets()
        return target

    def execute(self, frontend_analysis, frontend_params):
        analysis, params = normalize_frontend_params(frontend_analysis, frontend_params)
        funcs = {
            'exploration': dataset_profile_from_loaded,
            'characterization': distribution_plots_from_loaded,
            'normality': normality_tests_from_loaded,
            'correlation': correlation_from_loaded,
            'visualization': visualization_from_loaded,
            'kde': kde_from_loaded,
            'kruskal': kruskal_wallis_from_loaded,
            'mann_whitney': mann_whitney_from_loaded,
            'dimensionality': dimensionality_from_loaded,
            'dbscan': dbscan_from_loaded,
            'cluster_review': cluster_review_from_loaded,
        }
        run_id = dt.datetime.now().strftime('%Y%m%d_%H%M%S_') + uuid.uuid4().hex[:6]
        run_dir = RUNS_DIR / run_id; run_dir.mkdir(parents=True, exist_ok=True)
        plt.close('all')
        original_show = plt.show
        plt.show = lambda *args, **kwargs: None
        try:
            result = funcs[analysis](dfs=self.dfs, **params)
        finally:
            plt.show = original_show
        figures = []
        for i, num in enumerate(plt.get_fignums(), 1):
            fig = plt.figure(num)
            file = run_dir / f'figure_{i}.png'
            fig.savefig(file, dpi=140, bbox_inches='tight')
            figures.append({'name': file.name, 'url': f'/api/runs/{run_id}/files/{file.name}'})
        plt.close('all')
        tables = collect_tables(result)
        summary = json_safe(result)
        payload = {
            'id': run_id, 'analysis': frontend_analysis, 'backendAnalysis': analysis,
            'createdAt': dt.datetime.now().isoformat(timespec='seconds'), 'parameters': json_safe(frontend_params),
            'tables': tables, 'figures': figures, 'result': summary,
        }
        (run_dir / 'run.json').write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding='utf-8')
        self.runs.insert(0, payload)
        return payload

    def load_saved_runs(self):
        self.runs = []
        for run_file in sorted(RUNS_DIR.glob('*/run.json'), reverse=True)[:50]:
            try: self.runs.append(json.loads(run_file.read_text(encoding='utf-8')))
            except Exception: pass

STATE = WorkbenchState()


class ApiHandler(BaseHTTPRequestHandler):
    server_version = 'MicrobiotaAPI/1.0'

    def _cors(self):
        self.send_header('Access-Control-Allow-Origin', '*')
        self.send_header('Access-Control-Allow-Headers', 'Content-Type')
        self.send_header('Access-Control-Allow-Methods', 'GET, POST, OPTIONS')

    def do_OPTIONS(self):
        self.send_response(204); self._cors(); self.end_headers()

    def do_GET(self):
        parsed = urlparse(self.path); path = parsed.path
        if path == '/api/health': return self._json({'ok': True, 'datasets': len(STATE.dfs)})
        if path == '/api/datasets': return self._json({'datasets': STATE.dataset_metadata()})
        if path == '/api/runs':
            return self._json({'runs': [{k: v for k, v in r.items() if k != 'result'} for r in STATE.runs[:50]]})
        m = re.fullmatch(r'/api/runs/([^/]+)', path)
        if m:
            run = next((r for r in STATE.runs if r.get('id') == m.group(1)), None)
            return self._json(run or {'error': 'Corrida no encontrada'}, 200 if run else 404)
        m = re.fullmatch(r'/api/runs/([^/]+)/files/(.+)', path)
        if m:
            run_id, name = m.group(1), Path(unquote(m.group(2))).name
            file = (RUNS_DIR / run_id / name).resolve()
            if str(file).startswith(str((RUNS_DIR / run_id).resolve())) and file.exists():
                return self._file(file)
            return self._json({'error': 'Archivo no encontrado'}, 404)
        if path.startswith('/api/'):
            return self._json({'error': 'Ruta no encontrada'}, 404)
        return self._serve_angular(path)

    def do_POST(self):
        parsed = urlparse(self.path); path = parsed.path
        try:
            if path == '/api/datasets/upload':
                files = self._multipart_files()
                if not files: return self._json({'error': 'No se recibieron archivos'}, 400)
                saved = [STATE.save_upload(name, content).name for name, content in files]
                return self._json({'saved': saved, 'datasets': STATE.dataset_metadata()}, 201)
            payload = self._read_json()
            if path == '/api/ask':
                response = STATE.engine.answer(
                    payload.get('question', ''), selected_dataset=payload.get('dataset') or None,
                    provider=payload.get('provider') or 'local', model=payload.get('model') or 'phi4-mini-reasoning')
                return self._json({'text': response.text, 'target_analysis': response.target_analysis,
                                   'suggestions': json_safe(response.suggestions), 'warnings': json_safe(response.warnings),
                                   'context': json_safe(response.context)})
            if path == '/api/analyze':
                response = STATE.engine.analyze_datasets()
                return self._json({'text': response.text, 'target_analysis': response.target_analysis,
                                   'suggestions': json_safe(response.suggestions), 'warnings': json_safe(response.warnings),
                                   'context': json_safe(response.context)})
            if path == '/api/run':
                if not STATE.dfs: return self._json({'error': 'Carga al menos un dataset antes de ejecutar.'}, 400)
                return self._json(STATE.execute(payload.get('analysis'), payload.get('params') or {}), 201)
            return self._json({'error': 'Ruta no encontrada'}, 404)
        except Exception as exc:
            traceback.print_exc()
            return self._json({'error': str(exc), 'detail': traceback.format_exc().splitlines()[-8:]}, 500)

    def _read_json(self):
        length = int(self.headers.get('Content-Length', '0') or 0)
        if not length: return {}
        return json.loads(self.rfile.read(length).decode('utf-8') or '{}')

    def _multipart_files(self):
        ctype = self.headers.get('Content-Type', '')
        if 'multipart/form-data' not in ctype: return []
        length = int(self.headers.get('Content-Length', '0') or 0)
        raw = self.rfile.read(length)
        msg = BytesParser(policy=default).parsebytes(
            f'Content-Type: {ctype}\r\nMIME-Version: 1.0\r\n\r\n'.encode() + raw)
        out = []
        for part in msg.iter_parts():
            filename = part.get_filename()
            if filename: out.append((filename, part.get_payload(decode=True) or b''))
        return out

    def _json(self, payload, status=200):
        data = json.dumps(payload, ensure_ascii=False).encode('utf-8')
        self.send_response(status); self._cors(); self.send_header('Content-Type', 'application/json; charset=utf-8')
        self.send_header('Content-Length', str(len(data))); self.end_headers(); self.wfile.write(data)

    def _file(self, path):
        data = path.read_bytes(); self.send_response(200); self._cors()
        self.send_header('Content-Type', mimetypes.guess_type(path.name)[0] or 'application/octet-stream')
        self.send_header('Content-Length', str(len(data))); self.end_headers(); self.wfile.write(data)

    def _serve_angular(self, path):
        if not ANGULAR_DIST.exists():
            return self._json({'error': 'Angular no está compilado. Ejecuta npm run build en microbiota-health-angular.'}, 404)
        rel = path.lstrip('/') or 'index.html'
        candidate = (ANGULAR_DIST / rel).resolve()
        if not str(candidate).startswith(str(ANGULAR_DIST.resolve())) or not candidate.is_file():
            candidate = ANGULAR_DIST / 'index.html'
        return self._file(candidate)

    def log_message(self, fmt, *args):
        print('[HTTP]', fmt % args)


def run(host=DEFAULT_HOST, port=DEFAULT_PORT):
    server = ThreadingHTTPServer((host, int(port)), ApiHandler)
    print(f'Microbiota Workbench: http://{host}:{port}')
    print(f'Datasets: {DATA_DIR}')
    print(f'Angular dist: {ANGULAR_DIST}')
    try: server.serve_forever()
    except KeyboardInterrupt: pass
    finally: server.server_close()

if __name__ == '__main__':
    run()
