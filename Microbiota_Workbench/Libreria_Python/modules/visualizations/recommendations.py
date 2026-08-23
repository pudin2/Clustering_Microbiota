"""Recomendador automático de visualizaciones."""

from __future__ import annotations

import itertools

import numpy as np
import pandas as pd

from .models import Recommendation


def _numeric_columns(df: pd.DataFrame) -> list[str]:
    return list(df.select_dtypes(include=[np.number]).columns)


def _categorical_columns(df: pd.DataFrame, max_unique: int = 20) -> list[str]:
    cols = []
    for col in df.columns:
        s = df[col]
        if pd.api.types.is_object_dtype(s) or pd.api.types.is_categorical_dtype(s.dtype) or pd.api.types.is_bool_dtype(s):
            if s.nunique(dropna=True) <= max_unique:
                cols.append(col)
    return cols


def recommend_visualizations(df: pd.DataFrame, *, max_results: int = 8) -> list[Recommendation]:
    """Propone gráficos útiles sin usar IA externa.

    Prioriza distribuciones, comparaciones por grupos y pares numéricos con
    correlaciones absolutas altas.
    """

    numeric = _numeric_columns(df)
    categorical = _categorical_columns(df)
    recs: list[Recommendation] = []

    for col in numeric[:3]:
        recs.append(
            Recommendation(
                title=f"Distribución de {col}",
                reason="Variable numérica: un histograma permite detectar forma, asimetría y valores extremos.",
                config={"plot_type": "histogram", "x": col, "show_stats": True},
                priority=30,
            )
        )

    if numeric and categorical:
        for value, group in itertools.islice(itertools.product(numeric, categorical), 3):
            recs.append(
                Recommendation(
                    title=f"{value} por {group}",
                    reason="Combina una variable numérica y una categórica para comparar distribuciones entre grupos.",
                    config={"plot_type": "boxplot", "x": group, "y": value, "color": group, "show_stats": True},
                    priority=20,
                )
            )

    if len(numeric) >= 2:
        corr = df[numeric].corr(numeric_only=True).abs()
        pairs: list[tuple[float, str, str]] = []
        for i, x in enumerate(numeric):
            for y in numeric[i + 1 :]:
                value = corr.loc[x, y]
                if pd.notna(value):
                    pairs.append((float(value), x, y))
        for value, x, y in sorted(pairs, reverse=True)[:3]:
            recs.append(
                Recommendation(
                    title=f"{x} vs {y}",
                    reason=f"Relación numérica con |r|≈{value:.2f}; conviene explorarla con dispersión y tendencia.",
                    config={"plot_type": "scatter", "x": x, "y": y, "trend": True, "show_stats": True},
                    priority=10,
                )
            )

        if len(numeric) >= 3:
            recs.append(
                Recommendation(
                    title="Mapa de correlaciones",
                    reason="Hay varias variables numéricas; un heatmap ayuda a detectar relaciones globales.",
                    config={"plot_type": "heatmap", "heatmap_cols": numeric[:12]},
                    priority=15,
                )
            )

    recs.sort(key=lambda r: r.priority)
    return recs[: int(max_results)]
