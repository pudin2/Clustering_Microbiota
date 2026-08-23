import contextlib
import datetime as _dt
import io
import json
import os
import queue
import re
import threading
import traceback
import unicodedata
import webbrowser
from pathlib import Path
import tkinter as tk
from tkinter import filedialog, messagebox, simpledialog, ttk

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
from matplotlib.backends.backend_tkagg import FigureCanvasTkAgg, NavigationToolbar2Tk
from matplotlib.figure import Figure

try:
    from PIL import Image, ImageTk
    HAS_PIL = True
except Exception:
    Image = None
    ImageTk = None
    HAS_PIL = False

from modules.load import load_dataframe_from_path
from modules.characterization import distribution_plots_from_loaded, normality_tests_from_loaded
from modules.kde import kde_from_loaded
from modules.kruskal_wallis import kruskal_wallis_from_loaded
from modules.mann_whitney import mann_whitney_from_loaded
from modules.dbscan import dbscan_from_loaded
from modules.exploration import (
    cluster_review_from_loaded,
    correlation_from_loaded,
    dataset_profile_from_loaded,
    dimensionality_from_loaded,
)
from modules.visualizations import (
    Debouncer,
    InteractiveController,
    PresetStore,
    ViewHistory,
    VisualizationConfig,
    build_visualization,
    dataset_from_selection,
    export_plot_result,
    infer_filter_specs,
    recommend_visualizations,
    suggest_analysis_routes,
    visualization_from_loaded,
)
from modules.smart_assistant import AssistantResponse, OpenAssistantEngine


APP_TITLE = "Microbiota Statistical Workbench"
DEFAULT_OUTPUT_DIR = Path(__file__).resolve().parents[1] / "outputs_gui"
HELP_ICON_TEXT = "!"

HELP_TEXTS = {
    "__button__.Cargar": "Carga uno o varios archivos CSV o tabulados. Cada archivo queda disponible como dataset dentro de la sesion.",
    "__button__.Vista": "Abre una vista rapida del dataset seleccionado para revisar columnas y primeras filas.",
    "__button__.Quitar": "Quita de memoria el dataset seleccionado. No borra el archivo original.",
    "__button__.Cambiar": "Cambia la carpeta donde se guardan tablas, figuras y manifiestos de cada corrida.",
    "__button__.Abrir": "Abre la carpeta de salida actual en el explorador de archivos.",
    "__button__.Cargar corrida": "Carga una carpeta de resultados previamente generada para verla en el panel Resultados.",
    "__button__.Historial": "Busca corridas guardadas dentro de la carpeta de salida y las lista en Resultados.",
    "__button__.Abrir seleccionado": "Abre la tabla, figura o HTML interactivo seleccionado con la aplicacion predeterminada.",
    "__button__.Actualizar vista": "Recarga la previsualizacion del resultado seleccionado.",
    "__button__.Abrir carpeta": "Abre la carpeta completa de la corrida activa.",
    "__button__.Perfilar dataset": "Analiza tipos de columnas, faltantes, continuidad probable y bins sugeridos. Es el primer paso recomendado.",
    "__button__.Calcular correlaciones": "Calcula Pearson y Spearman, matriz de correlacion, p-valores y correcciones por multiples pruebas.",
    "__button__.Generar visualizaciones": "Genera las visualizaciones configuradas y las guarda como corrida.",
    "__button__.Actualizar constructor": "Redibuja la grafica del constructor usando las capas marcadas.",
    "__button__.Guardar constructor": "Guarda la grafica actual del constructor, los datos usados y el manifest en Resultados.",
    "__button__.Ejecutar caracterizacion": "Genera resumen descriptivo e histogramas del dataset seleccionado.",
    "__button__.Ejecutar normalidad": "Evalua supuestos de distribucion para variables numericas.",
    "__button__.Ejecutar KDE": "Estima densidades KDE para abundancias positivas y compara kernels.",
    "__button__.Ejecutar Kruskal-Wallis": "Compara tres o mas grupos para cada variable numerica seleccionada.",
    "__button__.Ejecutar Mann-Whitney": "Compara dos grupos para cada variable numerica seleccionada.",
    "__button__.Ejecutar reduccion": "Aplica preprocesamiento y reduccion dimensional sin hacer clustering.",
    "__button__.Ejecutar DBSCAN": "Ejecuta DBSCAN con los parametros definidos y guarda tablas, metricas y figuras.",
    "__button__.Revisar clusterizacion": "Evalua clusters ya existentes con metricas internas, tamanos, ruido y recomendacion.",
    "__button__.Preguntar": "Envia tu objetivo al agente matematico. Phi-4 revisa la ruta, pero Python conserva los calculos.",
    "__button__.Analizar datasets": "Hace una revision preliminar de estructura, calidad, faltantes, grupos y riesgos antes de elegir pruebas.",
    "__button__.Aplicar sugerencias": "Llena automaticamente los campos sugeridos por el asistente en la pestaña correspondiente.",
    "df_name": "Elige el dataset cargado que quieres analizar.",
    "assistant_dataset": "Dataset sobre el que quieres preguntar. Si lo dejas vacio, el asistente escoge uno.",
    "assistant_question": "Describe el objetivo matematico o estadistico. El agente propone una ruta de pruebas con paths reales del proyecto.",
    "assistant_provider": "Local usa Phi-4 Mini Reasoning mediante Ollama. Reglas desactiva el LLM; Cloud queda como opcion compatible.",
    "assistant_model": "Modelo del agente. Para 12 GB de RAM se deja por defecto phi4-mini-reasoning en Ollama local.",
    "data_df_name": "Elige el dataset que contiene las variables principales del analisis.",
    "meta_df_name": "Dataset con variables descriptivas para anexar o resumir; puede ser el mismo dataset principal.",
    "id_col": "Columna que identifica cada muestra o persona. Usualmente ID.",
    "meta_id_col": "Columna ID del dataset meta para unirlo con el resultado.",
    "numeric_cols": "Columnas numericas a analizar. Puedes seleccionar varias; se iran acumulando separadas por coma.",
    "feature_cols": "Variables numericas que entran al modelo o metrica. Selecciona varias si quieres comparar perfiles.",
    "value_cols": "Variables que se analizaran como valores de respuesta. Si queda vacio, se usan las numericas disponibles.",
    "group_col": "Columna categorica que define grupos, por ejemplo sex, bmi_class o ciudad.",
    "groups_to_compare": "Selecciona exactamente dos grupos para Mann-Whitney.",
    "alpha": "Nivel de significancia. 0.05 es comun; valores menores son mas estrictos.",
    "bins": "Numero de barras del histograma. Si no sabes, usa Exploracion para ver bins sugeridos.",
    "max_category_values": "Maximo de categorias frecuentes que se listan por columna categorica.",
    "analysis_mode": "by_column analiza variable por variable; full_matrix aplana todas; both ejecuta ambos.",
    "value_mode": "all usa todos los valores; positive solo positivos; both compara ambos enfoques.",
    "test_method": "Prueba estadistica de distribucion. both ejecuta Shapiro y Anderson cuando aplica.",
    "min_non_null": "Minimo de datos no faltantes para aceptar una variable en el calculo.",
    "max_plot_vars": "Maximo de variables dibujadas en el heatmap para mantenerlo legible.",
    "x_col": "Variable del eje X para graficas conjuntas y el constructor visual.",
    "y_col": "Variable del eje Y para graficas conjuntas y el constructor visual.",
    "hue_col": "Variable para colorear o comparar grupos. Puede dejarse vacia.",
    "violin_cols": "Variables numericas para graficos de violin. Puedes seleccionar varias.",
    "rank_abundance": "Activa rank-abundancia para datos tipo OTU o abundancias.",
    "abundance_cols": "Columnas de abundancia. Si queda vacio, se intentan usar las numericas del dataset.",
    "abundance_id_col": "Columna de identificador que no debe tratarse como abundancia.",
    "top_n": "Numero maximo de OTUs o features a mostrar en rank-abundancia.",
    "log_scale": "Usa escala logaritmica cuando los valores tienen rangos muy diferentes.",
    "grid_size": "Cantidad de puntos para evaluar KDE. Mas puntos dan curva mas fina, pero tarda mas.",
    "cv_subsample": "Muestras usadas para validar bandwidth. Aumentarlo mejora estabilidad y aumenta tiempo.",
    "cv_folds": "Particiones para validacion cruzada. Usa 3 si no estas seguro.",
    "cv_bw_grid": "Cantidad de bandwidths candidatos por kernel.",
    "min_bandwidth": "Piso minimo del bandwidth para evitar curvas artificialmente estrechas.",
    "cv_max_expansions": "Cuantas veces se amplia la busqueda si el mejor bandwidth cae en un borde.",
    "test_kernel_bandwidths": "Opcional: escribe kernel=valor, por ejemplo gaussian=1.5, cauchy=2.",
    "min_group_size": "Minimo de observaciones por grupo para aceptar una prueba.",
    "apply_fdr": "Aplica Benjamini-Hochberg para controlar falsos descubrimientos.",
    "missing_strategy": "Como tratar faltantes: fill_zero, drop_rows o median.",
    "remove_zero_rows": "Quita filas cuya suma numerica es cero. Util en matrices de abundancia.",
    "min_prevalence": "Filtro de variables por proporcion minima de valores positivos. Ejemplo: 0.05.",
    "min_total_abundance": "Filtro por suma minima de abundancia en una variable.",
    "transform_method": "Transformacion antes de modelar: none, log1p o clr.",
    "pseudocount": "Valor agregado antes de CLR para evitar log de cero. Usualmente 1.0.",
    "scale": "Estandariza variables para que ninguna domine solo por escala.",
    "embedding_method": "Tecnica de reduccion: pca es la opcion inicial mas interpretable.",
    "n_components": "Numero de dimensiones de salida. Usa 2 para graficar, 3 si quieres mas estructura.",
    "random_state": "Semilla para reproducibilidad.",
    "embedding_kwargs": "Opciones avanzadas en JSON, por ejemplo {\"perplexity\": 20}. Puede quedar vacio.",
    "variance_thresholds": "Umbrales para revisar cuantas componentes PCA explican la varianza. Ejemplo: 0.8, 0.9, 0.95.",
    "eps": "Radio de vecindad de DBSCAN. Revisalo con k-distance.",
    "min_samples": "Minimo de vecinos para formar region densa.",
    "calculate_k_distance": "Calcula una curva de distancia para orientar la eleccion de eps.",
    "k_distance_min_samples": "Vecino usado en la curva k-distance. Suele coincidir con min_samples o ser cercano.",
    "summary_numeric_cols": "Variables numericas que se resumiran por cluster.",
    "summary_categorical_cols": "Variables categoricas que se contaran por cluster.",
    "summary_numeric_aggs": "Agregaciones separadas por coma: median, mean, min, max.",
    "label_col": "Columna que contiene etiquetas de cluster ya calculadas.",
    "ignore_noise": "Ignora la etiqueta de ruido al calcular metricas internas.",
    "noise_label": "Etiqueta usada para ruido. En DBSCAN normalmente es -1.",
    "layer_scatter": "Muestra puntos individuales.",
    "layer_line": "Une puntos ordenados por X. Util en series o trayectorias.",
    "layer_trend": "Agrega una tendencia lineal para ver direccion general.",
    "layer_density": "Agrega una capa de densidad/hexbin debajo de los puntos.",
    "layer_centroids": "Marca promedios por grupo cuando hay columna Color.",
    "builder_log_x": "Usa escala logaritmica en X.",
    "builder_log_y": "Usa escala logaritmica en Y.",
    "point_alpha": "Opacidad de puntos entre 0 y 1.",
    "point_size": "Tamano de los puntos en la grafica.",
    "verbose": "Escribe detalles de la ejecucion en el log lateral.",
    "plot_type": "Selecciona el tipo de gráfico. Automático elige una opción según X/Y y sus tipos.",
    "facet_col": "Divide la visualización en paneles por los valores de esta columna.",
    "builder_id_col": "Identificador del registro; se muestra en hover e inspector cuando está disponible.",
    "hover_cols": "Columnas extra que aparecerán al pasar el mouse por un punto. Sepáralas por coma.",
    "heatmap_cols": "Variables numéricas incluidas en el mapa de correlaciones.",
    "builder_title": "Título opcional para la visualización actual.",
    "max_facets": "Número máximo de paneles cuando usas Dividir por.",
    "builder_bins": "Número de bins para histogramas.",
    "auto_update": "Actualiza automáticamente la vista unos milisegundos después de cambiar un control.",
    "show_stats": "Calcula y muestra estadísticas asociadas al gráfico actual.",
    "abundance_group_col": "Genera una curva de rank-abundancia independiente por cada grupo.",
    "rank_show_cumulative": "Añade la abundancia acumulada a la visualización rank-abundancia.",
    "rank_highlight_top": "Cantidad de features superiores que se resaltan en rank-abundancia.",
    "rank_search": "Filtra rank-abundancia por texto contenido en el nombre de la feature.",
    "hover_enabled": "Activa tooltips al mover el mouse sobre puntos del gráfico.",
    "inspector_enabled": "Al hacer clic sobre un punto muestra el registro completo en el inspector.",
    "selection_mode": "Permite seleccionar observaciones con lazo o rectángulo para crear subconjuntos.",
    "legend_toggle": "Permite hacer clic en la leyenda para ocultar o volver a mostrar series.",
    "__button__.Recomendar vistas": "Analiza el dataset y propone gráficos útiles que puedes aplicar con un clic.",
    "__button__.Guardar preset": "Guarda la configuración actual del constructor para reutilizarla después.",
    "__button__.Cargar preset": "Recupera una configuración de visualización guardada anteriormente.",
    "__button__.Deshacer": "Vuelve a la configuración anterior del constructor visual.",
    "__button__.Rehacer": "Restaura una configuración que acabas de deshacer.",
    "__button__.Reset vista": "Restaura los límites originales de zoom y desplazamiento del gráfico.",
    "__button__.Abrir HTML": "Abre la versión Plotly interactiva en el navegador cuando está disponible.",
    "__button__.Crear dataset selección": "Crea un nuevo dataset en memoria con las observaciones seleccionadas en el gráfico.",
    "__button__.Exportar todo": "Exporta PNG, SVG, PDF, CSV, XLSX y HTML interactivo de la vista actual.",
}


def sanitize_name(value, fallback="artifact"):
    text = str(value).strip()
    text = re.sub(r"[^\w.\-]+", "_", text, flags=re.ASCII)
    text = text.strip("._")
    return text[:120] or fallback


def unique_name(name, existing):
    base = sanitize_name(name, "dataset")
    if base not in existing:
        return base
    i = 2
    while f"{base}_{i}" in existing:
        i += 1
    return f"{base}_{i}"


def split_list(text):
    if text is None:
        return None
    items = [x.strip() for x in str(text).replace(";", ",").split(",")]
    items = [x for x in items if x]
    return items or None


def parse_optional_float(text):
    text = str(text).strip()
    if not text:
        return None
    return float(text)


def parse_optional_int(text):
    text = str(text).strip()
    if not text:
        return None
    return int(text)


def parse_float_tuple(text, default=None):
    items = split_list(text)
    if not items:
        return default
    return tuple(float(item) for item in items)


def parse_bool(value):
    return bool(value)


def parse_tuple(text):
    items = split_list(text)
    return tuple(items) if items else None


def parse_json_dict(text):
    text = str(text).strip()
    if not text:
        return {}
    data = json.loads(text)
    if not isinstance(data, dict):
        raise ValueError("Debe ser un objeto JSON, por ejemplo: {\"perplexity\": 20}")
    return data


def parse_bandwidths(text):
    text = str(text).strip()
    if not text:
        return None
    if text.startswith("{"):
        data = json.loads(text)
        return {str(k): float(v) for k, v in data.items()}

    result = {}
    for part in text.replace(";", ",").split(","):
        part = part.strip()
        if not part:
            continue
        if "=" not in part:
            raise ValueError("Usa kernel=valor, por ejemplo gaussian=1.5")
        key, value = part.split("=", 1)
        result[key.strip()] = float(value.strip())
    return result or None


def json_safe(value):
    if value is None or isinstance(value, (str, int, float, bool)):
        return value
    if isinstance(value, (np.integer,)):
        return int(value)
    if isinstance(value, (np.floating,)):
        if np.isfinite(value):
            return float(value)
        return None
    if isinstance(value, (np.bool_,)):
        return bool(value)
    if isinstance(value, Path):
        return str(value)
    if isinstance(value, dict):
        safe = {}
        for k, v in value.items():
            if isinstance(v, (pd.DataFrame, pd.Series, np.ndarray)):
                safe[str(k)] = f"<{type(v).__name__} exported separately>"
            else:
                safe[str(k)] = json_safe(v)
        return safe
    if isinstance(value, (list, tuple)):
        if len(value) > 100:
            return f"<{type(value).__name__} length={len(value)} exported separately>"
        return [json_safe(v) for v in value]
    return repr(value)


class HelpTooltip:

    def __init__(self, widget, text, delay_ms=350, wraplength=340):
        self.widget = widget
        self.text = str(text)
        self.delay_ms = delay_ms
        self.wraplength = wraplength
        self._after_id = None
        self._tip = None

        widget.bind("<Enter>", self._schedule, add="+")
        widget.bind("<Leave>", self._hide, add="+")
        widget.bind("<Button-1>", self._toggle, add="+")


    def _schedule(self, _event=None):
        self._cancel()
        self._after_id = self.widget.after(self.delay_ms, self._show)


    def _cancel(self):
        if self._after_id is not None:
            try:
                self.widget.after_cancel(self._after_id)
            except Exception:
                pass
            self._after_id = None


    def _toggle(self, _event=None):
        self._cancel()
        if self._tip is not None:
            self._hide()
        else:
            self._show()


    def _show(self):
        if self._tip is not None or not self.text:
            return

        try:
            x = self.widget.winfo_rootx() + 18
            y = self.widget.winfo_rooty() + self.widget.winfo_height() + 8
        except Exception:
            x, y = 100, 100

        self._tip = tk.Toplevel(self.widget)
        self._tip.wm_overrideredirect(True)
        self._tip.wm_geometry(f"+{x}+{y}")
        self._tip.attributes("-topmost", True)

        frame = tk.Frame(self._tip, background="#fff7d6", borderwidth=1, relief="solid")
        frame.pack(fill="both", expand=True)

        label = tk.Label(
            frame,
            text=self.text,
            justify="left",
            background="#fff7d6",
            foreground="#20242a",
            font=("Segoe UI", 9),
            padx=10,
            pady=7,
            wraplength=self.wraplength,
        )
        label.pack()


    def _hide(self, _event=None):
        self._cancel()
        if self._tip is not None:
            try:
                self._tip.destroy()
            except Exception:
                pass
            self._tip = None


class FigureCapture:
    def __init__(self, figure_dir):
        self.figure_dir = Path(figure_dir)
        self.figure_dir.mkdir(parents=True, exist_ok=True)
        self.saved = []
        self.counter = 0
        self._old_show = None


    def __enter__(self):
        plt.switch_backend("Agg")
        fig = plt.figure(figsize=(0.1, 0.1))
        plt.close(fig)
        self._old_show = plt.show
        plt.show = self.show
        return self


    def __exit__(self, exc_type, exc, tb):
        self.save_open_figures()
        plt.show = self._old_show
        plt.close("all")


    def _title_for(self, fig):
        if getattr(fig, "_suptitle", None) is not None:
            text = fig._suptitle.get_text()
            if text:
                return text
        for ax in fig.axes:
            text = ax.get_title()
            if text:
                return text
        return "figure"


    def save_open_figures(self):
        for num in list(plt.get_fignums()):
            fig = plt.figure(num)
            self.counter += 1
            name = sanitize_name(self._title_for(fig), "figure")
            path = self.figure_dir / f"{self.counter:02d}_{name}.png"
            fig.savefig(path, dpi=180, bbox_inches="tight")
            self.saved.append(path)
            plt.close(fig)


    def show(self, *args, **kwargs):
        self.save_open_figures()


class ArtifactExporter:

    def __init__(self, run_dir):
        self.run_dir = Path(run_dir).resolve()
        self.tables_dir = self.run_dir / "tables"
        self.arrays_dir = self.run_dir / "arrays"
        self.objects_dir = self.run_dir / "objects"
        self.tables_dir.mkdir(parents=True, exist_ok=True)
        self.arrays_dir.mkdir(parents=True, exist_ok=True)
        self.objects_dir.mkdir(parents=True, exist_ok=True)
        self.manifest = {"tables": [], "arrays": [], "objects": [], "html": []}
        self.excel_tables = []


    def export(self, obj, prefix="result"):
        self._export_obj(obj, sanitize_name(prefix, "result"))
        self._write_excel_book()
        return self.manifest


    def _export_obj(self, obj, prefix):
        if getattr(obj, "artifact_kind", None) == "html":
            filename = getattr(obj, "filename", None) or f"{prefix}.html"
            path = self.objects_dir / sanitize_name(Path(filename).stem, prefix)
            path = path.with_suffix(".html")
            path.write_text(getattr(obj, "html", ""), encoding="utf-8")
            self.manifest["html"].append({
                "name": getattr(obj, "title", prefix),
                "path": str(path)
            })
            return

        if isinstance(obj, pd.DataFrame):
            path = self.tables_dir / f"{prefix}.csv"
            obj.to_csv(path, index=False, encoding="utf-8-sig")
            self.excel_tables.append((prefix, obj))
            self.manifest["tables"].append({"name": prefix, "path": str(path), "rows": int(obj.shape[0]), "columns": int(obj.shape[1])})
            return

        if isinstance(obj, pd.Series):
            path = self.tables_dir / f"{prefix}.csv"
            obj.to_frame().to_csv(path, index=True, encoding="utf-8-sig")
            self.excel_tables.append((prefix, obj.to_frame()))
            self.manifest["tables"].append({"name": prefix, "path": str(path), "rows": int(obj.shape[0]), "columns": 1})
            return

        if isinstance(obj, np.ndarray):
            arr = np.asarray(obj)
            if arr.ndim <= 2:
                path = self.arrays_dir / f"{prefix}.csv"
                pd.DataFrame(arr).to_csv(path, index=False, encoding="utf-8-sig")
            else:
                path = self.arrays_dir / f"{prefix}.npy"
                np.save(path, arr)
            self.manifest["arrays"].append({"name": prefix, "path": str(path), "shape": list(arr.shape)})
            return

        if isinstance(obj, dict):
            scalar_items = {}
            for key, value in obj.items():
                child_prefix = sanitize_name(f"{prefix}_{key}", prefix)
                if (
                    getattr(value, "artifact_kind", None) == "html"
                    or isinstance(value, (pd.DataFrame, pd.Series, np.ndarray, dict, list, tuple))
                ):
                    self._export_obj(value, child_prefix)
                else:
                    scalar_items[str(key)] = json_safe(value)
            if scalar_items:
                self._write_json(prefix, scalar_items)
            return

        if isinstance(obj, (list, tuple)):
            for i, value in enumerate(obj, start=1):
                self._export_obj(value, sanitize_name(f"{prefix}_{i:02d}", prefix))
            return

        self._write_json(prefix, json_safe(obj))


    def _write_json(self, name, payload):
        path = self.objects_dir / f"{sanitize_name(name)}.json"
        with path.open("w", encoding="utf-8") as fh:
            json.dump(payload, fh, ensure_ascii=False, indent=2)
        self.manifest["objects"].append({"name": name, "path": str(path)})


    def _write_excel_book(self):
        if not self.excel_tables:
            return
        path = self.run_dir / "tables.xlsx"
        try:
            with pd.ExcelWriter(path) as writer:
                used = set()
                for name, df in self.excel_tables:
                    sheet = sanitize_name(name, "sheet")[:31] or "sheet"
                    base = sheet
                    i = 2
                    while sheet in used:
                        suffix = f"_{i}"
                        sheet = f"{base[:31 - len(suffix)]}{suffix}"
                        i += 1
                    used.add(sheet)
                    df.to_excel(writer, sheet_name=sheet, index=False)
            self.manifest["excel_workbook"] = str(path)
        except Exception as exc:
            self.manifest["excel_workbook_error"] = str(exc)


class ScrollFrame(ttk.Frame):
    
    def __init__(self, master):
        super().__init__(master)
        self.canvas = tk.Canvas(self, highlightthickness=0)
        self.scrollbar = ttk.Scrollbar(self, orient="vertical", command=self.canvas.yview)
        self.inner = ttk.Frame(self.canvas)
        self.window_id = self.canvas.create_window((0, 0), window=self.inner, anchor="nw")

        self.canvas.configure(yscrollcommand=self.scrollbar.set)
        self.canvas.grid(row=0, column=0, sticky="nsew")
        self.scrollbar.grid(row=0, column=1, sticky="ns")
        self.grid_rowconfigure(0, weight=1)
        self.grid_columnconfigure(0, weight=1)

        self.inner.bind("<Configure>", self._on_inner_configure)
        self.canvas.bind("<Configure>", self._on_canvas_configure)


    def _on_inner_configure(self, _event):
        self.canvas.configure(scrollregion=self.canvas.bbox("all"))


    def _on_canvas_configure(self, event):
        self.canvas.itemconfigure(self.window_id, width=event.width)


class MicrobiotaGUI(tk.Tk):

    def __init__(self):
        super().__init__()
        self.title(APP_TITLE)
        self.geometry("1320x820")
        self.minsize(1120, 720)

        self.dfs = {}
        self.results = {}
        self.result_manifests = {}
        self.result_run_dirs = {}
        self.active_result_key = None
        self.current_table_path = None
        self.current_figure_path = None
        self.figure_image_ref = None
        self.visible_tables = {}
        self.visible_figures = {}
        self.last_run_dir = None
        self.worker = None
        self.msg_queue = queue.Queue()
        self.inputs = {}
        self.df_combos = []
        self.column_combos = []
        self.numeric_column_dropdowns = []
        self.categorical_column_dropdowns = []
        self.group_value_dropdowns = []
        self.loading_result_view = False
        self.results_lists_notebook = None
        self.assistant_engine = OpenAssistantEngine(self.dfs)
        self.assistant_last_response = None
        self.assistant_suggestion_payload = None

        # Estado del constructor visual V2
        self.visual_builder_result = None
        self.visual_builder_current_data = None
        self.visual_builder_current_config = None
        self.visual_builder_interaction = None
        self.visual_builder_selected_indices = []
        self.visual_builder_selected_df = None
        self.visual_builder_history = ViewHistory(max_items=100)
        self.visual_builder_presets = PresetStore()
        self.visual_builder_presets_loaded = False
        self.visual_builder_debouncer = Debouncer(self.after, self.after_cancel, delay_ms=400)
        self.visual_builder_applying_state = False
        self.visual_filter_rows = {}
        self.visual_filter_specs = {}
        self.visual_filter_dataset_name = None
        self.visual_recommendations = []

        self._configure_style()
        self._build_ui()
        self.after(150, self._poll_queue)


    def _configure_style(self):
        style = ttk.Style(self)
        try:
            style.theme_use("clam")
        except tk.TclError:
            pass
        style.configure("TFrame", background="#f5f6f8")
        style.configure("Sidebar.TFrame", background="#eef1f4")
        style.configure("Header.TLabel", background="#f5f6f8", foreground="#20242a", font=("Segoe UI", 16, "bold"))
        style.configure("Subtle.TLabel", background="#f5f6f8", foreground="#5d6673")
        style.configure("Help.TLabel", background="#fff2b8", foreground="#7a4d00", font=("Segoe UI", 9, "bold"))
        style.configure("TLabelframe", background="#f5f6f8")
        style.configure("TLabelframe.Label", font=("Segoe UI", 10, "bold"))
        style.configure("Accent.TButton", font=("Segoe UI", 10, "bold"))
        style.configure("Treeview", rowheight=24)


    def _build_ui(self):
        root = ttk.Frame(self)
        root.pack(fill="both", expand=True)
        root.grid_columnconfigure(0, minsize=340)
        root.grid_columnconfigure(1, weight=1)
        root.grid_rowconfigure(0, weight=1)

        sidebar = ttk.Frame(root, style="Sidebar.TFrame", padding=12)
        sidebar.grid(row=0, column=0, sticky="nsew")
        sidebar.grid_rowconfigure(5, weight=1)

        ttk.Label(sidebar, text="Microbiota Workbench", font=("Segoe UI", 15, "bold"), background="#eef1f4").grid(row=0, column=0, sticky="w")
        ttk.Label(sidebar, text="Datos en memoria, exportes por corrida", background="#eef1f4", foreground="#5d6673").grid(row=1, column=0, sticky="w", pady=(2, 12))

        data_box = ttk.LabelFrame(sidebar, text="Datasets cargados", padding=8)
        data_box.grid(row=2, column=0, sticky="nsew", pady=(0, 10))
        data_box.grid_columnconfigure(0, weight=1)

        btns = ttk.Frame(data_box)
        btns.grid(row=0, column=0, sticky="ew", pady=(0, 8))
        btns.grid_columnconfigure((0, 1, 2), weight=1)
        load_btn = ttk.Button(btns, text="Cargar", command=self.load_files)
        load_btn.grid(row=0, column=0, sticky="ew", padx=(0, 4))
        self._decorate_button_help(load_btn, "Cargar")
        preview_btn = ttk.Button(btns, text="Vista", command=self.preview_selected_dataset)
        preview_btn.grid(row=0, column=1, sticky="ew", padx=4)
        self._decorate_button_help(preview_btn, "Vista")
        remove_btn = ttk.Button(btns, text="Quitar", command=self.remove_selected_dataset)
        remove_btn.grid(row=0, column=2, sticky="ew", padx=(4, 0))
        self._decorate_button_help(remove_btn, "Quitar")

        self.dataset_tree = ttk.Treeview(data_box, columns=("shape",), show="tree headings", height=8)
        self.dataset_tree.heading("#0", text="Nombre")
        self.dataset_tree.heading("shape", text="Shape")
        self.dataset_tree.column("#0", width=190, stretch=True)
        self.dataset_tree.column("shape", width=95, anchor="center", stretch=False)
        self.dataset_tree.grid(row=1, column=0, sticky="nsew")

        output_box = ttk.LabelFrame(sidebar, text="Salida", padding=8)
        output_box.grid(row=3, column=0, sticky="ew", pady=(0, 10))
        output_box.grid_columnconfigure(0, weight=1)
        self.output_dir_var = tk.StringVar(value=str(DEFAULT_OUTPUT_DIR))
        ttk.Entry(output_box, textvariable=self.output_dir_var).grid(row=0, column=0, sticky="ew", pady=(0, 6))
        output_btns = ttk.Frame(output_box)
        output_btns.grid(row=1, column=0, sticky="ew")
        output_btns.grid_columnconfigure((0, 1), weight=1)
        change_btn = ttk.Button(output_btns, text="Cambiar", command=self.choose_output_dir)
        change_btn.grid(row=0, column=0, sticky="ew", padx=(0, 4))
        self._decorate_button_help(change_btn, "Cambiar")
        open_btn = ttk.Button(output_btns, text="Abrir", command=self.open_output_dir)
        open_btn.grid(row=0, column=1, sticky="ew", padx=(4, 0))
        self._decorate_button_help(open_btn, "Abrir")

        memory_box = ttk.LabelFrame(sidebar, text="Resultados cargados", padding=8)
        memory_box.grid(row=4, column=0, sticky="ew", pady=(0, 10))
        memory_box.grid_columnconfigure(0, weight=1)
        self.result_tree = ttk.Treeview(memory_box, columns=("created",), show="tree headings", height=5)
        self.result_tree.heading("#0", text="Analisis")
        self.result_tree.heading("created", text="Fecha")
        self.result_tree.column("#0", width=180, stretch=True)
        self.result_tree.column("created", width=125, stretch=False)
        self.result_tree.grid(row=0, column=0, sticky="ew")
        self.result_tree.bind("<<TreeviewSelect>>", self.on_result_selected)
        result_btns = ttk.Frame(memory_box)
        result_btns.grid(row=1, column=0, sticky="ew", pady=(8, 0))
        result_btns.grid_columnconfigure((0, 1), weight=1)
        load_run_btn = ttk.Button(result_btns, text="Cargar corrida", command=self.load_run_folder)
        load_run_btn.grid(row=0, column=0, sticky="ew", padx=(0, 4))
        self._decorate_button_help(load_run_btn, "Cargar corrida")
        history_btn = ttk.Button(result_btns, text="Historial", command=self.load_saved_runs)
        history_btn.grid(row=0, column=1, sticky="ew", padx=(4, 0))
        self._decorate_button_help(history_btn, "Historial")

        log_box = ttk.LabelFrame(sidebar, text="Log", padding=8)
        log_box.grid(row=5, column=0, sticky="nsew")
        log_box.grid_columnconfigure(0, weight=1)
        log_box.grid_rowconfigure(0, weight=1)
        self.log_text = tk.Text(log_box, height=12, wrap="word", relief="flat", bg="#ffffff", fg="#20242a")
        self.log_text.grid(row=0, column=0, sticky="nsew")

        main = ttk.Frame(root, padding=16)
        main.grid(row=0, column=1, sticky="nsew")
        main.grid_columnconfigure(0, weight=1)
        main.grid_rowconfigure(2, weight=1)

        ttk.Label(main, text="Panel de analisis", style="Header.TLabel").grid(row=0, column=0, sticky="w")
        ttk.Label(
            main,
            text=f"Empieza por Exploracion. Usa {HELP_ICON_TEXT} para saber que poner en cada campo o boton.",
            style="Subtle.TLabel"
        ).grid(row=1, column=0, sticky="w", pady=(2, 12))

        self.notebook = ttk.Notebook(main)
        self.notebook.grid(row=2, column=0, sticky="nsew")

        self._build_assistant_tab()
        self._build_exploration_tab()
        self._build_characterization_tab()
        self._build_normality_tab()
        self._build_correlation_tab()
        self._build_visualization_tab()
        self._build_kde_tab()
        self._build_kruskal_tab()
        self._build_mann_whitney_tab()
        self._build_dimensionality_tab()
        self._build_dbscan_tab()
        self._build_cluster_review_tab()
        self._build_results_tab()

        self.status_var = tk.StringVar(value="Listo")
        ttk.Label(main, textvariable=self.status_var, style="Subtle.TLabel").grid(row=3, column=0, sticky="ew", pady=(10, 0))


    def _new_tab(self, title):
        frame = ScrollFrame(self.notebook)
        self.notebook.add(frame, text=title)
        body = frame.inner
        body.grid_columnconfigure(0, weight=1)
        return body


    def _section(self, parent, title, row):
        box = ttk.LabelFrame(parent, text=title, padding=12)
        box.grid(row=row, column=0, sticky="ew", pady=(0, 12))
        box.grid_columnconfigure(1, weight=1)
        box.grid_columnconfigure(3, weight=1)
        return box


    def _help_text(self, group, key, label, kind="field", explicit=None):
        if explicit:
            return explicit
        if group and key:
            text = HELP_TEXTS.get(f"{group}.{key}")
            if text:
                return text
        if key:
            text = HELP_TEXTS.get(key)
            if text:
                return text
        if kind == "button":
            return f"Ejecuta la accion '{label}'. Los resultados se muestran en el log y, cuando aplica, en la pestaña Resultados."
        if kind == "check":
            return f"Activa o desactiva esta opcion: {label}."
        if kind == "columns":
            return f"Selecciona una o varias columnas para '{label}'. Cada seleccion se agrega separada por coma."
        return f"Completa el campo '{label}' con el valor solicitado para este analisis."


    def _add_help_marker(self, parent, text, row=0, column=1, sticky="w", padx=(6, 0)):
        marker = ttk.Label(parent, text=HELP_ICON_TEXT, style="Help.TLabel", padding=(5, 1))
        marker.grid(row=row, column=column, sticky=sticky, padx=padx)
        HelpTooltip(marker, text)
        return marker


    def _add_label_with_help(self, box, group, key, label, row, col, kind="field", help_text=None):
        frame = ttk.Frame(box)
        frame.grid(row=row, column=col, sticky="w", padx=(0, 8), pady=4)
        ttk.Label(frame, text=label).grid(row=0, column=0, sticky="w")
        self._add_help_marker(
            frame,
            self._help_text(group, key, label, kind=kind, explicit=help_text),
            row=0,
            column=1,
        )
        return frame


    def _add_entry(self, box, group, key, label, default="", row=0, col=0, width=22, help_text=None):
        self._add_label_with_help(box, group, key, label, row, col, help_text=help_text)
        var = tk.StringVar(value=str(default))
        entry = ttk.Entry(box, textvariable=var, width=width)
        entry.grid(row=row, column=col + 1, sticky="ew", pady=4, padx=(0, 16))
        self.inputs.setdefault(group, {})[key] = var
        return entry


    def _add_numeric_columns_dropdown(
        self,
        box,
        group,
        key,
        label,
        dataset_key,
        row=0,
        col=0,
        width=42,
        help_text=None
    ):
        self._add_label_with_help(
            box,
            group,
            key,
            label,
            row,
            col,
            kind="columns",
            help_text=help_text
        )

        numeric_var = tk.StringVar(value="")

        combo = ttk.Combobox(
            box,
            textvariable=numeric_var,
            values=[],
            width=width,
            state="normal"
        )

        combo.grid(
            row=row,
            column=col + 1,
            sticky="ew",
            pady=4,
            padx=(0, 16)
        )

        self.inputs.setdefault(group, {})[key] = numeric_var

        selector = {
            "group": group,
            "key": key,
            "dataset_key": dataset_key,
            "combo": combo,
            "var": numeric_var,
            "selected_text": ""
        }

        self.numeric_column_dropdowns.append(selector)

        combo.bind("<<ComboboxSelected>>", self.on_numeric_column_dropdown_selected)
        combo.bind("<KeyRelease>", self.on_numeric_columns_text_edited)
        combo.bind("<FocusOut>", self.on_numeric_columns_text_edited)

        return combo


    def get_numeric_columns_for_dataset(self, dataset_name):
        df = self.dfs.get(dataset_name)

        if df is None:
            return []

        numeric_cols = list(df.select_dtypes(include=[np.number]).columns)

        if numeric_cols:
            return [str(col) for col in numeric_cols]

        detected_cols = []

        for col in df.columns:
            converted = pd.to_numeric(df[col], errors="coerce")

            if converted.notna().sum() > 0:
                detected_cols.append(str(col))

        return detected_cols


    def refresh_numeric_column_dropdowns(self):
        for selector in self.numeric_column_dropdowns:
            group = selector["group"]
            dataset_key = selector["dataset_key"]
            combo = selector["combo"]
            numeric_var = selector["var"]

            dataset_var = self.inputs.get(group, {}).get(dataset_key)

            if dataset_var is None:
                columns = []
            else:
                dataset_name = dataset_var.get()
                columns = self.get_numeric_columns_for_dataset(dataset_name)

            current_selected = split_list(numeric_var.get()) or []
            valid_selected = [col for col in current_selected if col in columns]

            selected_text = ", ".join(valid_selected)

            numeric_var.set(selected_text)
            selector["selected_text"] = selected_text
            combo.configure(values=columns)


    def on_numeric_columns_text_edited(self, event):
        combo = event.widget

        for selector in self.numeric_column_dropdowns:
            if selector["combo"] == combo:
                selector["selected_text"] = selector["var"].get().strip()
                break


    def on_numeric_column_dropdown_selected(self, event):
        combo = event.widget

        for selector in self.numeric_column_dropdowns:
            if selector["combo"] == combo:
                selected_column = selector["var"].get().strip()
                previous_text = selector.get("selected_text", "")
                current_selected = split_list(previous_text) or []

                if selected_column:
                    if selected_column not in current_selected:
                        current_selected.append(selected_column)

                    selected_text = ", ".join(current_selected)
                    selector["var"].set(selected_text)
                    selector["selected_text"] = selected_text

                break


    def _add_categorical_columns_dropdown(
        self,
        box,
        group,
        key,
        label,
        dataset_key,
        row=0,
        col=0,
        width=42,
        help_text=None
    ):
        self._add_label_with_help(
            box,
            group,
            key,
            label,
            row,
            col,
            kind="columns",
            help_text=help_text
        )

        categorical_var = tk.StringVar(value="")

        combo = ttk.Combobox(
            box,
            textvariable=categorical_var,
            values=[],
            width=width,
            state="normal"
        )

        combo.grid(
            row=row,
            column=col + 1,
            sticky="ew",
            pady=4,
            padx=(0, 16)
        )

        self.inputs.setdefault(group, {})[key] = categorical_var

        selector = {
            "group": group,
            "key": key,
            "dataset_key": dataset_key,
            "combo": combo,
            "var": categorical_var,
            "selected_text": ""
        }

        self.categorical_column_dropdowns.append(selector)

        combo.bind("<<ComboboxSelected>>", self.on_categorical_column_dropdown_selected)
        combo.bind("<KeyRelease>", self.on_categorical_columns_text_edited)
        combo.bind("<FocusOut>", self.on_categorical_columns_text_edited)

        return combo


    def get_categorical_columns_for_dataset(self, dataset_name):
        df = self.dfs.get(dataset_name)

        if df is None:
            return []

        categorical_cols = []

        for col in df.columns:
            series = df[col]

            if pd.api.types.is_numeric_dtype(series):
                continue

            categorical_cols.append(str(col))

        return categorical_cols


    def refresh_categorical_column_dropdowns(self):
        for selector in self.categorical_column_dropdowns:
            group = selector["group"]
            dataset_key = selector["dataset_key"]
            combo = selector["combo"]
            categorical_var = selector["var"]

            dataset_var = self.inputs.get(group, {}).get(dataset_key)

            if dataset_var is None:
                columns = []
            else:
                dataset_name = dataset_var.get()
                columns = self.get_categorical_columns_for_dataset(dataset_name)

            current_selected = split_list(categorical_var.get()) or []
            valid_selected = [col for col in current_selected if col in columns]

            selected_text = ", ".join(valid_selected)

            categorical_var.set(selected_text)
            selector["selected_text"] = selected_text
            combo.configure(values=columns)


    def on_categorical_columns_text_edited(self, event):
        combo = event.widget

        for selector in self.categorical_column_dropdowns:
            if selector["combo"] == combo:
                selector["selected_text"] = selector["var"].get().strip()
                break


    def on_categorical_column_dropdown_selected(self, event):
        combo = event.widget

        for selector in self.categorical_column_dropdowns:
            if selector["combo"] == combo:
                selected_column = selector["var"].get().strip()
                previous_text = selector.get("selected_text", "")
                current_selected = split_list(previous_text) or []

                if selected_column:
                    if selected_column not in current_selected:
                        current_selected.append(selected_column)

                    selected_text = ", ".join(current_selected)
                    selector["var"].set(selected_text)
                    selector["selected_text"] = selected_text

                break


    def _add_group_values_dropdown(
        self,
        box,
        group,
        key,
        label,
        dataset_key,
        column_key,
        row=0,
        col=0,
        width=42,
        help_text=None
    ):
        self._add_label_with_help(
            box,
            group,
            key,
            label,
            row,
            col,
            kind="columns",
            help_text=help_text
        )

        value_var = tk.StringVar(value="")

        combo = ttk.Combobox(
            box,
            textvariable=value_var,
            values=[],
            width=width,
            state="normal"
        )

        combo.grid(
            row=row,
            column=col + 1,
            sticky="ew",
            pady=4,
            padx=(0, 16)
        )

        self.inputs.setdefault(group, {})[key] = value_var

        selector = {
            "group": group,
            "key": key,
            "dataset_key": dataset_key,
            "column_key": column_key,
            "combo": combo,
            "var": value_var,
            "selected_text": ""
        }

        self.group_value_dropdowns.append(selector)

        combo.bind("<<ComboboxSelected>>", self.on_group_value_dropdown_selected)
        combo.bind("<KeyRelease>", self.on_group_values_text_edited)
        combo.bind("<FocusOut>", self.on_group_values_text_edited)

        return combo


    def get_unique_values_for_column(self, dataset_name, column_name):
        df = self.dfs.get(dataset_name)

        if df is None:
            return []

        if not column_name:
            return []

        if column_name not in df.columns:
            return []

        values = df[column_name].dropna()

        result = []

        for value in pd.unique(values):
            text_value = str(value).strip()

            if text_value:
                result.append(text_value)

        result = sorted(result, key=lambda item: item.lower())

        return result


    def refresh_group_value_dropdowns(self):
        for selector in self.group_value_dropdowns:
            group = selector["group"]
            dataset_key = selector["dataset_key"]
            column_key = selector["column_key"]
            combo = selector["combo"]
            value_var = selector["var"]

            dataset_var = self.inputs.get(group, {}).get(dataset_key)
            column_var = self.inputs.get(group, {}).get(column_key)

            if dataset_var is None or column_var is None:
                values = []
            else:
                dataset_name = dataset_var.get()
                column_name = column_var.get()
                values = self.get_unique_values_for_column(dataset_name, column_name)

            current_selected = split_list(value_var.get()) or []
            valid_selected = [item for item in current_selected if item in values]

            selected_text = ", ".join(valid_selected)

            value_var.set(selected_text)
            selector["selected_text"] = selected_text
            combo.configure(values=values)


    def on_group_values_text_edited(self, event):
        combo = event.widget

        for selector in self.group_value_dropdowns:
            if selector["combo"] == combo:
                selector["selected_text"] = selector["var"].get().strip()
                break


    def on_group_value_dropdown_selected(self, event):
        combo = event.widget

        for selector in self.group_value_dropdowns:
            if selector["combo"] == combo:
                selected_value = selector["var"].get().strip()
                previous_text = selector.get("selected_text", "")
                current_selected = split_list(previous_text) or []

                if selected_value:
                    if selected_value not in current_selected:
                        current_selected.append(selected_value)

                    selected_text = ", ".join(current_selected)
                    selector["var"].set(selected_text)
                    selector["selected_text"] = selected_text

                break


    def _add_combo(
        self,
        box,
        group,
        key,
        label,
        values,
        default="",
        row=0,
        col=0,
        width=22,
        dataset_combo=False,
        column_for=None,
        help_text=None
    ):
        self._add_label_with_help(box, group, key, label, row, col, help_text=help_text)

        var = tk.StringVar(value=default)

        combo = ttk.Combobox(
            box,
            textvariable=var,
            values=values,
            width=width
        )

        combo.grid(row=row, column=col + 1, sticky="ew", pady=4, padx=(0, 16))

        self.inputs.setdefault(group, {})[key] = var

        if dataset_combo:
            self.df_combos.append(combo)
            combo.bind("<<ComboboxSelected>>", lambda _event: self.refresh_columns(), add="+")
            combo.bind("<FocusOut>", lambda _event: self.refresh_columns(), add="+")

        if column_for:
            self.column_combos.append((combo, column_for))
            combo.bind("<<ComboboxSelected>>", lambda _event: self.refresh_group_value_dropdowns(), add="+")
            combo.bind("<FocusOut>", lambda _event: self.refresh_group_value_dropdowns(), add="+")

        return combo


    def _add_check(self, box, group, key, label, default=True, row=0, col=0, help_text=None):
        var = tk.BooleanVar(value=default)
        frame = ttk.Frame(box)
        frame.grid(row=row, column=col, columnspan=2, sticky="w", pady=4, padx=(0, 16))
        check = ttk.Checkbutton(frame, text=label, variable=var)
        check.grid(row=0, column=0, sticky="w")
        self._add_help_marker(
            frame,
            self._help_text(group, key, label, kind="check", explicit=help_text),
            row=0,
            column=1,
        )
        self.inputs.setdefault(group, {})[key] = var
        return check


    def _run_button(self, parent, row, label, command, help_text=None):
        frame = ttk.Frame(parent)
        frame.grid(row=row, column=0, sticky="ew", pady=(4, 0))
        frame.grid_columnconfigure(0, weight=1)
        btn = ttk.Button(frame, text=label, style="Accent.TButton", command=command)
        btn.grid(row=0, column=0, sticky="ew")
        self._add_help_marker(
            frame,
            self._help_text(None, None, label, kind="button", explicit=HELP_TEXTS.get(f"__button__.{label}") or help_text),
            row=0,
            column=1,
            padx=(8, 0),
        )
        return btn


    def _decorate_button_help(self, button, label, help_text=None):
        button.configure(text=f"{label} {HELP_ICON_TEXT}")
        HelpTooltip(
            button,
            help_text or HELP_TEXTS.get(f"__button__.{label}") or self._help_text(None, None, label, kind="button")
        )
        return button


    def _build_results_tab(self):
        self.results_tab = ttk.Frame(self.notebook, padding=10)
        self.notebook.add(self.results_tab, text="Resultados")
        self.results_tab.grid_rowconfigure(1, weight=1)
        self.results_tab.grid_columnconfigure(0, weight=1)

        header = ttk.Frame(self.results_tab)
        header.grid(row=0, column=0, sticky="ew", pady=(0, 10))
        header.grid_columnconfigure(0, weight=1)
        self.results_title_var = tk.StringVar(value="Sin resultados cargados")
        ttk.Label(header, textvariable=self.results_title_var, font=("Segoe UI", 11, "bold")).grid(row=0, column=0, sticky="w")
        load_run_btn = ttk.Button(header, text="Cargar corrida", command=self.load_run_folder)
        load_run_btn.grid(row=0, column=1, padx=(8, 0))
        self._decorate_button_help(load_run_btn, "Cargar corrida")
        load_manifest_btn = ttk.Button(header, text="Cargar manifest", command=self.load_manifest_file)
        load_manifest_btn.grid(row=0, column=2, padx=(8, 0))
        self._decorate_button_help(load_manifest_btn, "Cargar manifest", "Carga directamente un archivo manifest.json de una corrida guardada.")
        history_btn = ttk.Button(header, text="Historial", command=self.load_saved_runs)
        history_btn.grid(row=0, column=3, padx=(8, 0))
        self._decorate_button_help(history_btn, "Historial")
        open_run_btn = ttk.Button(header, text="Abrir carpeta", command=self.open_active_run_dir)
        open_run_btn.grid(row=0, column=4, padx=(8, 0))
        self._decorate_button_help(open_run_btn, "Abrir carpeta")

        paned = ttk.PanedWindow(self.results_tab, orient="horizontal")
        paned.grid(row=1, column=0, sticky="nsew")

        left = ttk.Frame(paned, padding=(0, 0, 10, 0))
        right = ttk.Frame(paned)
        left.grid_rowconfigure(0, weight=1)
        left.grid_columnconfigure(0, weight=1)
        right.grid_rowconfigure(0, weight=1)
        right.grid_columnconfigure(0, weight=1)
        paned.add(left, weight=1)
        paned.add(right, weight=4)

        self.results_lists_notebook = ttk.Notebook(left)
        self.results_lists_notebook.grid(row=0, column=0, sticky="nsew")
        self.results_lists_notebook.bind("<<NotebookTabChanged>>", self.on_result_list_tab_changed)

        lists = self.results_lists_notebook

        table_list_frame = ttk.Frame(lists, padding=6)
        table_list_frame.grid_rowconfigure(0, weight=1)
        table_list_frame.grid_columnconfigure(0, weight=1)
        lists.add(table_list_frame, text="Tablas")
        self.table_list = ttk.Treeview(
            table_list_frame,
            columns=("rows", "cols"),
            show="tree headings",
            height=14,
            selectmode="browse"
        )
        self.table_list.heading("#0", text="Tabla")
        self.table_list.heading("rows", text="Filas")
        self.table_list.heading("cols", text="Cols")
        self.table_list.column("#0", width=210, stretch=True)
        self.table_list.column("rows", width=70, anchor="e", stretch=False)
        self.table_list.column("cols", width=55, anchor="e", stretch=False)
        self.table_list.grid(row=0, column=0, sticky="nsew")
        self.table_list.bind("<<TreeviewSelect>>", self.on_table_selected)
        table_scroll = ttk.Scrollbar(table_list_frame, orient="vertical", command=self.table_list.yview)
        table_scroll.grid(row=0, column=1, sticky="ns")
        self.table_list.configure(yscrollcommand=table_scroll.set)

        figure_list_frame = ttk.Frame(lists, padding=6)
        figure_list_frame.grid_rowconfigure(0, weight=1)
        figure_list_frame.grid_columnconfigure(0, weight=1)
        lists.add(figure_list_frame, text="Figuras")
        self.figure_list = ttk.Treeview(
            figure_list_frame,
            show="tree",
            height=14,
            selectmode="browse"
        )
        self.figure_list.heading("#0", text="Figura")
        self.figure_list.column("#0", width=280, stretch=True)
        self.figure_list.grid(row=0, column=0, sticky="nsew")
        self.figure_list.bind("<<TreeviewSelect>>", self.on_figure_selected)
        fig_scroll = ttk.Scrollbar(figure_list_frame, orient="vertical", command=self.figure_list.yview)
        fig_scroll.grid(row=0, column=1, sticky="ns")
        self.figure_list.configure(yscrollcommand=fig_scroll.set)

        list_buttons = ttk.Frame(left)
        list_buttons.grid(row=1, column=0, sticky="ew", pady=(10, 0))
        list_buttons.grid_columnconfigure((0, 1), weight=1)
        open_selected_btn = ttk.Button(list_buttons, text="Abrir seleccionado", command=self.open_selected_result_file)
        open_selected_btn.grid(row=0, column=0, sticky="ew", padx=(0, 4))
        self._decorate_button_help(open_selected_btn, "Abrir seleccionado")
        refresh_btn = ttk.Button(list_buttons, text="Actualizar vista", command=self.refresh_active_result_view)
        refresh_btn.grid(row=0, column=1, sticky="ew", padx=(4, 0))
        self._decorate_button_help(refresh_btn, "Actualizar vista")

        self.preview_notebook = ttk.Notebook(right)
        self.preview_notebook.grid(row=0, column=0, sticky="nsew")

        table_preview_frame = ttk.Frame(self.preview_notebook, padding=8)
        table_preview_frame.grid_rowconfigure(1, weight=1)
        table_preview_frame.grid_columnconfigure(0, weight=1)
        self.preview_notebook.add(table_preview_frame, text="Vista de tabla")
        self.table_info_var = tk.StringVar(value="Selecciona una tabla para verla.")
        ttk.Label(table_preview_frame, textvariable=self.table_info_var, style="Subtle.TLabel").grid(row=0, column=0, sticky="ew", pady=(0, 6))
        table_grid = ttk.Frame(table_preview_frame)
        table_grid.grid(row=1, column=0, sticky="nsew")
        table_grid.grid_rowconfigure(0, weight=1)
        table_grid.grid_columnconfigure(0, weight=1)
        self.table_preview = ttk.Treeview(table_grid, show="headings")
        self.table_preview.grid(row=0, column=0, sticky="nsew")
        table_y = ttk.Scrollbar(table_grid, orient="vertical", command=self.table_preview.yview)
        table_x = ttk.Scrollbar(table_grid, orient="horizontal", command=self.table_preview.xview)
        table_y.grid(row=0, column=1, sticky="ns")
        table_x.grid(row=1, column=0, sticky="ew")
        self.table_preview.configure(yscrollcommand=table_y.set, xscrollcommand=table_x.set)

        figure_preview_frame = ttk.Frame(self.preview_notebook, padding=8)
        figure_preview_frame.grid_rowconfigure(1, weight=1)
        figure_preview_frame.grid_columnconfigure(0, weight=1)
        self.preview_notebook.add(figure_preview_frame, text="Vista de figura")
        self.figure_info_var = tk.StringVar(value="Selecciona una figura para verla.")
        ttk.Label(figure_preview_frame, textvariable=self.figure_info_var, style="Subtle.TLabel").grid(row=0, column=0, sticky="ew", pady=(0, 6))
        figure_grid = ttk.Frame(figure_preview_frame)
        figure_grid.grid(row=1, column=0, sticky="nsew")
        figure_grid.grid_rowconfigure(0, weight=1)
        figure_grid.grid_columnconfigure(0, weight=1)
        self.figure_canvas = tk.Canvas(figure_grid, bg="#ffffff", highlightthickness=0)
        self.figure_canvas.grid(row=0, column=0, sticky="nsew")
        fig_y = ttk.Scrollbar(figure_grid, orient="vertical", command=self.figure_canvas.yview)
        fig_x = ttk.Scrollbar(figure_grid, orient="horizontal", command=self.figure_canvas.xview)
        fig_y.grid(row=0, column=1, sticky="ns")
        fig_x.grid(row=1, column=0, sticky="ew")
        self.figure_canvas.configure(yscrollcommand=fig_y.set, xscrollcommand=fig_x.set)


    def _build_assistant_tab(self):
        group = "assistant"
        tab = self._new_tab("Asistente")
        tab.grid_rowconfigure(2, weight=1)

        setup_box = self._section(tab, "Pequeno matematico", 0)
        self._add_combo(
            setup_box,
            group,
            "assistant_dataset",
            "Dataset",
            [],
            "",
            0,
            0,
            dataset_combo=True,
            help_text=HELP_TEXTS["assistant_dataset"],
        )
        self._add_combo(
            setup_box,
            group,
            "assistant_provider",
            "Motor IA",
            ["local", "rules", "cloud"],
            "local",
            0,
            2,
            help_text=HELP_TEXTS["assistant_provider"],
        )
        self._add_entry(
            setup_box,
            group,
            "assistant_model",
            "Modelo",
            os.getenv("OLLAMA_MODEL", "phi4-mini-reasoning:3.8b-q4_K_M"),
            1,
            0,
            help_text=HELP_TEXTS["assistant_model"],
        )

        question_box = self._section(tab, "Pregunta en lenguaje natural", 1)
        label_frame = ttk.Frame(question_box)
        label_frame.grid(row=0, column=0, columnspan=4, sticky="w", pady=(0, 4))
        ttk.Label(label_frame, text="Pregunta").grid(row=0, column=0, sticky="w")
        self._add_help_marker(label_frame, HELP_TEXTS["assistant_question"], row=0, column=1)
        self.assistant_question_text = tk.Text(
            question_box,
            height=5,
            wrap="word",
            relief="solid",
            borderwidth=1,
            bg="#ffffff",
            fg="#20242a",
        )
        self.assistant_question_text.grid(row=1, column=0, columnspan=4, sticky="ew", pady=(0, 8))
        self.assistant_question_text.insert(
            "1.0",
            "Quiero comparar glucosa entre grupos de sexo. Que prueba y parametros uso?"
        )

        actions = ttk.Frame(question_box)
        actions.grid(row=2, column=0, columnspan=4, sticky="ew")
        actions.grid_columnconfigure((0, 2, 4), weight=1)
        ask_btn = ttk.Button(actions, text="Preguntar", style="Accent.TButton", command=self.ask_assistant)
        ask_btn.grid(row=0, column=0, sticky="ew", padx=(0, 6))
        self._add_help_marker(actions, HELP_TEXTS["__button__.Preguntar"], row=0, column=1, padx=(0, 10))
        analyze_btn = ttk.Button(actions, text="Analizar datasets", command=self.ask_assistant_dataset_summary)
        analyze_btn.grid(row=0, column=2, sticky="ew", padx=(6, 6))
        self._add_help_marker(actions, HELP_TEXTS["__button__.Analizar datasets"], row=0, column=3, padx=(0, 10))
        apply_btn = ttk.Button(actions, text="Aplicar sugerencias", command=self.apply_assistant_suggestions)
        apply_btn.grid(row=0, column=4, sticky="ew", padx=(6, 0))
        self._add_help_marker(actions, HELP_TEXTS["__button__.Aplicar sugerencias"], row=0, column=5)

        response_box = ttk.LabelFrame(tab, text="Respuesta y sugerencias", padding=8)
        response_box.grid(row=2, column=0, sticky="nsew", pady=(0, 12))
        response_box.grid_rowconfigure(0, weight=1)
        response_box.grid_columnconfigure(0, weight=1)
        self.assistant_response_text = tk.Text(
            response_box,
            height=18,
            wrap="word",
            relief="flat",
            bg="#ffffff",
            fg="#20242a",
        )
        self.assistant_response_text.grid(row=0, column=0, sticky="nsew")
        assistant_scroll = ttk.Scrollbar(response_box, orient="vertical", command=self.assistant_response_text.yview)
        assistant_scroll.grid(row=0, column=1, sticky="ns")
        self.assistant_response_text.configure(yscrollcommand=assistant_scroll.set)
        self._set_assistant_text(
            "Carga datasets y describe tu objetivo. Haré revisión preliminar, propondré una ruta de pruebas "
            "con el path de cada función Python y, después de ejecutar, podré interpretar los resultados reales."
        )


    def _build_exploration_tab(self):
        group = "exploration"
        tab = self._new_tab("Exploracion")
        box = self._section(tab, "Perfilado de variables", 0)

        self._add_combo(
            box,
            group,
            "df_name",
            "Dataset",
            [],
            "",
            0,
            0,
            dataset_combo=True
        )

        self._add_numeric_columns_dropdown(
            box,
            group,
            "numeric_cols",
            "Forzar numericas",
            dataset_key="df_name",
            row=1,
            col=0,
            width=42
        )

        self._add_entry(
            box,
            group,
            "max_category_values",
            "Max categorias",
            "12",
            1,
            2
        )

        self._add_check(
            box,
            group,
            "verbose",
            "Mostrar resumen en log",
            True,
            2,
            0
        )

        self._run_button(tab, 1, "Perfilar dataset", lambda: self.run_analysis("exploration"))


    def _build_characterization_tab(self):
        group = "characterization"
        tab = self._new_tab("Caracterizacion")
        box = self._section(tab, "Parametros", 0)

        self._add_combo(
            box,
            group,
            "df_name",
            "Dataset",
            [],
            "",
            0,
            0,
            dataset_combo=True
        )

        self._add_combo(
            box,
            group,
            "analysis_mode",
            "Modo",
            ["by_column", "full_matrix", "both"],
            "both",
            0,
            2
        )

        self._add_numeric_columns_dropdown(
            box,
            group,
            "numeric_cols",
            "Columnas numéricas",
            dataset_key="df_name",
            row=1,
            col=0,
            width=42
        )

        self._add_entry(
            box,
            group,
            "bins",
            "Bins",
            "80",
            1,
            2
        )

        self._add_check(
            box,
            group,
            "plot_positive_hist",
            "Graficar solo valores positivos",
            True,
            3,
            0
        )

        self._add_check(
            box,
            group,
            "verbose",
            "Mostrar resumen en log",
            True,
            3,
            2
        )

        self._run_button(tab, 1, "Ejecutar caracterizacion", lambda: self.run_analysis("characterization"))


    def _build_normality_tab(self):
        group = "normality"
        tab = self._new_tab("Normalidad")
        box = self._section(tab, "Parametros", 0)

        self._add_combo(
            box,
            group,
            "df_name",
            "Dataset",
            [],
            "",
            0,
            0,
            dataset_combo=True
        )

        self._add_combo(
            box,
            group,
            "analysis_mode",
            "Modo",
            ["by_column", "full_matrix", "both"],
            "both",
            0,
            2
        )

        self._add_numeric_columns_dropdown(
            box,
            group,
            "numeric_cols",
            "Columnas numéricas",
            dataset_key="df_name",
            row=1,
            col=0,
            width=42
        )

        self._add_combo(
            box,
            group,
            "value_mode",
            "Valores",
            ["all", "positive", "both"],
            "both",
            1,
            2
        )

        self._add_combo(
            box,
            group,
            "test_method",
            "Prueba",
            ["shapiro", "anderson", "both"],
            "both",
            2,
            0
        )

        self._add_entry(
            box,
            group,
            "alpha",
            "Alpha",
            "",
            2,
            2
        )

        self._add_check(
            box,
            group,
            "verbose",
            "Mostrar resumen en log",
            True,
            3,
            0
        )

        self._run_button(tab, 1, "Ejecutar normalidad", lambda: self.run_analysis("normality"))


    def _build_correlation_tab(self):
        group = "correlation"
        tab = self._new_tab("Correlacion")
        box = self._section(tab, "Pearson y Spearman", 0)

        self._add_combo(
            box,
            group,
            "df_name",
            "Dataset",
            [],
            "",
            0,
            0,
            dataset_combo=True
        )

        self._add_numeric_columns_dropdown(
            box,
            group,
            "numeric_cols",
            "Variables",
            dataset_key="df_name",
            row=1,
            col=0,
            width=42
        )

        self._add_entry(box, group, "alpha", "Alpha", "0.05", 1, 2)
        self._add_entry(box, group, "min_non_null", "Min datos", "3", 2, 0)
        self._add_entry(box, group, "max_plot_vars", "Max heatmap", "25", 2, 2)
        self._add_check(box, group, "verbose", "Mostrar resumen en log", True, 3, 0)

        self._run_button(tab, 1, "Calcular correlaciones", lambda: self.run_analysis("correlation"))


    def _build_visualization_tab(self):
        group = "visualization"
        tab = self._new_tab("Visualizaciones")

        # ------------------------------------------------------------------
        # 1) Configuración principal
        # ------------------------------------------------------------------
        config_box = self._section(tab, "Constructor visual V2", 0)
        self._add_combo(
            config_box,
            group,
            "df_name",
            "Dataset",
            [],
            "",
            0,
            0,
            dataset_combo=True,
        )
        self._add_combo(
            config_box,
            group,
            "plot_type",
            "Tipo de gráfico",
            [
                "Automático",
                "Dispersión",
                "Línea",
                "Barras",
                "Histograma",
                "Boxplot",
                "Violín",
                "Densidad",
                "Heatmap",
                "Rank-abundancia",
            ],
            "Automático",
            0,
            2,
        )
        self._add_combo(config_box, group, "x_col", "X", [], "", 1, 0, column_for=(group, "df_name"))
        self._add_combo(config_box, group, "y_col", "Y", [], "", 1, 2, column_for=(group, "df_name"))
        self._add_combo(config_box, group, "hue_col", "Color", [], "", 2, 0, column_for=(group, "df_name"))
        self._add_combo(config_box, group, "facet_col", "Dividir por", [], "", 2, 2, column_for=(group, "df_name"))
        self._add_combo(config_box, group, "builder_id_col", "ID / registro", [], "", 3, 0, column_for=(group, "df_name"))
        self._add_entry(config_box, group, "hover_cols", "Hover extra", "", 3, 2, width=34)
        self._add_entry(config_box, group, "builder_title", "Título", "", 4, 0, width=34)
        self._add_numeric_columns_dropdown(
            config_box,
            group,
            "heatmap_cols",
            "Variables heatmap",
            dataset_key="df_name",
            row=4,
            col=2,
            width=34,
        )
        self._add_entry(config_box, group, "max_facets", "Máx. paneles", "12", 5, 0)
        self._add_entry(config_box, group, "builder_bins", "Bins histograma", "30", 5, 2)
        self._add_check(config_box, group, "auto_update", "Actualización automática", True, 6, 0)
        self._add_check(config_box, group, "show_stats", "Mostrar estadísticas", True, 6, 2)

        # ------------------------------------------------------------------
        # 2) Filtros dinámicos
        # ------------------------------------------------------------------
        filter_box = self._section(tab, "Filtros interactivos", 1)
        filter_controls = ttk.Frame(filter_box)
        filter_controls.grid(row=0, column=0, columnspan=4, sticky="ew", pady=(0, 8))
        filter_controls.grid_columnconfigure(0, weight=1)

        self.visual_filter_column_var = tk.StringVar(value="")
        self.visual_filter_column_combo = ttk.Combobox(
            filter_controls,
            textvariable=self.visual_filter_column_var,
            values=[],
            state="readonly",
            width=38,
        )
        self.visual_filter_column_combo.grid(row=0, column=0, sticky="ew", padx=(0, 6))
        ttk.Button(filter_controls, text="Agregar filtro", command=self.add_visual_filter).grid(row=0, column=1, padx=(0, 6))
        ttk.Button(filter_controls, text="Limpiar filtros", command=self.clear_visual_filters).grid(row=0, column=2)

        self.visual_filters_container = ttk.Frame(filter_box)
        self.visual_filters_container.grid(row=1, column=0, columnspan=4, sticky="ew")
        self.visual_filters_container.grid_columnconfigure(0, weight=1)
        self.visual_filters_empty_var = tk.StringVar(value="Selecciona una columna y pulsa Agregar filtro.")
        ttk.Label(
            self.visual_filters_container,
            textvariable=self.visual_filters_empty_var,
            style="Subtle.TLabel",
        ).grid(row=0, column=0, sticky="w")

        # ------------------------------------------------------------------
        # 3) Rank-abundancia avanzado
        # ------------------------------------------------------------------
        rank_box = self._section(tab, "Rank-abundancia avanzado", 2)
        self._add_check(rank_box, group, "rank_abundance", "Modo rank-abundancia", False, 0, 0)
        self._add_combo(rank_box, group, "abundance_id_col", "ID", [], "", 0, 2, column_for=(group, "df_name"))
        self._add_combo(rank_box, group, "abundance_group_col", "Agrupar por", [], "", 1, 0, column_for=(group, "df_name"))
        self._add_numeric_columns_dropdown(
            rank_box,
            group,
            "abundance_cols",
            "Columnas abundancia",
            dataset_key="df_name",
            row=1,
            col=2,
            width=34,
        )
        self._add_entry(rank_box, group, "top_n", "Top N", "2000", 2, 0)
        self._add_check(rank_box, group, "log_scale", "Escala log", True, 2, 2)
        self._add_check(rank_box, group, "rank_show_cumulative", "Mostrar acumulado", False, 3, 0)
        self._add_entry(rank_box, group, "rank_highlight_top", "Resaltar Top", "10", 3, 2)
        self._add_entry(rank_box, group, "rank_search", "Buscar feature", "", 4, 0, width=34)
        self._add_check(rank_box, group, "verbose", "Mostrar resumen en log", True, 4, 2)

        # ------------------------------------------------------------------
        # 4) Capas y estilo
        # ------------------------------------------------------------------
        style_box = self._section(tab, "Capas y estilo", 3)
        self._add_check(style_box, group, "layer_scatter", "Puntos", True, 0, 0)
        self._add_check(style_box, group, "layer_line", "Línea", False, 0, 2)
        self._add_check(style_box, group, "layer_trend", "Tendencia", True, 1, 0)
        self._add_check(style_box, group, "layer_density", "Densidad", False, 1, 2)
        self._add_check(style_box, group, "layer_centroids", "Centroides", False, 2, 0)
        self._add_check(style_box, group, "builder_log_x", "Log X", False, 2, 2)
        self._add_check(style_box, group, "builder_log_y", "Log Y", False, 3, 0)

        self._add_label_with_help(style_box, group, "point_alpha", "Opacidad", 3, 2)
        alpha_var = tk.DoubleVar(value=0.75)
        alpha_frame = ttk.Frame(style_box)
        alpha_frame.grid(row=3, column=3, sticky="ew", pady=4, padx=(0, 16))
        alpha_frame.grid_columnconfigure(0, weight=1)
        alpha_scale = ttk.Scale(alpha_frame, from_=0.05, to=1.0, variable=alpha_var, orient="horizontal")
        alpha_scale.grid(row=0, column=0, sticky="ew")
        self.visual_alpha_value_var = tk.StringVar(value="0.75")
        ttk.Label(alpha_frame, textvariable=self.visual_alpha_value_var, width=6).grid(row=0, column=1, padx=(8, 0))
        self.inputs.setdefault(group, {})["point_alpha"] = alpha_var

        self._add_label_with_help(style_box, group, "point_size", "Tamaño puntos", 4, 0)
        size_var = tk.DoubleVar(value=34.0)
        size_frame = ttk.Frame(style_box)
        size_frame.grid(row=4, column=1, sticky="ew", pady=4, padx=(0, 16))
        size_frame.grid_columnconfigure(0, weight=1)
        size_scale = ttk.Scale(size_frame, from_=4, to=200, variable=size_var, orient="horizontal")
        size_scale.grid(row=0, column=0, sticky="ew")
        self.visual_size_value_var = tk.StringVar(value="34")
        ttk.Label(size_frame, textvariable=self.visual_size_value_var, width=6).grid(row=0, column=1, padx=(8, 0))
        self.inputs.setdefault(group, {})["point_size"] = size_var

        # ------------------------------------------------------------------
        # 5) Interacción
        # ------------------------------------------------------------------
        interaction_box = self._section(tab, "Interacción", 4)
        self._add_check(interaction_box, group, "hover_enabled", "Hover", True, 0, 0)
        self._add_check(interaction_box, group, "inspector_enabled", "Inspector por clic", True, 0, 2)
        self._add_combo(
            interaction_box,
            group,
            "selection_mode",
            "Selección",
            ["Ninguna", "Lazo", "Rectángulo"],
            "Ninguna",
            1,
            0,
        )
        self._add_check(interaction_box, group, "legend_toggle", "Leyenda clicable", True, 1, 2)
        self.visual_selection_status_var = tk.StringVar(value="0 registros seleccionados")
        ttk.Label(interaction_box, textvariable=self.visual_selection_status_var, style="Subtle.TLabel").grid(
            row=2, column=0, columnspan=2, sticky="w", pady=(6, 0)
        )
        ttk.Button(interaction_box, text="Limpiar selección", command=self.clear_visual_selection).grid(
            row=2, column=2, sticky="ew", padx=(0, 16), pady=(6, 0)
        )
        create_sel_btn = ttk.Button(interaction_box, text="Crear dataset selección", command=self.create_dataset_from_visual_selection)
        create_sel_btn.grid(row=2, column=3, sticky="ew", pady=(6, 0))
        HelpTooltip(create_sel_btn, HELP_TEXTS["__button__.Crear dataset selección"])

        # ------------------------------------------------------------------
        # 6) Acciones de navegación/configuración
        # ------------------------------------------------------------------
        actions = ttk.LabelFrame(tab, text="Acciones", padding=8)
        actions.grid(row=5, column=0, sticky="ew", pady=(0, 12))
        for col in range(6):
            actions.grid_columnconfigure(col, weight=1)

        action_specs = [
            ("Deshacer", self.undo_visual_view),
            ("Rehacer", self.redo_visual_view),
            ("Recomendar vistas", self.show_visual_recommendations),
            ("Guardar preset", self.save_visual_preset),
            ("Cargar preset", self.show_visual_presets),
            ("Actualizar ahora", self.update_visual_builder),
            ("Reset vista", self.reset_visual_view),
            ("Abrir HTML", self.open_visual_interactive),
            ("Guardar corrida", self.save_visual_builder_output),
            ("Exportar todo", self.export_visual_builder_dialog),
        ]
        for i, (label, command) in enumerate(action_specs):
            row = i // 5
            col = i % 5
            btn = ttk.Button(actions, text=label, command=command, style="Accent.TButton" if label in {"Actualizar ahora", "Guardar corrida"} else "TButton")
            btn.grid(row=row, column=col, sticky="ew", padx=3, pady=3)
            help_key = f"__button__.{label}"
            if help_key in HELP_TEXTS:
                HelpTooltip(btn, HELP_TEXTS[help_key])
            if label == "Abrir HTML":
                self.visual_open_html_btn = btn
                btn.configure(state="disabled")

        # ------------------------------------------------------------------
        # 7) Vista Matplotlib interactiva
        # ------------------------------------------------------------------
        builder_preview = ttk.LabelFrame(tab, text="Vista interactiva", padding=8)
        builder_preview.grid(row=6, column=0, sticky="nsew", pady=(0, 12))
        builder_preview.grid_columnconfigure(0, weight=1)

        self.visual_builder_hint_var = tk.StringVar(
            value="Elige un dataset y variables. Con actualización automática la vista se redibuja sola."
        )
        ttk.Label(builder_preview, textvariable=self.visual_builder_hint_var, style="Subtle.TLabel").grid(
            row=0, column=0, sticky="ew", pady=(0, 6)
        )

        self.visual_builder_canvas_host = ttk.Frame(builder_preview)
        self.visual_builder_canvas_host.grid(row=1, column=0, sticky="nsew")
        self.visual_builder_canvas_host.grid_columnconfigure(0, weight=1)
        self.visual_builder_canvas_host.grid_rowconfigure(0, weight=1)
        self.visual_builder_toolbar_host = ttk.Frame(builder_preview)
        self.visual_builder_toolbar_host.grid(row=2, column=0, sticky="ew", pady=(4, 0))

        placeholder = Figure(figsize=(8.8, 5.2), dpi=100)
        ax = placeholder.add_subplot(111)
        ax.text(0.5, 0.5, "Selecciona variables para iniciar", ha="center", va="center", transform=ax.transAxes)
        ax.set_axis_off()
        self.visual_builder_figure = placeholder
        self.visual_builder_ax = ax
        self.visual_builder_canvas = FigureCanvasTkAgg(placeholder, master=self.visual_builder_canvas_host)
        self.visual_builder_canvas.draw()
        self.visual_builder_canvas.get_tk_widget().grid(row=0, column=0, sticky="nsew")
        self.visual_builder_toolbar = NavigationToolbar2Tk(
            self.visual_builder_canvas,
            self.visual_builder_toolbar_host,
            pack_toolbar=False,
        )
        self.visual_builder_toolbar.grid(row=0, column=0, sticky="ew")

        # ------------------------------------------------------------------
        # 8) Estadísticas, selección e inspector
        # ------------------------------------------------------------------
        details_box = ttk.LabelFrame(tab, text="Detalles de la vista", padding=8)
        details_box.grid(row=7, column=0, sticky="ew", pady=(0, 12))
        details_box.grid_columnconfigure(0, weight=1)
        details_notebook = ttk.Notebook(details_box)
        details_notebook.grid(row=0, column=0, sticky="ew")

        stats_frame = ttk.Frame(details_notebook, padding=6)
        selection_frame = ttk.Frame(details_notebook, padding=6)
        record_frame = ttk.Frame(details_notebook, padding=6)
        details_notebook.add(stats_frame, text="Estadísticas")
        details_notebook.add(selection_frame, text="Selección")
        details_notebook.add(record_frame, text="Inspector")
        for frame in (stats_frame, selection_frame, record_frame):
            frame.grid_columnconfigure(0, weight=1)

        self.visual_builder_stats_text = tk.Text(stats_frame, height=9, wrap="word", relief="flat", bg="#ffffff")
        self.visual_builder_stats_text.grid(row=0, column=0, sticky="ew")
        self.visual_builder_selection_text = tk.Text(selection_frame, height=9, wrap="none", relief="flat", bg="#ffffff")
        self.visual_builder_selection_text.grid(row=0, column=0, sticky="ew")
        self.visual_builder_record_text = tk.Text(record_frame, height=9, wrap="word", relief="flat", bg="#ffffff")
        self.visual_builder_record_text.grid(row=0, column=0, sticky="ew")
        self._set_visual_text(self.visual_builder_stats_text, "Actualiza una visualización para ver estadísticas.")
        self._set_visual_text(self.visual_builder_selection_text, "No hay registros seleccionados.")
        self._set_visual_text(self.visual_builder_record_text, "Haz clic sobre un punto para inspeccionar el registro.")

        # Traces se registran al final para no disparar actualizaciones durante la construcción.
        self._bind_visual_auto_update_traces()
        self.after_idle(self.refresh_visual_filter_candidates)


    def _build_kde_tab(self):
        group = "kde"
        tab = self._new_tab("KDE")
        box = self._section(tab, "Parametros", 0)
        self._add_combo(box, group, "data_df_name", "Dataset OTU", [], dataset_combo=True)
        self._add_entry(box, group, "grid_size", "Grid size", "", 0, 2)
        self._add_entry(box, group, "cv_subsample", "CV subsample", "", 1, 0)
        self._add_entry(box, group, "cv_folds", "CV folds", "", 1, 2)
        self._add_entry(box, group, "cv_bw_grid", "CV BW grid", "", 2, 0)
        self._add_entry(box, group, "min_bandwidth", "Min bandwidth", "", 2, 2)
        self._add_entry(box, group, "cv_max_expansions", "Max expansions", "", 3, 0)
        self._add_entry(box, group, "test_kernel_bandwidths", "BW por kernel", "", 3, 2)
        self._add_check(box, group, "verbose", "Mostrar resumen en log", True, 4, 0)
        self._run_button(tab, 1, "Ejecutar KDE", lambda: self.run_analysis("kde"))


    def _build_kruskal_tab(self):
        group = "kruskal"
        tab = self._new_tab("Kruskal-Wallis")
        box = self._section(tab, "Parametros", 0)

        self._add_combo(
            box,
            group,
            "group_df_name",
            "Dataset grupos",
            [],
            "",
            0,
            0,
            dataset_combo=True
        )

        self._add_combo(
            box,
            group,
            "value_df_name",
            "Dataset valores",
            [],
            "",
            0,
            2,
            dataset_combo=True
        )

        self._add_combo(
            box,
            group,
            "group_col",
            "Columna grupo",
            [],
            "",
            1,
            0,
            column_for=("kruskal", "group_df_name")
        )

        self._add_combo(
            box,
            group,
            "id_col_group",
            "ID grupos",
            [],
            "",
            1,
            2,
            column_for=("kruskal", "group_df_name")
        )

        self._add_combo(
            box,
            group,
            "id_col_value",
            "ID valores",
            [],
            "",
            2,
            0,
            column_for=("kruskal", "value_df_name")
        )

        self._add_numeric_columns_dropdown(
            box,
            group,
            "value_cols",
            "Variables",
            dataset_key="value_df_name",
            row=2,
            col=2,
            width=42
        )

        self._add_entry(
            box,
            group,
            "alpha",
            "Alpha",
            "",
            3,
            0
        )

        self._add_entry(
            box,
            group,
            "min_group_size",
            "Min grupo",
            "",
            3,
            2
        )

        self._add_check(
            box,
            group,
            "apply_fdr",
            "Aplicar FDR",
            True,
            4,
            0
        )

        self._add_check(
            box,
            group,
            "verbose",
            "Mostrar resumen en log",
            True,
            4,
            2
        )

        self._run_button(
            tab,
            1,
            "Ejecutar Kruskal-Wallis",
            lambda: self.run_analysis("kruskal")
        )

    def _build_mann_whitney_tab(self):
        group = "mann_whitney"
        tab = self._new_tab("Mann-Whitney")
        box = self._section(tab, "Parametros", 0)

        self._add_combo(
            box,
            group,
            "group_df_name",
            "Dataset grupos",
            [],
            "",
            0,
            0,
            dataset_combo=True
        )

        self._add_combo(
            box,
            group,
            "value_df_name",
            "Dataset valores",
            [],
            "",
            0,
            2,
            dataset_combo=True
        )

        self._add_combo(
            box,
            group,
            "group_col",
            "Columna grupo",
            [],
            "",
            1,
            0,
            column_for=("mann_whitney", "group_df_name")
        )

        self._add_group_values_dropdown(
            box,
            group,
            "groups_to_compare",
            "Grupos",
            dataset_key="group_df_name",
            column_key="group_col",
            row=1,
            col=2,
            width=42
        )

        self._add_combo(
            box,
            group,
            "id_col_group",
            "ID grupos",
            [],
            "",
            2,
            0,
            column_for=("mann_whitney", "group_df_name")
        )

        self._add_combo(
            box,
            group,
            "id_col_value",
            "ID valores",
            [],
            "",
            2,
            2,
            column_for=("mann_whitney", "value_df_name")
        )

        self._add_numeric_columns_dropdown(
            box,
            group,
            "value_cols",
            "Variables",
            dataset_key="value_df_name",
            row=3,
            col=0,
            width=42
        )

        self._add_combo(
            box,
            group,
            "alternative",
            "Alternativa",
            ["two-sided", "less", "greater"],
            "two-sided",
            3,
            2
        )

        self._add_entry(
            box,
            group,
            "alpha",
            "Alpha",
            "",
            4,
            0
        )

        self._add_entry(
            box,
            group,
            "min_group_size",
            "Min grupo",
            "",
            4,
            2
        )

        self._add_check(
            box,
            group,
            "apply_fdr",
            "Aplicar FDR",
            True,
            5,
            0
        )

        self._add_check(
            box,
            group,
            "verbose",
            "Mostrar resumen en log",
            True,
            5,
            2
        )

        self._run_button(
            tab,
            1,
            "Ejecutar Mann-Whitney",
            lambda: self.run_analysis("mann_whitney")
        )


    def _build_dimensionality_tab(self):
        group = "dimensionality"
        tab = self._new_tab("Reduccion")

        data_box = self._section(tab, "Datos y preprocesamiento", 0)
        self._add_combo(data_box, group, "data_df_name", "Dataset", [], "", 0, 0, dataset_combo=True)
        self._add_combo(data_box, group, "id_col", "ID", [], "", 0, 2, column_for=("dimensionality", "data_df_name"))
        self._add_numeric_columns_dropdown(
            data_box,
            group,
            "feature_cols",
            "Features",
            dataset_key="data_df_name",
            row=1,
            col=0,
            width=42
        )
        self._add_combo(data_box, group, "missing_strategy", "Faltantes", ["fill_zero", "drop_rows", "median"], "fill_zero", 2, 0)
        self._add_check(data_box, group, "remove_zero_rows", "Quitar filas suma 0", True, 2, 2)
        self._add_entry(data_box, group, "min_prevalence", "Min prevalence", "", 3, 0)
        self._add_entry(data_box, group, "min_total_abundance", "Min abundance", "", 3, 2)

        model_box = self._section(tab, "Reduccion dimensional", 1)
        self._add_combo(model_box, group, "transform_method", "Transformacion", ["none", "log1p", "clr"], "none", 0, 0)
        self._add_entry(model_box, group, "pseudocount", "Pseudocount", "1.0", 0, 2)
        self._add_check(model_box, group, "scale", "Escalar variables", True, 1, 0)
        self._add_combo(model_box, group, "embedding_method", "Embedding", ["none", "pca", "kpca", "isomap", "mds", "tsne", "umap"], "pca", 1, 2)
        self._add_entry(model_box, group, "n_components", "Componentes", "3", 2, 0)
        self._add_entry(model_box, group, "random_state", "Random state", "42", 2, 2)
        self._add_entry(model_box, group, "embedding_kwargs", "Embedding JSON", "", 3, 0)
        self._add_entry(model_box, group, "variance_thresholds", "Umbrales PCA", "0.8, 0.9, 0.95", 3, 2)
        self._add_check(model_box, group, "verbose", "Mostrar resumen en log", True, 4, 0)

        self._run_button(tab, 2, "Ejecutar reduccion", lambda: self.run_analysis("dimensionality"))


    def _build_dbscan_tab(self):
        group = "dbscan"
        tab = self._new_tab("DBSCAN")

        data_box = self._section(tab, "Datos y limpieza", 0)

        self._add_combo(
            data_box,
            group,
            "data_df_name",
            "Dataset datos",
            [],
            "",
            0,
            0,
            dataset_combo=True
        )

        self._add_combo(
            data_box,
            group,
            "id_col",
            "ID datos",
            [],
            "",
            0,
            2,
            column_for=("dbscan", "data_df_name")
        )

        self._add_numeric_columns_dropdown(
            data_box,
            group,
            "feature_cols",
            "Features numéricos",
            dataset_key="data_df_name",
            row=1,
            col=0,
            width=42
        )

        self._add_combo(
            data_box,
            group,
            "meta_df_name",
            "Dataset meta",
            [],
            "",
            1,
            2,
            dataset_combo=True
        )

        self._add_combo(
            data_box,
            group,
            "meta_id_col",
            "ID meta",
            [],
            "",
            2,
            0,
            column_for=("dbscan", "meta_df_name")
        )

        self._add_combo(
            data_box,
            group,
            "missing_strategy",
            "Faltantes",
            ["fill_zero", "drop_rows", "median"],
            "fill_zero",
            2,
            2
        )

        self._add_check(
            data_box,
            group,
            "drop_non_numeric",
            "Quitar no numéricas",
            True,
            3,
            0
        )

        self._add_check(
            data_box,
            group,
            "remove_zero_rows",
            "Quitar filas suma 0",
            True,
            3,
            2
        )

        self._add_entry(
            data_box,
            group,
            "min_prevalence",
            "Min prevalence",
            "",
            4,
            0
        )

        self._add_entry(
            data_box,
            group,
            "min_total_abundance",
            "Min abundance",
            "",
            4,
            2
        )

        model_box = self._section(tab, "Modelo", 1)

        self._add_entry(
            model_box,
            group,
            "eps",
            "eps",
            "",
            0,
            0
        )

        self._add_entry(
            model_box,
            group,
            "min_samples",
            "Min samples",
            "",
            0,
            2
        )

        self._add_combo(
            model_box,
            group,
            "transform_method",
            "Transformación",
            ["none", "log1p", "clr"],
            "none",
            1,
            0
        )

        self._add_entry(
            model_box,
            group,
            "pseudocount",
            "Pseudocount",
            "",
            1,
            2
        )

        self._add_check(
            model_box,
            group,
            "scale",
            "Escalar variables",
            True,
            2,
            0
        )

        self._add_combo(
            model_box,
            group,
            "embedding_method",
            "Embedding",
            ["none", "pca", "kpca", "isomap", "mds", "tsne", "umap"],
            "none",
            2,
            2
        )

        self._add_entry(
            model_box,
            group,
            "n_components",
            "Componentes",
            "",
            3,
            0
        )

        self._add_entry(
            model_box,
            group,
            "random_state",
            "Random state",
            "42",
            3,
            2
        )

        self._add_entry(
            model_box,
            group,
            "embedding_kwargs",
            "Embedding JSON",
            "",
            4,
            0
        )

        out_box = self._section(tab, "Figuras y resumen", 2)

        self._add_check(
            out_box,
            group,
            "calculate_k_distance",
            "Calcular k-distance",
            True,
            0,
            0
        )

        self._add_entry(
            out_box,
            group,
            "k_distance_min_samples",
            "K-distance min_samples",
            "",
            0,
            2
        )

        self._add_check(
            out_box,
            group,
            "plot_k_distance_graph",
            "Guardar figura k-distance",
            True,
            1,
            0
        )

        self._add_check(
            out_box,
            group,
            "plot_embedding_graph",
            "Guardar figura embedding",
            True,
            1,
            2
        )

        self._add_numeric_columns_dropdown(
            out_box,
            group,
            "summary_numeric_cols",
            "Resumen numérico",
            dataset_key="meta_df_name",
            row=2,
            col=0,
            width=42
        )

        self._add_categorical_columns_dropdown(
            out_box,
            group,
            "summary_categorical_cols",
            "Resumen categórico",
            dataset_key="meta_df_name",
            row=2,
            col=2,
            width=42
        )

        self._add_entry(
            out_box,
            group,
            "summary_numeric_aggs",
            "Agregaciones",
            "median",
            3,
            0
        )

        self._add_check(
            out_box,
            group,
            "verbose",
            "Mostrar resumen en log",
            True,
            3,
            2
        )

        self._run_button(
            tab,
            3,
            "Ejecutar DBSCAN",
            lambda: self.run_analysis("dbscan")
        )


    def _build_cluster_review_tab(self):
        group = "cluster_review"
        tab = self._new_tab("Revision clusters")
        box = self._section(tab, "Metricas y criterios", 0)

        self._add_combo(
            box,
            group,
            "df_name",
            "Dataset",
            [],
            "",
            0,
            0,
            dataset_combo=True
        )

        self._add_combo(
            box,
            group,
            "label_col",
            "Columna cluster",
            [],
            "",
            0,
            2,
            column_for=("cluster_review", "df_name")
        )

        self._add_numeric_columns_dropdown(
            box,
            group,
            "feature_cols",
            "Features",
            dataset_key="df_name",
            row=1,
            col=0,
            width=42
        )

        self._add_check(box, group, "ignore_noise", "Ignorar ruido", True, 2, 0)
        self._add_entry(box, group, "noise_label", "Etiqueta ruido", "-1", 2, 2)
        self._add_entry(box, group, "min_cluster_size", "Min cluster", "3", 3, 0)
        self._add_check(box, group, "verbose", "Mostrar resumen en log", True, 3, 2)

        self._run_button(tab, 1, "Revisar clusterizacion", lambda: self.run_analysis("cluster_review"))


    def _input_value(self, group, key, default=""):
        var = self.inputs.get(group, {}).get(key)
        if var is None:
            return default
        return var.get()


    def _set_visual_text(self, widget, text):
        widget.configure(state="normal")
        widget.delete("1.0", "end")
        widget.insert("1.0", str(text))
        widget.configure(state="disabled")


    def _plot_type_to_backend(self, value):
        mapping = {
            "Automático": "auto",
            "Dispersión": "scatter",
            "Línea": "line",
            "Barras": "bar",
            "Histograma": "histogram",
            "Boxplot": "boxplot",
            "Violín": "violin",
            "Densidad": "density",
            "Heatmap": "heatmap",
            "Rank-abundancia": "rank_abundance",
        }
        return mapping.get(str(value).strip(), str(value).strip().lower() or "auto")


    def _plot_type_to_ui(self, value):
        mapping = {
            "auto": "Automático",
            "scatter": "Dispersión",
            "line": "Línea",
            "bar": "Barras",
            "histogram": "Histograma",
            "boxplot": "Boxplot",
            "violin": "Violín",
            "density": "Densidad",
            "heatmap": "Heatmap",
            "rank_abundance": "Rank-abundancia",
        }
        return mapping.get(str(value).strip().lower(), str(value))


    def _bind_visual_auto_update_traces(self):
        group = "visualization"
        for key, var in self.inputs.get(group, {}).items():
            try:
                var.trace_add("write", lambda *_args, k=key: self._on_visual_input_changed(k))
            except Exception:
                pass

        try:
            self.inputs[group]["point_alpha"].trace_add("write", lambda *_: self._update_visual_slider_labels())
            self.inputs[group]["point_size"].trace_add("write", lambda *_: self._update_visual_slider_labels())
        except Exception:
            pass
        self._update_visual_slider_labels()


    def _update_visual_slider_labels(self):
        try:
            self.visual_alpha_value_var.set(f"{float(self._input_value('visualization', 'point_alpha', 0.75)):.2f}")
        except Exception:
            pass
        try:
            self.visual_size_value_var.set(f"{float(self._input_value('visualization', 'point_size', 34)):.0f}")
        except Exception:
            pass


    def _on_visual_input_changed(self, key=None):
        if self.visual_builder_applying_state:
            return

        group = "visualization"
        if key == "df_name":
            self.after_idle(self.refresh_visual_filter_candidates)

        if key == "rank_abundance":
            try:
                if parse_bool(self.inputs[group]["rank_abundance"].get()):
                    self.visual_builder_applying_state = True
                    self.inputs[group]["plot_type"].set("Rank-abundancia")
                self.visual_builder_applying_state = False
            except Exception:
                self.visual_builder_applying_state = False

        if key == "plot_type":
            try:
                is_rank = self._plot_type_to_backend(self.inputs[group]["plot_type"].get()) == "rank_abundance"
                current = parse_bool(self.inputs[group]["rank_abundance"].get())
                if is_rank != current:
                    self.visual_builder_applying_state = True
                    self.inputs[group]["rank_abundance"].set(is_rank)
                    self.visual_builder_applying_state = False
            except Exception:
                self.visual_builder_applying_state = False

        self._schedule_visual_update()


    def _schedule_visual_update(self):
        if self.visual_builder_applying_state:
            return
        auto_var = self.inputs.get("visualization", {}).get("auto_update")
        if auto_var is None or not parse_bool(auto_var.get()):
            return
        df_name = self._input_value("visualization", "df_name").strip()
        if not df_name or df_name not in self.dfs:
            return
        self.visual_builder_debouncer.trigger(lambda: self.update_visual_builder(show_errors=False))


    def refresh_visual_filter_candidates(self):
        if not hasattr(self, "visual_filter_column_combo"):
            return
        df_name = self._input_value("visualization", "df_name").strip()
        df = self.dfs.get(df_name)

        if df_name != self.visual_filter_dataset_name:
            self._clear_visual_filter_widgets()
            self.visual_filter_dataset_name = df_name

        if df is None:
            self.visual_filter_specs = {}
            self.visual_filter_column_combo.configure(values=[])
            self.visual_filter_column_var.set("")
            return

        try:
            specs = infer_filter_specs(df)
        except Exception:
            specs = []
        self.visual_filter_specs = {str(spec.column): spec for spec in specs}
        columns = list(self.visual_filter_specs.keys())
        self.visual_filter_column_combo.configure(values=columns)
        if columns and self.visual_filter_column_var.get() not in columns:
            self.visual_filter_column_var.set(columns[0])
        elif not columns:
            self.visual_filter_column_var.set("")


    def _clear_visual_filter_widgets(self):
        if not hasattr(self, "visual_filters_container"):
            self.visual_filter_rows = {}
            return
        for child in self.visual_filters_container.winfo_children():
            child.destroy()
        self.visual_filter_rows = {}
        if hasattr(self, "visual_filters_empty_var"):
            self.visual_filters_empty_var.set("Selecciona una columna y pulsa Agregar filtro.")
        ttk.Label(
            self.visual_filters_container,
            textvariable=self.visual_filters_empty_var,
            style="Subtle.TLabel",
        ).grid(row=0, column=0, sticky="w")


    def clear_visual_filters(self, schedule=True):
        self._clear_visual_filter_widgets()
        if schedule:
            self._schedule_visual_update()


    def add_visual_filter(self, column=None, initial_rule=None, schedule=True):
        if not hasattr(self, "visual_filters_container"):
            return
        column = str(column or self.visual_filter_column_var.get()).strip()
        if not column or column not in self.visual_filter_specs:
            return
        if column in self.visual_filter_rows:
            return

        # Quita el texto vacío la primera vez que se agrega un filtro.
        if not self.visual_filter_rows:
            for child in self.visual_filters_container.winfo_children():
                child.destroy()

        spec = self.visual_filter_specs[column]
        row_frame = ttk.Frame(self.visual_filters_container)
        row_frame.grid(row=len(self.visual_filter_rows), column=0, sticky="ew", pady=3)
        row_frame.grid_columnconfigure(1, weight=1)
        ttk.Label(row_frame, text=column, width=24).grid(row=0, column=0, sticky="w", padx=(0, 6))

        include_na = tk.BooleanVar(value=False)
        record = {"frame": row_frame, "kind": spec.kind, "include_na": include_na}

        if spec.kind == "numeric":
            lo_default = "" if spec.minimum is None else f"{spec.minimum:g}"
            hi_default = "" if spec.maximum is None else f"{spec.maximum:g}"
            if isinstance(initial_rule, dict):
                lo_default = "" if initial_rule.get("min") is None else str(initial_rule.get("min"))
                hi_default = "" if initial_rule.get("max") is None else str(initial_rule.get("max"))
                include_na.set(bool(initial_rule.get("include_na", False)))
            lo_var = tk.StringVar(value=lo_default)
            hi_var = tk.StringVar(value=hi_default)
            editor = ttk.Frame(row_frame)
            editor.grid(row=0, column=1, sticky="ew")
            editor.grid_columnconfigure((0, 2), weight=1)
            ttk.Entry(editor, textvariable=lo_var, width=14).grid(row=0, column=0, sticky="ew")
            ttk.Label(editor, text=" a ").grid(row=0, column=1)
            ttk.Entry(editor, textvariable=hi_var, width=14).grid(row=0, column=2, sticky="ew")
            record.update({"min_var": lo_var, "max_var": hi_var})
            vars_to_trace = [lo_var, hi_var, include_na]
        elif spec.kind == "datetime":
            start_default = ""
            end_default = ""
            if spec.values:
                start_default = str(spec.values[0])
                end_default = str(spec.values[-1])
            if isinstance(initial_rule, dict):
                start_default = str(initial_rule.get("start", initial_rule.get("min", start_default)) or "")
                end_default = str(initial_rule.get("end", initial_rule.get("max", end_default)) or "")
                include_na.set(bool(initial_rule.get("include_na", False)))
            start_var = tk.StringVar(value=start_default)
            end_var = tk.StringVar(value=end_default)
            editor = ttk.Frame(row_frame)
            editor.grid(row=0, column=1, sticky="ew")
            editor.grid_columnconfigure((0, 2), weight=1)
            ttk.Entry(editor, textvariable=start_var).grid(row=0, column=0, sticky="ew")
            ttk.Label(editor, text=" a ").grid(row=0, column=1)
            ttk.Entry(editor, textvariable=end_var).grid(row=0, column=2, sticky="ew")
            record.update({"start_var": start_var, "end_var": end_var})
            vars_to_trace = [start_var, end_var, include_na]
        else:
            values = [str(v) for v in spec.values]
            default_values = ""
            if isinstance(initial_rule, dict):
                selected = initial_rule.get("values", initial_rule.get("selected", []))
                default_values = ", ".join(map(str, selected or []))
                include_na.set(bool(initial_rule.get("include_na", False)))
            elif isinstance(initial_rule, (list, tuple, set)):
                default_values = ", ".join(map(str, initial_rule))
            elif initial_rule not in (None, ""):
                default_values = str(initial_rule)
            values_var = tk.StringVar(value=default_values)
            combo = ttk.Combobox(row_frame, textvariable=values_var, values=values, state="normal")
            combo.grid(row=0, column=1, sticky="ew")
            record.update({"values_var": values_var, "values": values})
            vars_to_trace = [values_var, include_na]

        na_check = ttk.Checkbutton(row_frame, text="NA", variable=include_na)
        na_check.grid(row=0, column=2, padx=(8, 4))
        ttk.Button(row_frame, text="×", width=3, command=lambda c=column: self.remove_visual_filter(c)).grid(row=0, column=3)

        self.visual_filter_rows[column] = record
        self.visual_filters_empty_var.set("")
        for var in vars_to_trace:
            try:
                var.trace_add("write", lambda *_args: self._schedule_visual_update())
            except Exception:
                pass
        if schedule:
            self._schedule_visual_update()


    def remove_visual_filter(self, column):
        record = self.visual_filter_rows.pop(column, None)
        if record:
            record["frame"].destroy()
        # Reacomoda las filas.
        for row, item in enumerate(self.visual_filter_rows.values()):
            item["frame"].grid_configure(row=row)
        if not self.visual_filter_rows:
            self._clear_visual_filter_widgets()
        self._schedule_visual_update()


    def _collect_visual_filters(self):
        filters = {}
        for column, record in self.visual_filter_rows.items():
            kind = record["kind"]
            include_na = bool(record["include_na"].get())
            if kind == "numeric":
                lo = parse_optional_float(record["min_var"].get())
                hi = parse_optional_float(record["max_var"].get())
                filters[column] = {"min": lo, "max": hi, "include_na": include_na}
            elif kind == "datetime":
                start = record["start_var"].get().strip() or None
                end = record["end_var"].get().strip() or None
                if start is not None or end is not None or include_na:
                    filters[column] = {"start": start, "end": end, "include_na": include_na}
            else:
                values = split_list(record["values_var"].get()) or []
                if values or include_na:
                    # Intenta recuperar el tipo original cuando sea posible.
                    spec = self.visual_filter_specs.get(column)
                    typed_values = values
                    if spec is not None and spec.values:
                        lookup = {str(v): v for v in spec.values}
                        typed_values = [lookup.get(v, v) for v in values]
                    filters[column] = {"values": typed_values, "include_na": include_na}
        return filters


    def _collect_visual_builder_config(self):
        group = "visualization"
        df_name = self._input_value(group, "df_name").strip()
        if not df_name:
            raise ValueError("Selecciona un dataset.")
        if df_name not in self.dfs:
            raise KeyError(f"No existe el dataset '{df_name}'.")

        plot_type = self._plot_type_to_backend(self._input_value(group, "plot_type", "Automático"))
        if parse_bool(self.inputs[group]["rank_abundance"].get()):
            plot_type = "rank_abundance"

        x_col = self._input_value(group, "x_col").strip() or None
        y_col = self._input_value(group, "y_col").strip() or None
        hue_col = self._input_value(group, "hue_col").strip() or None
        facet_col = self._input_value(group, "facet_col").strip() or None
        id_col = self._input_value(group, "builder_id_col").strip() or None

        cfg = VisualizationConfig(
            plot_type=plot_type,
            x=x_col,
            y=y_col,
            color=hue_col,
            facet=facet_col,
            id_col=id_col,
            hover_cols=split_list(self._input_value(group, "hover_cols")) or [],
            filters=self._collect_visual_filters(),
            points=parse_bool(self.inputs[group]["layer_scatter"].get()),
            line=parse_bool(self.inputs[group]["layer_line"].get()),
            trend=parse_bool(self.inputs[group]["layer_trend"].get()),
            density=parse_bool(self.inputs[group]["layer_density"].get()),
            centroids=parse_bool(self.inputs[group]["layer_centroids"].get()),
            show_stats=parse_bool(self.inputs[group]["show_stats"].get()),
            log_x=parse_bool(self.inputs[group]["builder_log_x"].get()),
            log_y=parse_bool(self.inputs[group]["builder_log_y"].get()),
            opacity=min(max(float(self._input_value(group, "point_alpha", 0.75)), 0.05), 1.0),
            point_size=min(max(float(self._input_value(group, "point_size", 34)), 4.0), 300.0),
            bins=max(2, int(float(self._input_value(group, "builder_bins", 30) or 30))),
            max_facets=max(1, int(float(self._input_value(group, "max_facets", 12) or 12))),
            heatmap_cols=split_list(self._input_value(group, "heatmap_cols")) or [],
            abundance_cols=split_list(self._input_value(group, "abundance_cols")) or [],
            abundance_id_col=self._input_value(group, "abundance_id_col").strip() or None,
            abundance_group_col=self._input_value(group, "abundance_group_col").strip() or None,
            top_n=parse_optional_int(self._input_value(group, "top_n")),
            rank_log_scale=parse_bool(self.inputs[group]["log_scale"].get()),
            rank_show_cumulative=parse_bool(self.inputs[group]["rank_show_cumulative"].get()),
            rank_highlight_top=max(0, int(float(self._input_value(group, "rank_highlight_top", 10) or 10))),
            rank_search=self._input_value(group, "rank_search").strip() or None,
            title=self._input_value(group, "builder_title").strip() or None,
            interactive=True,
        )
        return {"df_name": df_name, **cfg.to_dict()}


    def _state_to_visual_config(self, state):
        return VisualizationConfig.from_mapping({k: v for k, v in state.items() if k != "df_name"})


    def _format_visual_object(self, value, max_rows=30):
        if value is None:
            return "Sin estadísticas para esta vista."
        if isinstance(value, pd.DataFrame):
            return value.head(max_rows).to_string(index=False)
        if isinstance(value, pd.Series):
            return value.head(max_rows).to_string()
        if isinstance(value, dict):
            lines = []
            for key, item in value.items():
                lines.append(f"[{key}]")
                if isinstance(item, pd.DataFrame):
                    lines.append(item.head(max_rows).to_string(index=False))
                elif isinstance(item, pd.Series):
                    lines.append(item.head(max_rows).to_string())
                elif isinstance(item, dict):
                    try:
                        lines.append(json.dumps(json_safe(item), ensure_ascii=False, indent=2))
                    except Exception:
                        lines.append(str(item))
                else:
                    lines.append(str(item))
                lines.append("")
            return "\n".join(lines).strip()
        try:
            return json.dumps(json_safe(value), ensure_ascii=False, indent=2)
        except Exception:
            return str(value)


    def _render_visual_builder_result(self, result, state):
        if self.visual_builder_interaction is not None:
            try:
                self.visual_builder_interaction.disconnect()
            except Exception:
                pass
            self.visual_builder_interaction = None

        old_figure = getattr(self, "visual_builder_figure", None)
        for child in self.visual_builder_canvas_host.winfo_children():
            child.destroy()
        for child in self.visual_builder_toolbar_host.winfo_children():
            child.destroy()

        self.visual_builder_result = result
        self.visual_builder_current_data = result.data
        self.visual_builder_current_config = state
        self.visual_builder_figure = result.figure
        self.visual_builder_ax = result.axes[0] if result.axes else None

        self.visual_builder_canvas = FigureCanvasTkAgg(result.figure, master=self.visual_builder_canvas_host)
        self.visual_builder_canvas.draw()
        self.visual_builder_canvas.get_tk_widget().grid(row=0, column=0, sticky="nsew")
        self.visual_builder_toolbar = NavigationToolbar2Tk(
            self.visual_builder_canvas,
            self.visual_builder_toolbar_host,
            pack_toolbar=False,
        )
        self.visual_builder_toolbar.grid(row=0, column=0, sticky="ew")

        if old_figure is not None and old_figure is not result.figure:
            try:
                plt.close(old_figure)
            except Exception:
                pass

        self._set_visual_text(self.visual_builder_stats_text, self._format_visual_object(result.stats))
        self.clear_visual_selection(update_text=True)
        self._set_visual_text(self.visual_builder_record_text, "Haz clic sobre un punto para inspeccionar el registro.")

        html_available = result.interactive_html is not None
        if hasattr(self, "visual_open_html_btn"):
            self.visual_open_html_btn.configure(state="normal" if html_available else "disabled")

        # Interacción Matplotlib desacoplada del backend de gráficos.
        hover_cols = list(state.get("hover_cols") or [])
        id_col = state.get("id_col")
        if id_col and id_col not in hover_cols:
            hover_cols.insert(0, id_col)
        controller = InteractiveController(
            figure=result.figure,
            canvas=self.visual_builder_canvas,
            data=result.data if isinstance(result.data, pd.DataFrame) else pd.DataFrame(),
            hover_cols=hover_cols,
            on_selection=self._on_visual_selection,
            on_record=self._on_visual_record,
        )
        controller.remember_view()
        if parse_bool(self.inputs["visualization"]["hover_enabled"].get()):
            controller.attach_hover()
        if parse_bool(self.inputs["visualization"]["inspector_enabled"].get()):
            controller.attach_point_inspector()

        selection_mode = self._input_value("visualization", "selection_mode", "Ninguna")
        if selection_mode == "Lazo":
            for ax in result.axes:
                controller.attach_lasso(ax)
        elif selection_mode == "Rectángulo":
            for ax in result.axes:
                controller.attach_rectangle(ax)
        if parse_bool(self.inputs["visualization"]["legend_toggle"].get()):
            controller.attach_legend_toggle()
        self.visual_builder_interaction = controller

        plot_type = result.metadata.get("plot_type", state.get("plot_type", ""))
        rows = len(result.data) if isinstance(result.data, pd.DataFrame) else 0
        self.visual_builder_hint_var.set(
            f"{state['df_name']} | {plot_type} | {rows:,} registros visibles"
        )


    def update_visual_builder(self, show_errors=True, push_history=True):
        try:
            state = self._collect_visual_builder_config()
            df = self.dfs[state["df_name"]]
            cfg = self._state_to_visual_config(state)
            result = build_visualization(df, cfg)
            self._render_visual_builder_result(result, state)
            if push_history and not self.visual_builder_applying_state:
                self.visual_builder_history.push(state)
            rows = len(result.data) if isinstance(result.data, pd.DataFrame) else 0
            if hasattr(self, "status_var"):
                self.status_var.set(f"Constructor actualizado: {rows} registros")
            if show_errors or parse_bool(self.inputs["visualization"]["verbose"].get()):
                self._log(
                    f"Constructor visual V2: {state['df_name']} | "
                    f"{result.metadata.get('plot_type', state.get('plot_type'))} | filas={rows}"
                )
            return result
        except Exception as exc:
            if show_errors:
                messagebox.showerror(APP_TITLE, f"No se pudo construir la gráfica:\n{exc}")
                self._log(f"Error en constructor visual: {exc}")
            elif hasattr(self, "status_var"):
                self.status_var.set(f"Vista pendiente: {exc}")
            return None


    def _on_visual_record(self, index, row):
        lines = [f"Índice fuente: {index}", ""]
        for key, value in row.items():
            if key == "__source_index__":
                continue
            lines.append(f"{key}: {value}")
        self._set_visual_text(self.visual_builder_record_text, "\n".join(lines))


    def _on_visual_selection(self, indices, selected_df):
        self.visual_builder_selected_indices = list(indices)
        self.visual_builder_selected_df = selected_df.copy()
        self.visual_selection_status_var.set(f"{len(indices)} registros seleccionados")

        if selected_df.empty:
            self._set_visual_text(self.visual_builder_selection_text, "No hay registros seleccionados.")
            return

        preview = selected_df.drop(columns=["__source_index__"], errors="ignore").head(20)
        lines = [f"Registros seleccionados: {len(selected_df)}", "", preview.to_string(index=False)]

        state = self.visual_builder_current_config or {}
        value_col = state.get("y") or state.get("x")
        group_col = state.get("color")
        try:
            routes = suggest_analysis_routes(
                selected_df,
                value_col=value_col,
                group_col=group_col,
            )
        except Exception:
            routes = []
        if routes:
            lines.extend(["", "Rutas sugeridas:"])
            lines.extend(f"- {route.get('label', route.get('module'))}" for route in routes)
        self._set_visual_text(self.visual_builder_selection_text, "\n".join(lines))


    def clear_visual_selection(self, update_text=True):
        self.visual_builder_selected_indices = []
        self.visual_builder_selected_df = None
        if hasattr(self, "visual_selection_status_var"):
            self.visual_selection_status_var.set("0 registros seleccionados")
        if update_text and hasattr(self, "visual_builder_selection_text"):
            self._set_visual_text(self.visual_builder_selection_text, "No hay registros seleccionados.")
        if self.visual_builder_interaction is not None:
            self.visual_builder_interaction.selected_indices = []


    def create_dataset_from_visual_selection(self):
        if self.visual_builder_result is None or not self.visual_builder_selected_indices:
            messagebox.showinfo(APP_TITLE, "Selecciona uno o varios registros en el gráfico primero.")
            return
        if not isinstance(self.visual_builder_result.data, pd.DataFrame):
            return
        selected = dataset_from_selection(
            self.visual_builder_result.data,
            self.visual_builder_selected_indices,
        )
        selected = selected.drop(columns=["__source_index__"], errors="ignore")
        if selected.empty:
            messagebox.showinfo(APP_TITLE, "La selección actual no contiene registros.")
            return
        base = (self.visual_builder_current_config or {}).get("df_name", "dataset")
        name = unique_name(f"{base}_seleccion", self.dfs)
        self.dfs[name] = selected
        self.refresh_datasets()
        self._log(f"Dataset creado desde selección visual: {name} -> {selected.shape}")
        self.status_var.set(f"Nuevo dataset: {name}")


    def reset_visual_view(self):
        if self.visual_builder_interaction is not None:
            self.visual_builder_interaction.reset_view()


    def open_visual_interactive(self):
        result = self.visual_builder_result
        if result is None or result.interactive_html is None:
            messagebox.showinfo(APP_TITLE, "Esta vista no tiene versión HTML interactiva disponible.")
            return
        output_root = Path(self.output_dir_var.get() or DEFAULT_OUTPUT_DIR).expanduser()
        preview_dir = output_root / "interactive_preview"
        preview_dir.mkdir(parents=True, exist_ok=True)
        stamp = _dt.datetime.now().strftime("%Y%m%d_%H%M%S")
        filename = result.interactive_html.filename or f"visual_{stamp}.html"
        path = preview_dir / f"{stamp}_{sanitize_name(filename, 'visual.html')}"
        if path.suffix.lower() != ".html":
            path = path.with_suffix(".html")
        path.write_text(result.interactive_html.html, encoding="utf-8")
        webbrowser.open(path.resolve().as_uri())
        self._log(f"HTML interactivo abierto: {path}")


    def _apply_visual_state(self, state, update=True):
        if not state:
            return
        group = "visualization"
        self.visual_builder_applying_state = True
        try:
            df_name = state.get("df_name", self._input_value(group, "df_name"))
            if df_name:
                self.inputs[group]["df_name"].set(df_name)
                self.refresh_columns()
                self.refresh_visual_filter_candidates()

            mapping = {
                "x": "x_col",
                "y": "y_col",
                "color": "hue_col",
                "facet": "facet_col",
                "id_col": "builder_id_col",
                "title": "builder_title",
                "max_facets": "max_facets",
                "bins": "builder_bins",
                "points": "layer_scatter",
                "line": "layer_line",
                "trend": "layer_trend",
                "density": "layer_density",
                "centroids": "layer_centroids",
                "show_stats": "show_stats",
                "log_x": "builder_log_x",
                "log_y": "builder_log_y",
                "opacity": "point_alpha",
                "point_size": "point_size",
                "abundance_id_col": "abundance_id_col",
                "abundance_group_col": "abundance_group_col",
                "top_n": "top_n",
                "rank_log_scale": "log_scale",
                "rank_show_cumulative": "rank_show_cumulative",
                "rank_highlight_top": "rank_highlight_top",
                "rank_search": "rank_search",
            }
            self.inputs[group]["plot_type"].set(self._plot_type_to_ui(state.get("plot_type", "auto")))
            self.inputs[group]["rank_abundance"].set(state.get("plot_type") == "rank_abundance")

            for source_key, gui_key in mapping.items():
                if source_key not in state or gui_key not in self.inputs[group]:
                    continue
                value = state[source_key]
                var = self.inputs[group][gui_key]
                if isinstance(var, tk.BooleanVar):
                    var.set(bool(value))
                elif isinstance(var, tk.DoubleVar):
                    if value is not None:
                        var.set(float(value))
                else:
                    var.set("" if value is None else str(value))

            self.inputs[group]["hover_cols"].set(", ".join(state.get("hover_cols") or []))
            self.inputs[group]["heatmap_cols"].set(", ".join(state.get("heatmap_cols") or []))
            self.inputs[group]["abundance_cols"].set(", ".join(state.get("abundance_cols") or []))

            self._clear_visual_filter_widgets()
            for column, rule in (state.get("filters") or {}).items():
                if column in self.visual_filter_specs:
                    self.add_visual_filter(column=column, initial_rule=rule, schedule=False)
        finally:
            self.visual_builder_applying_state = False

        self._update_visual_slider_labels()
        if update:
            self.update_visual_builder(show_errors=True, push_history=False)


    def undo_visual_view(self):
        state = self.visual_builder_history.undo()
        if state:
            self._apply_visual_state(state, update=True)


    def redo_visual_view(self):
        state = self.visual_builder_history.redo()
        if state:
            self._apply_visual_state(state, update=True)


    def _visual_preset_path(self):
        output_root = Path(self.output_dir_var.get() or DEFAULT_OUTPUT_DIR).expanduser()
        output_root.mkdir(parents=True, exist_ok=True)
        return output_root / "visualization_presets.json"


    def _ensure_visual_presets_loaded(self):
        if self.visual_builder_presets_loaded:
            return
        path = self._visual_preset_path()
        if path.exists():
            try:
                self.visual_builder_presets.load_file(path)
            except Exception as exc:
                self._log(f"No se pudieron cargar presets de visualización: {exc}")
        self.visual_builder_presets_loaded = True


    def save_visual_preset(self):
        try:
            state = self._collect_visual_builder_config()
        except Exception as exc:
            messagebox.showerror(APP_TITLE, f"No se puede guardar el preset:\n{exc}")
            return
        name = simpledialog.askstring(APP_TITLE, "Nombre del preset:", parent=self)
        if not name:
            return
        self._ensure_visual_presets_loaded()
        self.visual_builder_presets.save(name, state)
        self.visual_builder_presets.save_file(self._visual_preset_path())
        self._log(f"Preset de visualización guardado: {name}")


    def show_visual_presets(self):
        self._ensure_visual_presets_loaded()
        names = self.visual_builder_presets.names()
        if not names:
            messagebox.showinfo(APP_TITLE, "Aún no hay presets de visualización guardados.")
            return

        top = tk.Toplevel(self)
        top.title("Presets de visualización")
        top.geometry("520x360")
        frame = ttk.Frame(top, padding=10)
        frame.pack(fill="both", expand=True)
        frame.grid_rowconfigure(0, weight=1)
        frame.grid_columnconfigure(0, weight=1)
        listbox = tk.Listbox(frame)
        listbox.grid(row=0, column=0, sticky="nsew")
        for name in names:
            listbox.insert("end", name)

        buttons = ttk.Frame(frame)
        buttons.grid(row=1, column=0, sticky="ew", pady=(8, 0))
        buttons.grid_columnconfigure((0, 1), weight=1)

        def apply_selected():
            selection = listbox.curselection()
            if not selection:
                return
            name = listbox.get(selection[0])
            state = self.visual_builder_presets.get(name)
            top.destroy()
            self._apply_visual_state(state, update=True)
            self.visual_builder_history.push(state)

        def delete_selected():
            selection = listbox.curselection()
            if not selection:
                return
            name = listbox.get(selection[0])
            self.visual_builder_presets.delete(name)
            self.visual_builder_presets.save_file(self._visual_preset_path())
            listbox.delete(selection[0])

        ttk.Button(buttons, text="Aplicar", command=apply_selected).grid(row=0, column=0, sticky="ew", padx=(0, 4))
        ttk.Button(buttons, text="Eliminar", command=delete_selected).grid(row=0, column=1, sticky="ew", padx=(4, 0))
        listbox.bind("<Double-1>", lambda _event: apply_selected())


    def show_visual_recommendations(self):
        df_name = self._input_value("visualization", "df_name").strip()
        df = self.dfs.get(df_name)
        if df is None:
            messagebox.showinfo(APP_TITLE, "Selecciona un dataset primero.")
            return
        try:
            recommendations = recommend_visualizations(df)
        except Exception as exc:
            messagebox.showerror(APP_TITLE, f"No se pudieron generar recomendaciones:\n{exc}")
            return
        if not recommendations:
            messagebox.showinfo(APP_TITLE, "No se encontraron recomendaciones para este dataset.")
            return
        self.visual_recommendations = recommendations

        top = tk.Toplevel(self)
        top.title(f"Visualizaciones recomendadas - {df_name}")
        top.geometry("760x480")
        frame = ttk.Frame(top, padding=10)
        frame.pack(fill="both", expand=True)
        frame.grid_rowconfigure(0, weight=1)
        frame.grid_columnconfigure(0, weight=1)
        frame.grid_columnconfigure(1, weight=2)

        listbox = tk.Listbox(frame)
        listbox.grid(row=0, column=0, sticky="nsew", padx=(0, 8))
        detail = tk.Text(frame, wrap="word", relief="flat", bg="#ffffff")
        detail.grid(row=0, column=1, sticky="nsew")
        for rec in recommendations:
            listbox.insert("end", rec.title)

        def show_detail(_event=None):
            selection = listbox.curselection()
            if not selection:
                return
            rec = recommendations[selection[0]]
            detail.delete("1.0", "end")
            detail.insert("1.0", f"{rec.title}\n\n{rec.reason}\n\nConfiguración:\n{json.dumps(rec.config, ensure_ascii=False, indent=2)}")

        def apply_selected():
            selection = listbox.curselection()
            if not selection:
                return
            rec = recommendations[selection[0]]
            try:
                base = self._collect_visual_builder_config()
            except Exception:
                base = {"df_name": df_name}
            base.update(rec.config)
            base["df_name"] = df_name
            top.destroy()
            self._apply_visual_state(base, update=True)
            self.visual_builder_history.push(base)

        listbox.bind("<<ListboxSelect>>", show_detail)
        listbox.bind("<Double-1>", lambda _event: apply_selected())
        ttk.Button(frame, text="Aplicar recomendación", command=apply_selected, style="Accent.TButton").grid(
            row=1, column=0, columnspan=2, sticky="ew", pady=(8, 0)
        )
        listbox.selection_set(0)
        show_detail()


    def save_visual_builder_output(self):
        if self.visual_builder_result is None:
            self.update_visual_builder(show_errors=True)
        result = self.visual_builder_result
        state = self.visual_builder_current_config
        if result is None or state is None:
            return

        try:
            output_root = Path(self.output_dir_var.get() or DEFAULT_OUTPUT_DIR).expanduser()
            output_root.mkdir(parents=True, exist_ok=True)
            stamp = _dt.datetime.now().strftime("%Y%m%d_%H%M%S")
            run_dir = output_root / f"{stamp}_visual_builder_v2"
            run_dir.mkdir(parents=True, exist_ok=True)

            created = export_plot_result(
                result,
                run_dir,
                basename="visual_builder",
                formats=("png", "csv", "html"),
            )

            stats_manifest = {"tables": [], "arrays": [], "objects": [], "html": []}
            if result.stats is not None:
                stats_manifest = ArtifactExporter(run_dir).export(result.stats, prefix="visual_builder_stats")

            tables = []
            if "csv" in created and isinstance(result.data, pd.DataFrame):
                tables.append({
                    "name": "visual_builder_data",
                    "path": str(created["csv"]),
                    "rows": int(result.data.shape[0]),
                    "columns": int(result.data.shape[1]),
                })

            if self.visual_builder_selected_df is not None and not self.visual_builder_selected_df.empty:
                selected_path = run_dir / "tables" / "visual_builder_selection.csv"
                selected_path.parent.mkdir(parents=True, exist_ok=True)
                selection_to_save = self.visual_builder_selected_df.drop(columns=["__source_index__"], errors="ignore")
                selection_to_save.to_csv(selected_path, index=False, encoding="utf-8-sig")
                tables.append({
                    "name": "visual_builder_selection",
                    "path": str(selected_path),
                    "rows": int(selection_to_save.shape[0]),
                    "columns": int(selection_to_save.shape[1]),
                })

            tables.extend(stats_manifest.get("tables", []))
            html_items = list(stats_manifest.get("html", []))
            if "html" in created:
                html_items.append({"name": "visual_builder_interactive", "path": str(created["html"])})

            manifest = {
                "tables": tables,
                "arrays": stats_manifest.get("arrays", []),
                "objects": stats_manifest.get("objects", []) + ([{"name": "metadata", "path": str(created["metadata"])}] if "metadata" in created else []),
                "html": html_items,
                "figures": [str(created["png"])] if "png" in created else [],
                "analysis": "visual_builder_v2",
                "created_at": _dt.datetime.now().isoformat(timespec="seconds"),
                "parameters": json_safe(state),
            }
            if stats_manifest.get("excel_workbook"):
                manifest["excel_workbook"] = stats_manifest["excel_workbook"]

            manifest_path = run_dir / "manifest.json"
            manifest_path.write_text(json.dumps(manifest, ensure_ascii=False, indent=2), encoding="utf-8")

            key = self._register_result_manifest(
                manifest=manifest,
                run_dir=run_dir,
                result={"visual_builder_data": result.data, "visual_builder_stats": result.stats},
                manifest_path=manifest_path,
                select=True,
            )
            self.last_run_dir = run_dir
            self._log(f"Constructor visual V2 guardado: {run_dir}")
            self.status_var.set(f"Visualización guardada: {key}")
        except Exception as exc:
            messagebox.showerror(APP_TITLE, f"No se pudo guardar el constructor:\n{exc}")
            self._log(f"Error guardando constructor visual: {exc}")


    def export_visual_builder_dialog(self):
        if self.visual_builder_result is None:
            self.update_visual_builder(show_errors=True)
        if self.visual_builder_result is None:
            return
        directory = filedialog.askdirectory(
            title="Carpeta para exportar la visualización",
            initialdir=self.output_dir_var.get() or str(DEFAULT_OUTPUT_DIR),
        )
        if not directory:
            return
        try:
            created = export_plot_result(
                self.visual_builder_result,
                directory,
                basename="visualization",
                formats=("png", "svg", "pdf", "csv", "xlsx", "html"),
            )
            self._log("Exportación visual: " + ", ".join(f"{k}={v}" for k, v in created.items()))
            self.status_var.set(f"Exportados {len(created)} artefactos")
        except Exception as exc:
            messagebox.showerror(APP_TITLE, f"No se pudo exportar la visualización:\n{exc}")
            self._log(f"Error exportando visualización: {exc}")


    def _set_assistant_text(self, text):
        self.assistant_response_text.configure(state="normal")
        self.assistant_response_text.delete("1.0", "end")
        self.assistant_response_text.insert("1.0", str(text))
        self.assistant_response_text.configure(state="disabled")


    def _append_assistant_text(self, text):
        self.assistant_response_text.configure(state="normal")
        self.assistant_response_text.insert("end", "\n\n" + str(text))
        self.assistant_response_text.see("end")
        self.assistant_response_text.configure(state="disabled")


    def _assistant_question_mentions_results(self, question):
        normalized = unicodedata.normalize("NFKD", str(question).lower())
        q = "".join(char for char in normalized if not unicodedata.combining(char))
        return any(
            word in q
            for word in [
                "resultado",
                "resultados",
                "salio",
                "salieron",
                "interpreta",
                "interpretar",
                "conclusion",
                "conclusiones",
                "reporte",
            ]
        )


    def _assistant_results_response(self, question, provider="local", model="phi4-mini-reasoning"):
        key = self.active_result_key
        if not key and self.result_manifests:
            key = next(reversed(self.result_manifests))

        if not key:
            return AssistantResponse(
                text=(
                    "Todavia no hay resultados cargados o ejecutados. "
                    "Primero corre un analisis o usa 'Cargar corrida'. Despues puedo revisar tablas, figuras, "
                    "parametros y senalar que mirar."
                ),
                target_analysis="results",
                warnings=["No hay corridas disponibles."],
            )

        manifest = self.result_manifests.get(key, {})
        run_dir = self.result_run_dirs.get(key)
        analysis = manifest.get("analysis", "resultado")
        tables = manifest.get("tables", []) or []
        figures = manifest.get("figures", []) or []
        html = manifest.get("html", []) or []
        params = manifest.get("parameters", {}) or {}

        lines = [
            f"Estoy revisando la corrida activa: {key}.",
            f"Tipo de analisis: {analysis}. Tiene {len(tables)} tabla(s), {len(figures)} figura(s) y {len(html)} HTML interactivo(s).",
        ]

        if params:
            priority = [
                "df_name", "data_df_name", "group_df_name", "value_df_name", "group_col",
                "value_cols", "numeric_cols", "feature_cols", "alpha", "eps", "min_samples",
                "transform_method", "embedding_method",
            ]
            shown = []
            for name in priority:
                if name in params and params[name] not in (None, "", []):
                    shown.append(f"{name}={params[name]}")
            if shown:
                lines.append("Parametros clave: " + "; ".join(shown[:8]) + ".")

        table_notes = self._assistant_table_result_notes(tables, run_dir)
        if table_notes:
            lines.append("Lectura rapida de tablas:\n" + "\n".join(table_notes))
        elif tables:
            lines.append("Hay tablas guardadas, pero no encontre columnas de p-valores o metricas faciles de resumir automaticamente.")

        if html:
            names = [str(item.get("name", "HTML")) for item in html[:3]]
            lines.append("Para explorar visualmente, abre los HTML interactivos desde Resultados: " + ", ".join(names) + ".")
        elif figures:
            lines.append("Revisa las figuras en la pestana Resultados; si quieres compararlas con capas, recrealas desde Visualizaciones.")

        warnings = []
        try:
            interpretation = self.assistant_engine.interpret_results(
                {
                    "analysis": analysis,
                    "parameters": params,
                    "table_notes": table_notes,
                    "table_count": len(tables),
                    "figure_count": len(figures),
                    "html_count": len(html),
                },
                question=question,
                provider=provider,
                model=model,
            )
            if interpretation:
                lines.append(interpretation)
        except Exception as exc:
            warnings.append(f"No pude obtener la interpretación del modelo local: {exc}")
            lines.append("Se mantiene la lectura determinística de los resultados mostrada arriba.")

        lines.append("Siguiente paso: valida la conclusión contra el objetivo del estudio y ejecuta la siguiente prueba de la ruta si corresponde.")
        return AssistantResponse(
            text="\n".join(lines),
            target_analysis="results",
            warnings=warnings,
            context={"result_key": key, "analysis": analysis},
        )


    def _assistant_table_result_notes(self, tables, run_dir):
        notes = []

        def resolve(path_text):
            path = Path(path_text)
            if path.is_absolute() or path.exists():
                return path
            if run_dir:
                return Path(run_dir) / path
            return path

        for table in tables[:8]:
            path = resolve(table.get("path", ""))
            if not path.exists() or path.suffix.lower() != ".csv":
                continue
            try:
                df = pd.read_csv(path, nrows=1000)
            except Exception:
                continue
            lower_cols = {str(col).lower(): col for col in df.columns}
            p_cols = [
                col for low, col in lower_cols.items()
                if low in {"p", "p_value", "pvalue", "p_val", "p_adj", "p_adjusted", "q_value"}
                or "p_value" in low
                or "fdr" in low
                or "bonferroni" in low
            ]
            metric_cols = [
                col for low, col in lower_cols.items()
                if low in {"silhouette", "calinski_harabasz", "davies_bouldin", "ari", "ami"}
                or "silhouette" in low
                or "davies" in low
                or "calinski" in low
            ]
            table_name = table.get("name") or path.stem
            for col in p_cols[:2]:
                values = pd.to_numeric(df[col], errors="coerce").dropna()
                if values.empty:
                    continue
                significant = int((values < 0.05).sum())
                notes.append(
                    f"- {table_name}: {significant} de {len(values)} pruebas tienen {col} < 0.05; minimo observado {values.min():.4g}."
                )
            for col in metric_cols[:2]:
                values = pd.to_numeric(df[col], errors="coerce").dropna()
                if values.empty:
                    continue
                notes.append(
                    f"- {table_name}: {col} va de {values.min():.4g} a {values.max():.4g}; revisa filas con mejor valor antes de decidir."
                )
            if len(notes) >= 6:
                break
        return notes[:6]


    def ask_assistant(self):
        if self.worker and self.worker.is_alive():
            messagebox.showinfo(APP_TITLE, "Ya hay un analisis en ejecucion. Espera a que termine.")
            return
        question = self.assistant_question_text.get("1.0", "end").strip()
        if not question:
            messagebox.showinfo(APP_TITLE, "Escribe una pregunta para el asistente.")
            return

        self.assistant_engine.update_dfs(self.dfs)
        selected = self.inputs.get("assistant", {}).get("assistant_dataset", tk.StringVar()).get().strip() or None
        provider = self.inputs.get("assistant", {}).get("assistant_provider", tk.StringVar(value="local")).get().strip() or "local"
        default_model = os.getenv("OLLAMA_MODEL", "phi4-mini-reasoning:3.8b-q4_K_M") if provider == "local" else "qwen3.5-9b"
        model = self.inputs.get("assistant", {}).get("assistant_model", tk.StringVar(value=default_model)).get().strip() or default_model
        self._set_assistant_text("Pensando sobre tus datos y parametros...")
        self.status_var.set("Asistente pensando...")
        mode = "results" if self._assistant_question_mentions_results(question) else "question"
        thread = threading.Thread(
            target=self._assistant_worker,
            args=(mode, question, selected, provider, model),
            daemon=True,
        )
        thread.start()


    def ask_assistant_dataset_summary(self):
        self.assistant_engine.update_dfs(self.dfs)
        self._set_assistant_text("Revisando datasets cargados...")
        self.status_var.set("Asistente revisando datasets...")
        thread = threading.Thread(
            target=self._assistant_worker,
            args=("summary", "", None, "rules", ""),
            daemon=True,
        )
        thread.start()


    def _assistant_worker(self, mode, question, selected, provider, model):
        try:
            if mode == "summary":
                response = self.assistant_engine.analyze_datasets()
            elif mode == "results":
                response = self._assistant_results_response(question, provider=provider, model=model)
            else:
                response = self.assistant_engine.answer(
                    question,
                    selected_dataset=selected,
                    provider=provider,
                    model=model,
                )
            self.msg_queue.put(("assistant_done", response))
        except Exception:
            self.msg_queue.put(("assistant_error", traceback.format_exc()))


    def _render_assistant_response(self, response):
        self.assistant_last_response = response
        self.assistant_suggestion_payload = response.suggestions or {}

        parts = [response.text]
        if response.warnings:
            parts.append("Avisos:\n" + "\n".join(f"- {item}" for item in response.warnings))
        metrics = (response.context or {}).get("llm_metrics") or {}
        if metrics:
            parts.append(
                "Rendimiento del modelo:\n"
                f"- Total: {metrics.get('total_seconds')} s\n"
                f"- Carga: {metrics.get('load_seconds')} s\n"
                f"- Lectura del prompt: {metrics.get('prompt_seconds')} s ({metrics.get('prompt_tokens')} tokens)\n"
                f"- Generación: {metrics.get('generation_seconds')} s ({metrics.get('generated_tokens')} tokens)\n"
                f"- Velocidad: {metrics.get('tokens_per_second')} tokens/s"
            )
        if response.suggestions:
            parts.append("Parametros sugeridos:\n" + json.dumps(response.suggestions, ensure_ascii=False, indent=2))
        else:
            parts.append("No hay parametros automaticos para aplicar todavia.")

        self._set_assistant_text("\n\n".join(parts))
        self.status_var.set("Asistente listo")


    def apply_assistant_suggestions(self):
        suggestions = self.assistant_suggestion_payload or {}
        if not suggestions:
            messagebox.showinfo(APP_TITLE, "Todavia no hay sugerencias para aplicar.")
            return

        applied_groups = []
        for group, params in suggestions.items():
            if group not in self.inputs:
                continue
            applied = 0
            for key, value in params.items():
                var = self.inputs[group].get(key)
                if var is None:
                    continue
                if isinstance(var, tk.BooleanVar):
                    var.set(bool(value))
                else:
                    if isinstance(value, (list, tuple)):
                        value = ", ".join(map(str, value))
                    var.set("" if value is None else str(value))
                applied += 1
            if applied:
                applied_groups.append(group)

        self.refresh_columns()
        if applied_groups:
            self._select_analysis_tab(applied_groups[0])
            self._append_assistant_text(
                "Aplique sugerencias en: " + ", ".join(applied_groups) + ". Revisa los campos antes de ejecutar."
            )
            self._log("Asistente aplico parametros en: " + ", ".join(applied_groups))
        else:
            messagebox.showinfo(APP_TITLE, "Las sugerencias no coinciden con campos editables de la interfaz.")


    def _select_analysis_tab(self, analysis):
        labels = {
            "assistant": "Asistente",
            "exploration": "Exploracion",
            "characterization": "Caracterizacion",
            "normality": "Normalidad",
            "correlation": "Correlacion",
            "visualization": "Visualizaciones",
            "kde": "KDE",
            "kruskal": "Kruskal-Wallis",
            "mann_whitney": "Mann-Whitney",
            "dimensionality": "Reduccion",
            "dbscan": "DBSCAN",
            "cluster_review": "Revision clusters",
            "results": "Resultados",
        }
        target_label = labels.get(analysis)
        if not target_label:
            return
        for i in range(self.notebook.index("end")):
            if self.notebook.tab(i, "text") == target_label:
                self.notebook.select(i)
                return



    def load_files(self):
        paths = filedialog.askopenfilenames(
            title="Selecciona datasets",
            filetypes=[
                ("Archivos soportados", "*.csv *.otus *.txt *.meta *.taxonomy"),
                ("CSV", "*.csv"),
                ("Tabulados", "*.otus *.txt *.meta *.taxonomy"),
                ("Todos", "*.*"),
            ],
        )
        if not paths:
            return
        for path_text in paths:
            path = Path(path_text)
            try:
                df = load_dataframe_from_path(path)
                name = unique_name(path.stem, self.dfs)
                self.dfs[name] = df
                self._log(f"Cargado: {name} -> {df.shape}")
            except Exception as exc:
                self._log(f"Error cargando {path.name}: {exc}")
        self.refresh_datasets()


    def remove_selected_dataset(self):
        selected = self.dataset_tree.selection()
        if not selected:
            return
        for item in selected:
            name = self.dataset_tree.item(item, "text")
            self.dfs.pop(name, None)
            self._log(f"Dataset quitado de memoria: {name}")
        self.refresh_datasets()


    def preview_selected_dataset(self):
        selected = self.dataset_tree.selection()
        if not selected:
            messagebox.showinfo(APP_TITLE, "Selecciona un dataset para previsualizar.")
            return

        name = self.dataset_tree.item(selected[0], "text")
        df = self.dfs.get(name)
        if df is None:
            return

        top = tk.Toplevel(self)
        top.title(f"Vista previa - {name}")
        top.geometry("1100x580")
        top.minsize(850, 420)

        frame = ttk.Frame(top, padding=10)
        frame.pack(fill="both", expand=True)

        frame.grid_rowconfigure(1, weight=1)
        frame.grid_columnconfigure(0, weight=1)

        ttk.Label(
            frame,
            text=f"{name} | shape {df.shape}",
            font=("Segoe UI", 11, "bold")
        ).grid(row=0, column=0, sticky="w", pady=(0, 8))

        table_frame = ttk.Frame(frame)
        table_frame.grid(row=1, column=0, sticky="nsew")
        
        table_frame.grid_rowconfigure(0, weight=1)
        table_frame.grid_columnconfigure(0, weight=1)
        
        tree = ttk.Treeview(table_frame, show="headings")

        yscroll = ttk.Scrollbar(
            table_frame,
            orient="vertical",
            command=tree.yview
        )

        xscroll = ttk.Scrollbar(
            table_frame,
            orient="horizontal",
            command=tree.xview
        )

        tree.configure(
            yscrollcommand=yscroll.set,
            xscrollcommand=xscroll.set
        )

        tree.grid(row=0, column=0, sticky="nsew")
        yscroll.grid(row=0, column=1, sticky="ns")
        xscroll.grid(row=1, column=0, sticky="ew")

        preview = df.head(100).copy()

        max_cols = min(len(preview.columns), 80)

        columns = [str(c) for c in preview.columns[:max_cols]]
        tree["columns"] = columns

        for col in columns:
            tree.heading(col, text=col)
            tree.column(
                col,
                width=140,
                minwidth=90,
                stretch=False,
                anchor="w"
            )

        for _, row in preview.iloc[:, :max_cols].iterrows():
            values = []
                
            for v in row.tolist():
                if pd.isna(v):
                    values.append("")
                else:
                    values.append(str(v)[:160])

            tree.insert("", "end", values=values)

        tree.bind("<MouseWheel>", self._on_preview_dataset_mousewheel)
        tree.bind("<Shift-MouseWheel>", self._on_preview_dataset_shift_mousewheel)

        info_var = tk.StringVar(
            value=(
                f"Mostrando primeras {len(preview)} filas y primeras {max_cols} columnas. "
                "Usa la barra inferior o Shift + rueda para moverte lateralmente."
            )
        )

        ttk.Label(
            frame,
            textvariable=info_var,
            style="Subtle.TLabel"
        ).grid(row=2, column=0, sticky="ew", pady=(8, 0))

        
    def _on_preview_dataset_mousewheel(self, event):
        tree = event.widget

        if event.delta:
            tree.yview_scroll(int(-1 * (event.delta / 120)), "units")

        return "break"


    def _on_preview_dataset_shift_mousewheel(self, event):
        tree = event.widget
        
        if event.delta:
            tree.xview_scroll(int(-1 * (event.delta / 120)), "units")

        return "break"


    def refresh_datasets(self):
        self.assistant_engine.update_dfs(self.dfs)

        for item in self.dataset_tree.get_children():
            self.dataset_tree.delete(item)

        for name, df in sorted(self.dfs.items()):
            self.dataset_tree.insert("", "end", text=name, values=(f"{df.shape[0]} x {df.shape[1]}",))

        names = sorted(self.dfs.keys())

        for combo in self.df_combos:
            current = combo.get()
            combo.configure(values=names)

            if names:
                if current not in names:
                    combo.set(names[0])
            else:
                combo.set("")

        self.refresh_columns()


    def refresh_columns(self):
        for combo, (group, dataset_key) in self.column_combos:
            dataset_name = self.inputs.get(group, {}).get(dataset_key, tk.StringVar()).get()
            df = self.dfs.get(dataset_name)
            combo.configure(values=[] if df is None else list(map(str, df.columns)))

        self.refresh_numeric_column_dropdowns()
        self.refresh_categorical_column_dropdowns()
        self.refresh_group_value_dropdowns()
        self.refresh_visual_filter_candidates()


    def load_manifest_file(self):
        path = filedialog.askopenfilename(
            title="Cargar manifest de una corrida",
            initialdir=self.output_dir_var.get() or str(DEFAULT_OUTPUT_DIR),
            filetypes=[("Manifest JSON", "manifest.json"), ("JSON", "*.json"), ("Todos", "*.*")],
        )
        if not path:
            return
        self._load_manifest_path(Path(path))


    def load_run_folder(self):
        path = filedialog.askdirectory(
            title="Cargar carpeta de resultados",
            initialdir=self.output_dir_var.get() or str(DEFAULT_OUTPUT_DIR),
        )
        if not path:
            return

        manifest_path = Path(path) / "manifest.json"
        if not manifest_path.exists():
            messagebox.showerror(APP_TITLE, f"La carpeta seleccionada no contiene manifest.json:\n{Path(path)}")
            return

        self._load_manifest_path(manifest_path)


    def load_saved_runs(self):
        output_root = Path(self.output_dir_var.get() or DEFAULT_OUTPUT_DIR).expanduser()
        if not output_root.exists():
            messagebox.showinfo(APP_TITLE, f"No existe la carpeta de salida:\n{output_root}")
            return

        manifest_paths = self._discover_manifest_paths(output_root)
        if not manifest_paths:
            messagebox.showinfo(APP_TITLE, f"No se encontraron corridas con manifest.json en:\n{output_root}")
            return

        loaded = 0
        selected_key = None
        for manifest_path in manifest_paths:
            key = self._load_manifest_path(manifest_path, select=False, quiet=True)
            if key:
                loaded += 1
                selected_key = selected_key or key

        if selected_key:
            self.result_tree.selection_set(selected_key)
            self.result_tree.focus(selected_key)
            self.show_result_key(selected_key)

        self._log(f"Historial cargado desde {output_root}: {loaded} corrida(s).")
        self.status_var.set(f"Historial cargado: {loaded} corrida(s).")


    def _discover_manifest_paths(self, output_root):
        output_root = Path(output_root)
        candidates = []

        direct_manifest = output_root / "manifest.json"
        if direct_manifest.exists():
            candidates.append(direct_manifest)

        candidates.extend(output_root.glob("*/manifest.json"))
        unique = {}
        for path in candidates:
            try:
                unique[str(path.resolve())] = path
            except OSError:
                unique[str(path)] = path

        return sorted(
            unique.values(),
            key=lambda item: item.stat().st_mtime if item.exists() else 0,
            reverse=True,
        )


    def _load_manifest_path(self, manifest_path, select=True, quiet=False):
        manifest_path = Path(manifest_path)
        try:
            manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
        except Exception as exc:
            if not quiet:
                messagebox.showerror(APP_TITLE, f"No se pudo leer el manifest:\n{exc}")
            return None

        key = self._register_result_manifest(
            manifest=manifest,
            run_dir=manifest_path.parent,
            result=None,
            manifest_path=manifest_path,
            select=select,
        )
        if key and not quiet:
            self._log(f"Manifest cargado: {manifest_path}")
        return key


    def _register_result_manifest(self, manifest, run_dir, result=None, manifest_path=None, select=True):
        run_dir = Path(run_dir)
        manifest_path = Path(manifest_path) if manifest_path else run_dir / "manifest.json"

        existing_key = self._existing_result_key_for_manifest(manifest_path)
        if existing_key:
            if select:
                self.result_tree.selection_set(existing_key)
                self.result_tree.focus(existing_key)
                self.show_result_key(existing_key)
            return existing_key

        key = unique_name(self._result_key_from_manifest(manifest, run_dir), self.result_manifests)
        self.results[key] = result
        self.result_manifests[key] = manifest
        self.result_run_dirs[key] = run_dir
        self.result_tree.insert("", "end", iid=key, text=key, values=(self._format_result_created(manifest, manifest_path),))

        if select:
            self.result_tree.selection_set(key)
            self.result_tree.focus(key)
            self.show_result_key(key)

        return key


    def _existing_result_key_for_manifest(self, manifest_path):
        try:
            target = Path(manifest_path).resolve()
        except OSError:
            target = Path(manifest_path)

        for key, run_dir in self.result_run_dirs.items():
            try:
                current = (Path(run_dir) / "manifest.json").resolve()
            except OSError:
                current = Path(run_dir) / "manifest.json"
            if current == target:
                return key
        return None


    def _result_key_from_manifest(self, manifest, run_dir):
        analysis = manifest.get("analysis") or Path(run_dir).name or "resultado"
        created = str(manifest.get("created_at", "")).strip()
        stamp = ""
        if created:
            try:
                stamp = _dt.datetime.fromisoformat(created).strftime("%Y%m%d_%H%M%S")
            except ValueError:
                stamp = sanitize_name(created, "")
        if not stamp:
            stamp = sanitize_name(Path(run_dir).name, _dt.datetime.now().strftime("%Y%m%d_%H%M%S"))
        return sanitize_name(f"{analysis}_{stamp}", "resultado")


    def _format_result_created(self, manifest, manifest_path=None):
        created = str(manifest.get("created_at", "")).strip()
        if created:
            try:
                return _dt.datetime.fromisoformat(created).strftime("%Y-%m-%d %H:%M")
            except ValueError:
                return created[:16]

        if manifest_path:
            try:
                return _dt.datetime.fromtimestamp(Path(manifest_path).stat().st_mtime).strftime("%Y-%m-%d %H:%M")
            except OSError:
                pass

        return _dt.datetime.now().strftime("%Y-%m-%d %H:%M")


    def on_result_selected(self, _event=None):
        selected = self.result_tree.selection()
        if not selected:
            return
        self.show_result_key(selected[0])


    def show_result_key(self, key):
        manifest = self.result_manifests.get(key)
        if not manifest:
            return

        self.loading_result_view = True

        try:
            self.active_result_key = key
            self.visible_tables = {}
            self.visible_figures = {}
            self.current_table_path = None
            self.current_figure_path = None

            for item in self.table_list.get_children():
                self.table_list.delete(item)

            for item in self.figure_list.get_children():
                self.figure_list.delete(item)

            run_dir = self.result_run_dirs.get(key)
            analysis = manifest.get("analysis", key)
            created = manifest.get("created_at", "")
            self.results_title_var.set(f"{analysis} | {created} | {run_dir}")

            for i, table in enumerate(manifest.get("tables", []), start=1):
                iid = f"{key}_table_{i}"
                self.visible_tables[iid] = table
                name = table.get("name") or Path(table.get("path", "")).name
                rows = table.get("rows", "")
                cols = table.get("columns", "")

                self.table_list.insert(
                    "",
                    "end",
                    iid=iid,
                    text=name,
                    values=(rows, cols)
                )


            for i, figure_path in enumerate(manifest.get("figures", []), start=1):
                iid = f"{key}_figure_{i}"
                path = self._artifact_path(figure_path)
                self.visible_figures[iid] = path

                self.figure_list.insert(
                    "",
                    "end",
                    iid=iid,
                    text=path.name
                )

            for i, html_item in enumerate(manifest.get("html", []), start=1):
                html_path = html_item.get("path", html_item) if isinstance(html_item, dict) else html_item
                iid = f"{key}_html_{i}"
                path = self._artifact_path(html_path)
                self.visible_figures[iid] = path

                self.figure_list.insert(
                    "",
                    "end",
                    iid=iid,
                    text=f"HTML: {path.name}"
                )

            table_items = self.table_list.get_children()
            figure_items = self.figure_list.get_children()

            if table_items:
                first_table = table_items[0]
                self.table_list.selection_set(first_table)
                self.table_list.focus(first_table)
                self.table_list.see(first_table)
            else:
                self.clear_table_preview("Esta corrida no tiene tablas exportadas.")

            if figure_items:
                first_figure = figure_items[0]
                self.figure_list.selection_set(first_figure)
                self.figure_list.focus(first_figure)
                self.figure_list.see(first_figure)
            else:
                self.clear_figure_preview("Esta corrida no tiene figuras exportadas.")

            self.notebook.select(self.results_tab)

            if self.results_lists_notebook is not None:
                current_left_tab = self.results_lists_notebook.index("current")

                if current_left_tab == 0 and table_items:
                    self.show_current_table_selection()
                elif current_left_tab == 1 and figure_items:
                    self.show_current_figure_selection()
                elif table_items:
                    self.results_lists_notebook.select(0)
                    self.show_current_table_selection()
                elif figure_items:
                    self.results_lists_notebook.select(1)
                    self.show_current_figure_selection()

        finally:
            self.loading_result_view = False


    def refresh_active_result_view(self):
        if self.active_result_key:
            self.show_result_key(self.active_result_key)


    def on_table_selected(self, _event=None):
        if self.loading_result_view:
            return

        self.show_current_table_selection()


    def on_figure_selected(self, _event=None):
        if self.loading_result_view:
            return

        self.show_current_figure_selection()


    def on_result_list_tab_changed(self, _event=None):
        if self.loading_result_view:
            return

        if self.results_lists_notebook is None:
            return

        current_tab = self.results_lists_notebook.index("current")

        if current_tab == 0:
            self.show_current_table_selection()
        elif current_tab == 1:
            self.show_current_figure_selection()


    def show_current_table_selection(self):
        selected = self.table_list.selection()

        if selected:
            iid = selected[0]
        else:
            iid = self.table_list.focus()

        if not iid:
            table_items = self.table_list.get_children()

            if not table_items:
                self.clear_table_preview("No hay tablas disponibles.")
                return

            iid = table_items[0]
            self.table_list.selection_set(iid)
            self.table_list.focus(iid)
            self.table_list.see(iid)

        table = self.visible_tables.get(iid)

        if table is None:
            return

        self.show_table_preview(table)
        self.preview_notebook.select(0)


    def show_current_figure_selection(self):
        selected = self.figure_list.selection()

        if selected:
            iid = selected[0]
        else:
            iid = self.figure_list.focus()

        if not iid:
            figure_items = self.figure_list.get_children()

            if not figure_items:
                self.clear_figure_preview("No hay figuras disponibles.")
                return

            iid = figure_items[0]
            self.figure_list.selection_set(iid)
            self.figure_list.focus(iid)
            self.figure_list.see(iid)

        path = self.visible_figures.get(iid)

        if path is None:
            return

        self.show_figure_preview(path)
        self.preview_notebook.select(1)


    def _artifact_path(self, path_text):
        path = Path(path_text)
        if path.is_absolute():
            return path
        if path.exists():
            return path
        run_dir = self.result_run_dirs.get(self.active_result_key)
        if run_dir:
            return run_dir / path
        return path


    def clear_table_preview(self, message):
        for item in self.table_preview.get_children():
            self.table_preview.delete(item)
        self.table_preview["columns"] = []
        self.table_info_var.set(message)
        self.current_table_path = None


    def show_table_preview(self, table):
        path = self._artifact_path(table.get("path", ""))
        self.current_table_path = path
        if not path.exists():
            self.clear_table_preview(f"No existe el archivo: {path}")
            return
        try:
            df = pd.read_csv(path, nrows=500)
        except Exception as exc:
            self.clear_table_preview(f"No se pudo leer la tabla: {exc}")
            return

        for item in self.table_preview.get_children():
            self.table_preview.delete(item)

        max_cols = min(len(df.columns), 80)
        column_ids = [f"c{i}" for i in range(max_cols)]
        self.table_preview["columns"] = column_ids
        for i, col in enumerate(df.columns[:max_cols]):
            label = str(col)
            width = max(90, min(220, 8 * len(label) + 30))
            self.table_preview.heading(column_ids[i], text=label)
            self.table_preview.column(column_ids[i], width=width, stretch=False)

        for _, row in df.iloc[:, :max_cols].iterrows():
            values = []
            for value in row.tolist():
                if pd.isna(value):
                    values.append("")
                else:
                    text = str(value)
                    values.append(text[:160])
            self.table_preview.insert("", "end", values=values)

        rows = table.get("rows", "?")
        cols = table.get("columns", "?")
        rows_count = int(rows) if str(rows).isdigit() else None
        cols_count = int(cols) if str(cols).isdigit() else None
        suffix = ""
        if rows_count is not None and rows_count > 500:
            suffix += " | mostrando primeras 500 filas"
        if cols_count is not None and cols_count > max_cols:
            suffix += f" | mostrando primeras {max_cols} columnas"
        self.table_info_var.set(f"{table.get('name', path.name)} | {rows} x {cols} | {path}{suffix}")
        self.preview_notebook.select(0)


    def clear_figure_preview(self, message):
        self.figure_canvas.delete("all")
        self.figure_canvas.configure(scrollregion=(0, 0, 0, 0))
        self.figure_info_var.set(message)
        self.current_figure_path = None
        self.figure_image_ref = None


    def show_figure_preview(self, path):
        path = Path(path)
        self.current_figure_path = path
        self.figure_canvas.delete("all")
        if not path.exists():
            self.clear_figure_preview(f"No existe la figura: {path}")
            return

        if path.suffix.lower() in {".html", ".htm"}:
            self.figure_canvas.create_text(
                24,
                24,
                anchor="nw",
                text="Archivo interactivo HTML.\nUsa 'Abrir seleccionado' para verlo en el navegador.",
                fill="#20242a",
                font=("Segoe UI", 12)
            )
            self.figure_canvas.configure(scrollregion=(0, 0, 640, 140))
            self.figure_info_var.set(f"{path.name} | {path}")
            self.preview_notebook.select(1)
            return

        try:
            if HAS_PIL:
                image = Image.open(path)
                self.figure_canvas.update_idletasks()
                max_w = max(760, self.figure_canvas.winfo_width() - 30)
                max_h = max(520, self.figure_canvas.winfo_height() - 30)
                ratio = min(max_w / image.width, max_h / image.height, 1.0)
                size = (max(1, int(image.width * ratio)), max(1, int(image.height * ratio)))
                if size != image.size:
                    image = image.resize(size, Image.LANCZOS)
                self.figure_image_ref = ImageTk.PhotoImage(image)
            else:
                self.figure_image_ref = tk.PhotoImage(file=str(path))
                size = (self.figure_image_ref.width(), self.figure_image_ref.height())
        except Exception as exc:
            self.clear_figure_preview(f"No se pudo abrir la figura: {exc}")
            return

        self.figure_canvas.create_image(12, 12, anchor="nw", image=self.figure_image_ref)
        self.figure_canvas.configure(scrollregion=(0, 0, size[0] + 24, size[1] + 24))
        self.figure_info_var.set(f"{path.name} | {path}")
        self.preview_notebook.select(1)


    def open_selected_result_file(self):
        current_preview = self.preview_notebook.index("current")
        path = self.current_figure_path if current_preview == 1 else self.current_table_path
        if path is None:
            selected_fig = self.figure_list.selection()
            selected_table = self.table_list.selection()
            if selected_fig:
                path = self.visible_figures.get(selected_fig[0])
            elif selected_table:
                table = self.visible_tables.get(selected_table[0], {})
                path = self._artifact_path(table.get("path", ""))
        if path is None:
            messagebox.showinfo(APP_TITLE, "Selecciona una tabla o figura.")
            return
        try:
            os.startfile(path)
        except Exception as exc:
            messagebox.showerror(APP_TITLE, f"No se pudo abrir el archivo:\n{exc}")


    def open_active_run_dir(self):
        path = None
        if self.active_result_key:
            path = self.result_run_dirs.get(self.active_result_key)
        if path is None:
            path = self.last_run_dir
        if path is None:
            path = Path(self.output_dir_var.get()).expanduser()
        try:
            Path(path).mkdir(parents=True, exist_ok=True)
            os.startfile(path)
        except Exception as exc:
            messagebox.showerror(APP_TITLE, f"No se pudo abrir la carpeta:\n{exc}")


    def choose_output_dir(self):
        path = filedialog.askdirectory(title="Carpeta de salida", initialdir=self.output_dir_var.get() or str(DEFAULT_OUTPUT_DIR))
        if path:
            self.output_dir_var.set(path)


    def open_output_dir(self):
        path = Path(self.output_dir_var.get()).expanduser()
        path.mkdir(parents=True, exist_ok=True)
        try:
            os.startfile(path)
        except Exception as exc:
            messagebox.showerror(APP_TITLE, f"No se pudo abrir la carpeta:\n{exc}")


    def run_analysis(self, analysis):
        if self.worker and self.worker.is_alive():
            messagebox.showinfo(APP_TITLE, "Ya hay un analisis en ejecucion.")
            return
        if not self.dfs:
            messagebox.showinfo(APP_TITLE, "Carga al menos un dataset antes de ejecutar.")
            return
        self.refresh_columns()
        try:
            params = self._collect_params(analysis)
            output_root = Path(self.output_dir_var.get()).expanduser()
        except Exception as exc:
            messagebox.showerror(APP_TITLE, f"Revisa los parametros:\n{exc}")
            return
        self.status_var.set(f"Ejecutando {analysis}...")
        self._log(f"\n=== Ejecutando {analysis} ===")
        self.worker = threading.Thread(target=self._worker_run, args=(analysis, params, output_root), daemon=True)
        self.worker.start()


    def _worker_run(self, analysis, params, output_root):
        try:
            output_root.mkdir(parents=True, exist_ok=True)
            stamp = _dt.datetime.now().strftime("%Y%m%d_%H%M%S")
            run_dir = output_root / f"{stamp}_{sanitize_name(analysis)}"
            run_dir.mkdir(parents=True, exist_ok=True)
            figure_dir = run_dir / "figures"

            stdout = io.StringIO()
            with contextlib.redirect_stdout(stdout), contextlib.redirect_stderr(stdout), FigureCapture(figure_dir) as figs:
                result = self._execute(analysis, params)

            log_text = stdout.getvalue()
            if log_text:
                (run_dir / "execution_log.txt").write_text(log_text, encoding="utf-8")

            exporter = ArtifactExporter(run_dir)
            manifest = exporter.export(result, prefix=analysis)
            manifest.update({
                "analysis": analysis,
                "created_at": _dt.datetime.now().isoformat(timespec="seconds"),
                "parameters": json_safe(params),
                "figures": [str(p) for p in figs.saved],
            })
            with (run_dir / "manifest.json").open("w", encoding="utf-8") as fh:
                json.dump(manifest, fh, ensure_ascii=False, indent=2)
            with (run_dir / "parameters.json").open("w", encoding="utf-8") as fh:
                json.dump(json_safe(params), fh, ensure_ascii=False, indent=2)

            self.msg_queue.put(("done", analysis, result, run_dir, manifest, log_text))
        except Exception:
            self.msg_queue.put(("error", analysis, traceback.format_exc()))


    def _collect_params(self, analysis):
        values = {key: var.get() for key, var in self.inputs[analysis].items()}

        if analysis == "exploration":
            return {
                "df_name": values["df_name"],
                "numeric_cols": split_list(values["numeric_cols"]),
                "max_category_values": int(values["max_category_values"]),
                "verbose": parse_bool(values["verbose"]),
            }

        if analysis == "characterization":
            return {
                "df_name": values["df_name"],
                "numeric_cols": split_list(values["numeric_cols"]),
                "analysis_mode": values["analysis_mode"],
                "bins": int(values["bins"]),
                "plot_positive_hist": parse_bool(values["plot_positive_hist"]),
                "verbose": parse_bool(values["verbose"]),
            }

        if analysis == "normality":
            return {
                "df_name": values["df_name"],
                "numeric_cols": split_list(values["numeric_cols"]),
                "analysis_mode": values["analysis_mode"],
                "value_mode": values["value_mode"],
                "test_method": values["test_method"],
                "alpha": float(values["alpha"]),
                "verbose": parse_bool(values["verbose"]),
            }

        if analysis == "correlation":
            return {
                "df_name": values["df_name"],
                "numeric_cols": split_list(values["numeric_cols"]),
                "alpha": float(values["alpha"]),
                "min_non_null": int(values["min_non_null"]),
                "max_plot_vars": int(values["max_plot_vars"]),
                "verbose": parse_bool(values["verbose"]),
            }

        if analysis == "visualization":
            plot_type = self._plot_type_to_backend(values.get("plot_type", "Automático"))
            x_col = values.get("x_col", "").strip() or None
            y_col = values.get("y_col", "").strip() or None
            hue_col = values.get("hue_col", "").strip() or None
            group_col = hue_col if plot_type in {"violin", "boxplot"} else None
            violin_cols = [y_col] if plot_type == "violin" and y_col else None
            rank_mode = parse_bool(values.get("rank_abundance", False)) or plot_type == "rank_abundance"
            return {
                "df_name": values["df_name"],
                "x_col": x_col if plot_type in {"auto", "scatter"} else None,
                "y_col": y_col if plot_type in {"auto", "scatter"} else None,
                "hue_col": hue_col,
                "group_col": group_col,
                "violin_cols": violin_cols,
                "rank_abundance": rank_mode,
                "abundance_cols": split_list(values.get("abundance_cols", "")),
                "abundance_id_col": values.get("abundance_id_col", "").strip() or "ID",
                "top_n": parse_optional_int(values.get("top_n", "")),
                "log_scale": parse_bool(values.get("log_scale", True)),
                "verbose": parse_bool(values.get("verbose", True)),
            }

        if analysis == "kde":
            return {
                "data_df_name": values["data_df_name"],
                "grid_size": int(values["grid_size"]),
                "cv_subsample": int(values["cv_subsample"]),
                "cv_folds": int(values["cv_folds"]),
                "cv_bw_grid": int(values["cv_bw_grid"]),
                "min_bandwidth": float(values["min_bandwidth"]),
                "cv_max_expansions": int(values["cv_max_expansions"]),
                "test_kernel_bandwidths": parse_bandwidths(values["test_kernel_bandwidths"]),
                "verbose": parse_bool(values["verbose"]),
            }

        if analysis == "kruskal":
            return {
                "alpha": float(values["alpha"]),
                "group_df_name": values["group_df_name"],
                "value_df_name": values["value_df_name"],
                "group_col": values["group_col"],
                "id_col_group": values["id_col_group"],
                "id_col_value": values["id_col_value"],
                "value_cols": split_list(values["value_cols"]),
                "min_group_size": int(values["min_group_size"]),
                "apply_fdr": parse_bool(values["apply_fdr"]),
                "verbose": parse_bool(values["verbose"]),
            }

        if analysis == "mann_whitney":
            groups = split_list(values["groups_to_compare"])
            return {
                "alpha": float(values["alpha"]),
                "group_df_name": values["group_df_name"],
                "value_df_name": values["value_df_name"],
                "group_col": values["group_col"],
                "groups_to_compare": tuple(groups) if groups else None,
                "id_col_group": values["id_col_group"],
                "id_col_value": values["id_col_value"],
                "value_cols": split_list(values["value_cols"]),
                "min_group_size": int(values["min_group_size"]),
                "alternative": values["alternative"],
                "apply_fdr": parse_bool(values["apply_fdr"]),
                "verbose": parse_bool(values["verbose"]),
            }

        if analysis == "dimensionality":
            return {
                "data_df_name": values["data_df_name"],
                "id_col": values["id_col"].strip() or None,
                "feature_cols": split_list(values["feature_cols"]),
                "missing_strategy": values["missing_strategy"],
                "remove_zero_rows": parse_bool(values["remove_zero_rows"]),
                "min_prevalence": parse_optional_float(values["min_prevalence"]),
                "min_total_abundance": parse_optional_float(values["min_total_abundance"]),
                "transform_method": values["transform_method"],
                "pseudocount": float(values["pseudocount"]),
                "scale": parse_bool(values["scale"]),
                "embedding_method": values["embedding_method"],
                "n_components": int(values["n_components"]),
                "random_state": int(values["random_state"]),
                "embedding_kwargs": parse_json_dict(values["embedding_kwargs"]),
                "variance_thresholds": parse_float_tuple(
                    values["variance_thresholds"],
                    default=(0.8, 0.9, 0.95)
                ),
                "verbose": parse_bool(values["verbose"]),
            }

        if analysis == "dbscan":
            meta_df_name = values["meta_df_name"].strip() or None
            return {
                "data_df_name": values["data_df_name"],
                "id_col": values["id_col"].strip() or None,
                "feature_cols": split_list(values["feature_cols"]),
                "meta_df_name": meta_df_name,
                "meta_id_col": values["meta_id_col"].strip() or None,
                "eps": float(values["eps"]),
                "min_samples": int(values["min_samples"]),
                "calculate_k_distance": parse_bool(values["calculate_k_distance"]),
                "k_distance_min_samples": int(values["k_distance_min_samples"]),
                "drop_non_numeric": parse_bool(values["drop_non_numeric"]),
                "missing_strategy": values["missing_strategy"],
                "remove_zero_rows": parse_bool(values["remove_zero_rows"]),
                "min_prevalence": parse_optional_float(values["min_prevalence"]),
                "min_total_abundance": parse_optional_float(values["min_total_abundance"]),
                "transform_method": values["transform_method"],
                "pseudocount": float(values["pseudocount"]),
                "scale": parse_bool(values["scale"]),
                "embedding_method": values["embedding_method"],
                "n_components": int(values["n_components"]),
                "random_state": int(values["random_state"]),
                "embedding_kwargs": parse_json_dict(values["embedding_kwargs"]),
                "plot_k_distance_graph": parse_bool(values["plot_k_distance_graph"]),
                "plot_embedding_graph": parse_bool(values["plot_embedding_graph"]),
                "summary_numeric_cols": split_list(values["summary_numeric_cols"]),
                "summary_categorical_cols": split_list(values["summary_categorical_cols"]),
                "summary_numeric_aggs": parse_tuple(values["summary_numeric_aggs"]) or ("median",),
                "verbose": parse_bool(values["verbose"]),
            }

        if analysis == "cluster_review":
            label_col = values["label_col"].strip()
            if not label_col:
                raise ValueError("Selecciona una columna de cluster.")
            return {
                "df_name": values["df_name"],
                "label_col": label_col,
                "feature_cols": split_list(values["feature_cols"]),
                "ignore_noise": parse_bool(values["ignore_noise"]),
                "noise_label": values["noise_label"].strip() or "-1",
                "min_cluster_size": int(values["min_cluster_size"]),
                "verbose": parse_bool(values["verbose"]),
            }

        raise ValueError(f"Analisis desconocido: {analysis}")


    def _execute(self, analysis, params):
        if analysis == "exploration":
            return dataset_profile_from_loaded(dfs=self.dfs, **params)
        if analysis == "characterization":
            return distribution_plots_from_loaded(dfs=self.dfs, **params)
        if analysis == "normality":
            return normality_tests_from_loaded(dfs=self.dfs, **params)
        if analysis == "correlation":
            return correlation_from_loaded(dfs=self.dfs, **params)
        if analysis == "visualization":
            return visualization_from_loaded(dfs=self.dfs, **params)
        if analysis == "kde":
            return kde_from_loaded(dfs=self.dfs, **params)
        if analysis == "kruskal":
            return kruskal_wallis_from_loaded(dfs=self.dfs, **params)
        if analysis == "mann_whitney":
            return mann_whitney_from_loaded(dfs=self.dfs, **params)
        if analysis == "dimensionality":
            return dimensionality_from_loaded(dfs=self.dfs, **params)
        if analysis == "dbscan":
            return dbscan_from_loaded(dfs=self.dfs, **params)
        if analysis == "cluster_review":
            return cluster_review_from_loaded(dfs=self.dfs, **params)
        raise ValueError(f"Analisis desconocido: {analysis}")


    def _poll_queue(self):
        try:
            while True:
                message = self.msg_queue.get_nowait()
                kind = message[0]
                if kind == "done":
                    _, analysis, result, run_dir, manifest, log_text = message
                    self.last_run_dir = Path(run_dir)
                    key = self._register_result_manifest(
                        manifest=manifest,
                        run_dir=run_dir,
                        result=result,
                        manifest_path=Path(run_dir) / "manifest.json",
                        select=True,
                    )
                    if log_text:
                        self._log(log_text.rstrip())
                    self._log(f"Terminado: {analysis}")
                    self._log(f"Salida: {run_dir}")
                    self._log(
                        f"Tablas: {len(manifest.get('tables', []))} | "
                        f"Arrays: {len(manifest.get('arrays', []))} | "
                        f"Figuras: {len(manifest.get('figures', []))} | "
                        f"HTML: {len(manifest.get('html', []))}"
                    )
                    self.status_var.set(f"Listo. Ultima salida: {run_dir}")
                elif kind == "error":
                    _, analysis, trace = message
                    self._log(f"Error en {analysis}:\n{trace}")
                    self.status_var.set(f"Error en {analysis}")
                    messagebox.showerror(APP_TITLE, f"El analisis fallo. Revisa el log.\n\n{trace.splitlines()[-1]}")
                elif kind == "assistant_done":
                    _, response = message
                    self._render_assistant_response(response)
                    self._log("Asistente genero una recomendacion.")
                elif kind == "assistant_error":
                    _, trace = message
                    self._set_assistant_text(f"El asistente fallo. Revisa el detalle:\n\n{trace}")
                    self._log(f"Error en asistente:\n{trace}")
                    self.status_var.set("Error en asistente")
        except queue.Empty:
            pass
        self.after(150, self._poll_queue)

    def _log(self, text):
        self.log_text.insert("end", str(text) + "\n")
        self.log_text.see("end")



def main():
    app = MicrobiotaGUI()
    app.mainloop()


if __name__ == "__main__":
    main()
