"""API compatible con la versión anterior del módulo Visualizaciones.

La implementación pesada vive ahora en archivos especializados. Esta función
se conserva para que la GUI actual siga pudiendo llamar
``visualization_from_loaded`` mientras migramos el constructor visual.
"""

from __future__ import annotations

import matplotlib.pyplot as plt
import pandas as pd

from .builder import build_visualization
from .models import HTMLArtifact, VisualizationConfig
from .rank_abundance import build_rank_abundance
from .statistics import group_summary


def _as_list(value):
    if value is None:
        return None
    if isinstance(value, str):
        items = [item.strip() for item in value.replace(";", ",").split(",")]
        return [item for item in items if item] or None
    return list(value)


def _get_df(dfs, df_name):
    if df_name not in dfs:
        raise KeyError(f"No existe '{df_name}' en dfs. Disponibles: {list(dfs.keys())}")
    return dfs[df_name].copy()


def visualization_from_loaded(
    dfs,
    df_name,
    x_col=None,
    y_col=None,
    hue_col=None,
    group_col=None,
    violin_cols=None,
    rank_abundance=False,
    abundance_cols=None,
    abundance_id_col="ID",
    top_n=2000,
    log_scale=True,
    verbose=True,
):
    """Compatibilidad con la API original, delegando a la arquitectura V2."""

    df = _get_df(dfs, df_name)
    output = {}

    if x_col and y_col:
        result = build_visualization(
            df,
            VisualizationConfig(
                plot_type="scatter",
                x=x_col,
                y=y_col,
                color=hue_col if hue_col in df.columns else None,
                interactive=True,
                title=f"Variables conjuntas: {x_col} vs {y_col}",
            ),
        )
        result.figure.show()
        output["joint_plot_data"] = result.data
        if result.interactive_html is not None:
            output["joint_plot_interactive"] = result.interactive_html

    violin_cols = _as_list(violin_cols)
    if violin_cols:
        missing = [c for c in violin_cols if c not in df.columns]
        if missing:
            raise KeyError(f"Estas columnas no existen para violin: {missing}")
        if group_col and group_col not in df.columns:
            raise KeyError(f"La columna de grupo '{group_col}' no existe en '{df_name}'")

        summaries = []
        for col in violin_cols:
            if group_col:
                cfg = VisualizationConfig(plot_type="violin", x=group_col, y=col, color=None, show_stats=True, interactive=True, title=f"Gráfico de violín: {col}")
            else:
                # Sin grupo se usa histograma como vista general, pero se conserva
                # el resumen descriptivo esperado por la API antigua.
                cfg = VisualizationConfig(plot_type="histogram", x=col, show_stats=True, interactive=True, title=f"Distribución: {col}")
            result = build_visualization(df, cfg)
            result.figure.show()
            summaries.append(group_summary(result.data, col, group_col if group_col else None).assign(variable=col))
        output["violin_summary"] = pd.concat(summaries, ignore_index=True) if summaries else pd.DataFrame()

    if rank_abundance:
        result = build_rank_abundance(
            df,
            abundance_cols,
            id_col=abundance_id_col,
            top_n=top_n,
            log_scale=log_scale,
            interactive=True,
        )
        result.figure.show()
        output["rank_abundance"] = result.data
        output["rank_abundance_summary"] = result.stats
        if result.interactive_html is not None:
            output["rank_abundance_interactive"] = result.interactive_html

    if verbose:
        pieces = list(output.keys())
        print(f"Visualizaciones generadas para {df_name}: {', '.join(pieces) if pieces else 'ninguna'}")
    return output


__all__ = ["HTMLArtifact", "visualization_from_loaded"]
