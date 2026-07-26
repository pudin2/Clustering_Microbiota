import json
import os
import unicodedata
from pathlib import Path
from dataclasses import dataclass, field

import numpy as np
import pandas as pd
import requests


def _load_dotenv_file():
    """Carga un .env sencillo sin agregar una dependencia obligatoria."""
    candidates = [Path.cwd() / ".env", Path(__file__).resolve().parent / ".env"]
    for path in candidates:
        if not path.exists():
            continue
        for raw_line in path.read_text(encoding="utf-8").splitlines():
            line = raw_line.strip()
            if not line or line.startswith("#") or "=" not in line:
                continue
            key, value = line.split("=", 1)
            key = key.strip()
            value = value.strip().strip('"').strip("'")
            if key and key not in os.environ:
                os.environ[key] = value
        break


_load_dotenv_file()


@dataclass
class AssistantResponse:
    text: str
    target_analysis: str | None = None
    suggestions: dict = field(default_factory=dict)
    warnings: list[str] = field(default_factory=list)
    context: dict = field(default_factory=dict)


def _as_text_list(values, max_items=8):
    result = []
    for value in values[:max_items]:
        result.append(str(value))
    return result


def _safe_unique(series):
    try:
        return int(series.nunique(dropna=True))
    except Exception:
        return 0


class DatasetInspector:

    def __init__(self, dfs):
        self.dfs = dfs


    def dataset_names(self):
        return sorted(self.dfs.keys())


    def inspect(self, df_name):
        if df_name not in self.dfs:
            raise KeyError(f"No existe el dataset '{df_name}'. Disponibles: {list(self.dfs.keys())}")

        df = self.dfs[df_name]
        numeric_cols = []
        categorical_cols = []
        id_like_cols = []
        mixed_cols = []

        for col in df.columns:
            series = df[col]
            non_null = int(series.notna().sum())
            unique = _safe_unique(series)
            numeric = pd.to_numeric(series, errors="coerce")
            numeric_ratio = float(numeric.notna().sum() / non_null) if non_null else 0.0

            if pd.api.types.is_numeric_dtype(series) or numeric_ratio >= 0.85:
                numeric_cols.append(str(col))
            elif non_null > 0 and unique == non_null:
                id_like_cols.append(str(col))
            elif unique <= max(20, int(0.08 * max(len(df), 1))):
                categorical_cols.append(str(col))
            else:
                mixed_cols.append(str(col))

        abundance_like = self._looks_like_abundance_matrix(df, numeric_cols)
        missing_pct = float(df.isna().sum().sum() / max(df.shape[0] * df.shape[1], 1))

        sparse_zero_pct = np.nan
        if numeric_cols:
            sample_cols = numeric_cols[: min(len(numeric_cols), 500)]
            values = df[sample_cols].apply(pd.to_numeric, errors="coerce").to_numpy(dtype=float)
            values = values[np.isfinite(values)]
            if values.size:
                sparse_zero_pct = float(np.mean(values == 0))

        group_candidates = []
        for col in categorical_cols:
            unique = _safe_unique(df[col])
            if 2 <= unique <= 12:
                group_candidates.append(col)

        numeric_candidates = self._prioritize_numeric(df, numeric_cols)

        return {
            "name": df_name,
            "shape": tuple(df.shape),
            "numeric_cols": numeric_cols,
            "categorical_cols": categorical_cols,
            "id_like_cols": id_like_cols,
            "mixed_cols": mixed_cols,
            "group_candidates": group_candidates,
            "numeric_candidates": numeric_candidates,
            "abundance_like": abundance_like,
            "missing_pct": missing_pct,
            "zero_pct_numeric_sample": sparse_zero_pct,
            "column_examples": list(map(str, df.columns[:12])),
        }


    def _prioritize_numeric(self, df, numeric_cols):
        preferred = [
            "glucose",
            "HDL",
            "LDL",
            "waist",
            "age",
            "bmi",
            "HOMA_IR",
            "triglycerides",
            "body_fat",
            "Calories",
            "Fiber",
        ]
        lower_map = {str(col).lower(): str(col) for col in numeric_cols}
        ordered = []
        for name in preferred:
            if name.lower() in lower_map:
                ordered.append(lower_map[name.lower()])
        for col in numeric_cols:
            if col not in ordered and not str(col).lower().startswith("otu"):
                ordered.append(col)
        for col in numeric_cols:
            if col not in ordered:
                ordered.append(col)
        return ordered[:12]


    def _looks_like_abundance_matrix(self, df, numeric_cols):
        if len(numeric_cols) >= 100:
            return True
        otu_like = sum(1 for col in numeric_cols if str(col).lower().startswith("otu"))
        if otu_like >= 20:
            return True
        if df.shape[1] >= 80 and len(numeric_cols) >= df.shape[1] * 0.65:
            return True
        return False


    def summarize_all(self):
        rows = []
        for name in self.dataset_names():
            info = self.inspect(name)
            rows.append({
                "dataset": name,
                "rows": info["shape"][0],
                "columns": info["shape"][1],
                "numeric": len(info["numeric_cols"]),
                "categorical": len(info["categorical_cols"]),
                "id_like": len(info["id_like_cols"]),
                "abundance_like": info["abundance_like"],
                "missing_pct": round(info["missing_pct"], 4),
                "zero_pct_numeric_sample": None if not np.isfinite(info["zero_pct_numeric_sample"]) else round(info["zero_pct_numeric_sample"], 4),
            })
        return pd.DataFrame(rows)


class OpenAssistantEngine:

    def __init__(self, dfs=None):
        self.dfs = dfs or {}
        self.inspector = DatasetInspector(self.dfs)
        self.last_response = None


    def update_dfs(self, dfs):
        self.dfs = dfs or {}
        self.inspector = DatasetInspector(self.dfs)


    def analyze_datasets(self):
        if not self.dfs:
            return AssistantResponse(
                text="Carga primero uno o varios datasets. Despues puedo revisar columnas, tipos, faltantes y sugerir el primer analisis.",
                warnings=["No hay datasets cargados."],
            )

        summary = self.inspector.summarize_all()
        lines = ["Revise los datasets cargados:"]
        for row in summary.to_dict("records"):
            kind = "matriz de abundancia probable" if row["abundance_like"] else "tabla clinica/dietaria probable"
            lines.append(
                f"- {row['dataset']}: {row['rows']} filas x {row['columns']} columnas; "
                f"{row['numeric']} numericas, {row['categorical']} categoricas; {kind}."
            )

        first = summary.iloc[0]["dataset"] if len(summary) else None
        suggestions = {}
        if first:
            suggestions = {
                "exploration": {
                    "df_name": first,
                    "max_category_values": "12",
                    "verbose": True,
                }
            }
            lines.append("")
            lines.append("Siguiente paso recomendado: ejecuta Exploracion para confirmar tipos, continuidad y bins sugeridos.")

        response = AssistantResponse(
            text="\n".join(lines),
            target_analysis="exploration",
            suggestions=suggestions,
            context={"summary": summary.to_dict("records")},
        )
        self.last_response = response
        return response


    def answer(self, question, selected_dataset=None, provider="cloud", model="qwen3.5-9b", use_ollama=None, base_url=None, api_key=None):
        question = str(question or "").strip()
        if not question:
            return AssistantResponse(text="Escribe una pregunta o describe que quieres comparar.")

        if not self.dfs:
            return AssistantResponse(
                text="Carga primero tus datasets. Luego puedo sugerir pruebas, preprocesamiento y completar parametros.",
                warnings=["No hay datasets cargados."],
            )

        df_name = self._choose_dataset(question, selected_dataset)
        info = self.inspector.inspect(df_name)
        response = self._heuristic_answer(question, info)

        # Compatibilidad con versiones anteriores: use_ollama=True fuerza modo local.
        if use_ollama is True:
            provider = "local"
        elif use_ollama is False and provider is None:
            provider = "rules"

        provider = str(provider or "cloud").strip().lower()
        if provider not in {"cloud", "local", "rules"}:
            response.warnings.append(f"Proveedor desconocido '{provider}'. Se usaron reglas locales.")
            provider = "rules"

        if provider in {"cloud", "local"}:
            try:
                llm_text = self._llm_answer(
                    question=question,
                    info=info,
                    local_response=response,
                    provider=provider,
                    model=model,
                    base_url=base_url,
                    api_key=api_key,
                )
                # Conserva la recomendación determinística y agrega la revisión del agente.
                response.text = response.text + "\n\n" + llm_text
                response.context["llm_provider"] = provider
                response.context["llm_model"] = model
            except Exception as exc:
                response.warnings.append(f"No pude usar el modelo {provider}: {exc}")
                response.text += (
                    "\n\nEl modelo no estuvo disponible. Se conservó la recomendación "
                    "determinística basada en reglas y en la estructura del dataset."
                )

        self.last_response = response
        return response


    def _choose_dataset(self, question, selected_dataset):
        if selected_dataset and selected_dataset in self.dfs:
            return selected_dataset

        question_lower = self._normalize_text(question)
        for name in self.inspector.dataset_names():
            if self._normalize_text(name) in question_lower:
                return name

        names = self.inspector.dataset_names()
        for name in names:
            info = self.inspector.inspect(name)
            if info["abundance_like"] and any(word in question_lower for word in ["otu", "abundancia", "microbiota", "kde", "rank"]):
                return name

        return names[0]


    def _heuristic_answer(self, question, info):
        q = self._normalize_text(question)
        text_parts = []
        suggestions = {}
        target = None
        warnings = []

        numeric = list(dict.fromkeys(info["numeric_candidates"] + info["numeric_cols"]))
        groups = info["group_candidates"]
        first_group = self._choose_group_col(q, info)
        first_numeric = self._choose_numeric_cols(q, numeric)[: min(6, len(numeric))]
        wants_visual = any(word in q for word in ["grafic", "visual", "plot", "violin", "dispersion", "scatter", "rank"])
        wants_group_compare = (
            any(word in q for word in ["compar", "grupo", "grupos", "diferencia", "signific", "mann", "kruskal"])
            or (" por " in f" {q} " and first_group is not None and not wants_visual)
        )

        if any(word in q for word in ["preproces", "limpiar", "faltante", "ceros", "normalizar", "transformar"]):
            target = "dimensionality"
            transform = "clr" if info["abundance_like"] else "log1p"
            missing = "fill_zero" if info["abundance_like"] else "median"
            suggestions[target] = {
                "data_df_name": info["name"],
                "id_col": self._guess_id_col(info),
                "feature_cols": ", ".join(first_numeric),
                "missing_strategy": missing,
                "remove_zero_rows": bool(info["abundance_like"]),
                "transform_method": transform,
                "pseudocount": "1.0",
                "scale": True,
                "embedding_method": "pca",
                "n_components": "3",
                "random_state": "42",
                "variance_thresholds": "0.8, 0.9, 0.95",
                "verbose": True,
            }
            text_parts.append(
                f"Para {info['name']} recomiendo preprocesar con faltantes='{missing}', "
                f"transformacion='{transform}' y escalado=True."
            )
            if info["abundance_like"]:
                text_parts.append("Parece una matriz de abundancias: CLR con pseudocount 1.0 y quitar filas suma 0 suele ser razonable.")

        elif any(word in q for word in ["correl", "relacion", "asociacion lineal", "pearson", "spearman"]):
            target = "correlation"
            suggestions[target] = {
                "df_name": info["name"],
                "numeric_cols": ", ".join(first_numeric),
                "alpha": "0.05",
                "min_non_null": "3",
                "max_plot_vars": "25",
                "verbose": True,
            }
            text_parts.append(
                "Usaria Correlacion con Pearson y Spearman. Pearson captura relacion lineal; Spearman captura relacion monotona y tolera mejor asimetrias."
            )

        elif wants_group_compare:
            if first_group is None:
                target = "exploration"
                warnings.append("No encontre una columna categorica clara para grupos.")
                suggestions[target] = {"df_name": info["name"], "max_category_values": "12", "verbose": True}
                text_parts.append("Primero ejecutaria Exploracion para confirmar que columna define los grupos.")
            else:
                group_count = self._group_count(info["name"], first_group)
                if group_count == 2:
                    target = "mann_whitney"
                    values = self._group_values(info["name"], first_group, limit=2)
                    suggestions[target] = {
                        "group_df_name": info["name"],
                        "value_df_name": info["name"],
                        "group_col": first_group,
                        "groups_to_compare": ", ".join(values),
                        "id_col_group": self._guess_id_col(info),
                        "id_col_value": self._guess_id_col(info),
                        "value_cols": ", ".join(first_numeric),
                        "alpha": "0.05",
                        "min_group_size": "3",
                        "alternative": "two-sided",
                        "apply_fdr": True,
                        "verbose": True,
                    }
                    text_parts.append(f"Como {first_group} tiene dos grupos, usaria Mann-Whitney para comparar medianas/distribuciones.")
                else:
                    target = "kruskal"
                    suggestions[target] = {
                        "group_df_name": info["name"],
                        "value_df_name": info["name"],
                        "group_col": first_group,
                        "id_col_group": self._guess_id_col(info),
                        "id_col_value": self._guess_id_col(info),
                        "value_cols": ", ".join(first_numeric),
                        "alpha": "0.05",
                        "min_group_size": "3",
                        "apply_fdr": True,
                        "verbose": True,
                    }
                    text_parts.append(f"Como {first_group} tiene {group_count} grupos, usaria Kruskal-Wallis.")

        elif any(word in q for word in ["cluster", "clusterizar", "dbscan", "agrup"]):
            target = "dbscan"
            transform = "clr" if info["abundance_like"] else "none"
            suggestions[target] = {
                "data_df_name": info["name"],
                "id_col": self._guess_id_col(info),
                "feature_cols": ", ".join(first_numeric),
                "meta_df_name": info["name"],
                "meta_id_col": self._guess_id_col(info),
                "eps": "1.0",
                "min_samples": "3",
                "calculate_k_distance": True,
                "k_distance_min_samples": "8",
                "drop_non_numeric": True,
                "missing_strategy": "fill_zero" if info["abundance_like"] else "median",
                "remove_zero_rows": bool(info["abundance_like"]),
                "transform_method": transform,
                "pseudocount": "1.0",
                "scale": True,
                "embedding_method": "pca",
                "n_components": "3",
                "random_state": "42",
                "plot_k_distance_graph": True,
                "plot_embedding_graph": True,
                "summary_numeric_cols": ", ".join(first_numeric[:3]),
                "summary_categorical_cols": ", ".join(groups[:2]),
                "summary_numeric_aggs": "median",
                "verbose": True,
            }
            text_parts.append("Para DBSCAN primero miraria k-distance para ajustar eps. Empieza con PCA 3D y min_samples entre 3 y 8.")

        elif wants_visual:
            target = "visualization"
            x_col, y_col = self._choose_xy(first_numeric)
            suggestions[target] = {
                "df_name": info["name"],
                "x_col": x_col,
                "y_col": y_col,
                "hue_col": first_group or "",
                "group_col": first_group or "",
                "violin_cols": ", ".join(first_numeric[:3]),
                "rank_abundance": bool(info["abundance_like"]),
                "abundance_id_col": self._guess_id_col(info),
                "top_n": "2000",
                "log_scale": True,
                "layer_scatter": True,
                "layer_trend": True,
                "layer_centroids": bool(first_group),
                "point_alpha": "0.75",
                "point_size": "34",
                "verbose": True,
            }
            text_parts.append("Usaria Visualizaciones y el Constructor visual: marca puntos, tendencia y centroides para comparar capas.")
            if info["abundance_like"]:
                text_parts.append("Como parece abundancia, tambien activaria rank-abundancia con escala log.")

        elif any(word in q for word in ["normal", "normalidad", "distribucion", "shapiro", "anderson"]):
            target = "normality"
            suggestions[target] = {
                "df_name": info["name"],
                "numeric_cols": ", ".join(first_numeric),
                "analysis_mode": "by_column",
                "value_mode": "both",
                "test_method": "both",
                "alpha": "0.05",
                "verbose": True,
            }
            text_parts.append("Para revisar distribuciones usaria Normalidad con valores all y positive. En abundancias, los positivos suelen ser mas informativos.")

        elif any(word in q for word in ["kde", "densidad", "kernel"]):
            target = "kde"
            suggestions[target] = {
                "data_df_name": info["name"],
                "grid_size": "1000",
                "cv_subsample": "1000",
                "cv_folds": "3",
                "cv_bw_grid": "8",
                "min_bandwidth": "1.0",
                "cv_max_expansions": "4",
                "test_kernel_bandwidths": "",
                "verbose": True,
            }
            text_parts.append("Para KDE usaria los valores positivos, grid 1000 y CV de bandwidth con 3 folds.")

        else:
            target = "exploration"
            suggestions[target] = {
                "df_name": info["name"],
                "max_category_values": "12",
                "verbose": True,
            }
            text_parts.append(
                "Empezaria por Exploracion para entender tipos de columnas, faltantes, continuidad y posibles grupos."
            )

        text_parts.insert(0, self._dataset_intro(info))
        if target:
            text_parts.append(f"\nPuedo llenar automaticamente la pestaña: {target}. Revisa y ejecuta cuando estes de acuerdo.")

        return AssistantResponse(
            text="\n".join(text_parts),
            target_analysis=target,
            suggestions=suggestions,
            warnings=warnings,
            context={"dataset_info": self._compact_info(info)},
        )


    def _dataset_intro(self, info):
        kind = "matriz de abundancia probable" if info["abundance_like"] else "tabla clinica/dietaria probable"
        return (
            f"Estoy mirando {info['name']} ({info['shape'][0]} filas x {info['shape'][1]} columnas), "
            f"que parece {kind}. Detecte {len(info['numeric_cols'])} columnas numericas y "
            f"{len(info['categorical_cols'])} categoricas."
        )


    def _compact_info(self, info):
        return {
            "name": info["name"],
            "shape": info["shape"],
            "numeric_candidates": _as_text_list(info["numeric_candidates"], 10),
            "group_candidates": _as_text_list(info["group_candidates"], 8),
            "abundance_like": info["abundance_like"],
            "missing_pct": info["missing_pct"],
            "zero_pct_numeric_sample": info["zero_pct_numeric_sample"],
        }


    def _guess_id_col(self, info):
        for candidate in ["ID", "id", "Sample", "sample", "Codalt"]:
            if candidate in info["id_like_cols"] or candidate in info["numeric_cols"] or candidate in info["categorical_cols"]:
                return candidate
        return info["id_like_cols"][0] if info["id_like_cols"] else ""


    def _normalize_text(self, text):
        normalized = unicodedata.normalize("NFKD", str(text).lower())
        return "".join(char for char in normalized if not unicodedata.combining(char))


    def _choose_group_col(self, question, info):
        groups = info["group_candidates"]
        if not groups:
            return None

        q = self._normalize_text(question)
        group_norm = {self._normalize_text(col): col for col in groups}

        for norm_name, original in group_norm.items():
            readable = norm_name.replace("_", " ")
            compact = norm_name.replace("_", "")
            if norm_name in q or readable in q or compact in q:
                return original

        alias_groups = [
            (["sexo", "sex", "genero", "gender"], ["sex"]),
            (["ciudad", "city"], ["city"]),
            (["edad", "rango de edad", "age range"], ["age_range"]),
            (["sangre", "oculta", "hidden blood", "hiden blood"], ["hiden_blood", "hidden_blood"]),
            (["imc", "bmi", "clase de peso", "obesidad"], ["bmi_class"]),
            (["heces", "stool", "consistencia"], ["stool_consistency"]),
            (["medicamento", "medicament", "farmaco"], ["medicament"]),
        ]
        for triggers, candidates in alias_groups:
            if any(trigger in q for trigger in triggers):
                for candidate in candidates:
                    norm_candidate = self._normalize_text(candidate)
                    if norm_candidate in group_norm:
                        return group_norm[norm_candidate]

        return groups[0]


    def _choose_numeric_cols(self, question, numeric):
        if not numeric:
            return []

        q = self._normalize_text(question)
        selected = []

        def add_col(col):
            if col in numeric and col not in selected:
                selected.append(col)

        norm_map = {self._normalize_text(col): col for col in numeric}
        for norm_name, original in norm_map.items():
            readable = norm_name.replace("_", " ")
            compact = norm_name.replace("_", "")
            if norm_name in q or readable in q or compact in q:
                add_col(original)

        alias_groups = [
            (["glucosa"], ["glucose"]),
            (["colesterol"], ["cholesterol"]),
            (["trigliceridos"], ["triglycerides"]),
            (["presion", "tension"], ["systolic_bp", "diastolic_bp"]),
            (["imc", "indice de masa corporal"], ["bmi"]),
            (["grasa corporal"], ["body_fat"]),
            (["cintura"], ["waist"]),
            (["fibra"], ["fiber", "Fiber"]),
            (["proteina"], ["per_protein", "per_animal_protein"]),
            (["carbohidratos"], ["per_carbohydrates"]),
            (["grasa saturada"], ["per_saturated_fat"]),
        ]
        for triggers, candidates in alias_groups:
            if any(trigger in q for trigger in triggers):
                for candidate in candidates:
                    norm_candidate = self._normalize_text(candidate)
                    if norm_candidate in norm_map:
                        add_col(norm_map[norm_candidate])

        for col in numeric:
            add_col(col)
        return selected


    def _choose_xy(self, numeric):
        if len(numeric) >= 2:
            return numeric[0], numeric[1]
        if len(numeric) == 1:
            return numeric[0], numeric[0]
        return "", ""


    def _group_count(self, df_name, group_col):
        if not group_col:
            return 0
        return int(self.dfs[df_name][group_col].dropna().nunique())


    def _group_values(self, df_name, group_col, limit=2):
        values = self.dfs[df_name][group_col].dropna().astype(str).str.strip()
        values = [value for value in pd.unique(values) if value]
        return values[:limit]


    def _dataset_evidence(self, info, max_rows=8):
        """Construye evidencia compacta; evita enviar el dataset completo al modelo."""
        df = self.dfs[info["name"]]
        numeric = info["numeric_candidates"][:8]
        evidence = {
            "dataset": info["name"],
            "shape": info["shape"],
            "abundance_like": info["abundance_like"],
            "missing_pct": round(float(info["missing_pct"]), 5),
            "group_candidates": info["group_candidates"][:8],
            "numeric_candidates": numeric,
        }
        summaries = {}
        for col in numeric:
            values = pd.to_numeric(df[col], errors="coerce").dropna()
            if values.empty:
                continue
            summaries[col] = {
                "n": int(values.size),
                "missing": int(df[col].isna().sum()),
                "unique": int(values.nunique()),
                "mean": float(values.mean()),
                "median": float(values.median()),
                "std": float(values.std(ddof=1)) if values.size > 1 else None,
                "min": float(values.min()),
                "max": float(values.max()),
                "zero_pct": float((values == 0).mean()),
            }
        evidence["numeric_summary"] = summaries
        group_summary = {}
        for col in info["group_candidates"][:5]:
            counts = df[col].astype(str).replace("nan", np.nan).dropna().value_counts().head(12)
            group_summary[col] = {str(k): int(v) for k, v in counts.items()}
        evidence["group_counts"] = group_summary
        evidence["column_names"] = list(map(str, df.columns[:80]))
        return evidence


    def _build_agent_prompt(self, question, info, local_response):
        return {
            "system": (
                "Eres BioStat Pocket Agent, un equipo virtual de bioestadística para investigación en microbiota, "
                "nutrición y datos clínicos. Trabajas como cinco especialistas coordinados: "
                "(1) diseñador de estudio, (2) auditor de calidad y supuestos, (3) selector de pruebas, "
                "(4) especialista en parámetros y multiplicidad, y (5) intérprete científico. "
                "No inventes variables ni resultados. Distingue recomendación, supuesto, limitación y decisión. "
                "No afirmes causalidad a partir de asociaciones. Para microbiota considera composicionalidad, "
                "ceros, prevalencia, sobredispersión y corrección por múltiples pruebas. "
                "Responde en español, con secciones: Recomendación, Por qué, Parámetros, Verificaciones, "
                "Interpretación y Limitaciones. Sé accionable y prudente."
            ),
            "user": {
                "question": question,
                "dataset_evidence": self._dataset_evidence(info),
                "deterministic_engine": {
                    "target_analysis": local_response.target_analysis,
                    "suggestions": local_response.suggestions,
                    "warnings": local_response.warnings,
                },
                "task": (
                    "Revisa críticamente la recomendación determinística. Corrígela si es necesario, explica "
                    "qué prueba usar, qué parámetros configurar, qué diagnósticos ejecutar antes y cómo interpretar "
                    "los resultados. Si falta información del diseño (pareado, longitudinal, covariables, outcome, "
                    "unidad experimental), indícalo explícitamente y ofrece decisiones condicionales."
                ),
            },
        }


    def _llm_answer(self, question, info, local_response, provider, model, base_url=None, api_key=None):
        prompt = self._build_agent_prompt(question, info, local_response)
        if provider == "local":
            return self._ollama_answer(prompt, model=model)
        return self._cloud_answer(prompt, model=model, base_url=base_url, api_key=api_key)


    def _ollama_answer(self, prompt, model="qwen3.5:9b"):
        url = os.getenv("OLLAMA_BASE_URL", "http://localhost:11434").rstrip("/") + "/api/generate"
        response = requests.post(
            url,
            json={
                "model": model,
                "prompt": json.dumps(prompt, ensure_ascii=False),
                "stream": False,
                "options": {"temperature": 0.15, "num_ctx": 16384},
            },
            timeout=float(os.getenv("LLM_TIMEOUT_SECONDS", "90")),
        )
        response.raise_for_status()
        data = response.json()
        text = data.get("response", "").strip()
        if not text:
            raise RuntimeError("Ollama respondió sin texto.")
        return "Revisión del agente local:\n" + text


    def _cloud_answer(self, prompt, model="qwen3.5-9b", base_url=None, api_key=None):
        # Compatible con Qwen API Platform, Alibaba Model Studio y otros endpoints OpenAI-compatible.
        base_url = (base_url or os.getenv("QWEN_CLOUD_BASE_URL") or os.getenv("OPENAI_COMPATIBLE_BASE_URL") or "").rstrip("/")
        api_key = api_key or os.getenv("QWEN_CLOUD_API_KEY") or os.getenv("DASHSCOPE_API_KEY")
        model = model or os.getenv("QWEN_CLOUD_MODEL", "qwen3.5-9b")
        if not base_url:
            raise RuntimeError("Falta QWEN_CLOUD_BASE_URL en el archivo .env o en las variables de entorno.")
        if not api_key:
            raise RuntimeError("Falta QWEN_CLOUD_API_KEY (o DASHSCOPE_API_KEY).")
        url = base_url if base_url.endswith("/chat/completions") else base_url + "/chat/completions"
        response = requests.post(
            url,
            headers={"Authorization": f"Bearer {api_key}", "Content-Type": "application/json"},
            json={
                "model": model,
                "messages": [
                    {"role": "system", "content": prompt["system"]},
                    {"role": "user", "content": json.dumps(prompt["user"], ensure_ascii=False)},
                ],
                "temperature": 0.15,
                "top_p": 0.8,
                "max_tokens": 2400,
            },
            timeout=float(os.getenv("LLM_TIMEOUT_SECONDS", "90")),
        )
        response.raise_for_status()
        data = response.json()
        choices = data.get("choices") or []
        if not choices:
            raise RuntimeError(f"Respuesta cloud sin choices: {data}")
        text = (choices[0].get("message") or {}).get("content", "").strip()
        if not text:
            raise RuntimeError("El proveedor cloud respondió sin texto.")
        return "Revisión del agente cloud:\n" + text
