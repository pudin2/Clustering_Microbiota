"""API pública del módulo de visualizaciones V2."""

from .builder import auto_select_plot_type, build_visualization, prepare_visual_data
from .export import export_dataframe, export_figure, export_html, export_plot_result
from .filters import apply_filters, filter_positive, infer_filter_specs
from .integration import dataset_from_selection, suggest_analysis_routes
from .interaction import InteractiveController
from .models import (
    FilterSpec,
    HTMLArtifact,
    PlotResult,
    Recommendation,
    ValidationMessage,
    VisualizationConfig,
)
from .rank_abundance import (
    build_rank_abundance,
    calculate_rank_abundance,
    infer_abundance_columns,
    plot_rank_abundance,
    plotly_rank_abundance,
    rank_abundance_summary,
)
from .recommendations import recommend_visualizations
from .state import Debouncer, PresetStore, ViewHistory
from .statistics import (
    centroid_summary,
    group_significance,
    group_summary,
    pair_statistics,
    regression_line,
)
from .validation import HELP_TEXT, contextual_help, validate_config
from .visualizations import visualization_from_loaded

__all__ = [
    "HTMLArtifact",
    "FilterSpec",
    "PlotResult",
    "Recommendation",
    "ValidationMessage",
    "VisualizationConfig",
    "build_visualization",
    "auto_select_plot_type",
    "prepare_visual_data",
    "apply_filters",
    "infer_filter_specs",
    "filter_positive",
    "InteractiveController",
    "calculate_rank_abundance",
    "build_rank_abundance",
    "infer_abundance_columns",
    "plot_rank_abundance",
    "plotly_rank_abundance",
    "rank_abundance_summary",
    "pair_statistics",
    "regression_line",
    "centroid_summary",
    "group_summary",
    "group_significance",
    "recommend_visualizations",
    "ViewHistory",
    "PresetStore",
    "Debouncer",
    "dataset_from_selection",
    "suggest_analysis_routes",
    "export_figure",
    "export_dataframe",
    "export_html",
    "export_plot_result",
    "HELP_TEXT",
    "contextual_help",
    "validate_config",
    "visualization_from_loaded",
]
