"""Exportación de gráficos, datos visibles, selección y HTML interactivo."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import pandas as pd

from .models import PlotResult


def export_figure(figure: Any, path: str | Path, *, dpi: int = 180) -> Path:
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    suffix = path.suffix.lower()
    if suffix not in {".png", ".svg", ".pdf"}:
        raise ValueError("Formato de figura soportado: PNG, SVG o PDF.")
    figure.savefig(path, dpi=dpi, bbox_inches="tight")
    return path


def export_dataframe(df: pd.DataFrame, path: str | Path) -> Path:
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    suffix = path.suffix.lower()
    if suffix == ".csv":
        df.to_csv(path, index=False, encoding="utf-8-sig")
    elif suffix in {".xlsx", ".xls"}:
        df.to_excel(path, index=False)
    elif suffix == ".parquet":
        df.to_parquet(path, index=False)
    else:
        raise ValueError("Formato de datos soportado: CSV, XLSX o Parquet.")
    return path


def export_html(html: str, path: str | Path) -> Path:
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(html, encoding="utf-8")
    return path


def export_plot_result(
    result: PlotResult,
    directory: str | Path,
    *,
    basename: str = "visualization",
    formats: tuple[str, ...] = ("png", "csv", "html"),
) -> dict[str, Path]:
    """Exporta de forma homogénea todos los artefactos disponibles."""

    directory = Path(directory)
    directory.mkdir(parents=True, exist_ok=True)
    created: dict[str, Path] = {}

    normalized = {f.lower().lstrip(".") for f in formats}
    for fmt in ("png", "svg", "pdf"):
        if fmt in normalized and result.figure is not None:
            created[fmt] = export_figure(result.figure, directory / f"{basename}.{fmt}")

    if "csv" in normalized and isinstance(result.data, pd.DataFrame):
        created["csv"] = export_dataframe(result.data, directory / f"{basename}_data.csv")
    if "xlsx" in normalized and isinstance(result.data, pd.DataFrame):
        created["xlsx"] = export_dataframe(result.data, directory / f"{basename}_data.xlsx")

    if "html" in normalized and result.interactive_html is not None:
        created["html"] = export_html(
            result.interactive_html.html,
            directory / (result.interactive_html.filename or f"{basename}.html"),
        )

    meta_path = directory / f"{basename}_metadata.json"
    meta_path.write_text(json.dumps(result.metadata, ensure_ascii=False, indent=2, default=str), encoding="utf-8")
    created["metadata"] = meta_path
    return created
