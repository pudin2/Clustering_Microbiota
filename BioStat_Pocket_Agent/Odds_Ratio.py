import pandas as pd
import numpy as np
import tkinter as tk
from tkinter import filedialog
from pathlib import Path
from scipy.stats import fisher_exact


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


def load_single_dataframe():
    root = tk.Tk()
    root.withdraw()
    root.attributes("-topmost", True)

    file_path = filedialog.askopenfilename(
        title="Selecciona el CSV completo con OTUs y hidden_blood",
        filetypes=[
            ("Archivos soportados", "*.csv *.otus *.txt *.meta *.taxonomy"),
            ("CSV", "*.csv"),
            ("Todos los archivos", "*.*")
        ]
    )

    if not file_path:
        print("No se seleccionó ningún archivo.")
        return None

    df = load_dataframe_from_path(file_path)
    print(f"Cargado: {Path(file_path).name} -> shape {df.shape}")

    return df


def detect_blood_column(df):
    """
    Detecta automáticamente si la columna se llama:
    hidden_blood o hiden_blood.
    """

    possible_cols = ["hidden_blood", "hiden_blood"]

    for col in possible_cols:
        if col in df.columns:
            return col

    raise KeyError(
        "No se encontró la columna de sangre oculta. "
        "Debe llamarse 'hidden_blood' o 'hiden_blood'. "
        f"Columnas disponibles: {list(df.columns)}"
    )


def calculate_odds_ratio_ci(a, b, c, d):
    """
    Tabla 2x2 usada:

                      Evento sí     Evento no
    Positive             a             b
    Negative             c             d

    OR = (a/b) / (c/d) = (a*d)/(b*c)

    Si alguna celda es cero, se aplica corrección de Haldane-Anscombe:
    sumar 0.5 a todas las celdas para calcular OR e IC.
    """

    cells = np.array([a, b, c, d], dtype=float)

    correction_applied = False

    if np.any(cells == 0):
        cells = cells + 0.5
        correction_applied = True

    a_c, b_c, c_c, d_c = cells

    odds_ratio = (a_c * d_c) / (b_c * c_c)

    log_or = np.log(odds_ratio)

    se_log_or = np.sqrt(
        (1 / a_c) +
        (1 / b_c) +
        (1 / c_c) +
        (1 / d_c)
    )

    ci_lower = np.exp(log_or - 1.96 * se_log_or)
    ci_upper = np.exp(log_or + 1.96 * se_log_or)

    return odds_ratio, ci_lower, ci_upper, correction_applied


def interpret_or(odds_ratio, ci_lower, ci_upper):
    if pd.isna(odds_ratio):
        return "No interpretable"

    if ci_lower <= 1 <= ci_upper:
        direction = "El intervalo de confianza incluye 1; la asociación no es concluyente."
    else:
        direction = "El intervalo de confianza no incluye 1; la asociación es más consistente."

    if odds_ratio > 1:
        return (
            "OR > 1: el evento del OTU es más frecuente en sangre oculta positiva. "
            + direction
        )
    elif odds_ratio < 1:
        return (
            "OR < 1: el evento del OTU es menos frecuente en sangre oculta positiva. "
            + direction
        )
    else:
        return (
            "OR = 1: no hay diferencia aparente en la frecuencia del evento. "
            + direction
        )


def build_otu_2x2_tables_from_complete_df(
    df,
    otu_cols=("Otu00043", "Otu00036"),
    id_col="ID",
    blood_col=None,
    positive_label="Positive",
    negative_label="Negative"
):
    df = df.copy()

    if blood_col is None:
        blood_col = detect_blood_column(df)

    required_cols = [id_col, blood_col] + list(otu_cols)

    for col in required_cols:
        if col not in df.columns:
            raise KeyError(
                f"No existe la columna '{col}' en el archivo cargado. "
                f"Columnas disponibles: {list(df.columns)}"
            )

    df[blood_col] = df[blood_col].astype(str).str.strip()

    working_df = df[
        df[blood_col].isin([positive_label, negative_label])
    ][required_cols].copy()

    count_rows = []
    summary_rows = []

    for otu_col in otu_cols:
        working_df[otu_col] = pd.to_numeric(
            working_df[otu_col],
            errors="coerce"
        ).fillna(0)

        positive_abundance_values = working_df.loc[
            working_df[otu_col] > 0,
            otu_col
        ]

        if len(positive_abundance_values) > 0:
            high_threshold = positive_abundance_values.quantile(0.75)
        else:
            high_threshold = np.nan

        criteria = [
            {
                "analysis_type": "Presencia / ausencia del OTU",
                "event_definition": "El OTU se considera PRESENTE cuando su abundancia es mayor o igual a 1",
                "no_event_definition": "El OTU se considera AUSENTE cuando su abundancia es igual a 0",
                "threshold_used": 1,
                "event_series": working_df[otu_col] >= 1
            },
            {
                "analysis_type": "Alta abundancia / no alta abundancia del OTU",
                "event_definition": "El OTU se considera en ALTA ABUNDANCIA cuando su abundancia es mayor o igual al percentil 75 de sus valores positivos",
                "no_event_definition": "El OTU se considera en NO ALTA ABUNDANCIA cuando su abundancia está por debajo del percentil 75 de sus valores positivos",
                "threshold_used": high_threshold,
                "event_series": (
                    working_df[otu_col] >= high_threshold
                    if not np.isnan(high_threshold)
                    else pd.Series(False, index=working_df.index)
                )
            }
        ]

        for item in criteria:
            analysis_type = item["analysis_type"]
            event_definition = item["event_definition"]
            no_event_definition = item["no_event_definition"]
            threshold_used = item["threshold_used"]
            event_series = item["event_series"]

            temp = working_df.copy()
            temp["evento_otu"] = event_series

            # Tabla 2x2:
            # a = sangre oculta positiva y evento del OTU
            # b = sangre oculta positiva y NO evento del OTU
            # c = sangre oculta negativa y evento del OTU
            # d = sangre oculta negativa y NO evento del OTU

            a = int(((temp[blood_col] == positive_label) & (temp["evento_otu"] == True)).sum())
            b = int(((temp[blood_col] == positive_label) & (temp["evento_otu"] == False)).sum())
            c = int(((temp[blood_col] == negative_label) & (temp["evento_otu"] == True)).sum())
            d = int(((temp[blood_col] == negative_label) & (temp["evento_otu"] == False)).sum())

            positive_total = a + b
            negative_total = c + d

            positive_event_pct = (a / positive_total * 100) if positive_total > 0 else np.nan
            negative_event_pct = (c / negative_total * 100) if negative_total > 0 else np.nan

            odds_ratio, ci_lower, ci_upper, correction_applied = calculate_odds_ratio_ci(
                a, b, c, d
            )

            fisher_table = [[a, b], [c, d]]
            fisher_or, fisher_p_value = fisher_exact(
                fisher_table,
                alternative="two-sided"
            )

            # ============================
            # TABLA 1: CONTEOS CLAROS
            # ============================

            count_rows.append({
                "OTU analizado": otu_col,
                "Tipo de análisis": analysis_type,
                "Umbral usado para definir el evento": threshold_used,
                "Grupo de sangre oculta": "Sangre oculta POSITIVA",
                "Definición del evento del OTU": event_definition,
                "Número de personas CON evento del OTU": a,
                "Definición del no evento del OTU": no_event_definition,
                "Número de personas SIN evento del OTU": b,
                "Total de personas en este grupo de sangre oculta": positive_total,
                "Porcentaje de personas CON evento del OTU en este grupo": positive_event_pct
            })

            count_rows.append({
                "OTU analizado": otu_col,
                "Tipo de análisis": analysis_type,
                "Umbral usado para definir el evento": threshold_used,
                "Grupo de sangre oculta": "Sangre oculta NEGATIVA",
                "Definición del evento del OTU": event_definition,
                "Número de personas CON evento del OTU": c,
                "Definición del no evento del OTU": no_event_definition,
                "Número de personas SIN evento del OTU": d,
                "Total de personas en este grupo de sangre oculta": negative_total,
                "Porcentaje de personas CON evento del OTU en este grupo": negative_event_pct
            })

            # ============================
            # TABLA 2: RESUMEN OR + IC95
            # ============================

            summary_rows.append({
                "OTU analizado": otu_col,
                "Tipo de análisis": analysis_type,
                "Qué significa el evento del OTU": event_definition,
                "Umbral usado para definir el evento": threshold_used,

                "a: Sangre oculta POSITIVA y CON evento del OTU": a,
                "b: Sangre oculta POSITIVA y SIN evento del OTU": b,
                "c: Sangre oculta NEGATIVA y CON evento del OTU": c,
                "d: Sangre oculta NEGATIVA y SIN evento del OTU": d,

                "Total con sangre oculta POSITIVA": positive_total,
                "Total con sangre oculta NEGATIVA": negative_total,

                "% con evento del OTU entre sangre oculta POSITIVA": positive_event_pct,
                "% con evento del OTU entre sangre oculta NEGATIVA": negative_event_pct,

                "Odds Ratio OR": odds_ratio,
                "Límite inferior IC 95% del OR": ci_lower,
                "Límite superior IC 95% del OR": ci_upper,
                "p-valor prueba exacta de Fisher": fisher_p_value,

                "¿Se aplicó corrección 0.5 por celdas en cero?": (
                    "Sí" if correction_applied else "No"
                ),

                "Interpretación del OR": interpret_or(odds_ratio, ci_lower, ci_upper)
            })

    count_table = pd.DataFrame(count_rows)
    summary_table = pd.DataFrame(summary_rows)

    return working_df, count_table, summary_table


def save_tables_to_csv(count_table, summary_table):
    root = tk.Tk()
    root.withdraw()
    root.attributes("-topmost", True)

    output_dir = filedialog.askdirectory(
        title="Selecciona la carpeta donde guardar las tablas CSV"
    )

    if not output_dir:
        output_dir = "."

    output_dir = Path(output_dir)

    count_path = output_dir / "tabla_2x2_conteos_clara_otu_sangre_oculta.csv"
    summary_path = output_dir / "tabla_2x2_or_ic95_clara_otu_sangre_oculta.csv"

    count_table.to_csv(count_path, index=False, encoding="utf-8-sig")
    summary_table.to_csv(summary_path, index=False, encoding="utf-8-sig")

    print("\nArchivos generados correctamente:")
    print(count_path)
    print(summary_path)

    return count_path, summary_path


# ==============================
# EJECUCIÓN PRINCIPAL
# ==============================

df_complete = load_single_dataframe()

if df_complete is not None:
    merged_otu_blood, count_table, summary_table = build_otu_2x2_tables_from_complete_df(
        df=df_complete,
        otu_cols=("Otu00043", "Otu00036"),
        id_col="ID",
        blood_col=None,  # Detecta automáticamente hidden_blood o hiden_blood
        positive_label="Positive",
        negative_label="Negative"
    )

    print("\nTabla 2x2 de conteos:")
    print(count_table)

    print("\nTabla resumen con odds ratio e IC 95%:")
    print(summary_table)

    save_tables_to_csv(count_table, summary_table)

else:
    print("No se pudo ejecutar el análisis porque no se cargó ningún archivo.")