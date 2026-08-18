"""Constructor de visualizaciones desacoplado de la interfaz gráfica."""

from __future__ import annotations

import math
from typing import Any

import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
import seaborn as sns

from .filters import apply_filters, filter_positive
from .models import HTMLArtifact, PlotResult, VisualizationConfig
from .rank_abundance import build_rank_abundance
from .statistics import (
    centroid_summary,
    format_pair_annotation,
    group_significance,
    group_summary,
    pair_statistics,
    regression_line,
)
from .validation import validate_config

try:
    import plotly.express as px
except Exception:  # pragma: no cover
    px = None


PLOT_ALIASES = {
    "automatico": "auto",
    "automático": "auto",
    "dispersion": "scatter",
    "dispersión": "scatter",
    "linea": "line",
    "línea": "line",
    "barras": "bar",
    "histograma": "histogram",
    "violín": "violin",
    "violin": "violin",
    "densidad": "density",
    "mapa_calor": "heatmap",
    "rango_abundancia": "rank_abundance",
    "rank-abundance": "rank_abundance",
    "rank_abundance": "rank_abundance",
}


def normalize_plot_type(value: str | None) -> str:
    key = str(value or "auto").strip().lower().replace(" ", "_")
    return PLOT_ALIASES.get(key, key)


def auto_select_plot_type(df: pd.DataFrame, config: VisualizationConfig) -> str:
    """Elige gráfico según variables y tipos de datos."""

    x, y = config.x, config.y
    if config.abundance_cols and not x and not y:
        return "rank_abundance"
    if x and y:
        x_num = pd.api.types.is_numeric_dtype(df[x]) if x in df.columns else False
        y_num = pd.api.types.is_numeric_dtype(df[y]) if y in df.columns else False
        if x_num and y_num:
            return "scatter"
        if x_num != y_num:
            return "boxplot"
        return "bar"
    if x:
        return "histogram" if pd.api.types.is_numeric_dtype(df[x]) else "bar"
    if config.heatmap_cols or len(df.select_dtypes(include=[np.number]).columns) >= 2:
        return "heatmap"
    raise ValueError("No hay suficientes variables para seleccionar automáticamente una visualización.")


def _coerce_config(config: VisualizationConfig | dict[str, Any] | None, **kwargs: Any) -> VisualizationConfig:
    if isinstance(config, VisualizationConfig):
        cfg = VisualizationConfig.from_mapping(config.to_dict())
    elif isinstance(config, dict):
        cfg = VisualizationConfig.from_mapping(config)
    else:
        cfg = VisualizationConfig()
    for key, value in kwargs.items():
        if key in cfg.__dataclass_fields__:
            setattr(cfg, key, value)
    return cfg


def prepare_visual_data(df: pd.DataFrame, config: VisualizationConfig) -> pd.DataFrame:
    """Aplica filtros, conserva índice de origen y limpia variables requeridas."""

    out = apply_filters(df, config.filters, keep_source_index=True)
    cols_to_numeric: list[str] = []
    plot_type = normalize_plot_type(config.plot_type)
    if plot_type in {"scatter", "line", "density"} or (plot_type == "auto" and config.x and config.y):
        cols_to_numeric = [c for c in (config.x, config.y) if c]
    elif plot_type == "histogram" and config.x:
        cols_to_numeric = [config.x]
    for col in cols_to_numeric:
        if col in out.columns:
            out[col] = pd.to_numeric(out[col], errors="coerce")
    if cols_to_numeric:
        out = out.dropna(subset=cols_to_numeric)
    if config.log_x and config.x:
        out = filter_positive(out, [config.x])
    if config.log_y and config.y:
        out = filter_positive(out, [config.y])
    return out


def _set_artist_indices(artist: Any, frame: pd.DataFrame) -> None:
    source = frame["__source_index__"].to_numpy() if "__source_index__" in frame.columns else frame.index.to_numpy()
    try:
        artist._visual_row_indices = source
    except Exception:
        pass


def _draw_scatter(ax: Any, frame: pd.DataFrame, cfg: VisualizationConfig) -> dict[str, Any]:
    if not cfg.x or not cfg.y:
        raise ValueError("Dispersión requiere X e Y.")
    stats_out: dict[str, Any] = {}

    groups = [(None, frame)]
    if cfg.color and cfg.color in frame.columns:
        groups = list(frame.groupby(cfg.color, dropna=False, sort=False))

    for label, g in groups:
        scatter = ax.scatter(
            g[cfg.x],
            g[cfg.y],
            s=float(cfg.point_size),
            alpha=float(cfg.opacity),
            label=str(label) if label is not None else None,
            picker=True,
        )
        _set_artist_indices(scatter, g)
        if cfg.trend and len(g) >= 2 and g[cfg.x].nunique() >= 2:
            line = regression_line(g, cfg.x, cfg.y)
            if len(line):
                ax.plot(line[cfg.x], line[cfg.y], linestyle="--", linewidth=1.5)
        if cfg.show_stats:
            stats_out[str(label) if label is not None else "all"] = pair_statistics(g, cfg.x, cfg.y)

    if cfg.density and len(frame) > 2:
        ax.hexbin(frame[cfg.x], frame[cfg.y], gridsize=28, mincnt=1, alpha=min(0.55, cfg.opacity))

    if cfg.centroids:
        centroids = centroid_summary(frame, cfg.x, cfg.y, cfg.color if cfg.color in frame.columns else None)
        for _, row in centroids.iterrows():
            label = row[cfg.color] if cfg.color and cfg.color in row.index else None
            ax.scatter(row["centroid_x"], row["centroid_y"], marker="X", s=max(90, cfg.point_size * 2.2), label=f"Centroide {label}" if label is not None else "Centroide")

    if cfg.color and cfg.color in frame.columns:
        ax.legend(title=cfg.color)
    ax.set_xlabel(cfg.x)
    ax.set_ylabel(cfg.y)
    return stats_out


def _draw_line(ax: Any, frame: pd.DataFrame, cfg: VisualizationConfig) -> dict[str, Any]:
    if not cfg.x or not cfg.y:
        raise ValueError("Línea requiere X e Y.")
    groups = [(None, frame)] if not cfg.color else list(frame.groupby(cfg.color, dropna=False, sort=False))
    stats_out = {}
    for label, g in groups:
        g = g.sort_values(cfg.x)
        ax.plot(g[cfg.x], g[cfg.y], marker="o" if cfg.points else None, alpha=cfg.opacity, label=str(label) if label is not None else None)
        if cfg.show_stats:
            stats_out[str(label) if label is not None else "all"] = pair_statistics(g, cfg.x, cfg.y)
    if cfg.color:
        ax.legend(title=cfg.color)
    ax.set_xlabel(cfg.x)
    ax.set_ylabel(cfg.y)
    return stats_out


def _draw_bar(ax: Any, frame: pd.DataFrame, cfg: VisualizationConfig) -> dict[str, Any]:
    if not cfg.x:
        raise ValueError("Barras requiere X.")
    if cfg.y:
        tmp = frame[[cfg.x, cfg.y] + ([cfg.color] if cfg.color and cfg.color != cfg.x else [])].copy()
        tmp[cfg.y] = pd.to_numeric(tmp[cfg.y], errors="coerce")
        tmp = tmp.dropna(subset=[cfg.y])
        if cfg.color and cfg.color != cfg.x:
            agg = tmp.groupby([cfg.x, cfg.color], dropna=False)[cfg.y].mean().reset_index()
            sns.barplot(data=agg, x=cfg.x, y=cfg.y, hue=cfg.color, ax=ax)
        else:
            agg = tmp.groupby(cfg.x, dropna=False)[cfg.y].mean().reset_index()
            sns.barplot(data=agg, x=cfg.x, y=cfg.y, ax=ax)
        ax.set_ylabel(f"Media de {cfg.y}")
    else:
        counts = frame[cfg.x].value_counts(dropna=False).rename_axis(cfg.x).reset_index(name="count")
        sns.barplot(data=counts, x=cfg.x, y="count", ax=ax)
        ax.set_ylabel("Conteo")
    ax.tick_params(axis="x", rotation=30)
    return {}


def _draw_histogram(ax: Any, frame: pd.DataFrame, cfg: VisualizationConfig) -> dict[str, Any]:
    if not cfg.x:
        raise ValueError("Histograma requiere X.")
    tmp = frame.copy()
    tmp[cfg.x] = pd.to_numeric(tmp[cfg.x], errors="coerce")
    tmp = tmp.dropna(subset=[cfg.x])
    sns.histplot(data=tmp, x=cfg.x, hue=cfg.color if cfg.color in tmp.columns else None, bins=int(cfg.bins), kde=True, ax=ax, alpha=cfg.opacity)
    return {"summary": group_summary(tmp, cfg.x, cfg.color if cfg.color in tmp.columns else None)} if cfg.show_stats else {}


def _categorical_numeric_axes(frame: pd.DataFrame, cfg: VisualizationConfig) -> tuple[str, str]:
    if not cfg.x or not cfg.y:
        raise ValueError("Boxplot/violín requiere X e Y.")
    x_num = pd.api.types.is_numeric_dtype(frame[cfg.x])
    y_num = pd.api.types.is_numeric_dtype(frame[cfg.y])
    if x_num and not y_num:
        return cfg.y, cfg.x
    return cfg.x, cfg.y


def _draw_box_or_violin(ax: Any, frame: pd.DataFrame, cfg: VisualizationConfig, kind: str) -> dict[str, Any]:
    cat, value = _categorical_numeric_axes(frame, cfg)
    tmp = frame.copy()
    tmp[value] = pd.to_numeric(tmp[value], errors="coerce")
    tmp = tmp.dropna(subset=[value])
    hue = cfg.color if cfg.color and cfg.color != cat and cfg.color in tmp.columns else None
    if kind == "violin":
        sns.violinplot(data=tmp, x=cat, y=value, hue=hue, inner="quartile", cut=0, ax=ax)
    else:
        sns.boxplot(data=tmp, x=cat, y=value, hue=hue, ax=ax)
    ax.tick_params(axis="x", rotation=30)
    stats_out: dict[str, Any] = {}
    if cfg.show_stats:
        stats_out["summary"] = group_summary(tmp, value, cat)
        if tmp[cat].nunique(dropna=True) >= 2:
            stats_out["significance"] = group_significance(tmp, value, cat)
    return stats_out


def _draw_density(ax: Any, frame: pd.DataFrame, cfg: VisualizationConfig) -> dict[str, Any]:
    if cfg.x and cfg.y:
        hb = ax.hexbin(frame[cfg.x], frame[cfg.y], gridsize=32, mincnt=1)
        ax.figure.colorbar(hb, ax=ax, label="Densidad")
        ax.set_xlabel(cfg.x)
        ax.set_ylabel(cfg.y)
    elif cfg.x:
        sns.kdeplot(data=frame, x=cfg.x, hue=cfg.color if cfg.color in frame.columns else None, fill=True, ax=ax)
    else:
        raise ValueError("Densidad requiere X o X/Y.")
    return {}


def _draw_heatmap(ax: Any, frame: pd.DataFrame, cfg: VisualizationConfig) -> dict[str, Any]:
    cols = [c for c in cfg.heatmap_cols if c in frame.columns] if cfg.heatmap_cols else list(frame.select_dtypes(include=[np.number]).columns)
    if len(cols) < 2:
        raise ValueError("Heatmap requiere al menos dos columnas numéricas.")
    corr = frame[cols].corr(numeric_only=True)
    sns.heatmap(corr, annot=len(cols) <= 10, cmap="vlag", center=0, ax=ax)
    return {"correlation_matrix": corr}


def _build_plotly(frame: pd.DataFrame, cfg: VisualizationConfig, plot_type: str) -> HTMLArtifact | None:
    if px is None or not cfg.interactive:
        return None
    hover_cols = [c for c in cfg.hover_cols if c in frame.columns]
    if cfg.id_col and cfg.id_col in frame.columns and cfg.id_col not in hover_cols:
        hover_cols.insert(0, cfg.id_col)
    kwargs = {"hover_data": hover_cols or None, "title": cfg.title}
    fig = None
    if plot_type == "scatter":
        fig = px.scatter(frame, x=cfg.x, y=cfg.y, color=cfg.color if cfg.color in frame.columns else None, facet_col=cfg.facet if cfg.facet in frame.columns else None, **kwargs)
        if cfg.trend:
            try:
                fig = px.scatter(frame, x=cfg.x, y=cfg.y, color=cfg.color if cfg.color in frame.columns else None, facet_col=cfg.facet if cfg.facet in frame.columns else None, trendline="ols", **kwargs)
            except Exception:
                pass
    elif plot_type == "line":
        fig = px.line(frame.sort_values(cfg.x), x=cfg.x, y=cfg.y, color=cfg.color if cfg.color in frame.columns else None, facet_col=cfg.facet if cfg.facet in frame.columns else None, markers=cfg.points, **kwargs)
    elif plot_type == "bar":
        if cfg.y:
            fig = px.bar(frame, x=cfg.x, y=cfg.y, color=cfg.color if cfg.color in frame.columns else None, facet_col=cfg.facet if cfg.facet in frame.columns else None, **kwargs)
        else:
            counts = frame[cfg.x].value_counts(dropna=False).rename_axis(cfg.x).reset_index(name="count")
            fig = px.bar(counts, x=cfg.x, y="count", title=cfg.title)
    elif plot_type == "histogram":
        fig = px.histogram(frame, x=cfg.x, color=cfg.color if cfg.color in frame.columns else None, facet_col=cfg.facet if cfg.facet in frame.columns else None, nbins=cfg.bins, **kwargs)
    elif plot_type == "boxplot":
        cat, value = _categorical_numeric_axes(frame, cfg)
        fig = px.box(frame, x=cat, y=value, color=cfg.color if cfg.color in frame.columns and cfg.color != cat else None, points="outliers", **kwargs)
    elif plot_type == "violin":
        cat, value = _categorical_numeric_axes(frame, cfg)
        fig = px.violin(frame, x=cat, y=value, color=cfg.color if cfg.color in frame.columns and cfg.color != cat else None, box=True, points="outliers", **kwargs)
    elif plot_type == "density" and cfg.x and cfg.y:
        fig = px.density_heatmap(frame, x=cfg.x, y=cfg.y, facet_col=cfg.facet if cfg.facet in frame.columns else None, **kwargs)
    elif plot_type == "heatmap":
        cols = [c for c in cfg.heatmap_cols if c in frame.columns] if cfg.heatmap_cols else list(frame.select_dtypes(include=[np.number]).columns)
        corr = frame[cols].corr(numeric_only=True)
        fig = px.imshow(corr, text_auto=len(cols) <= 10, aspect="auto", title=cfg.title or "Mapa de correlaciones")

    if fig is None:
        return None
    if cfg.log_x:
        fig.update_xaxes(type="log")
    if cfg.log_y:
        fig.update_yaxes(type="log")
    fig.update_layout(hovermode="closest")
    html = fig.to_html(full_html=True, include_plotlyjs=True)
    return HTMLArtifact(cfg.title or f"{plot_type} interactivo", html, filename=f"{plot_type}_interactive.html")


def _facet_values(frame: pd.DataFrame, cfg: VisualizationConfig) -> list[tuple[str | None, pd.DataFrame]]:
    if cfg.facet and cfg.facet in frame.columns:
        values = list(frame.groupby(cfg.facet, dropna=False, sort=False))[: int(cfg.max_facets)]
        return [(str(v), g) for v, g in values]
    return [(None, frame)]


def build_visualization(
    df: pd.DataFrame,
    config: VisualizationConfig | dict[str, Any] | None = None,
    **kwargs: Any,
) -> PlotResult:
    """Punto de entrada principal del constructor visual.

    Devuelve figura Matplotlib, datos visibles, estadísticas, HTML Plotly y
    metadata. La GUI decide cómo presentar/actualizar esos artefactos.
    """

    cfg = _coerce_config(config, **kwargs)
    messages = validate_config(df, cfg)
    errors = [m.message for m in messages if m.level == "error"]
    if errors:
        raise ValueError("; ".join(errors))

    frame = prepare_visual_data(df, cfg)
    plot_type = normalize_plot_type(cfg.plot_type)
    if plot_type == "auto":
        plot_type = auto_select_plot_type(frame, cfg)

    if plot_type == "rank_abundance":
        result = build_rank_abundance(
            frame,
            cfg.abundance_cols or None,
            id_col=cfg.abundance_id_col or cfg.id_col,
            group_col=cfg.abundance_group_col,
            top_n=cfg.top_n,
            log_scale=cfg.rank_log_scale,
            show_cumulative=cfg.rank_show_cumulative,
            highlight_top=cfg.rank_highlight_top,
            search=cfg.rank_search,
            interactive=cfg.interactive,
            title=cfg.title or "Rank-abundancia",
        )
        result.metadata.update({"config": cfg.to_dict(), "validation": [{"level": m.level, "field": m.field, "message": m.message} for m in messages]})
        return result

    facets = _facet_values(frame, cfg)
    n = len(facets)
    cols = min(3, n)
    rows = math.ceil(n / cols)
    fig, axes_array = plt.subplots(rows, cols, figsize=(6.2 * cols, 4.7 * rows), squeeze=False)
    flat_axes = list(axes_array.ravel())
    stats_out: dict[str, Any] = {}

    draw_map = {
        "scatter": _draw_scatter,
        "line": _draw_line,
        "bar": _draw_bar,
        "histogram": _draw_histogram,
        "boxplot": lambda ax, f, c: _draw_box_or_violin(ax, f, c, "boxplot"),
        "violin": lambda ax, f, c: _draw_box_or_violin(ax, f, c, "violin"),
        "density": _draw_density,
        "heatmap": _draw_heatmap,
    }
    if plot_type not in draw_map:
        raise ValueError(f"Tipo de gráfico no soportado: {plot_type}")

    for ax, (facet_value, facet_df) in zip(flat_axes, facets):
        piece_stats = draw_map[plot_type](ax, facet_df, cfg)
        key = facet_value if facet_value is not None else "all"
        stats_out[key] = piece_stats
        title = cfg.title or plot_type.replace("_", " ").title()
        if facet_value is not None:
            title = f"{title} | {cfg.facet}={facet_value}"
        ax.set_title(title)
        ax.grid(True, alpha=0.18)
        if cfg.log_x:
            ax.set_xscale("log")
        if cfg.log_y:
            ax.set_yscale("log")

    for ax in flat_axes[n:]:
        ax.set_visible(False)
    fig.tight_layout()

    html = _build_plotly(frame, cfg, plot_type)
    metadata = {
        "plot_type": plot_type,
        "rows_visible": int(len(frame)),
        "facets": [v for v, _ in facets if v is not None],
        "config": cfg.to_dict(),
        "validation": [{"level": m.level, "field": m.field, "message": m.message} for m in messages],
    }
    return PlotResult(
        figure=fig,
        axes=[ax for ax in flat_axes[:n] if ax.get_visible()],
        data=frame,
        stats=stats_out,
        interactive_html=html,
        metadata=metadata,
    )
