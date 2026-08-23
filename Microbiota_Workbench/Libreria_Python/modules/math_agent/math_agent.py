"""Core de planificación para el agente matemático.

El LLM nunca ejecuta cálculos estadísticos. Este módulo mantiene un catálogo
cerrado de pruebas disponibles en el proyecto, construye una ruta determinista
y produce evidencia compacta que puede ser revisada por un modelo local.
"""
from __future__ import annotations

from dataclasses import dataclass, asdict
from typing import Any

import numpy as np
import pandas as pd


DEFAULT_LOCAL_MODEL = "phi4-mini-reasoning"
DEFAULT_NUM_CTX = 2048
DEFAULT_NUM_PREDICT = 160


@dataclass(frozen=True)
class TestDefinition:
    id: str
    label: str
    module: str
    function: str
    purpose: str
    stage: str

    @property
    def path(self) -> str:
        return f"{self.module}::{self.function}"

    def as_dict(self) -> dict[str, Any]:
        data = asdict(self)
        data["path"] = self.path
        return data


TEST_CATALOG: dict[str, TestDefinition] = {
    "exploration": TestDefinition(
        "exploration", "Perfilado preliminar", "modules/exploration/exploration.py", "dataset_profile_from_loaded",
        "Revisar tipos, faltantes, cardinalidad, continuidad y calidad básica.", "precheck",
    ),
    "characterization": TestDefinition(
        "characterization", "Caracterización descriptiva", "modules/characterization/characterization.py", "distribution_plots_from_loaded",
        "Resumir distribución, tendencia central y dispersión.", "precheck",
    ),
    "normality": TestDefinition(
        "normality", "Diagnóstico de distribución", "modules/characterization/characterization.py", "normality_tests_from_loaded",
        "Evaluar normalidad y distribuciones candidatas antes de decidir pruebas dependientes de supuestos.", "assumption",
    ),
    "correlation": TestDefinition(
        "correlation", "Correlación", "modules/exploration/exploration.py", "correlation_from_loaded",
        "Cuantificar asociación lineal/monótona con Pearson y Spearman.", "analysis",
    ),
    "mann_whitney": TestDefinition(
        "mann_whitney", "Mann-Whitney U", "modules/mann_whitney/mann_whitney.py", "mann_whitney_from_loaded",
        "Comparar dos grupos independientes con una prueba no paramétrica.", "analysis",
    ),
    "kruskal": TestDefinition(
        "kruskal", "Kruskal-Wallis", "modules/kruskal_wallis/kruskal_wallis.py", "kruskal_wallis_from_loaded",
        "Comparar tres o más grupos independientes con una prueba no paramétrica.", "analysis",
    ),
    "kde": TestDefinition(
        "kde", "Estimación KDE", "modules/kde/kde.py", "kde_from_loaded",
        "Estimar forma de densidad y bandwidth en datos positivos.", "analysis",
    ),
    "dimensionality": TestDefinition(
        "dimensionality", "Reducción dimensional", "modules/exploration/exploration.py", "dimensionality_from_loaded",
        "Preparar, transformar y reducir dimensiones antes de clustering/exploración multivariada.", "analysis",
    ),
    "dbscan": TestDefinition(
        "dbscan", "DBSCAN", "modules/dbscan/dbscan.py", "dbscan_from_loaded",
        "Detectar agrupamientos y ruido por densidad.", "analysis",
    ),
    "cluster_review": TestDefinition(
        "cluster_review", "Revisión de clusters", "modules/exploration/exploration.py", "cluster_review_from_loaded",
        "Evaluar estabilidad/calidad interna, tamaños y ruido de una clusterización.", "validation",
    ),
}


def public_catalog() -> list[dict[str, Any]]:
    return [item.as_dict() for item in TEST_CATALOG.values()]


def preliminary_review(df: pd.DataFrame, info: dict[str, Any]) -> dict[str, Any]:
    """Evidencia determinista y compacta para la revisión preliminar."""
    n_rows, n_cols = df.shape
    duplicate_rows = int(df.duplicated().sum()) if n_rows else 0
    duplicate_pct = float(duplicate_rows / n_rows) if n_rows else 0.0

    high_missing = []
    constants = []
    near_constants = []
    infinite_numeric = {}

    for col in df.columns:
        s = df[col]
        miss = float(s.isna().mean()) if n_rows else 0.0
        if miss >= 0.20:
            high_missing.append({"column": str(col), "missing_pct": round(miss, 4)})

        nunique = int(s.nunique(dropna=True))
        if nunique <= 1:
            constants.append(str(col))
        elif n_rows >= 20 and nunique <= 2:
            counts = s.value_counts(dropna=True, normalize=True)
            if not counts.empty and float(counts.iloc[0]) >= 0.98:
                near_constants.append(str(col))

        if str(col) in info.get("numeric_cols", []):
            numeric = pd.to_numeric(s, errors="coerce").to_numpy(dtype=float)
            inf_count = int(np.isinf(numeric).sum())
            if inf_count:
                infinite_numeric[str(col)] = inf_count

    group_sizes = {}
    small_groups = []
    for col in info.get("group_candidates", [])[:8]:
        counts = df[col].dropna().astype(str).value_counts()
        group_sizes[str(col)] = {str(k): int(v) for k, v in counts.head(20).items()}
        too_small = {str(k): int(v) for k, v in counts.items() if int(v) < 3}
        if too_small:
            small_groups.append({"column": str(col), "groups_lt_3": too_small})

    flags = []
    missing_pct = float(info.get("missing_pct") or 0.0)
    zero_pct = info.get("zero_pct_numeric_sample")
    if missing_pct >= 0.10:
        flags.append(f"Faltantes globales relativamente altos ({missing_pct:.1%}).")
    if duplicate_pct > 0:
        flags.append(f"Se detectaron {duplicate_rows} filas duplicadas ({duplicate_pct:.1%}).")
    if high_missing:
        flags.append(f"Hay {len(high_missing)} columnas con al menos 20% de faltantes.")
    if constants:
        flags.append(f"Hay {len(constants)} columnas constantes o vacías.")
    if infinite_numeric:
        flags.append("Se detectaron valores infinitos en columnas numéricas.")
    if small_groups:
        flags.append("Algunos grupos candidatos tienen menos de 3 observaciones.")
    if zero_pct is not None:
        try:
            if np.isfinite(float(zero_pct)) and float(zero_pct) >= 0.50:
                flags.append(f"Alta proporción de ceros en la muestra numérica ({float(zero_pct):.1%}).")
        except Exception:
            pass
    if n_rows < 20:
        flags.append(f"Tamaño de muestra pequeño (n={n_rows}); interpretar inferencia con cautela.")

    return {
        "shape": [int(n_rows), int(n_cols)],
        "duplicate_rows": duplicate_rows,
        "duplicate_pct": round(duplicate_pct, 5),
        "high_missing_columns": high_missing[:20],
        "constant_columns": constants[:20],
        "near_constant_columns": near_constants[:20],
        "infinite_numeric": infinite_numeric,
        "group_sizes": group_sizes,
        "small_groups": small_groups[:10],
        "flags": flags,
    }


def _add_step(steps: list[dict[str, Any]], test_id: str, reason: str, parameters: dict[str, Any] | None = None,
              conditional: bool = False) -> None:
    if test_id not in TEST_CATALOG:
        return
    if any(step["test_id"] == test_id for step in steps):
        return
    definition = TEST_CATALOG[test_id]
    steps.append({
        "order": len(steps) + 1,
        "test_id": test_id,
        "test": definition.label,
        "stage": definition.stage,
        "path": definition.path,
        "reason": reason,
        "conditional": bool(conditional),
        "parameters": parameters or {},
    })


def build_test_path(
    target_analysis: str | None,
    suggestions: dict[str, Any],
    info: dict[str, Any],
    question: str = "",
) -> list[dict[str, Any]]:
    """Construye una ruta de pruebas válida usando únicamente funciones existentes."""
    steps: list[dict[str, Any]] = []
    target = target_analysis or "exploration"

    exploration_params = {
        "df_name": info.get("name", ""),
        "max_category_values": "12",
        "verbose": True,
    }
    _add_step(steps, "exploration", "Validar estructura y calidad antes de cualquier inferencia.", exploration_params)

    if target == "exploration":
        return steps

    if target in {"normality", "correlation", "mann_whitney", "kruskal", "kde"}:
        normality_params = suggestions.get("normality", {
            "df_name": info.get("name", ""),
            "numeric_cols": ", ".join(info.get("numeric_candidates", [])[:6]),
            "analysis_mode": "by_column",
            "value_mode": "both",
            "test_method": "both",
            "alpha": "0.05",
            "verbose": True,
        })
        _add_step(
            steps,
            "normality",
            "Diagnóstico de distribución para documentar supuestos y justificar el método final.",
            normality_params,
            conditional=(target not in {"normality"}),
        )

    if target == "dbscan":
        dim_params = suggestions.get("dimensionality", {
            "data_df_name": info.get("name", ""),
            "feature_cols": ", ".join(info.get("numeric_candidates", [])[:6]),
            "transform_method": "clr" if info.get("abundance_like") else "none",
            "scale": True,
            "embedding_method": "pca",
            "n_components": "3",
            "random_state": "42",
            "verbose": True,
        })
        _add_step(steps, "dimensionality", "Preparar y revisar el espacio de variables antes de DBSCAN.", dim_params)

    if target in TEST_CATALOG:
        _add_step(
            steps,
            target,
            "Prueba principal seleccionada para responder el objetivo indicado.",
            suggestions.get(target, {}),
        )

    if target == "dbscan":
        _add_step(
            steps,
            "cluster_review",
            "Validar la calidad de la solución de clusters antes de interpretarla.",
            {"df_name": info.get("name", "")},
        )

    return steps


def format_test_path(steps: list[dict[str, Any]]) -> str:
    if not steps:
        return "Ruta de pruebas: no definida."
    lines = ["Ruta de pruebas recomendada:"]
    for step in steps:
        marker = " (condicional)" if step.get("conditional") else ""
        lines.append(
            f"{step['order']}. {step['test']}{marker}\n"
            f"   Path: {step['path']}\n"
            f"   Motivo: {step['reason']}"
        )
    return "\n".join(lines)


def compact_result_evidence(manifest: dict[str, Any], table_notes: list[str]) -> dict[str, Any]:
    """Normaliza la evidencia que se envía al LLM para interpretar resultados."""
    return {
        "analysis": manifest.get("analysis", "resultado"),
        "parameters": manifest.get("parameters", {}) or {},
        "table_notes": list(table_notes or [])[:10],
        "table_count": len(manifest.get("tables", []) or []),
        "figure_count": len(manifest.get("figures", []) or []),
        "html_count": len(manifest.get("html", []) or []),
    }
