import contextlib
import datetime as _dt
import io
import json
import os
import queue
import re
import threading
import traceback
from pathlib import Path
import tkinter as tk
from tkinter import filedialog, messagebox, ttk

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd

try:
    from PIL import Image, ImageTk
    HAS_PIL = True
except Exception:
    Image = None
    ImageTk = None
    HAS_PIL = False

from Load import load_dataframe_from_path
from Caracterization import distribution_plots_from_loaded, normality_tests_from_loaded
from KDE import kde_from_loaded
from Kruscall_Wallis import kruskal_wallis_from_loaded
from Mann_Whitney import mann_whitney_from_loaded
from DB_Scan import dbscan_from_loaded


APP_TITLE = "Microbiota Statistical Workbench"
DEFAULT_OUTPUT_DIR = Path(__file__).resolve().parents[1] / "outputs_gui"


def sanitize_name(value, fallback="artifact"):
    text = str(value).strip()
    text = re.sub(r"[^\w.\-]+", "_", text, flags=re.ASCII)
    text = text.strip("._")
    return text[:120] or fallback


def unique_name(name, existing):
    base = sanitize_name(name, "dataset")
    if base not in existing:
        return base
    i = 2
    while f"{base}_{i}" in existing:
        i += 1
    return f"{base}_{i}"


def split_list(text):
    if text is None:
        return None
    items = [x.strip() for x in str(text).replace(";", ",").split(",")]
    items = [x for x in items if x]
    return items or None


def parse_optional_float(text):
    text = str(text).strip()
    if not text:
        return None
    return float(text)


def parse_bool(value):
    return bool(value)


def parse_tuple(text):
    items = split_list(text)
    return tuple(items) if items else None


def parse_json_dict(text):
    text = str(text).strip()
    if not text:
        return {}
    data = json.loads(text)
    if not isinstance(data, dict):
        raise ValueError("Debe ser un objeto JSON, por ejemplo: {\"perplexity\": 20}")
    return data


def parse_bandwidths(text):
    text = str(text).strip()
    if not text:
        return None
    if text.startswith("{"):
        data = json.loads(text)
        return {str(k): float(v) for k, v in data.items()}

    result = {}
    for part in text.replace(";", ",").split(","):
        part = part.strip()
        if not part:
            continue
        if "=" not in part:
            raise ValueError("Usa kernel=valor, por ejemplo gaussian=1.5")
        key, value = part.split("=", 1)
        result[key.strip()] = float(value.strip())
    return result or None


def json_safe(value):
    if value is None or isinstance(value, (str, int, float, bool)):
        return value
    if isinstance(value, (np.integer,)):
        return int(value)
    if isinstance(value, (np.floating,)):
        if np.isfinite(value):
            return float(value)
        return None
    if isinstance(value, (np.bool_,)):
        return bool(value)
    if isinstance(value, Path):
        return str(value)
    if isinstance(value, dict):
        safe = {}
        for k, v in value.items():
            if isinstance(v, (pd.DataFrame, pd.Series, np.ndarray)):
                safe[str(k)] = f"<{type(v).__name__} exported separately>"
            else:
                safe[str(k)] = json_safe(v)
        return safe
    if isinstance(value, (list, tuple)):
        if len(value) > 100:
            return f"<{type(value).__name__} length={len(value)} exported separately>"
        return [json_safe(v) for v in value]
    return repr(value)


class FigureCapture:
    def __init__(self, figure_dir):
        self.figure_dir = Path(figure_dir)
        self.figure_dir.mkdir(parents=True, exist_ok=True)
        self.saved = []
        self.counter = 0
        self._old_show = None


    def __enter__(self):
        plt.switch_backend("Agg")
        fig = plt.figure(figsize=(0.1, 0.1))
        plt.close(fig)
        self._old_show = plt.show
        plt.show = self.show
        return self


    def __exit__(self, exc_type, exc, tb):
        self.save_open_figures()
        plt.show = self._old_show
        plt.close("all")


    def _title_for(self, fig):
        if getattr(fig, "_suptitle", None) is not None:
            text = fig._suptitle.get_text()
            if text:
                return text
        for ax in fig.axes:
            text = ax.get_title()
            if text:
                return text
        return "figure"


    def save_open_figures(self):
        for num in list(plt.get_fignums()):
            fig = plt.figure(num)
            self.counter += 1
            name = sanitize_name(self._title_for(fig), "figure")
            path = self.figure_dir / f"{self.counter:02d}_{name}.png"
            fig.savefig(path, dpi=180, bbox_inches="tight")
            self.saved.append(path)
            plt.close(fig)


    def show(self, *args, **kwargs):
        self.save_open_figures()


class ArtifactExporter:

    def __init__(self, run_dir):
        self.run_dir = Path(run_dir).resolve()
        self.tables_dir = self.run_dir / "tables"
        self.arrays_dir = self.run_dir / "arrays"
        self.objects_dir = self.run_dir / "objects"
        self.tables_dir.mkdir(parents=True, exist_ok=True)
        self.arrays_dir.mkdir(parents=True, exist_ok=True)
        self.objects_dir.mkdir(parents=True, exist_ok=True)
        self.manifest = {"tables": [], "arrays": [], "objects": []}
        self.excel_tables = []


    def export(self, obj, prefix="result"):
        self._export_obj(obj, sanitize_name(prefix, "result"))
        self._write_excel_book()
        return self.manifest


    def _export_obj(self, obj, prefix):
        if isinstance(obj, pd.DataFrame):
            path = self.tables_dir / f"{prefix}.csv"
            obj.to_csv(path, index=False, encoding="utf-8-sig")
            self.excel_tables.append((prefix, obj))
            self.manifest["tables"].append({"name": prefix, "path": str(path), "rows": int(obj.shape[0]), "columns": int(obj.shape[1])})
            return

        if isinstance(obj, pd.Series):
            path = self.tables_dir / f"{prefix}.csv"
            obj.to_frame().to_csv(path, index=True, encoding="utf-8-sig")
            self.excel_tables.append((prefix, obj.to_frame()))
            self.manifest["tables"].append({"name": prefix, "path": str(path), "rows": int(obj.shape[0]), "columns": 1})
            return

        if isinstance(obj, np.ndarray):
            arr = np.asarray(obj)
            if arr.ndim <= 2:
                path = self.arrays_dir / f"{prefix}.csv"
                pd.DataFrame(arr).to_csv(path, index=False, encoding="utf-8-sig")
            else:
                path = self.arrays_dir / f"{prefix}.npy"
                np.save(path, arr)
            self.manifest["arrays"].append({"name": prefix, "path": str(path), "shape": list(arr.shape)})
            return

        if isinstance(obj, dict):
            scalar_items = {}
            for key, value in obj.items():
                child_prefix = sanitize_name(f"{prefix}_{key}", prefix)
                if isinstance(value, (pd.DataFrame, pd.Series, np.ndarray, dict, list, tuple)):
                    self._export_obj(value, child_prefix)
                else:
                    scalar_items[str(key)] = json_safe(value)
            if scalar_items:
                self._write_json(prefix, scalar_items)
            return

        if isinstance(obj, (list, tuple)):
            for i, value in enumerate(obj, start=1):
                self._export_obj(value, sanitize_name(f"{prefix}_{i:02d}", prefix))
            return

        self._write_json(prefix, json_safe(obj))


    def _write_json(self, name, payload):
        path = self.objects_dir / f"{sanitize_name(name)}.json"
        with path.open("w", encoding="utf-8") as fh:
            json.dump(payload, fh, ensure_ascii=False, indent=2)
        self.manifest["objects"].append({"name": name, "path": str(path)})


    def _write_excel_book(self):
        if not self.excel_tables:
            return
        path = self.run_dir / "tables.xlsx"
        try:
            with pd.ExcelWriter(path) as writer:
                used = set()
                for name, df in self.excel_tables:
                    sheet = sanitize_name(name, "sheet")[:31] or "sheet"
                    base = sheet
                    i = 2
                    while sheet in used:
                        suffix = f"_{i}"
                        sheet = f"{base[:31 - len(suffix)]}{suffix}"
                        i += 1
                    used.add(sheet)
                    df.to_excel(writer, sheet_name=sheet, index=False)
            self.manifest["excel_workbook"] = str(path)
        except Exception as exc:
            self.manifest["excel_workbook_error"] = str(exc)


class ScrollFrame(ttk.Frame):
    
    def __init__(self, master):
        super().__init__(master)
        self.canvas = tk.Canvas(self, highlightthickness=0)
        self.scrollbar = ttk.Scrollbar(self, orient="vertical", command=self.canvas.yview)
        self.inner = ttk.Frame(self.canvas)
        self.window_id = self.canvas.create_window((0, 0), window=self.inner, anchor="nw")

        self.canvas.configure(yscrollcommand=self.scrollbar.set)
        self.canvas.grid(row=0, column=0, sticky="nsew")
        self.scrollbar.grid(row=0, column=1, sticky="ns")
        self.grid_rowconfigure(0, weight=1)
        self.grid_columnconfigure(0, weight=1)

        self.inner.bind("<Configure>", self._on_inner_configure)
        self.canvas.bind("<Configure>", self._on_canvas_configure)


    def _on_inner_configure(self, _event):
        self.canvas.configure(scrollregion=self.canvas.bbox("all"))


    def _on_canvas_configure(self, event):
        self.canvas.itemconfigure(self.window_id, width=event.width)


class MicrobiotaGUI(tk.Tk):

    def __init__(self):
        super().__init__()
        self.title(APP_TITLE)
        self.geometry("1320x820")
        self.minsize(1120, 720)

        self.dfs = {}
        self.results = {}
        self.result_manifests = {}
        self.result_run_dirs = {}
        self.active_result_key = None
        self.current_table_path = None
        self.current_figure_path = None
        self.figure_image_ref = None
        self.visible_tables = {}
        self.visible_figures = {}
        self.last_run_dir = None
        self.worker = None
        self.msg_queue = queue.Queue()
        self.inputs = {}
        self.df_combos = []
        self.column_combos = []
        self.numeric_column_dropdowns = []
        self.categorical_column_dropdowns = []
        self.group_value_dropdowns = []
        self.loading_result_view = False
        self.results_lists_notebook = None

        self._configure_style()
        self._build_ui()
        self.after(150, self._poll_queue)


    def _configure_style(self):
        style = ttk.Style(self)
        try:
            style.theme_use("clam")
        except tk.TclError:
            pass
        style.configure("TFrame", background="#f5f6f8")
        style.configure("Sidebar.TFrame", background="#eef1f4")
        style.configure("Header.TLabel", background="#f5f6f8", foreground="#20242a", font=("Segoe UI", 16, "bold"))
        style.configure("Subtle.TLabel", background="#f5f6f8", foreground="#5d6673")
        style.configure("TLabelframe", background="#f5f6f8")
        style.configure("TLabelframe.Label", font=("Segoe UI", 10, "bold"))
        style.configure("Accent.TButton", font=("Segoe UI", 10, "bold"))
        style.configure("Treeview", rowheight=24)


    def _build_ui(self):
        root = ttk.Frame(self)
        root.pack(fill="both", expand=True)
        root.grid_columnconfigure(0, minsize=340)
        root.grid_columnconfigure(1, weight=1)
        root.grid_rowconfigure(0, weight=1)

        sidebar = ttk.Frame(root, style="Sidebar.TFrame", padding=12)
        sidebar.grid(row=0, column=0, sticky="nsew")
        sidebar.grid_rowconfigure(5, weight=1)

        ttk.Label(sidebar, text="Microbiota Workbench", font=("Segoe UI", 15, "bold"), background="#eef1f4").grid(row=0, column=0, sticky="w")
        ttk.Label(sidebar, text="Datos en memoria, exportes por corrida", background="#eef1f4", foreground="#5d6673").grid(row=1, column=0, sticky="w", pady=(2, 12))

        data_box = ttk.LabelFrame(sidebar, text="Datasets cargados", padding=8)
        data_box.grid(row=2, column=0, sticky="nsew", pady=(0, 10))
        data_box.grid_columnconfigure(0, weight=1)

        btns = ttk.Frame(data_box)
        btns.grid(row=0, column=0, sticky="ew", pady=(0, 8))
        btns.grid_columnconfigure((0, 1, 2), weight=1)
        ttk.Button(btns, text="Cargar", command=self.load_files).grid(row=0, column=0, sticky="ew", padx=(0, 4))
        ttk.Button(btns, text="Vista", command=self.preview_selected_dataset).grid(row=0, column=1, sticky="ew", padx=4)
        ttk.Button(btns, text="Quitar", command=self.remove_selected_dataset).grid(row=0, column=2, sticky="ew", padx=(4, 0))

        self.dataset_tree = ttk.Treeview(data_box, columns=("shape",), show="tree headings", height=8)
        self.dataset_tree.heading("#0", text="Nombre")
        self.dataset_tree.heading("shape", text="Shape")
        self.dataset_tree.column("#0", width=190, stretch=True)
        self.dataset_tree.column("shape", width=95, anchor="center", stretch=False)
        self.dataset_tree.grid(row=1, column=0, sticky="nsew")

        output_box = ttk.LabelFrame(sidebar, text="Salida", padding=8)
        output_box.grid(row=3, column=0, sticky="ew", pady=(0, 10))
        output_box.grid_columnconfigure(0, weight=1)
        self.output_dir_var = tk.StringVar(value=str(DEFAULT_OUTPUT_DIR))
        ttk.Entry(output_box, textvariable=self.output_dir_var).grid(row=0, column=0, sticky="ew", pady=(0, 6))
        output_btns = ttk.Frame(output_box)
        output_btns.grid(row=1, column=0, sticky="ew")
        output_btns.grid_columnconfigure((0, 1), weight=1)
        ttk.Button(output_btns, text="Cambiar", command=self.choose_output_dir).grid(row=0, column=0, sticky="ew", padx=(0, 4))
        ttk.Button(output_btns, text="Abrir", command=self.open_output_dir).grid(row=0, column=1, sticky="ew", padx=(4, 0))

        memory_box = ttk.LabelFrame(sidebar, text="Resultados cargados", padding=8)
        memory_box.grid(row=4, column=0, sticky="ew", pady=(0, 10))
        memory_box.grid_columnconfigure(0, weight=1)
        self.result_tree = ttk.Treeview(memory_box, columns=("created",), show="tree headings", height=5)
        self.result_tree.heading("#0", text="Analisis")
        self.result_tree.heading("created", text="Fecha")
        self.result_tree.column("#0", width=180, stretch=True)
        self.result_tree.column("created", width=125, stretch=False)
        self.result_tree.grid(row=0, column=0, sticky="ew")
        self.result_tree.bind("<<TreeviewSelect>>", self.on_result_selected)
        result_btns = ttk.Frame(memory_box)
        result_btns.grid(row=1, column=0, sticky="ew", pady=(8, 0))
        result_btns.grid_columnconfigure((0, 1), weight=1)
        ttk.Button(result_btns, text="Cargar corrida", command=self.load_run_folder).grid(row=0, column=0, sticky="ew", padx=(0, 4))
        ttk.Button(result_btns, text="Historial", command=self.load_saved_runs).grid(row=0, column=1, sticky="ew", padx=(4, 0))

        log_box = ttk.LabelFrame(sidebar, text="Log", padding=8)
        log_box.grid(row=5, column=0, sticky="nsew")
        log_box.grid_columnconfigure(0, weight=1)
        log_box.grid_rowconfigure(0, weight=1)
        self.log_text = tk.Text(log_box, height=12, wrap="word", relief="flat", bg="#ffffff", fg="#20242a")
        self.log_text.grid(row=0, column=0, sticky="nsew")

        main = ttk.Frame(root, padding=16)
        main.grid(row=0, column=1, sticky="nsew")
        main.grid_columnconfigure(0, weight=1)
        main.grid_rowconfigure(2, weight=1)

        ttk.Label(main, text="Panel de analisis", style="Header.TLabel").grid(row=0, column=0, sticky="w")
        ttk.Label(main, text="Escoge parametros, ejecuta y guarda tablas/figuras automaticamente.", style="Subtle.TLabel").grid(row=1, column=0, sticky="w", pady=(2, 12))

        self.notebook = ttk.Notebook(main)
        self.notebook.grid(row=2, column=0, sticky="nsew")

        self._build_characterization_tab()
        self._build_normality_tab()
        self._build_kde_tab()
        self._build_kruskal_tab()
        self._build_mann_whitney_tab()
        self._build_dbscan_tab()
        self._build_results_tab()

        self.status_var = tk.StringVar(value="Listo")
        ttk.Label(main, textvariable=self.status_var, style="Subtle.TLabel").grid(row=3, column=0, sticky="ew", pady=(10, 0))


    def _new_tab(self, title):
        frame = ScrollFrame(self.notebook)
        self.notebook.add(frame, text=title)
        body = frame.inner
        body.grid_columnconfigure(0, weight=1)
        return body


    def _section(self, parent, title, row):
        box = ttk.LabelFrame(parent, text=title, padding=12)
        box.grid(row=row, column=0, sticky="ew", pady=(0, 12))
        box.grid_columnconfigure(1, weight=1)
        box.grid_columnconfigure(3, weight=1)
        return box


    def _add_entry(self, box, group, key, label, default="", row=0, col=0, width=22):
        ttk.Label(box, text=label).grid(row=row, column=col, sticky="w", padx=(0, 8), pady=4)
        var = tk.StringVar(value=str(default))
        entry = ttk.Entry(box, textvariable=var, width=width)
        entry.grid(row=row, column=col + 1, sticky="ew", pady=4, padx=(0, 16))
        self.inputs.setdefault(group, {})[key] = var
        return entry


    def _add_numeric_columns_dropdown(
        self,
        box,
        group,
        key,
        label,
        dataset_key,
        row=0,
        col=0,
        width=42
    ):
        ttk.Label(box, text=label).grid(
            row=row,
            column=col,
            sticky="w",
            padx=(0, 8),
            pady=4
        )

        numeric_var = tk.StringVar(value="")

        combo = ttk.Combobox(
            box,
            textvariable=numeric_var,
            values=[],
            width=width,
            state="normal"
        )

        combo.grid(
            row=row,
            column=col + 1,
            sticky="ew",
            pady=4,
            padx=(0, 16)
        )

        self.inputs.setdefault(group, {})[key] = numeric_var

        selector = {
            "group": group,
            "key": key,
            "dataset_key": dataset_key,
            "combo": combo,
            "var": numeric_var,
            "selected_text": ""
        }

        self.numeric_column_dropdowns.append(selector)

        combo.bind("<<ComboboxSelected>>", self.on_numeric_column_dropdown_selected)
        combo.bind("<KeyRelease>", self.on_numeric_columns_text_edited)
        combo.bind("<FocusOut>", self.on_numeric_columns_text_edited)

        return combo


    def get_numeric_columns_for_dataset(self, dataset_name):
        df = self.dfs.get(dataset_name)

        if df is None:
            return []

        numeric_cols = list(df.select_dtypes(include=[np.number]).columns)

        if numeric_cols:
            return [str(col) for col in numeric_cols]

        detected_cols = []

        for col in df.columns:
            converted = pd.to_numeric(df[col], errors="coerce")

            if converted.notna().sum() > 0:
                detected_cols.append(str(col))

        return detected_cols


    def refresh_numeric_column_dropdowns(self):
        for selector in self.numeric_column_dropdowns:
            group = selector["group"]
            dataset_key = selector["dataset_key"]
            combo = selector["combo"]
            numeric_var = selector["var"]

            dataset_var = self.inputs.get(group, {}).get(dataset_key)

            if dataset_var is None:
                columns = []
            else:
                dataset_name = dataset_var.get()
                columns = self.get_numeric_columns_for_dataset(dataset_name)

            current_selected = split_list(numeric_var.get()) or []
            valid_selected = [col for col in current_selected if col in columns]

            selected_text = ", ".join(valid_selected)

            numeric_var.set(selected_text)
            selector["selected_text"] = selected_text
            combo.configure(values=columns)


    def on_numeric_columns_text_edited(self, event):
        combo = event.widget

        for selector in self.numeric_column_dropdowns:
            if selector["combo"] == combo:
                selector["selected_text"] = selector["var"].get().strip()
                break


    def on_numeric_column_dropdown_selected(self, event):
        combo = event.widget

        for selector in self.numeric_column_dropdowns:
            if selector["combo"] == combo:
                selected_column = selector["var"].get().strip()
                previous_text = selector.get("selected_text", "")
                current_selected = split_list(previous_text) or []

                if selected_column:
                    if selected_column not in current_selected:
                        current_selected.append(selected_column)

                    selected_text = ", ".join(current_selected)
                    selector["var"].set(selected_text)
                    selector["selected_text"] = selected_text

                break


    def _add_categorical_columns_dropdown(
        self,
        box,
        group,
        key,
        label,
        dataset_key,
        row=0,
        col=0,
        width=42
    ):
        ttk.Label(box, text=label).grid(
            row=row,
            column=col,
            sticky="w",
            padx=(0, 8),
            pady=4
        )

        categorical_var = tk.StringVar(value="")

        combo = ttk.Combobox(
            box,
            textvariable=categorical_var,
            values=[],
            width=width,
            state="normal"
        )

        combo.grid(
            row=row,
            column=col + 1,
            sticky="ew",
            pady=4,
            padx=(0, 16)
        )

        self.inputs.setdefault(group, {})[key] = categorical_var

        selector = {
            "group": group,
            "key": key,
            "dataset_key": dataset_key,
            "combo": combo,
            "var": categorical_var,
            "selected_text": ""
        }

        self.categorical_column_dropdowns.append(selector)

        combo.bind("<<ComboboxSelected>>", self.on_categorical_column_dropdown_selected)
        combo.bind("<KeyRelease>", self.on_categorical_columns_text_edited)
        combo.bind("<FocusOut>", self.on_categorical_columns_text_edited)

        return combo


    def get_categorical_columns_for_dataset(self, dataset_name):
        df = self.dfs.get(dataset_name)

        if df is None:
            return []

        categorical_cols = []

        for col in df.columns:
            series = df[col]

            if pd.api.types.is_numeric_dtype(series):
                continue

            categorical_cols.append(str(col))

        return categorical_cols


    def refresh_categorical_column_dropdowns(self):
        for selector in self.categorical_column_dropdowns:
            group = selector["group"]
            dataset_key = selector["dataset_key"]
            combo = selector["combo"]
            categorical_var = selector["var"]

            dataset_var = self.inputs.get(group, {}).get(dataset_key)

            if dataset_var is None:
                columns = []
            else:
                dataset_name = dataset_var.get()
                columns = self.get_categorical_columns_for_dataset(dataset_name)

            current_selected = split_list(categorical_var.get()) or []
            valid_selected = [col for col in current_selected if col in columns]

            selected_text = ", ".join(valid_selected)

            categorical_var.set(selected_text)
            selector["selected_text"] = selected_text
            combo.configure(values=columns)


    def on_categorical_columns_text_edited(self, event):
        combo = event.widget

        for selector in self.categorical_column_dropdowns:
            if selector["combo"] == combo:
                selector["selected_text"] = selector["var"].get().strip()
                break


    def on_categorical_column_dropdown_selected(self, event):
        combo = event.widget

        for selector in self.categorical_column_dropdowns:
            if selector["combo"] == combo:
                selected_column = selector["var"].get().strip()
                previous_text = selector.get("selected_text", "")
                current_selected = split_list(previous_text) or []

                if selected_column:
                    if selected_column not in current_selected:
                        current_selected.append(selected_column)

                    selected_text = ", ".join(current_selected)
                    selector["var"].set(selected_text)
                    selector["selected_text"] = selected_text

                break


    def _add_group_values_dropdown(
        self,
        box,
        group,
        key,
        label,
        dataset_key,
        column_key,
        row=0,
        col=0,
        width=42
    ):
        ttk.Label(box, text=label).grid(
            row=row,
            column=col,
            sticky="w",
            padx=(0, 8),
            pady=4
        )

        value_var = tk.StringVar(value="")

        combo = ttk.Combobox(
            box,
            textvariable=value_var,
            values=[],
            width=width,
            state="normal"
        )

        combo.grid(
            row=row,
            column=col + 1,
            sticky="ew",
            pady=4,
            padx=(0, 16)
        )

        self.inputs.setdefault(group, {})[key] = value_var

        selector = {
            "group": group,
            "key": key,
            "dataset_key": dataset_key,
            "column_key": column_key,
            "combo": combo,
            "var": value_var,
            "selected_text": ""
        }

        self.group_value_dropdowns.append(selector)

        combo.bind("<<ComboboxSelected>>", self.on_group_value_dropdown_selected)
        combo.bind("<KeyRelease>", self.on_group_values_text_edited)
        combo.bind("<FocusOut>", self.on_group_values_text_edited)

        return combo


    def get_unique_values_for_column(self, dataset_name, column_name):
        df = self.dfs.get(dataset_name)

        if df is None:
            return []

        if not column_name:
            return []

        if column_name not in df.columns:
            return []

        values = df[column_name].dropna()

        result = []

        for value in pd.unique(values):
            text_value = str(value).strip()

            if text_value:
                result.append(text_value)

        result = sorted(result, key=lambda item: item.lower())

        return result


    def refresh_group_value_dropdowns(self):
        for selector in self.group_value_dropdowns:
            group = selector["group"]
            dataset_key = selector["dataset_key"]
            column_key = selector["column_key"]
            combo = selector["combo"]
            value_var = selector["var"]

            dataset_var = self.inputs.get(group, {}).get(dataset_key)
            column_var = self.inputs.get(group, {}).get(column_key)

            if dataset_var is None or column_var is None:
                values = []
            else:
                dataset_name = dataset_var.get()
                column_name = column_var.get()
                values = self.get_unique_values_for_column(dataset_name, column_name)

            current_selected = split_list(value_var.get()) or []
            valid_selected = [item for item in current_selected if item in values]

            selected_text = ", ".join(valid_selected)

            value_var.set(selected_text)
            selector["selected_text"] = selected_text
            combo.configure(values=values)


    def on_group_values_text_edited(self, event):
        combo = event.widget

        for selector in self.group_value_dropdowns:
            if selector["combo"] == combo:
                selector["selected_text"] = selector["var"].get().strip()
                break


    def on_group_value_dropdown_selected(self, event):
        combo = event.widget

        for selector in self.group_value_dropdowns:
            if selector["combo"] == combo:
                selected_value = selector["var"].get().strip()
                previous_text = selector.get("selected_text", "")
                current_selected = split_list(previous_text) or []

                if selected_value:
                    if selected_value not in current_selected:
                        current_selected.append(selected_value)

                    selected_text = ", ".join(current_selected)
                    selector["var"].set(selected_text)
                    selector["selected_text"] = selected_text

                break


    def _add_combo(self, box, group, key, label, values, default="", row=0, col=0, width=22, dataset_combo=False, column_for=None):
        ttk.Label(box, text=label).grid(row=row, column=col, sticky="w", padx=(0, 8), pady=4)

        var = tk.StringVar(value=default)

        combo = ttk.Combobox(
            box,
            textvariable=var,
            values=values,
            width=width
        )

        combo.grid(row=row, column=col + 1, sticky="ew", pady=4, padx=(0, 16))

        self.inputs.setdefault(group, {})[key] = var

        if dataset_combo:
            self.df_combos.append(combo)
            combo.bind("<<ComboboxSelected>>", lambda _event: self.refresh_columns(), add="+")
            combo.bind("<FocusOut>", lambda _event: self.refresh_columns(), add="+")

        if column_for:
            self.column_combos.append((combo, column_for))
            combo.bind("<<ComboboxSelected>>", lambda _event: self.refresh_group_value_dropdowns(), add="+")
            combo.bind("<FocusOut>", lambda _event: self.refresh_group_value_dropdowns(), add="+")

        return combo


    def _add_check(self, box, group, key, label, default=True, row=0, col=0):
        var = tk.BooleanVar(value=default)
        check = ttk.Checkbutton(box, text=label, variable=var)
        check.grid(row=row, column=col, columnspan=2, sticky="w", pady=4, padx=(0, 16))
        self.inputs.setdefault(group, {})[key] = var
        return check


    def _run_button(self, parent, row, label, command):
        btn = ttk.Button(parent, text=label, style="Accent.TButton", command=command)
        btn.grid(row=row, column=0, sticky="ew", pady=(4, 0))
        return btn


    def _build_results_tab(self):
        self.results_tab = ttk.Frame(self.notebook, padding=10)
        self.notebook.add(self.results_tab, text="Resultados")
        self.results_tab.grid_rowconfigure(1, weight=1)
        self.results_tab.grid_columnconfigure(0, weight=1)

        header = ttk.Frame(self.results_tab)
        header.grid(row=0, column=0, sticky="ew", pady=(0, 10))
        header.grid_columnconfigure(0, weight=1)
        self.results_title_var = tk.StringVar(value="Sin resultados cargados")
        ttk.Label(header, textvariable=self.results_title_var, font=("Segoe UI", 11, "bold")).grid(row=0, column=0, sticky="w")
        ttk.Button(header, text="Cargar corrida", command=self.load_run_folder).grid(row=0, column=1, padx=(8, 0))
        ttk.Button(header, text="Cargar manifest", command=self.load_manifest_file).grid(row=0, column=2, padx=(8, 0))
        ttk.Button(header, text="Historial", command=self.load_saved_runs).grid(row=0, column=3, padx=(8, 0))
        ttk.Button(header, text="Abrir carpeta", command=self.open_active_run_dir).grid(row=0, column=4, padx=(8, 0))

        paned = ttk.PanedWindow(self.results_tab, orient="horizontal")
        paned.grid(row=1, column=0, sticky="nsew")

        left = ttk.Frame(paned, padding=(0, 0, 10, 0))
        right = ttk.Frame(paned)
        left.grid_rowconfigure(0, weight=1)
        left.grid_columnconfigure(0, weight=1)
        right.grid_rowconfigure(0, weight=1)
        right.grid_columnconfigure(0, weight=1)
        paned.add(left, weight=1)
        paned.add(right, weight=4)

        self.results_lists_notebook = ttk.Notebook(left)
        self.results_lists_notebook.grid(row=0, column=0, sticky="nsew")
        self.results_lists_notebook.bind("<<NotebookTabChanged>>", self.on_result_list_tab_changed)

        lists = self.results_lists_notebook

        table_list_frame = ttk.Frame(lists, padding=6)
        table_list_frame.grid_rowconfigure(0, weight=1)
        table_list_frame.grid_columnconfigure(0, weight=1)
        lists.add(table_list_frame, text="Tablas")
        self.table_list = ttk.Treeview(
            table_list_frame,
            columns=("rows", "cols"),
            show="tree headings",
            height=14,
            selectmode="browse"
        )
        self.table_list.heading("#0", text="Tabla")
        self.table_list.heading("rows", text="Filas")
        self.table_list.heading("cols", text="Cols")
        self.table_list.column("#0", width=210, stretch=True)
        self.table_list.column("rows", width=70, anchor="e", stretch=False)
        self.table_list.column("cols", width=55, anchor="e", stretch=False)
        self.table_list.grid(row=0, column=0, sticky="nsew")
        self.table_list.bind("<<TreeviewSelect>>", self.on_table_selected)
        table_scroll = ttk.Scrollbar(table_list_frame, orient="vertical", command=self.table_list.yview)
        table_scroll.grid(row=0, column=1, sticky="ns")
        self.table_list.configure(yscrollcommand=table_scroll.set)

        figure_list_frame = ttk.Frame(lists, padding=6)
        figure_list_frame.grid_rowconfigure(0, weight=1)
        figure_list_frame.grid_columnconfigure(0, weight=1)
        lists.add(figure_list_frame, text="Figuras")
        self.figure_list = ttk.Treeview(
            figure_list_frame,
            show="tree",
            height=14,
            selectmode="browse"
        )
        self.figure_list.heading("#0", text="Figura")
        self.figure_list.column("#0", width=280, stretch=True)
        self.figure_list.grid(row=0, column=0, sticky="nsew")
        self.figure_list.bind("<<TreeviewSelect>>", self.on_figure_selected)
        fig_scroll = ttk.Scrollbar(figure_list_frame, orient="vertical", command=self.figure_list.yview)
        fig_scroll.grid(row=0, column=1, sticky="ns")
        self.figure_list.configure(yscrollcommand=fig_scroll.set)

        list_buttons = ttk.Frame(left)
        list_buttons.grid(row=1, column=0, sticky="ew", pady=(10, 0))
        list_buttons.grid_columnconfigure((0, 1), weight=1)
        ttk.Button(list_buttons, text="Abrir seleccionado", command=self.open_selected_result_file).grid(row=0, column=0, sticky="ew", padx=(0, 4))
        ttk.Button(list_buttons, text="Actualizar vista", command=self.refresh_active_result_view).grid(row=0, column=1, sticky="ew", padx=(4, 0))

        self.preview_notebook = ttk.Notebook(right)
        self.preview_notebook.grid(row=0, column=0, sticky="nsew")

        table_preview_frame = ttk.Frame(self.preview_notebook, padding=8)
        table_preview_frame.grid_rowconfigure(1, weight=1)
        table_preview_frame.grid_columnconfigure(0, weight=1)
        self.preview_notebook.add(table_preview_frame, text="Vista de tabla")
        self.table_info_var = tk.StringVar(value="Selecciona una tabla para verla.")
        ttk.Label(table_preview_frame, textvariable=self.table_info_var, style="Subtle.TLabel").grid(row=0, column=0, sticky="ew", pady=(0, 6))
        table_grid = ttk.Frame(table_preview_frame)
        table_grid.grid(row=1, column=0, sticky="nsew")
        table_grid.grid_rowconfigure(0, weight=1)
        table_grid.grid_columnconfigure(0, weight=1)
        self.table_preview = ttk.Treeview(table_grid, show="headings")
        self.table_preview.grid(row=0, column=0, sticky="nsew")
        table_y = ttk.Scrollbar(table_grid, orient="vertical", command=self.table_preview.yview)
        table_x = ttk.Scrollbar(table_grid, orient="horizontal", command=self.table_preview.xview)
        table_y.grid(row=0, column=1, sticky="ns")
        table_x.grid(row=1, column=0, sticky="ew")
        self.table_preview.configure(yscrollcommand=table_y.set, xscrollcommand=table_x.set)

        figure_preview_frame = ttk.Frame(self.preview_notebook, padding=8)
        figure_preview_frame.grid_rowconfigure(1, weight=1)
        figure_preview_frame.grid_columnconfigure(0, weight=1)
        self.preview_notebook.add(figure_preview_frame, text="Vista de figura")
        self.figure_info_var = tk.StringVar(value="Selecciona una figura para verla.")
        ttk.Label(figure_preview_frame, textvariable=self.figure_info_var, style="Subtle.TLabel").grid(row=0, column=0, sticky="ew", pady=(0, 6))
        figure_grid = ttk.Frame(figure_preview_frame)
        figure_grid.grid(row=1, column=0, sticky="nsew")
        figure_grid.grid_rowconfigure(0, weight=1)
        figure_grid.grid_columnconfigure(0, weight=1)
        self.figure_canvas = tk.Canvas(figure_grid, bg="#ffffff", highlightthickness=0)
        self.figure_canvas.grid(row=0, column=0, sticky="nsew")
        fig_y = ttk.Scrollbar(figure_grid, orient="vertical", command=self.figure_canvas.yview)
        fig_x = ttk.Scrollbar(figure_grid, orient="horizontal", command=self.figure_canvas.xview)
        fig_y.grid(row=0, column=1, sticky="ns")
        fig_x.grid(row=1, column=0, sticky="ew")
        self.figure_canvas.configure(yscrollcommand=fig_y.set, xscrollcommand=fig_x.set)


    def _build_characterization_tab(self):
        group = "characterization"
        tab = self._new_tab("Caracterizacion")
        box = self._section(tab, "Parametros", 0)

        self._add_combo(
            box,
            group,
            "df_name",
            "Dataset",
            [],
            "",
            0,
            0,
            dataset_combo=True
        )

        self._add_combo(
            box,
            group,
            "analysis_mode",
            "Modo",
            ["by_column", "full_matrix", "both"],
            "both",
            0,
            2
        )

        self._add_numeric_columns_dropdown(
            box,
            group,
            "numeric_cols",
            "Columnas numéricas",
            dataset_key="df_name",
            row=1,
            col=0,
            width=42
        )

        self._add_entry(
            box,
            group,
            "bins",
            "Bins",
            "80",
            1,
            2
        )

        self._add_check(
            box,
            group,
            "plot_positive_hist",
            "Graficar solo valores positivos",
            True,
            3,
            0
        )

        self._add_check(
            box,
            group,
            "verbose",
            "Mostrar resumen en log",
            True,
            3,
            2
        )

        self._run_button(tab, 1, "Ejecutar caracterizacion", lambda: self.run_analysis("characterization"))


    def _build_normality_tab(self):
        group = "normality"
        tab = self._new_tab("Normalidad")
        box = self._section(tab, "Parametros", 0)

        self._add_combo(
            box,
            group,
            "df_name",
            "Dataset",
            [],
            "",
            0,
            0,
            dataset_combo=True
        )

        self._add_combo(
            box,
            group,
            "analysis_mode",
            "Modo",
            ["by_column", "full_matrix", "both"],
            "both",
            0,
            2
        )

        self._add_numeric_columns_dropdown(
            box,
            group,
            "numeric_cols",
            "Columnas numéricas",
            dataset_key="df_name",
            row=1,
            col=0,
            width=42
        )

        self._add_combo(
            box,
            group,
            "value_mode",
            "Valores",
            ["all", "positive", "both"],
            "both",
            1,
            2
        )

        self._add_combo(
            box,
            group,
            "test_method",
            "Prueba",
            ["shapiro", "anderson", "both"],
            "both",
            2,
            0
        )

        self._add_entry(
            box,
            group,
            "alpha",
            "Alpha",
            "",
            2,
            2
        )

        self._add_check(
            box,
            group,
            "verbose",
            "Mostrar resumen en log",
            True,
            3,
            0
        )

        self._run_button(tab, 1, "Ejecutar normalidad", lambda: self.run_analysis("normality"))


    def _build_kde_tab(self):
        group = "kde"
        tab = self._new_tab("KDE")
        box = self._section(tab, "Parametros", 0)
        self._add_combo(box, group, "data_df_name", "Dataset OTU", [], dataset_combo=True)
        self._add_entry(box, group, "grid_size", "Grid size", "", 0, 2)
        self._add_entry(box, group, "cv_subsample", "CV subsample", "", 1, 0)
        self._add_entry(box, group, "cv_folds", "CV folds", "", 1, 2)
        self._add_entry(box, group, "cv_bw_grid", "CV BW grid", "", 2, 0)
        self._add_entry(box, group, "min_bandwidth", "Min bandwidth", "", 2, 2)
        self._add_entry(box, group, "cv_max_expansions", "Max expansions", "", 3, 0)
        self._add_entry(box, group, "test_kernel_bandwidths", "BW por kernel", "", 3, 2)
        self._add_check(box, group, "verbose", "Mostrar resumen en log", True, 4, 0)
        self._run_button(tab, 1, "Ejecutar KDE", lambda: self.run_analysis("kde"))


    def _build_kruskal_tab(self):
        group = "kruskal"
        tab = self._new_tab("Kruskal-Wallis")
        box = self._section(tab, "Parametros", 0)

        self._add_combo(
            box,
            group,
            "group_df_name",
            "Dataset grupos",
            [],
            "",
            0,
            0,
            dataset_combo=True
        )

        self._add_combo(
            box,
            group,
            "value_df_name",
            "Dataset valores",
            [],
            "",
            0,
            2,
            dataset_combo=True
        )

        self._add_combo(
            box,
            group,
            "group_col",
            "Columna grupo",
            [],
            "",
            1,
            0,
            column_for=("kruskal", "group_df_name")
        )

        self._add_combo(
            box,
            group,
            "id_col_group",
            "ID grupos",
            [],
            "",
            1,
            2,
            column_for=("kruskal", "group_df_name")
        )

        self._add_combo(
            box,
            group,
            "id_col_value",
            "ID valores",
            [],
            "",
            2,
            0,
            column_for=("kruskal", "value_df_name")
        )

        self._add_numeric_columns_dropdown(
            box,
            group,
            "value_cols",
            "Variables",
            dataset_key="value_df_name",
            row=2,
            col=2,
            width=42
        )

        self._add_entry(
            box,
            group,
            "alpha",
            "Alpha",
            "",
            3,
            0
        )

        self._add_entry(
            box,
            group,
            "min_group_size",
            "Min grupo",
            "",
            3,
            2
        )

        self._add_check(
            box,
            group,
            "apply_fdr",
            "Aplicar FDR",
            True,
            4,
            0
        )

        self._add_check(
            box,
            group,
            "verbose",
            "Mostrar resumen en log",
            True,
            4,
            2
        )

        self._run_button(
            tab,
            1,
            "Ejecutar Kruskal-Wallis",
            lambda: self.run_analysis("kruskal")
        )

    def _build_mann_whitney_tab(self):
        group = "mann_whitney"
        tab = self._new_tab("Mann-Whitney")
        box = self._section(tab, "Parametros", 0)

        self._add_combo(
            box,
            group,
            "group_df_name",
            "Dataset grupos",
            [],
            "",
            0,
            0,
            dataset_combo=True
        )

        self._add_combo(
            box,
            group,
            "value_df_name",
            "Dataset valores",
            [],
            "",
            0,
            2,
            dataset_combo=True
        )

        self._add_combo(
            box,
            group,
            "group_col",
            "Columna grupo",
            [],
            "",
            1,
            0,
            column_for=("mann_whitney", "group_df_name")
        )

        self._add_group_values_dropdown(
            box,
            group,
            "groups_to_compare",
            "Grupos",
            dataset_key="group_df_name",
            column_key="group_col",
            row=1,
            col=2,
            width=42
        )

        self._add_combo(
            box,
            group,
            "id_col_group",
            "ID grupos",
            [],
            "",
            2,
            0,
            column_for=("mann_whitney", "group_df_name")
        )

        self._add_combo(
            box,
            group,
            "id_col_value",
            "ID valores",
            [],
            "",
            2,
            2,
            column_for=("mann_whitney", "value_df_name")
        )

        self._add_numeric_columns_dropdown(
            box,
            group,
            "value_cols",
            "Variables",
            dataset_key="value_df_name",
            row=3,
            col=0,
            width=42
        )

        self._add_combo(
            box,
            group,
            "alternative",
            "Alternativa",
            ["two-sided", "less", "greater"],
            "two-sided",
            3,
            2
        )

        self._add_entry(
            box,
            group,
            "alpha",
            "Alpha",
            "",
            4,
            0
        )

        self._add_entry(
            box,
            group,
            "min_group_size",
            "Min grupo",
            "",
            4,
            2
        )

        self._add_check(
            box,
            group,
            "apply_fdr",
            "Aplicar FDR",
            True,
            5,
            0
        )

        self._add_check(
            box,
            group,
            "verbose",
            "Mostrar resumen en log",
            True,
            5,
            2
        )

        self._run_button(
            tab,
            1,
            "Ejecutar Mann-Whitney",
            lambda: self.run_analysis("mann_whitney")
        )


    def _build_dbscan_tab(self):
        group = "dbscan"
        tab = self._new_tab("DBSCAN")

        data_box = self._section(tab, "Datos y limpieza", 0)

        self._add_combo(
            data_box,
            group,
            "data_df_name",
            "Dataset datos",
            [],
            "",
            0,
            0,
            dataset_combo=True
        )

        self._add_combo(
            data_box,
            group,
            "id_col",
            "ID datos",
            [],
            "",
            0,
            2,
            column_for=("dbscan", "data_df_name")
        )

        self._add_numeric_columns_dropdown(
            data_box,
            group,
            "feature_cols",
            "Features numéricos",
            dataset_key="data_df_name",
            row=1,
            col=0,
            width=42
        )

        self._add_combo(
            data_box,
            group,
            "meta_df_name",
            "Dataset meta",
            [],
            "",
            1,
            2,
            dataset_combo=True
        )

        self._add_combo(
            data_box,
            group,
            "meta_id_col",
            "ID meta",
            [],
            "",
            2,
            0,
            column_for=("dbscan", "meta_df_name")
        )

        self._add_combo(
            data_box,
            group,
            "missing_strategy",
            "Faltantes",
            ["fill_zero", "drop_rows", "median"],
            "fill_zero",
            2,
            2
        )

        self._add_check(
            data_box,
            group,
            "drop_non_numeric",
            "Quitar no numéricas",
            True,
            3,
            0
        )

        self._add_check(
            data_box,
            group,
            "remove_zero_rows",
            "Quitar filas suma 0",
            True,
            3,
            2
        )

        self._add_entry(
            data_box,
            group,
            "min_prevalence",
            "Min prevalence",
            "",
            4,
            0
        )

        self._add_entry(
            data_box,
            group,
            "min_total_abundance",
            "Min abundance",
            "",
            4,
            2
        )

        model_box = self._section(tab, "Modelo", 1)

        self._add_entry(
            model_box,
            group,
            "eps",
            "eps",
            "",
            0,
            0
        )

        self._add_entry(
            model_box,
            group,
            "min_samples",
            "Min samples",
            "",
            0,
            2
        )

        self._add_combo(
            model_box,
            group,
            "transform_method",
            "Transformación",
            ["none", "log1p", "clr"],
            "none",
            1,
            0
        )

        self._add_entry(
            model_box,
            group,
            "pseudocount",
            "Pseudocount",
            "",
            1,
            2
        )

        self._add_check(
            model_box,
            group,
            "scale",
            "Escalar variables",
            True,
            2,
            0
        )

        self._add_combo(
            model_box,
            group,
            "embedding_method",
            "Embedding",
            ["none", "pca", "kpca", "isomap", "mds", "tsne", "umap"],
            "none",
            2,
            2
        )

        self._add_entry(
            model_box,
            group,
            "n_components",
            "Componentes",
            "",
            3,
            0
        )

        self._add_entry(
            model_box,
            group,
            "random_state",
            "Random state",
            "42",
            3,
            2
        )

        self._add_entry(
            model_box,
            group,
            "embedding_kwargs",
            "Embedding JSON",
            "",
            4,
            0
        )

        out_box = self._section(tab, "Figuras y resumen", 2)

        self._add_check(
            out_box,
            group,
            "calculate_k_distance",
            "Calcular k-distance",
            True,
            0,
            0
        )

        self._add_entry(
            out_box,
            group,
            "k_distance_min_samples",
            "K-distance min_samples",
            "",
            0,
            2
        )

        self._add_check(
            out_box,
            group,
            "plot_k_distance_graph",
            "Guardar figura k-distance",
            True,
            1,
            0
        )

        self._add_check(
            out_box,
            group,
            "plot_embedding_graph",
            "Guardar figura embedding",
            True,
            1,
            2
        )

        self._add_numeric_columns_dropdown(
            out_box,
            group,
            "summary_numeric_cols",
            "Resumen numérico",
            dataset_key="meta_df_name",
            row=2,
            col=0,
            width=42
        )

        self._add_categorical_columns_dropdown(
            out_box,
            group,
            "summary_categorical_cols",
            "Resumen categórico",
            dataset_key="meta_df_name",
            row=2,
            col=2,
            width=42
        )

        self._add_entry(
            out_box,
            group,
            "summary_numeric_aggs",
            "Agregaciones",
            "median",
            3,
            0
        )

        self._add_check(
            out_box,
            group,
            "verbose",
            "Mostrar resumen en log",
            True,
            3,
            2
        )

        self._run_button(
            tab,
            3,
            "Ejecutar DBSCAN",
            lambda: self.run_analysis("dbscan")
        )



    def load_files(self):
        paths = filedialog.askopenfilenames(
            title="Selecciona datasets",
            filetypes=[
                ("Archivos soportados", "*.csv *.otus *.txt *.meta *.taxonomy"),
                ("CSV", "*.csv"),
                ("Tabulados", "*.otus *.txt *.meta *.taxonomy"),
                ("Todos", "*.*"),
            ],
        )
        if not paths:
            return
        for path_text in paths:
            path = Path(path_text)
            try:
                df = load_dataframe_from_path(path)
                name = unique_name(path.stem, self.dfs)
                self.dfs[name] = df
                self._log(f"Cargado: {name} -> {df.shape}")
            except Exception as exc:
                self._log(f"Error cargando {path.name}: {exc}")
        self.refresh_datasets()


    def remove_selected_dataset(self):
        selected = self.dataset_tree.selection()
        if not selected:
            return
        for item in selected:
            name = self.dataset_tree.item(item, "text")
            self.dfs.pop(name, None)
            self._log(f"Dataset quitado de memoria: {name}")
        self.refresh_datasets()


    def preview_selected_dataset(self):
        selected = self.dataset_tree.selection()
        if not selected:
            messagebox.showinfo(APP_TITLE, "Selecciona un dataset para previsualizar.")
            return

        name = self.dataset_tree.item(selected[0], "text")
        df = self.dfs.get(name)
        if df is None:
            return

        top = tk.Toplevel(self)
        top.title(f"Vista previa - {name}")
        top.geometry("1100x580")
        top.minsize(850, 420)

        frame = ttk.Frame(top, padding=10)
        frame.pack(fill="both", expand=True)

        frame.grid_rowconfigure(1, weight=1)
        frame.grid_columnconfigure(0, weight=1)

        ttk.Label(
            frame,
            text=f"{name} | shape {df.shape}",
            font=("Segoe UI", 11, "bold")
        ).grid(row=0, column=0, sticky="w", pady=(0, 8))

        table_frame = ttk.Frame(frame)
        table_frame.grid(row=1, column=0, sticky="nsew")
        
        table_frame.grid_rowconfigure(0, weight=1)
        table_frame.grid_columnconfigure(0, weight=1)
        
        tree = ttk.Treeview(table_frame, show="headings")

        yscroll = ttk.Scrollbar(
            table_frame,
            orient="vertical",
            command=tree.yview
        )

        xscroll = ttk.Scrollbar(
            table_frame,
            orient="horizontal",
            command=tree.xview
        )

        tree.configure(
            yscrollcommand=yscroll.set,
            xscrollcommand=xscroll.set
        )

        tree.grid(row=0, column=0, sticky="nsew")
        yscroll.grid(row=0, column=1, sticky="ns")
        xscroll.grid(row=1, column=0, sticky="ew")

        preview = df.head(100).copy()

        max_cols = min(len(preview.columns), 80)

        columns = [str(c) for c in preview.columns[:max_cols]]
        tree["columns"] = columns

        for col in columns:
            tree.heading(col, text=col)
            tree.column(
                col,
                width=140,
                minwidth=90,
                stretch=False,
                anchor="w"
            )

        for _, row in preview.iloc[:, :max_cols].iterrows():
            values = []
                
            for v in row.tolist():
                if pd.isna(v):
                    values.append("")
                else:
                    values.append(str(v)[:160])

            tree.insert("", "end", values=values)

        tree.bind("<MouseWheel>", self._on_preview_dataset_mousewheel)
        tree.bind("<Shift-MouseWheel>", self._on_preview_dataset_shift_mousewheel)

        info_var = tk.StringVar(
            value=(
                f"Mostrando primeras {len(preview)} filas y primeras {max_cols} columnas. "
                "Usa la barra inferior o Shift + rueda para moverte lateralmente."
            )
        )

        ttk.Label(
            frame,
            textvariable=info_var,
            style="Subtle.TLabel"
        ).grid(row=2, column=0, sticky="ew", pady=(8, 0))

        
    def _on_preview_dataset_mousewheel(self, event):
        tree = event.widget

        if event.delta:
            tree.yview_scroll(int(-1 * (event.delta / 120)), "units")

        return "break"


    def _on_preview_dataset_shift_mousewheel(self, event):
        tree = event.widget
        
        if event.delta:
            tree.xview_scroll(int(-1 * (event.delta / 120)), "units")

        return "break"


    def refresh_datasets(self):
        for item in self.dataset_tree.get_children():
            self.dataset_tree.delete(item)

        for name, df in sorted(self.dfs.items()):
            self.dataset_tree.insert("", "end", text=name, values=(f"{df.shape[0]} x {df.shape[1]}",))

        names = sorted(self.dfs.keys())

        for combo in self.df_combos:
            current = combo.get()
            combo.configure(values=names)

            if names:
                if current not in names:
                    combo.set(names[0])
            else:
                combo.set("")

        self.refresh_columns()


    def refresh_columns(self):
        for combo, (group, dataset_key) in self.column_combos:
            dataset_name = self.inputs.get(group, {}).get(dataset_key, tk.StringVar()).get()
            df = self.dfs.get(dataset_name)
            combo.configure(values=[] if df is None else list(map(str, df.columns)))

        self.refresh_numeric_column_dropdowns()
        self.refresh_categorical_column_dropdowns()
        self.refresh_group_value_dropdowns()


    def load_manifest_file(self):
        path = filedialog.askopenfilename(
            title="Cargar manifest de una corrida",
            initialdir=self.output_dir_var.get() or str(DEFAULT_OUTPUT_DIR),
            filetypes=[("Manifest JSON", "manifest.json"), ("JSON", "*.json"), ("Todos", "*.*")],
        )
        if not path:
            return
        self._load_manifest_path(Path(path))


    def load_run_folder(self):
        path = filedialog.askdirectory(
            title="Cargar carpeta de resultados",
            initialdir=self.output_dir_var.get() or str(DEFAULT_OUTPUT_DIR),
        )
        if not path:
            return

        manifest_path = Path(path) / "manifest.json"
        if not manifest_path.exists():
            messagebox.showerror(APP_TITLE, f"La carpeta seleccionada no contiene manifest.json:\n{Path(path)}")
            return

        self._load_manifest_path(manifest_path)


    def load_saved_runs(self):
        output_root = Path(self.output_dir_var.get() or DEFAULT_OUTPUT_DIR).expanduser()
        if not output_root.exists():
            messagebox.showinfo(APP_TITLE, f"No existe la carpeta de salida:\n{output_root}")
            return

        manifest_paths = self._discover_manifest_paths(output_root)
        if not manifest_paths:
            messagebox.showinfo(APP_TITLE, f"No se encontraron corridas con manifest.json en:\n{output_root}")
            return

        loaded = 0
        selected_key = None
        for manifest_path in manifest_paths:
            key = self._load_manifest_path(manifest_path, select=False, quiet=True)
            if key:
                loaded += 1
                selected_key = selected_key or key

        if selected_key:
            self.result_tree.selection_set(selected_key)
            self.result_tree.focus(selected_key)
            self.show_result_key(selected_key)

        self._log(f"Historial cargado desde {output_root}: {loaded} corrida(s).")
        self.status_var.set(f"Historial cargado: {loaded} corrida(s).")


    def _discover_manifest_paths(self, output_root):
        output_root = Path(output_root)
        candidates = []

        direct_manifest = output_root / "manifest.json"
        if direct_manifest.exists():
            candidates.append(direct_manifest)

        candidates.extend(output_root.glob("*/manifest.json"))
        unique = {}
        for path in candidates:
            try:
                unique[str(path.resolve())] = path
            except OSError:
                unique[str(path)] = path

        return sorted(
            unique.values(),
            key=lambda item: item.stat().st_mtime if item.exists() else 0,
            reverse=True,
        )


    def _load_manifest_path(self, manifest_path, select=True, quiet=False):
        manifest_path = Path(manifest_path)
        try:
            manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
        except Exception as exc:
            if not quiet:
                messagebox.showerror(APP_TITLE, f"No se pudo leer el manifest:\n{exc}")
            return None

        key = self._register_result_manifest(
            manifest=manifest,
            run_dir=manifest_path.parent,
            result=None,
            manifest_path=manifest_path,
            select=select,
        )
        if key and not quiet:
            self._log(f"Manifest cargado: {manifest_path}")
        return key


    def _register_result_manifest(self, manifest, run_dir, result=None, manifest_path=None, select=True):
        run_dir = Path(run_dir)
        manifest_path = Path(manifest_path) if manifest_path else run_dir / "manifest.json"

        existing_key = self._existing_result_key_for_manifest(manifest_path)
        if existing_key:
            if select:
                self.result_tree.selection_set(existing_key)
                self.result_tree.focus(existing_key)
                self.show_result_key(existing_key)
            return existing_key

        key = unique_name(self._result_key_from_manifest(manifest, run_dir), self.result_manifests)
        self.results[key] = result
        self.result_manifests[key] = manifest
        self.result_run_dirs[key] = run_dir
        self.result_tree.insert("", "end", iid=key, text=key, values=(self._format_result_created(manifest, manifest_path),))

        if select:
            self.result_tree.selection_set(key)
            self.result_tree.focus(key)
            self.show_result_key(key)

        return key


    def _existing_result_key_for_manifest(self, manifest_path):
        try:
            target = Path(manifest_path).resolve()
        except OSError:
            target = Path(manifest_path)

        for key, run_dir in self.result_run_dirs.items():
            try:
                current = (Path(run_dir) / "manifest.json").resolve()
            except OSError:
                current = Path(run_dir) / "manifest.json"
            if current == target:
                return key
        return None


    def _result_key_from_manifest(self, manifest, run_dir):
        analysis = manifest.get("analysis") or Path(run_dir).name or "resultado"
        created = str(manifest.get("created_at", "")).strip()
        stamp = ""
        if created:
            try:
                stamp = _dt.datetime.fromisoformat(created).strftime("%Y%m%d_%H%M%S")
            except ValueError:
                stamp = sanitize_name(created, "")
        if not stamp:
            stamp = sanitize_name(Path(run_dir).name, _dt.datetime.now().strftime("%Y%m%d_%H%M%S"))
        return sanitize_name(f"{analysis}_{stamp}", "resultado")


    def _format_result_created(self, manifest, manifest_path=None):
        created = str(manifest.get("created_at", "")).strip()
        if created:
            try:
                return _dt.datetime.fromisoformat(created).strftime("%Y-%m-%d %H:%M")
            except ValueError:
                return created[:16]

        if manifest_path:
            try:
                return _dt.datetime.fromtimestamp(Path(manifest_path).stat().st_mtime).strftime("%Y-%m-%d %H:%M")
            except OSError:
                pass

        return _dt.datetime.now().strftime("%Y-%m-%d %H:%M")


    def on_result_selected(self, _event=None):
        selected = self.result_tree.selection()
        if not selected:
            return
        self.show_result_key(selected[0])


    def show_result_key(self, key):
        manifest = self.result_manifests.get(key)
        if not manifest:
            return

        self.loading_result_view = True

        try:
            self.active_result_key = key
            self.visible_tables = {}
            self.visible_figures = {}
            self.current_table_path = None
            self.current_figure_path = None

            for item in self.table_list.get_children():
                self.table_list.delete(item)

            for item in self.figure_list.get_children():
                self.figure_list.delete(item)

            run_dir = self.result_run_dirs.get(key)
            analysis = manifest.get("analysis", key)
            created = manifest.get("created_at", "")
            self.results_title_var.set(f"{analysis} | {created} | {run_dir}")

            for i, table in enumerate(manifest.get("tables", []), start=1):
                iid = f"{key}_table_{i}"
                self.visible_tables[iid] = table
                name = table.get("name") or Path(table.get("path", "")).name
                rows = table.get("rows", "")
                cols = table.get("columns", "")

                self.table_list.insert(
                    "",
                    "end",
                    iid=iid,
                    text=name,
                    values=(rows, cols)
                )

            for i, array in enumerate(manifest.get("arrays", []), start=1):
                path = self._artifact_path(array.get("path", ""))
                if path.suffix.lower() != ".csv":
                    continue

                shape = array.get("shape", [])
                rows = shape[0] if len(shape) >= 1 else ""
                cols = shape[1] if len(shape) >= 2 else 1
                table = {
                    "name": f"{array.get('name', path.stem)} (array)",
                    "path": array.get("path", str(path)),
                    "rows": rows,
                    "columns": cols,
                }
                iid = f"{key}_array_{i}"
                self.visible_tables[iid] = table
                self.table_list.insert(
                    "",
                    "end",
                    iid=iid,
                    text=table["name"],
                    values=(rows, cols)
                )

            for i, figure_path in enumerate(manifest.get("figures", []), start=1):
                iid = f"{key}_figure_{i}"
                path = self._artifact_path(figure_path)
                self.visible_figures[iid] = path

                self.figure_list.insert(
                    "",
                    "end",
                    iid=iid,
                    text=path.name
                )

            table_items = self.table_list.get_children()
            figure_items = self.figure_list.get_children()

            if table_items:
                first_table = table_items[0]
                self.table_list.selection_set(first_table)
                self.table_list.focus(first_table)
                self.table_list.see(first_table)
            else:
                self.clear_table_preview("Esta corrida no tiene tablas exportadas.")

            if figure_items:
                first_figure = figure_items[0]
                self.figure_list.selection_set(first_figure)
                self.figure_list.focus(first_figure)
                self.figure_list.see(first_figure)
            else:
                self.clear_figure_preview("Esta corrida no tiene figuras exportadas.")

            self.notebook.select(self.results_tab)

            if self.results_lists_notebook is not None:
                current_left_tab = self.results_lists_notebook.index("current")

                if current_left_tab == 0 and table_items:
                    self.show_current_table_selection()
                elif current_left_tab == 1 and figure_items:
                    self.show_current_figure_selection()
                elif table_items:
                    self.results_lists_notebook.select(0)
                    self.show_current_table_selection()
                elif figure_items:
                    self.results_lists_notebook.select(1)
                    self.show_current_figure_selection()

        finally:
            self.loading_result_view = False


    def refresh_active_result_view(self):
        if self.active_result_key:
            self.show_result_key(self.active_result_key)


    def on_table_selected(self, _event=None):
        if self.loading_result_view:
            return

        self.show_current_table_selection()


    def on_figure_selected(self, _event=None):
        if self.loading_result_view:
            return

        self.show_current_figure_selection()


    def on_result_list_tab_changed(self, _event=None):
        if self.loading_result_view:
            return

        if self.results_lists_notebook is None:
            return

        current_tab = self.results_lists_notebook.index("current")

        if current_tab == 0:
            self.show_current_table_selection()
        elif current_tab == 1:
            self.show_current_figure_selection()


    def show_current_table_selection(self):
        selected = self.table_list.selection()

        if selected:
            iid = selected[0]
        else:
            iid = self.table_list.focus()

        if not iid:
            table_items = self.table_list.get_children()

            if not table_items:
                self.clear_table_preview("No hay tablas disponibles.")
                return

            iid = table_items[0]
            self.table_list.selection_set(iid)
            self.table_list.focus(iid)
            self.table_list.see(iid)

        table = self.visible_tables.get(iid)

        if table is None:
            return

        self.show_table_preview(table)
        self.preview_notebook.select(0)


    def show_current_figure_selection(self):
        selected = self.figure_list.selection()

        if selected:
            iid = selected[0]
        else:
            iid = self.figure_list.focus()

        if not iid:
            figure_items = self.figure_list.get_children()

            if not figure_items:
                self.clear_figure_preview("No hay figuras disponibles.")
                return

            iid = figure_items[0]
            self.figure_list.selection_set(iid)
            self.figure_list.focus(iid)
            self.figure_list.see(iid)

        path = self.visible_figures.get(iid)

        if path is None:
            return

        self.show_figure_preview(path)
        self.preview_notebook.select(1)


    def _artifact_path(self, path_text):
        path = Path(path_text)
        if path.is_absolute():
            return path
        if path.exists():
            return path
        run_dir = self.result_run_dirs.get(self.active_result_key)
        if run_dir:
            return run_dir / path
        return path


    def clear_table_preview(self, message):
        for item in self.table_preview.get_children():
            self.table_preview.delete(item)
        self.table_preview["columns"] = []
        self.table_info_var.set(message)
        self.current_table_path = None


    def show_table_preview(self, table):
        path = self._artifact_path(table.get("path", ""))
        self.current_table_path = path
        if not path.exists():
            self.clear_table_preview(f"No existe el archivo: {path}")
            return
        try:
            df = pd.read_csv(path, nrows=500)
        except Exception as exc:
            self.clear_table_preview(f"No se pudo leer la tabla: {exc}")
            return

        for item in self.table_preview.get_children():
            self.table_preview.delete(item)

        max_cols = min(len(df.columns), 80)
        column_ids = [f"c{i}" for i in range(max_cols)]
        self.table_preview["columns"] = column_ids
        for i, col in enumerate(df.columns[:max_cols]):
            label = str(col)
            width = max(90, min(220, 8 * len(label) + 30))
            self.table_preview.heading(column_ids[i], text=label)
            self.table_preview.column(column_ids[i], width=width, stretch=False)

        for _, row in df.iloc[:, :max_cols].iterrows():
            values = []
            for value in row.tolist():
                if pd.isna(value):
                    values.append("")
                else:
                    text = str(value)
                    values.append(text[:160])
            self.table_preview.insert("", "end", values=values)

        rows = table.get("rows", "?")
        cols = table.get("columns", "?")
        rows_count = int(rows) if str(rows).isdigit() else None
        cols_count = int(cols) if str(cols).isdigit() else None
        suffix = ""
        if rows_count is not None and rows_count > 500:
            suffix += " | mostrando primeras 500 filas"
        if cols_count is not None and cols_count > max_cols:
            suffix += f" | mostrando primeras {max_cols} columnas"
        self.table_info_var.set(f"{table.get('name', path.name)} | {rows} x {cols} | {path}{suffix}")
        self.preview_notebook.select(0)


    def clear_figure_preview(self, message):
        self.figure_canvas.delete("all")
        self.figure_canvas.configure(scrollregion=(0, 0, 0, 0))
        self.figure_info_var.set(message)
        self.current_figure_path = None
        self.figure_image_ref = None


    def show_figure_preview(self, path):
        path = Path(path)
        self.current_figure_path = path
        self.figure_canvas.delete("all")
        if not path.exists():
            self.clear_figure_preview(f"No existe la figura: {path}")
            return

        try:
            if HAS_PIL:
                image = Image.open(path)
                self.figure_canvas.update_idletasks()
                max_w = max(760, self.figure_canvas.winfo_width() - 30)
                max_h = max(520, self.figure_canvas.winfo_height() - 30)
                ratio = min(max_w / image.width, max_h / image.height, 1.0)
                size = (max(1, int(image.width * ratio)), max(1, int(image.height * ratio)))
                if size != image.size:
                    image = image.resize(size, Image.LANCZOS)
                self.figure_image_ref = ImageTk.PhotoImage(image)
            else:
                self.figure_image_ref = tk.PhotoImage(file=str(path))
                size = (self.figure_image_ref.width(), self.figure_image_ref.height())
        except Exception as exc:
            self.clear_figure_preview(f"No se pudo abrir la figura: {exc}")
            return

        self.figure_canvas.create_image(12, 12, anchor="nw", image=self.figure_image_ref)
        self.figure_canvas.configure(scrollregion=(0, 0, size[0] + 24, size[1] + 24))
        self.figure_info_var.set(f"{path.name} | {path}")
        self.preview_notebook.select(1)


    def open_selected_result_file(self):
        current_preview = self.preview_notebook.index("current")
        path = self.current_figure_path if current_preview == 1 else self.current_table_path
        if path is None:
            selected_fig = self.figure_list.selection()
            selected_table = self.table_list.selection()
            if selected_fig:
                path = self.visible_figures.get(selected_fig[0])
            elif selected_table:
                table = self.visible_tables.get(selected_table[0], {})
                path = self._artifact_path(table.get("path", ""))
        if path is None:
            messagebox.showinfo(APP_TITLE, "Selecciona una tabla o figura.")
            return
        try:
            os.startfile(path)
        except Exception as exc:
            messagebox.showerror(APP_TITLE, f"No se pudo abrir el archivo:\n{exc}")


    def open_active_run_dir(self):
        path = None
        if self.active_result_key:
            path = self.result_run_dirs.get(self.active_result_key)
        if path is None:
            path = self.last_run_dir
        if path is None:
            path = Path(self.output_dir_var.get()).expanduser()
        try:
            Path(path).mkdir(parents=True, exist_ok=True)
            os.startfile(path)
        except Exception as exc:
            messagebox.showerror(APP_TITLE, f"No se pudo abrir la carpeta:\n{exc}")


    def choose_output_dir(self):
        path = filedialog.askdirectory(title="Carpeta de salida", initialdir=self.output_dir_var.get() or str(DEFAULT_OUTPUT_DIR))
        if path:
            self.output_dir_var.set(path)


    def open_output_dir(self):
        path = Path(self.output_dir_var.get()).expanduser()
        path.mkdir(parents=True, exist_ok=True)
        try:
            os.startfile(path)
        except Exception as exc:
            messagebox.showerror(APP_TITLE, f"No se pudo abrir la carpeta:\n{exc}")


    def run_analysis(self, analysis):
        if self.worker and self.worker.is_alive():
            messagebox.showinfo(APP_TITLE, "Ya hay un analisis en ejecucion.")
            return
        if not self.dfs:
            messagebox.showinfo(APP_TITLE, "Carga al menos un dataset antes de ejecutar.")
            return
        self.refresh_columns()
        try:
            params = self._collect_params(analysis)
            output_root = Path(self.output_dir_var.get()).expanduser()
        except Exception as exc:
            messagebox.showerror(APP_TITLE, f"Revisa los parametros:\n{exc}")
            return
        self.status_var.set(f"Ejecutando {analysis}...")
        self._log(f"\n=== Ejecutando {analysis} ===")
        self.worker = threading.Thread(target=self._worker_run, args=(analysis, params, output_root), daemon=True)
        self.worker.start()


    def _worker_run(self, analysis, params, output_root):
        try:
            output_root.mkdir(parents=True, exist_ok=True)
            stamp = _dt.datetime.now().strftime("%Y%m%d_%H%M%S")
            run_dir = output_root / f"{stamp}_{sanitize_name(analysis)}"
            run_dir.mkdir(parents=True, exist_ok=True)
            figure_dir = run_dir / "figures"

            stdout = io.StringIO()
            with contextlib.redirect_stdout(stdout), contextlib.redirect_stderr(stdout), FigureCapture(figure_dir) as figs:
                result = self._execute(analysis, params)

            log_text = stdout.getvalue()
            if log_text:
                (run_dir / "execution_log.txt").write_text(log_text, encoding="utf-8")

            exporter = ArtifactExporter(run_dir)
            manifest = exporter.export(result, prefix=analysis)
            manifest.update({
                "analysis": analysis,
                "created_at": _dt.datetime.now().isoformat(timespec="seconds"),
                "parameters": json_safe(params),
                "figures": [str(p) for p in figs.saved],
            })
            with (run_dir / "manifest.json").open("w", encoding="utf-8") as fh:
                json.dump(manifest, fh, ensure_ascii=False, indent=2)
            with (run_dir / "parameters.json").open("w", encoding="utf-8") as fh:
                json.dump(json_safe(params), fh, ensure_ascii=False, indent=2)

            self.msg_queue.put(("done", analysis, result, run_dir, manifest, log_text))
        except Exception:
            self.msg_queue.put(("error", analysis, traceback.format_exc()))


    def _collect_params(self, analysis):
        values = {key: var.get() for key, var in self.inputs[analysis].items()}

        if analysis == "characterization":
            return {
                "df_name": values["df_name"],
                "numeric_cols": split_list(values["numeric_cols"]),
                "analysis_mode": values["analysis_mode"],
                "bins": int(values["bins"]),
                "plot_positive_hist": parse_bool(values["plot_positive_hist"]),
                "verbose": parse_bool(values["verbose"]),
            }

        if analysis == "normality":
            return {
                "df_name": values["df_name"],
                "numeric_cols": split_list(values["numeric_cols"]),
                "analysis_mode": values["analysis_mode"],
                "value_mode": values["value_mode"],
                "test_method": values["test_method"],
                "alpha": float(values["alpha"]),
                "verbose": parse_bool(values["verbose"]),
            }

        if analysis == "kde":
            return {
                "data_df_name": values["data_df_name"],
                "grid_size": int(values["grid_size"]),
                "cv_subsample": int(values["cv_subsample"]),
                "cv_folds": int(values["cv_folds"]),
                "cv_bw_grid": int(values["cv_bw_grid"]),
                "min_bandwidth": float(values["min_bandwidth"]),
                "cv_max_expansions": int(values["cv_max_expansions"]),
                "test_kernel_bandwidths": parse_bandwidths(values["test_kernel_bandwidths"]),
                "verbose": parse_bool(values["verbose"]),
            }

        if analysis == "kruskal":
            return {
                "alpha": float(values["alpha"]),
                "group_df_name": values["group_df_name"],
                "value_df_name": values["value_df_name"],
                "group_col": values["group_col"],
                "id_col_group": values["id_col_group"],
                "id_col_value": values["id_col_value"],
                "value_cols": split_list(values["value_cols"]),
                "min_group_size": int(values["min_group_size"]),
                "apply_fdr": parse_bool(values["apply_fdr"]),
                "verbose": parse_bool(values["verbose"]),
            }

        if analysis == "mann_whitney":
            groups = split_list(values["groups_to_compare"])
            return {
                "alpha": float(values["alpha"]),
                "group_df_name": values["group_df_name"],
                "value_df_name": values["value_df_name"],
                "group_col": values["group_col"],
                "groups_to_compare": tuple(groups) if groups else None,
                "id_col_group": values["id_col_group"],
                "id_col_value": values["id_col_value"],
                "value_cols": split_list(values["value_cols"]),
                "min_group_size": int(values["min_group_size"]),
                "alternative": values["alternative"],
                "apply_fdr": parse_bool(values["apply_fdr"]),
                "verbose": parse_bool(values["verbose"]),
            }

        if analysis == "dbscan":
            meta_df_name = values["meta_df_name"].strip() or None
            return {
                "data_df_name": values["data_df_name"],
                "id_col": values["id_col"].strip() or None,
                "feature_cols": split_list(values["feature_cols"]),
                "meta_df_name": meta_df_name,
                "meta_id_col": values["meta_id_col"].strip() or None,
                "eps": float(values["eps"]),
                "min_samples": int(values["min_samples"]),
                "calculate_k_distance": parse_bool(values["calculate_k_distance"]),
                "k_distance_min_samples": int(values["k_distance_min_samples"]),
                "drop_non_numeric": parse_bool(values["drop_non_numeric"]),
                "missing_strategy": values["missing_strategy"],
                "remove_zero_rows": parse_bool(values["remove_zero_rows"]),
                "min_prevalence": parse_optional_float(values["min_prevalence"]),
                "min_total_abundance": parse_optional_float(values["min_total_abundance"]),
                "transform_method": values["transform_method"],
                "pseudocount": float(values["pseudocount"]),
                "scale": parse_bool(values["scale"]),
                "embedding_method": values["embedding_method"],
                "n_components": int(values["n_components"]),
                "random_state": int(values["random_state"]),
                "embedding_kwargs": parse_json_dict(values["embedding_kwargs"]),
                "plot_k_distance_graph": parse_bool(values["plot_k_distance_graph"]),
                "plot_embedding_graph": parse_bool(values["plot_embedding_graph"]),
                "summary_numeric_cols": split_list(values["summary_numeric_cols"]),
                "summary_categorical_cols": split_list(values["summary_categorical_cols"]),
                "summary_numeric_aggs": parse_tuple(values["summary_numeric_aggs"]) or ("median",),
                "verbose": parse_bool(values["verbose"]),
            }

        raise ValueError(f"Analisis desconocido: {analysis}")


    def _execute(self, analysis, params):
        if analysis == "characterization":
            return distribution_plots_from_loaded(dfs=self.dfs, **params)
        if analysis == "normality":
            return normality_tests_from_loaded(dfs=self.dfs, **params)
        if analysis == "kde":
            return kde_from_loaded(dfs=self.dfs, **params)
        if analysis == "kruskal":
            return kruskal_wallis_from_loaded(dfs=self.dfs, **params)
        if analysis == "mann_whitney":
            return mann_whitney_from_loaded(dfs=self.dfs, **params)
        if analysis == "dbscan":
            return dbscan_from_loaded(dfs=self.dfs, **params)
        raise ValueError(f"Analisis desconocido: {analysis}")


    def _poll_queue(self):
        try:
            while True:
                message = self.msg_queue.get_nowait()
                kind = message[0]
                if kind == "done":
                    _, analysis, result, run_dir, manifest, log_text = message
                    self.last_run_dir = Path(run_dir)
                    key = self._register_result_manifest(
                        manifest=manifest,
                        run_dir=run_dir,
                        result=result,
                        manifest_path=Path(run_dir) / "manifest.json",
                        select=True,
                    )
                    if log_text:
                        self._log(log_text.rstrip())
                    self._log(f"Terminado: {analysis}")
                    self._log(f"Salida: {run_dir}")
                    self._log(f"Tablas: {len(manifest.get('tables', []))} | Arrays: {len(manifest.get('arrays', []))} | Figuras: {len(manifest.get('figures', []))}")
                    self.status_var.set(f"Listo. Ultima salida: {run_dir}")
                elif kind == "error":
                    _, analysis, trace = message
                    self._log(f"Error en {analysis}:\n{trace}")
                    self.status_var.set(f"Error en {analysis}")
                    messagebox.showerror(APP_TITLE, f"El analisis fallo. Revisa el log.\n\n{trace.splitlines()[-1]}")
        except queue.Empty:
            pass
        self.after(150, self._poll_queue)

    def _log(self, text):
        self.log_text.insert("end", str(text) + "\n")
        self.log_text.see("end")



def main():
    app = MicrobiotaGUI()
    app.mainloop()


if __name__ == "__main__":
    main()
