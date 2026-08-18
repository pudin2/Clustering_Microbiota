"""Modelos de datos compartidos por el módulo de visualizaciones.

Estos objetos mantienen la lógica de visualización desacoplada de Tkinter,
Qt, notebooks o una futura interfaz web.
"""

from __future__ import annotations

from dataclasses import asdict, dataclass, field
from typing import Any, Callable, Iterable, Mapping, Sequence


@dataclass(slots=True)
class HTMLArtifact:
    """Artefacto HTML portable para gráficos interactivos (p. ej. Plotly)."""

    title: str
    html: str
    filename: str | None = None
    artifact_kind: str = field(default="html", init=False)


@dataclass(slots=True)
class FilterSpec:
    """Descripción de un filtro sugerido para una columna."""

    column: str
    kind: str  # numeric | categorical | datetime | boolean
    minimum: float | None = None
    maximum: float | None = None
    values: list[Any] = field(default_factory=list)
    include_na: bool = False


@dataclass(slots=True)
class VisualizationConfig:
    """Configuración unificada del constructor visual.

    Los nombres de campos son deliberadamente neutrales para que la GUI pueda
    mapear sus widgets sin acoplarse a Matplotlib/Plotly.
    """

    plot_type: str = "auto"
    x: str | None = None
    y: str | None = None
    color: str | None = None
    facet: str | None = None
    id_col: str | None = None
    hover_cols: list[str] = field(default_factory=list)
    filters: dict[str, Any] = field(default_factory=dict)

    points: bool = True
    line: bool = False
    trend: bool = False
    density: bool = False
    centroids: bool = False
    show_stats: bool = False

    log_x: bool = False
    log_y: bool = False
    opacity: float = 0.75
    point_size: float = 34.0
    bins: int = 30
    max_facets: int = 12

    # Heatmap
    heatmap_cols: list[str] = field(default_factory=list)

    # Rank-abundancia
    abundance_cols: list[str] = field(default_factory=list)
    abundance_id_col: str | None = None
    abundance_group_col: str | None = None
    top_n: int | None = 2000
    rank_log_scale: bool = True
    rank_show_cumulative: bool = False
    rank_highlight_top: int = 10
    rank_search: str | None = None

    title: str | None = None
    interactive: bool = True

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)

    @classmethod
    def from_mapping(cls, values: Mapping[str, Any]) -> "VisualizationConfig":
        allowed = cls.__dataclass_fields__.keys()
        clean = {k: v for k, v in values.items() if k in allowed}
        return cls(**clean)


@dataclass
class PlotResult:
    """Resultado estándar de cualquier visualización."""

    figure: Any | None = None
    axes: list[Any] = field(default_factory=list)
    data: Any | None = None
    stats: Any | None = None
    interactive_html: HTMLArtifact | None = None
    metadata: dict[str, Any] = field(default_factory=dict)
    selected_indices: list[Any] = field(default_factory=list)


@dataclass(slots=True)
class Recommendation:
    """Recomendación de visualización derivada del esquema/contenido del dataset."""

    title: str
    reason: str
    config: dict[str, Any]
    priority: int = 100


@dataclass(slots=True)
class ValidationMessage:
    level: str  # info | warning | error
    field: str | None
    message: str


SelectionCallback = Callable[[list[Any], Any], None]
RecordCallback = Callable[[Any, Any], None]
