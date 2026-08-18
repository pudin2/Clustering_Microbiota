"""Estado del constructor: undo/redo, presets y debounce independiente de GUI."""

from __future__ import annotations

import copy
import json
from pathlib import Path
from typing import Any, Callable


class ViewHistory:
    """Historial simple para Undo/Redo de configuraciones."""

    def __init__(self, max_items: int = 100):
        self.max_items = int(max_items)
        self._items: list[dict[str, Any]] = []
        self._cursor = -1

    def push(self, config: dict[str, Any]) -> None:
        value = copy.deepcopy(config)
        if self._cursor >= 0 and self._items[self._cursor] == value:
            return
        del self._items[self._cursor + 1 :]
        self._items.append(value)
        if len(self._items) > self.max_items:
            overflow = len(self._items) - self.max_items
            del self._items[:overflow]
        self._cursor = len(self._items) - 1

    def can_undo(self) -> bool:
        return self._cursor > 0

    def can_redo(self) -> bool:
        return 0 <= self._cursor < len(self._items) - 1

    def current(self) -> dict[str, Any] | None:
        return copy.deepcopy(self._items[self._cursor]) if self._cursor >= 0 else None

    def undo(self) -> dict[str, Any] | None:
        if not self.can_undo():
            return self.current()
        self._cursor -= 1
        return self.current()

    def redo(self) -> dict[str, Any] | None:
        if not self.can_redo():
            return self.current()
        self._cursor += 1
        return self.current()


class PresetStore:
    """Colección de vistas guardadas, persistible como JSON."""

    def __init__(self):
        self._presets: dict[str, dict[str, Any]] = {}

    def names(self) -> list[str]:
        return sorted(self._presets)

    def save(self, name: str, config: dict[str, Any]) -> None:
        key = str(name).strip()
        if not key:
            raise ValueError("El nombre del preset no puede estar vacío.")
        self._presets[key] = copy.deepcopy(config)

    def get(self, name: str) -> dict[str, Any]:
        if name not in self._presets:
            raise KeyError(f"Preset inexistente: {name}")
        return copy.deepcopy(self._presets[name])

    def delete(self, name: str) -> None:
        self._presets.pop(name, None)

    def save_file(self, path: str | Path) -> Path:
        path = Path(path)
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(self._presets, ensure_ascii=False, indent=2, default=str), encoding="utf-8")
        return path

    def load_file(self, path: str | Path) -> None:
        data = json.loads(Path(path).read_text(encoding="utf-8"))
        if not isinstance(data, dict):
            raise ValueError("El archivo de presets debe contener un objeto JSON.")
        self._presets = {str(k): dict(v) for k, v in data.items()}


class Debouncer:
    """Debounce genérico compatible con ``tk_widget.after``.

    Ejemplo en GUI::

        debounce = Debouncer(root.after, root.after_cancel, 400)
        debounce.trigger(self.update_visual_builder)
    """

    def __init__(
        self,
        schedule: Callable[..., Any],
        cancel: Callable[[Any], Any],
        delay_ms: int = 400,
    ):
        self.schedule = schedule
        self.cancel = cancel
        self.delay_ms = int(delay_ms)
        self._handle: Any | None = None

    def trigger(self, callback: Callable[..., Any], *args: Any, **kwargs: Any) -> None:
        if self._handle is not None:
            try:
                self.cancel(self._handle)
            except Exception:
                pass
        self._handle = self.schedule(self.delay_ms, lambda: self._run(callback, *args, **kwargs))

    def _run(self, callback: Callable[..., Any], *args: Any, **kwargs: Any) -> None:
        self._handle = None
        callback(*args, **kwargs)
