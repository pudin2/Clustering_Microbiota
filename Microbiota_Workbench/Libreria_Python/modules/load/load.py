import pandas as pd
import tkinter as tk

from tkinter import filedialog
from pathlib import Path


def load_dataframe_from_path(path):
    path = Path(path)

    if not path.exists():
        raise FileNotFoundError(f"No existe el archivo: {path}")

    ext = path.suffix.lower()

    if ext == ".csv":
        df = pd.read_csv(path, delimiter=",")
        
    elif ext in [".otus", ".txt", ".meta", ".taxonomy"]:
        df = pd.read_csv(path, sep="\t")
        
    else:
        raise ValueError(
            f"Formato no soportado: {ext}. "
            "Usa archivos .csv, .otus, .txt, .meta o .taxonomy"
        )

    return df


def load_multiple_dataframes():
    root = tk.Tk()
    root.withdraw()  
    root.attributes("-topmost", True)  

    file_paths = filedialog.askopenfilenames(
        title="Selecciona uno o varios datasets",
        filetypes=[
            ("Archivos soportados", "*.csv *.otus *.txt *.meta *.taxonomy"),
            ("CSV", "*.csv"),
            ("OTUS", "*.otus"),
            ("TXT", "*.txt"),
            ("META", "*.meta"),
            ("TAXONOMY", "*.taxonomy"),
            ("Todos los archivos", "*.*")
        ]
    )

    if not file_paths:
        print("No se seleccionó ningún archivo.")
        return {}

    dataframes = {}

    for file_path in file_paths:
        path = Path(file_path)
        try:
            df = load_dataframe_from_path(path)
            dataframes[path.stem] = df
            print(f"Cargado: {path.name} -> shape {df.shape}")
        except Exception as e:
            print(f"Error al cargar {path.name}: {e}")

    return dataframes