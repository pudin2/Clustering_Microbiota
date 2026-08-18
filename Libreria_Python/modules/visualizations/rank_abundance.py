"""Cálculo y visualización avanzada de curvas de rank-abundancia."""

from __future__ import annotations

from typing import Iterable

import matplotlib.pyplot as plt
import numpy as np
import pandas as pd

from .models import HTMLArtifact, PlotResult

try:  # Dependencia opcional; el módulo sigue funcionando sin Plotly.
    import plotly.graph_objects as go
except Exception:  # pragma: no cover
    go = None


def _normalize_cols(value: Iterable[str] | str | None) -> list[str] | None:
    if value is None:
        return None
    if isinstance(value, str):
        return [x.strip() for x in value.replace(";", ",").split(",") if x.strip()]
    return [str(x) for x in value]


def infer_abundance_columns(
    df: pd.DataFrame,
    *,
    id_col: str | None = None,
    group_col: str | None = None,
) -> list[str]:
    """Infere columnas numéricas candidatas a abundancia."""

    excluded = {c for c in (id_col, group_col) if c}
    return [c for c in df.select_dtypes(include=[np.number]).columns if c not in excluded]


def _one_rank(
    frame: pd.DataFrame,
    abundance_cols: list[str],
    top_n: int | None,
    group_value: object | None,
) -> pd.DataFrame:
    abundance = frame[abundance_cols].apply(pd.to_numeric, errors="coerce").fillna(0)
    totals = abundance.sum(axis=0).sort_values(ascending=False)
    totals = totals[totals > 0]
    if top_n is not None and int(top_n) > 0:
        totals = totals.head(int(top_n))
    if totals.empty:
        return pd.DataFrame(
            columns=[
                "rank",
                "feature",
                "abundance",
                "relative_abundance",
                "cumulative_abundance",
                "cumulative_percent",
                "log10_abundance",
                "group",
            ]
        )

    abundance_values = totals.to_numpy(dtype=float)
    total_sum = float(abundance_values.sum())
    relative = abundance_values / total_sum if total_sum else np.zeros_like(abundance_values)
    cumulative = np.cumsum(abundance_values)
    return pd.DataFrame(
        {
            "rank": np.arange(1, len(totals) + 1, dtype=int),
            "feature": totals.index.astype(str),
            "abundance": abundance_values,
            "relative_abundance": relative,
            "cumulative_abundance": cumulative,
            "cumulative_percent": np.cumsum(relative) * 100.0,
            "log10_abundance": np.log10(abundance_values),
            "group": group_value if group_value is not None else "all",
        }
    )


def calculate_rank_abundance(
    df: pd.DataFrame,
    abundance_cols: Iterable[str] | str | None = None,
    *,
    id_col: str | None = None,
    group_col: str | None = None,
    top_n: int | None = 2000,
    search: str | None = None,
) -> pd.DataFrame:
    """Calcula ranking global o uno independiente por grupo.

    ``search`` no altera el ranking; solo filtra el dataframe de salida para
    localizar features sin recalcular sus posiciones.
    """

    cols = _normalize_cols(abundance_cols)
    if cols is None:
        cols = infer_abundance_columns(df, id_col=id_col, group_col=group_col)
    if not cols:
        raise ValueError("No se encontraron columnas de abundancia.")

    missing = [c for c in cols if c not in df.columns]
    if missing:
        raise KeyError(f"Columnas de abundancia inexistentes: {missing}")
    if group_col and group_col not in df.columns:
        raise KeyError(f"La columna de agrupación '{group_col}' no existe.")

    if group_col:
        pieces = [
            _one_rank(group_df, cols, top_n, group_value)
            for group_value, group_df in df.groupby(group_col, dropna=False, sort=False)
        ]
        result = pd.concat(pieces, ignore_index=True) if pieces else pd.DataFrame()
    else:
        result = _one_rank(df, cols, top_n, None)

    if result.empty:
        raise ValueError("No hay abundancias positivas para rank-abundancia.")

    if search:
        term = str(search).strip()
        if term:
            result = result[result["feature"].str.contains(term, case=False, regex=False)].copy()
    return result


def rank_abundance_summary(rank_df: pd.DataFrame) -> pd.DataFrame:
    """Resumen por grupo útil para mostrar en log o en una tarjeta informativa."""

    rows = []
    for group, g in rank_df.groupby("group", dropna=False):
        rows.append(
            {
                "group": group,
                "features": int(len(g)),
                "total_abundance": float(g["abundance"].sum()),
                "top_feature": str(g.iloc[0]["feature"]) if len(g) else None,
                "top_abundance": float(g.iloc[0]["abundance"]) if len(g) else np.nan,
                "features_to_80pct": int((g["cumulative_percent"] < 80).sum() + 1) if len(g) else 0,
            }
        )
    return pd.DataFrame(rows)


def plot_rank_abundance(
    rank_df: pd.DataFrame,
    *,
    log_scale: bool = True,
    show_cumulative: bool = False,
    highlight_top: int = 10,
    title: str = "Rank-abundancia",
) -> tuple[plt.Figure, list[plt.Axes]]:
    """Construye la versión Matplotlib, incluida comparación por grupos."""

    fig, ax = plt.subplots(figsize=(9, 5.5))
    axes = [ax]
    groups = list(rank_df.groupby("group", dropna=False, sort=False))
    for group, g in groups:
        label = None if len(groups) == 1 and str(group) == "all" else str(group)
        ax.plot(g["rank"], g["abundance"], marker=".", linewidth=1.2, label=label)
        if highlight_top and int(highlight_top) > 0:
            top = g.head(int(highlight_top))
            ax.scatter(top["rank"], top["abundance"], s=28, zorder=3)

    if log_scale:
        ax.set_yscale("log")
    ax.set_xlabel("Rank")
    ax.set_ylabel("Abundancia")
    ax.set_title(title)
    ax.grid(True, alpha=0.25)
    if len(groups) > 1:
        ax.legend(title="Grupo")

    if show_cumulative:
        ax2 = ax.twinx()
        axes.append(ax2)
        for group, g in groups:
            label = None if len(groups) == 1 else f"{group} acumulado"
            ax2.plot(g["rank"], g["cumulative_percent"], linestyle="--", linewidth=1, label=label)
        ax2.set_ylabel("Abundancia acumulada (%)")
        ax2.set_ylim(0, 105)

    fig.tight_layout()
    return fig, axes


def plotly_rank_abundance(
    rank_df: pd.DataFrame,
    *,
    log_scale: bool = True,
    show_cumulative: bool = False,
    highlight_top: int = 10,
    title: str = "Rank-abundancia interactiva",
) -> HTMLArtifact | None:
    """HTML Plotly con hover, zoom, leyenda clicable y comparación de grupos."""

    if go is None:
        return None

    fig = go.Figure()
    groups = list(rank_df.groupby("group", dropna=False, sort=False))
    for group, g in groups:
        name = "Rank-abundancia" if len(groups) == 1 and str(group) == "all" else str(group)
        custom = np.column_stack(
            [
                g["feature"].astype(str),
                g["relative_abundance"].to_numpy() * 100.0,
                g["cumulative_percent"].to_numpy(),
            ]
        )
        fig.add_trace(
            go.Scatter(
                x=g["rank"],
                y=g["abundance"],
                mode="lines+markers",
                name=name,
                customdata=custom,
                hovertemplate=(
                    "Rank: %{x}<br>"
                    "Feature: %{customdata[0]}<br>"
                    "Abundancia: %{y:,.4g}<br>"
                    "Relativa: %{customdata[1]:.3f}%<br>"
                    "Acumulada: %{customdata[2]:.2f}%<extra></extra>"
                ),
            )
        )
        if highlight_top and int(highlight_top) > 0:
            top = g.head(int(highlight_top))
            fig.add_trace(
                go.Scatter(
                    x=top["rank"],
                    y=top["abundance"],
                    mode="markers",
                    name=f"Top {min(int(highlight_top), len(top))} - {name}",
                    text=top["feature"],
                    hovertemplate="Rank: %{x}<br>Feature: %{text}<br>Abundancia: %{y:,.4g}<extra></extra>",
                    showlegend=False,
                )
            )
        if show_cumulative:
            fig.add_trace(
                go.Scatter(
                    x=g["rank"],
                    y=g["cumulative_percent"],
                    mode="lines",
                    line={"dash": "dash"},
                    name=f"{name} acumulado",
                    yaxis="y2",
                    hovertemplate="Rank: %{x}<br>Acumulada: %{y:.2f}%<extra></extra>",
                )
            )

    layout = dict(
        title=title,
        xaxis_title="Rank",
        yaxis_title="Abundancia",
        hovermode="closest",
        legend_title="Grupo",
    )
    if log_scale:
        layout["yaxis"] = {"type": "log", "title": "Abundancia (log)"}
    if show_cumulative:
        layout["yaxis2"] = {
            "title": "Acumulada (%)",
            "overlaying": "y",
            "side": "right",
            "range": [0, 105],
        }
    fig.update_layout(**layout)
    html = fig.to_html(full_html=True, include_plotlyjs=True)
    return HTMLArtifact(title, html, filename="rank_abundance_interactive.html")


def build_rank_abundance(
    df: pd.DataFrame,
    abundance_cols: Iterable[str] | str | None = None,
    *,
    id_col: str | None = None,
    group_col: str | None = None,
    top_n: int | None = 2000,
    log_scale: bool = True,
    show_cumulative: bool = False,
    highlight_top: int = 10,
    search: str | None = None,
    interactive: bool = True,
    title: str = "Rank-abundancia",
) -> PlotResult:
    rank_df = calculate_rank_abundance(
        df,
        abundance_cols,
        id_col=id_col,
        group_col=group_col,
        top_n=top_n,
        search=search,
    )
    fig, axes = plot_rank_abundance(
        rank_df,
        log_scale=log_scale,
        show_cumulative=show_cumulative,
        highlight_top=highlight_top,
        title=title,
    )
    html = (
        plotly_rank_abundance(
            rank_df,
            log_scale=log_scale,
            show_cumulative=show_cumulative,
            highlight_top=highlight_top,
            title=f"{title} interactiva",
        )
        if interactive
        else None
    )
    return PlotResult(
        figure=fig,
        axes=axes,
        data=rank_df,
        stats=rank_abundance_summary(rank_df),
        interactive_html=html,
        metadata={"plot_type": "rank_abundance", "groups": rank_df["group"].nunique()},
    )
