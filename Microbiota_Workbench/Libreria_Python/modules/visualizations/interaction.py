"""Interacción Matplotlib: hover, selección, inspector, leyenda clicable y reset.

No contiene referencias a Tkinter. La GUI únicamente debe pasar el canvas de
Matplotlib y callbacks propios.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Callable

import numpy as np
import pandas as pd
from matplotlib.collections import PathCollection
from matplotlib.path import Path
from matplotlib.widgets import LassoSelector, RectangleSelector

try:  # mejora el hover, pero no es obligatoria
    import mplcursors
except Exception:  # pragma: no cover
    mplcursors = None


@dataclass
class InteractiveController:
    figure: Any
    canvas: Any
    data: pd.DataFrame
    source_index_col: str = "__source_index__"
    hover_cols: list[str] = field(default_factory=list)
    on_selection: Callable[[list[Any], pd.DataFrame], None] | None = None
    on_record: Callable[[Any, pd.Series], None] | None = None

    selected_indices: list[Any] = field(default_factory=list, init=False)
    _connections: list[int] = field(default_factory=list, init=False)
    _selectors: list[Any] = field(default_factory=list, init=False)
    _cursor: Any | None = field(default=None, init=False)
    _initial_limits: dict[int, tuple[tuple[float, float], tuple[float, float]]] = field(default_factory=dict, init=False)
    _legend_map: dict[Any, Any] = field(default_factory=dict, init=False)

    def remember_view(self) -> None:
        self._initial_limits = {
            id(ax): (ax.get_xlim(), ax.get_ylim()) for ax in self.figure.axes
        }

    def reset_view(self) -> None:
        for ax in self.figure.axes:
            limits = self._initial_limits.get(id(ax))
            if limits:
                ax.set_xlim(*limits[0])
                ax.set_ylim(*limits[1])
        self.canvas.draw_idle()

    def _scatter_artists(self) -> list[PathCollection]:
        return [
            artist
            for ax in self.figure.axes
            for artist in ax.collections
            if isinstance(artist, PathCollection) and len(artist.get_offsets())
        ]

    def attach_hover(self) -> None:
        """Activa tooltip sobre puntos; usa mplcursors si está instalado."""

        artists = self._scatter_artists()
        if not artists:
            return
        if mplcursors is not None:
            self._cursor = mplcursors.cursor(artists, hover=True)

            @self._cursor.connect("add")
            def _on_add(sel):
                artist = sel.artist
                rows = getattr(artist, "_visual_row_indices", None)
                if rows is None or sel.index >= len(rows):
                    return
                idx = rows[int(sel.index)]
                row = self._row_by_source_index(idx)
                if row is None:
                    return
                cols = self.hover_cols or list(row.index[: min(8, len(row.index))])
                lines = [f"{c}: {row[c]}" for c in cols if c in row.index]
                sel.annotation.set_text("\n".join(lines))
            return

        # Fallback sin dependencia adicional.
        annotation_by_ax: dict[Any, Any] = {}
        for ax in self.figure.axes:
            ann = ax.annotate(
                "",
                xy=(0, 0),
                xytext=(12, 12),
                textcoords="offset points",
                bbox={"boxstyle": "round", "fc": "white", "alpha": 0.92},
                arrowprops={"arrowstyle": "->"},
            )
            ann.set_visible(False)
            annotation_by_ax[ax] = ann

        def motion(event):
            changed = False
            for artist in artists:
                ax = artist.axes
                ann = annotation_by_ax[ax]
                if event.inaxes is not ax:
                    if ann.get_visible():
                        ann.set_visible(False)
                        changed = True
                    continue
                hit, info = artist.contains(event)
                if hit and len(info.get("ind", [])):
                    pos = int(info["ind"][0])
                    rows = getattr(artist, "_visual_row_indices", None)
                    if rows is None or pos >= len(rows):
                        continue
                    idx = rows[pos]
                    row = self._row_by_source_index(idx)
                    if row is None:
                        continue
                    offsets = artist.get_offsets()
                    ann.xy = offsets[pos]
                    cols = self.hover_cols or list(row.index[: min(8, len(row.index))])
                    ann.set_text("\n".join(f"{c}: {row[c]}" for c in cols if c in row.index))
                    ann.set_visible(True)
                    changed = True
                elif ann.get_visible():
                    ann.set_visible(False)
                    changed = True
            if changed:
                self.canvas.draw_idle()

        self._connections.append(self.canvas.mpl_connect("motion_notify_event", motion))

    def attach_point_inspector(self) -> None:
        """Click sobre punto -> callback con índice y fila completa."""

        for artist in self._scatter_artists():
            artist.set_picker(True)

        def picked(event):
            artist = event.artist
            if not isinstance(artist, PathCollection) or not len(event.ind):
                return
            rows = getattr(artist, "_visual_row_indices", None)
            if rows is None:
                return
            idx = rows[int(event.ind[0])]
            row = self._row_by_source_index(idx)
            if row is not None and self.on_record:
                self.on_record(idx, row)

        self._connections.append(self.canvas.mpl_connect("pick_event", picked))

    def attach_lasso(self, ax: Any | None = None) -> None:
        ax = ax or (self.figure.axes[0] if self.figure.axes else None)
        if ax is None:
            return

        def onselect(vertices):
            path = Path(vertices)
            selected: list[Any] = []
            for artist in [a for a in self._scatter_artists() if a.axes is ax]:
                offsets = artist.get_offsets()
                rows = getattr(artist, "_visual_row_indices", None)
                if rows is None:
                    continue
                selected.extend(np.asarray(rows)[path.contains_points(offsets)].tolist())
            self._emit_selection(selected)

        selector = LassoSelector(ax, onselect)
        self._selectors.append(selector)

    def attach_rectangle(self, ax: Any | None = None) -> None:
        ax = ax or (self.figure.axes[0] if self.figure.axes else None)
        if ax is None:
            return

        def onselect(eclick, erelease):
            xmin, xmax = sorted([eclick.xdata, erelease.xdata])
            ymin, ymax = sorted([eclick.ydata, erelease.ydata])
            selected: list[Any] = []
            for artist in [a for a in self._scatter_artists() if a.axes is ax]:
                offsets = np.asarray(artist.get_offsets())
                rows = getattr(artist, "_visual_row_indices", None)
                if rows is None or offsets.size == 0:
                    continue
                mask = (
                    (offsets[:, 0] >= xmin)
                    & (offsets[:, 0] <= xmax)
                    & (offsets[:, 1] >= ymin)
                    & (offsets[:, 1] <= ymax)
                )
                selected.extend(np.asarray(rows)[mask].tolist())
            self._emit_selection(selected)

        selector = RectangleSelector(ax, onselect, useblit=True, button=[1], interactive=True)
        self._selectors.append(selector)

    def attach_legend_toggle(self) -> None:
        """Click en la leyenda para ocultar/mostrar series."""

        for ax in self.figure.axes:
            legend = ax.get_legend()
            if legend is None:
                continue
            original_by_label = {
                artist.get_label(): artist
                for artist in [*ax.lines, *ax.collections]
                if artist.get_label() and not artist.get_label().startswith("_")
            }
            handles = getattr(legend, "legend_handles", getattr(legend, "legendHandles", []))
            for handle, text in zip(handles, legend.get_texts()):
                label = text.get_text()
                target = original_by_label.get(label)
                if target is None:
                    continue
                handle.set_picker(True)
                self._legend_map[handle] = target

        if not self._legend_map:
            return

        def picked(event):
            handle = event.artist
            if handle not in self._legend_map:
                return
            target = self._legend_map[handle]
            visible = not target.get_visible()
            target.set_visible(visible)
            try:
                handle.set_alpha(1.0 if visible else 0.2)
            except Exception:
                pass
            self.canvas.draw_idle()

        self._connections.append(self.canvas.mpl_connect("pick_event", picked))

    def _emit_selection(self, values: list[Any]) -> None:
        self.selected_indices = list(dict.fromkeys(values))
        if self.on_selection:
            if self.source_index_col in self.data.columns:
                selected_df = self.data[self.data[self.source_index_col].isin(self.selected_indices)].copy()
            else:
                selected_df = self.data.loc[self.data.index.intersection(self.selected_indices)].copy()
            self.on_selection(self.selected_indices, selected_df)

    def _row_by_source_index(self, idx: Any) -> pd.Series | None:
        if self.source_index_col in self.data.columns:
            rows = self.data[self.data[self.source_index_col] == idx]
            return rows.iloc[0] if len(rows) else None
        if idx in self.data.index:
            row = self.data.loc[idx]
            return row.iloc[0] if isinstance(row, pd.DataFrame) else row
        return None

    def disconnect(self) -> None:
        for cid in self._connections:
            try:
                self.canvas.mpl_disconnect(cid)
            except Exception:
                pass
        self._connections.clear()
        for selector in self._selectors:
            try:
                selector.disconnect_events()
            except Exception:
                pass
        self._selectors.clear()
        if self._cursor is not None:
            try:
                self._cursor.remove()
            except Exception:
                pass
            self._cursor = None
