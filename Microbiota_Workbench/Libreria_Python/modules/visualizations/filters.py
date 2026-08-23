"""Filtros reutilizables para visualizaciones interactivas."""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from typing import Any

import numpy as np
import pandas as pd

from .models import FilterSpec


def _is_categorical_like(series: pd.Series, max_unique: int = 30) -> bool:
    if pd.api.types.is_bool_dtype(series):
        return True
    if pd.api.types.is_categorical_dtype(series.dtype) or pd.api.types.is_object_dtype(series.dtype):
        return True
    nunique = series.nunique(dropna=True)
    return nunique <= max_unique and not pd.api.types.is_float_dtype(series)


def infer_filter_specs(
    df: pd.DataFrame,
    *,
    max_categories: int = 50,
    include_datetime: bool = True,
) -> list[FilterSpec]:
    """Infere filtros apropiados para cada columna.

    Numéricas -> rango min/max.
    Categóricas/booleanas -> lista de valores.
    Datetime -> rango representado como timestamps en metadata del filtro.
    """

    specs: list[FilterSpec] = []
    for col in df.columns:
        s = df[col]
        if pd.api.types.is_datetime64_any_dtype(s):
            if include_datetime and s.notna().any():
                specs.append(
                    FilterSpec(
                        column=col,
                        kind="datetime",
                        values=[s.min(), s.max()],
                        include_na=bool(s.isna().any()),
                    )
                )
            continue

        if pd.api.types.is_bool_dtype(s):
            specs.append(
                FilterSpec(
                    column=col,
                    kind="boolean",
                    values=list(pd.unique(s.dropna())),
                    include_na=bool(s.isna().any()),
                )
            )
            continue

        if pd.api.types.is_numeric_dtype(s) and not _is_categorical_like(s):
            numeric = pd.to_numeric(s, errors="coerce")
            if numeric.notna().any():
                specs.append(
                    FilterSpec(
                        column=col,
                        kind="numeric",
                        minimum=float(numeric.min()),
                        maximum=float(numeric.max()),
                        include_na=bool(numeric.isna().any()),
                    )
                )
            continue

        values = list(pd.unique(s.dropna()))
        if len(values) <= max_categories:
            try:
                values = sorted(values)
            except TypeError:
                pass
            specs.append(
                FilterSpec(
                    column=col,
                    kind="categorical",
                    values=values,
                    include_na=bool(s.isna().any()),
                )
            )
    return specs


def _mask_numeric(series: pd.Series, rule: Any) -> pd.Series:
    numeric = pd.to_numeric(series, errors="coerce")
    include_na = False

    if isinstance(rule, Mapping):
        lo = rule.get("min", rule.get("minimum"))
        hi = rule.get("max", rule.get("maximum"))
        include_na = bool(rule.get("include_na", False))
    elif isinstance(rule, Sequence) and not isinstance(rule, (str, bytes)) and len(rule) >= 2:
        lo, hi = rule[0], rule[1]
    else:
        raise ValueError("Un filtro numérico debe ser (min, max) o {'min': ..., 'max': ...}.")

    mask = pd.Series(True, index=series.index)
    if lo is not None:
        mask &= numeric >= float(lo)
    if hi is not None:
        mask &= numeric <= float(hi)
    if include_na:
        mask |= numeric.isna()
    return mask


def _mask_datetime(series: pd.Series, rule: Any) -> pd.Series:
    dt = pd.to_datetime(series, errors="coerce")
    include_na = False
    if isinstance(rule, Mapping):
        start = rule.get("start", rule.get("min"))
        end = rule.get("end", rule.get("max"))
        include_na = bool(rule.get("include_na", False))
    elif isinstance(rule, Sequence) and not isinstance(rule, (str, bytes)) and len(rule) >= 2:
        start, end = rule[0], rule[1]
    else:
        raise ValueError("Un filtro de fecha debe ser (inicio, fin) o un mapping.")

    mask = pd.Series(True, index=series.index)
    if start is not None:
        mask &= dt >= pd.Timestamp(start)
    if end is not None:
        mask &= dt <= pd.Timestamp(end)
    if include_na:
        mask |= dt.isna()
    return mask


def _mask_categorical(series: pd.Series, rule: Any) -> pd.Series:
    include_na = False
    if isinstance(rule, Mapping):
        values = rule.get("values", rule.get("selected", []))
        include_na = bool(rule.get("include_na", False))
    elif isinstance(rule, (list, tuple, set, frozenset, np.ndarray, pd.Index)):
        values = list(rule)
    else:
        values = [rule]

    mask = series.isin(values)
    if include_na:
        mask |= series.isna()
    return mask


def apply_filters(
    df: pd.DataFrame,
    filters: Mapping[str, Any] | None,
    *,
    copy: bool = True,
    keep_source_index: bool = True,
    source_index_col: str = "__source_index__",
) -> pd.DataFrame:
    """Aplica filtros de rango/categoría/fecha sin depender de la GUI.

    Ejemplos::

        {"age": (20, 50), "sex": ["F"]}
        {"age": {"min": 20, "max": 50}, "city": {"values": ["Bogotá"]}}
    """

    out = df.copy() if copy else df
    if keep_source_index and source_index_col not in out.columns:
        out[source_index_col] = out.index

    if not filters:
        return out

    mask = pd.Series(True, index=out.index)
    for col, rule in filters.items():
        if col not in out.columns:
            raise KeyError(f"La columna de filtro '{col}' no existe.")
        if rule is None:
            continue

        s = out[col]
        if callable(rule):
            col_mask = s.map(rule).fillna(False).astype(bool)
        elif pd.api.types.is_datetime64_any_dtype(s):
            col_mask = _mask_datetime(s, rule)
        elif pd.api.types.is_numeric_dtype(s) and (
            isinstance(rule, Mapping)
            and any(k in rule for k in ("min", "max", "minimum", "maximum"))
            or isinstance(rule, tuple)
            and len(rule) >= 2
        ):
            col_mask = _mask_numeric(s, rule)
        else:
            col_mask = _mask_categorical(s, rule)
        mask &= col_mask.reindex(out.index, fill_value=False)

    return out.loc[mask].copy()


def filter_positive(df: pd.DataFrame, columns: list[str]) -> pd.DataFrame:
    """Conserva filas con valores > 0 en todas las columnas indicadas."""

    if not columns:
        return df.copy()
    out = df.copy()
    mask = pd.Series(True, index=out.index)
    for col in columns:
        if col not in out.columns:
            raise KeyError(f"La columna '{col}' no existe.")
        mask &= pd.to_numeric(out[col], errors="coerce") > 0
    return out.loc[mask].copy()
