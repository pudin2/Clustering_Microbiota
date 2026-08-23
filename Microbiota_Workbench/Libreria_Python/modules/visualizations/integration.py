"""Puentes entre selección visual y otros módulos estadísticos."""

from __future__ import annotations

from typing import Any, Iterable

import numpy as np
import pandas as pd


def dataset_from_selection(
    df: pd.DataFrame,
    selected_indices: Iterable[Any],
    *,
    source_index_col: str = "__source_index__",
    reset_index: bool = True,
) -> pd.DataFrame:
    """Crea un dataset a partir de índices seleccionados en la visualización."""

    ids = list(selected_indices)
    if source_index_col in df.columns:
        out = df[df[source_index_col].isin(ids)].copy()
    else:
        out = df.loc[df.index.intersection(ids)].copy()
    return out.reset_index(drop=True) if reset_index else out


def suggest_analysis_routes(
    df: pd.DataFrame,
    *,
    value_col: str | None = None,
    group_col: str | None = None,
    numeric_cols: list[str] | None = None,
) -> list[dict[str, Any]]:
    """Sugiere qué módulo estadístico puede recibir la selección actual."""

    suggestions: list[dict[str, Any]] = []
    if value_col and group_col and value_col in df.columns and group_col in df.columns:
        groups = int(df[group_col].dropna().nunique())
        if groups == 2:
            suggestions.append(
                {
                    "module": "mann_whitney",
                    "label": "Comparar los dos grupos con Mann-Whitney",
                    "params": {"value_col": value_col, "group_col": group_col},
                }
            )
        elif groups > 2:
            suggestions.append(
                {
                    "module": "kruskal_wallis",
                    "label": "Comparar los grupos con Kruskal-Wallis",
                    "params": {"value_col": value_col, "group_col": group_col},
                }
            )

    numeric_cols = numeric_cols or list(df.select_dtypes(include=[np.number]).columns)
    if len(numeric_cols) >= 2:
        suggestions.append(
            {
                "module": "dbscan",
                "label": "Explorar clustering DBSCAN con la selección",
                "params": {"columns": numeric_cols[: min(8, len(numeric_cols))]},
            }
        )
    return suggestions
