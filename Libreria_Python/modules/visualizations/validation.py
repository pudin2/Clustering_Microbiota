"""Validación y ayuda contextual del constructor visual."""

from __future__ import annotations

from typing import Any

import pandas as pd

from .models import ValidationMessage, VisualizationConfig


HELP_TEXT: dict[str, str] = {
    "plot_type": "Automático elige el gráfico según los tipos de variables seleccionadas.",
    "x": "Variable principal del eje X. Para dispersión debe ser numérica.",
    "y": "Variable del eje Y. Para dispersión debe ser numérica; puede omitirse en histograma/barras.",
    "color": "Separa observaciones por color y habilita leyenda interactiva.",
    "facet": "Divide la visualización en paneles independientes por categoría.",
    "filters": "Restringe los datos visibles sin alterar el dataset original.",
    "opacity": "Transparencia de 0 a 1; valores menores ayudan cuando hay sobreposición.",
    "point_size": "Tamaño de puntos en dispersión y gráficos relacionados.",
    "top_n": "Cantidad máxima de features a mostrar en rank-abundancia.",
    "abundance_group_col": "Genera una curva de rank-abundancia independiente por grupo.",
}


def contextual_help(field: str) -> str:
    return HELP_TEXT.get(field, "Sin ayuda contextual disponible para este campo.")


def _exists(df: pd.DataFrame, col: str | None) -> bool:
    return bool(col) and col in df.columns


def validate_config(df: pd.DataFrame, config: VisualizationConfig) -> list[ValidationMessage]:
    messages: list[ValidationMessage] = []
    for field_name in ("x", "y", "color", "facet", "id_col"):
        col = getattr(config, field_name)
        if col and col not in df.columns:
            messages.append(ValidationMessage("error", field_name, f"La columna '{col}' no existe."))

    if not 0 <= float(config.opacity) <= 1:
        messages.append(ValidationMessage("error", "opacity", "La opacidad debe estar entre 0 y 1."))
    if float(config.point_size) <= 0:
        messages.append(ValidationMessage("error", "point_size", "El tamaño de puntos debe ser mayor que 0."))
    if config.max_facets < 1:
        messages.append(ValidationMessage("error", "facet", "max_facets debe ser mayor que 0."))

    plot_type = config.plot_type.lower().replace("-", "_")
    numeric_pair_types = {"scatter", "dispersion", "density", "densidad"}
    if plot_type in numeric_pair_types:
        if not (_exists(df, config.x) and _exists(df, config.y)):
            messages.append(ValidationMessage("error", None, "Este gráfico requiere X e Y."))
        else:
            if not pd.api.types.is_numeric_dtype(df[config.x]):
                messages.append(ValidationMessage("warning", "x", "X no es numérica; se intentará convertir."))
            if not pd.api.types.is_numeric_dtype(df[config.y]):
                messages.append(ValidationMessage("warning", "y", "Y no es numérica; se intentará convertir."))

    if config.log_x and config.x and config.x in df.columns:
        s = pd.to_numeric(df[config.x], errors="coerce")
        if (s <= 0).any():
            messages.append(ValidationMessage("warning", "log_x", "Los valores X <= 0 serán excluidos."))
    if config.log_y and config.y and config.y in df.columns:
        s = pd.to_numeric(df[config.y], errors="coerce")
        if (s <= 0).any():
            messages.append(ValidationMessage("warning", "log_y", "Los valores Y <= 0 serán excluidos."))

    if plot_type in {"rank_abundance", "rank", "rango_abundancia"} and not config.abundance_cols:
        messages.append(
            ValidationMessage(
                "info",
                "abundance_cols",
                "No se especificaron columnas; se inferirán las columnas numéricas.",
            )
        )
    return messages
