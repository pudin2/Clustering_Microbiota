"""Estadísticas que pueden mostrarse o vincularse a las visualizaciones."""

from __future__ import annotations

import math
from typing import Any

import numpy as np
import pandas as pd
from scipy import stats


def pair_statistics(df: pd.DataFrame, x: str, y: str) -> dict[str, float | int]:
    """Regresión lineal + correlaciones Pearson/Spearman para dos variables."""

    tmp = df[[x, y]].copy()
    tmp[x] = pd.to_numeric(tmp[x], errors="coerce")
    tmp[y] = pd.to_numeric(tmp[y], errors="coerce")
    tmp = tmp.dropna()
    if len(tmp) < 2 or tmp[x].nunique() < 2 or tmp[y].nunique() < 2:
        return {"n": int(len(tmp))}

    lr = stats.linregress(tmp[x].to_numpy(), tmp[y].to_numpy())
    pearson_r, pearson_p = stats.pearsonr(tmp[x], tmp[y])
    spearman_r, spearman_p = stats.spearmanr(tmp[x], tmp[y])
    return {
        "n": int(len(tmp)),
        "slope": float(lr.slope),
        "intercept": float(lr.intercept),
        "r_squared": float(lr.rvalue**2),
        "regression_p": float(lr.pvalue),
        "pearson_r": float(pearson_r),
        "pearson_p": float(pearson_p),
        "spearman_r": float(spearman_r),
        "spearman_p": float(spearman_p),
    }


def regression_line(df: pd.DataFrame, x: str, y: str, points: int = 100) -> pd.DataFrame:
    """Devuelve coordenadas de una recta de regresión para dibujarla."""

    tmp = df[[x, y]].apply(pd.to_numeric, errors="coerce").dropna()
    if len(tmp) < 2 or tmp[x].nunique() < 2:
        return pd.DataFrame(columns=[x, y])
    slope, intercept = np.polyfit(tmp[x].to_numpy(), tmp[y].to_numpy(), 1)
    xs = np.linspace(float(tmp[x].min()), float(tmp[x].max()), int(points))
    return pd.DataFrame({x: xs, y: slope * xs + intercept})


def centroid_summary(df: pd.DataFrame, x: str, y: str, group: str | None = None) -> pd.DataFrame:
    """Calcula centroides de X/Y de forma global o por grupo."""

    cols = [x, y] + ([group] if group else [])
    tmp = df[cols].copy()
    tmp[x] = pd.to_numeric(tmp[x], errors="coerce")
    tmp[y] = pd.to_numeric(tmp[y], errors="coerce")
    tmp = tmp.dropna(subset=[x, y])

    if group:
        result = (
            tmp.groupby(group, dropna=False)[[x, y]]
            .mean()
            .reset_index()
            .rename(columns={x: "centroid_x", y: "centroid_y"})
        )
        result["n"] = tmp.groupby(group, dropna=False).size().to_numpy()
        return result

    return pd.DataFrame(
        [{"centroid_x": tmp[x].mean(), "centroid_y": tmp[y].mean(), "n": len(tmp)}]
    )


def group_summary(df: pd.DataFrame, value: str, group: str | None = None) -> pd.DataFrame:
    """Resumen descriptivo para histogramas, boxplots y violines."""

    cols = [value] + ([group] if group else [])
    tmp = df[cols].copy()
    tmp[value] = pd.to_numeric(tmp[value], errors="coerce")
    tmp = tmp.dropna(subset=[value])

    def one(g: pd.DataFrame, label: Any) -> dict[str, Any]:
        s = g[value]
        return {
            "group": label,
            "n": int(s.count()),
            "mean": float(s.mean()),
            "median": float(s.median()),
            "std": float(s.std(ddof=1)) if s.count() > 1 else math.nan,
            "min": float(s.min()),
            "q1": float(s.quantile(0.25)),
            "q3": float(s.quantile(0.75)),
            "max": float(s.max()),
        }

    if group:
        return pd.DataFrame([one(g, label) for label, g in tmp.groupby(group, dropna=False)])
    return pd.DataFrame([one(tmp, "all")])


def group_significance(df: pd.DataFrame, value: str, group: str) -> dict[str, Any]:
    """Selecciona Mann-Whitney (2 grupos) o Kruskal-Wallis (>2)."""

    tmp = df[[value, group]].copy()
    tmp[value] = pd.to_numeric(tmp[value], errors="coerce")
    tmp = tmp.dropna(subset=[value, group])
    grouped = [(name, g[value].to_numpy()) for name, g in tmp.groupby(group) if len(g)]

    if len(grouped) < 2:
        return {"test": None, "groups": len(grouped), "n": int(len(tmp))}

    if len(grouped) == 2:
        stat, p = stats.mannwhitneyu(grouped[0][1], grouped[1][1], alternative="two-sided")
        return {
            "test": "mann_whitney",
            "statistic": float(stat),
            "p_value": float(p),
            "groups": [grouped[0][0], grouped[1][0]],
            "n": int(len(tmp)),
        }

    stat, p = stats.kruskal(*(values for _, values in grouped))
    return {
        "test": "kruskal_wallis",
        "statistic": float(stat),
        "p_value": float(p),
        "groups": [name for name, _ in grouped],
        "n": int(len(tmp)),
    }


def format_pair_annotation(values: dict[str, Any]) -> str:
    """Texto compacto para anotación dentro del gráfico."""

    if "r_squared" not in values:
        return f"n={values.get('n', 0)}"
    return (
        f"n={values['n']}\n"
        f"R²={values['r_squared']:.3f}\n"
        f"r={values['pearson_r']:.3f}\n"
        f"p={values['pearson_p']:.3g}"
    )
