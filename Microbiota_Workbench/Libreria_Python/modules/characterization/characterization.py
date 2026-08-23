import seaborn as sns
import pandas as pd
import numpy as np
import matplotlib.pyplot as plt
import warnings

from scipy.stats import shapiro, anderson
from scipy import stats


def get_numeric_df(df, numeric_cols=None):

    if numeric_cols is None:
        df_num = df.select_dtypes(include=[np.number]).copy()
    else:
        missing = [c for c in numeric_cols if c not in df.columns]
        if missing:
            raise KeyError(f"Estas columnas no existen en el DataFrame: {missing}")

        df_num = df[numeric_cols].copy()

        for col in df_num.columns:
            df_num[col] = pd.to_numeric(df_num[col], errors="coerce")

        df_num = df_num.select_dtypes(include=[np.number])

    if df_num.empty:
        raise ValueError("El DataFrame no contiene columnas numéricas para analizar.")

    return df_num


def flatten_numeric_values(df_num):

    valores = df_num.to_numpy(dtype=float).ravel()
    valores = valores[np.isfinite(valores)]
    return valores


def summarize_flat_values(df_original, df_num, valores):

    valores_pos = valores[valores > 0]

    summary = {
        "shape_original": df_original.shape,
        "shape_numeric": df_num.shape,
        "n_total_finitos": int(len(valores)),
        "n_positivos": int(len(valores_pos)),
        "n_ceros": int(np.sum(valores == 0)),
        "min": float(np.min(valores)) if len(valores) > 0 else np.nan,
        "max": float(np.max(valores)) if len(valores) > 0 else np.nan,
        "mean": float(np.mean(valores)) if len(valores) > 0 else np.nan,
        "median": float(np.median(valores)) if len(valores) > 0 else np.nan,
        "std": float(np.std(valores, ddof=1)) if len(valores) > 1 else np.nan,
    }

    return summary


def plot_flat_scatter(valores, figsize=(10, 4), title="Valores numéricos (incluye ceros)"):

    plt.figure(figsize=figsize)
    plt.scatter(np.arange(len(valores)), valores, s=10, alpha=0.6, edgecolor="none")
    plt.title(title)
    plt.xlabel("Índice (aplanado)")
    plt.ylabel("Valor")
    plt.grid(True, alpha=0.25)
    plt.tight_layout()
    plt.show()


def plot_histogram(valores, bins=100, figsize=(10, 4), title="Histograma", xlabel="Valor"):

    plt.figure(figsize=figsize)
    sns.histplot(valores, bins=bins, kde=False)
    plt.title(title)
    plt.xlabel(xlabel)
    plt.ylabel("Frecuencia")
    plt.tight_layout()
    plt.show()
    
def distribution_plots_from_loaded(
    dfs,
    df_name,
    numeric_cols=None,
    analysis_mode="by_column",   # "by_column", "full_matrix", "both"
    bins=100,
    plot_positive_hist=True,
    figsize_scatter=(10, 4),
    figsize_hist=(10, 4),
    verbose=True
):
    if df_name not in dfs:
        raise KeyError(f"No existe '{df_name}' en dfs. Disponibles: {list(dfs.keys())}")

    if analysis_mode not in ["by_column", "full_matrix", "both"]:
        raise ValueError("analysis_mode debe ser 'by_column', 'full_matrix' o 'both'.")

    df = dfs[df_name].copy()
    df_num = get_numeric_df(df, numeric_cols=numeric_cols)

    if df_num.empty:
        raise ValueError("El DataFrame no contiene columnas numéricas para analizar.")

    if verbose:
        print(f"DataFrame analizado: {df_name}")
        print(f"Shape original: {df.shape}")
        print(f"Shape numérico: {df_num.shape}")
        print(f"Columnas numéricas analizadas: {df_num.columns.tolist()}")
        print(f"Modo de análisis: {analysis_mode}")

    result = {
        "df_name": df_name,
        "df_numeric": df_num
    }

    if analysis_mode in ["by_column", "both"]:
        results = []

        for col in df_num.columns:
            serie = pd.to_numeric(df_num[col], errors="coerce")
            valores = serie.to_numpy(dtype=float)
            valores = valores[np.isfinite(valores)]
            valores_pos = valores[valores > 0]

            if len(valores) == 0:
                summary = {
                    "variable": col,
                    "n_total_finitos": 0,
                    "n_positivos": 0,
                    "n_ceros": 0,
                    "min": np.nan,
                    "max": np.nan,
                    "mean": np.nan,
                    "median": np.nan,
                    "std": np.nan,
                    "status": "Sin valores numéricos finitos"
                }
                results.append(summary)

                if verbose:
                    print(f"\nVariable: {col}")
                    print("Sin valores numéricos finitos.")
                continue

            summary = {
                "variable": col,
                "n_total_finitos": int(len(valores)),
                "n_positivos": int(len(valores_pos)),
                "n_ceros": int(np.sum(valores == 0)),
                "min": float(np.min(valores)),
                "max": float(np.max(valores)),
                "mean": float(np.mean(valores)),
                "median": float(np.median(valores)),
                "std": float(np.std(valores, ddof=1)) if len(valores) > 1 else np.nan,
                "status": "OK"
            }
            results.append(summary)

            if verbose:
                print(f"\nVariable: {col}")
                print(f"N total (finitos): {summary['n_total_finitos']}")
                print(f"N positivos: {summary['n_positivos']}")
                print(f"N ceros: {summary['n_ceros']}")
                print(f"Min: {summary['min']}")
                print(f"Max: {summary['max']}")
                print(f"Media: {summary['mean']}")
                print(f"Mediana: {summary['median']}")
                print(f"Desv. estándar: {summary['std']}")

            plot_flat_scatter(
                valores,
                figsize=figsize_scatter,
                title=f"{df_name} | {col} | Dispersión (incluye ceros)"
            )

            plot_histogram(
                valores,
                bins=bins,
                figsize=figsize_hist,
                title=f"{df_name} | {col} | Histograma (incluye ceros)",
                xlabel=col
            )

            if plot_positive_hist:
                if len(valores_pos) > 0:
                    plot_histogram(
                        valores_pos,
                        bins=bins,
                        figsize=figsize_hist,
                        title=f"{df_name} | {col} | Histograma X > 0",
                        xlabel=f"{col} (positivo)"
                    )
                else:
                    print(f"{col}: No hay valores positivos para graficar el histograma de X|X>0.")

        results_df = pd.DataFrame(results)
        result["summary_by_column"] = results_df

    if analysis_mode in ["full_matrix", "both"]:
        valores = df_num.to_numpy(dtype=float).ravel()
        valores = valores[np.isfinite(valores)]
        valores_pos = valores[valores > 0]

        if len(valores) == 0:
            summary_matrix = {
                "variable": "FULL_MATRIX",
                "n_total_finitos": 0,
                "n_positivos": 0,
                "n_ceros": 0,
                "min": np.nan,
                "max": np.nan,
                "mean": np.nan,
                "median": np.nan,
                "std": np.nan,
                "status": "Sin valores numéricos finitos"
            }
        else:
            summary_matrix = {
                "variable": "FULL_MATRIX",
                "n_total_finitos": int(len(valores)),
                "n_positivos": int(len(valores_pos)),
                "n_ceros": int(np.sum(valores == 0)),
                "min": float(np.min(valores)),
                "max": float(np.max(valores)),
                "mean": float(np.mean(valores)),
                "median": float(np.median(valores)),
                "std": float(np.std(valores, ddof=1)) if len(valores) > 1 else np.nan,
                "status": "OK"
            }

            if verbose:
                print("\n=== MATRIZ COMPLETA ===")
                print(f"N total (finitos): {summary_matrix['n_total_finitos']}")
                print(f"N positivos: {summary_matrix['n_positivos']}")
                print(f"N ceros: {summary_matrix['n_ceros']}")
                print(f"Min: {summary_matrix['min']}")
                print(f"Max: {summary_matrix['max']}")
                print(f"Media: {summary_matrix['mean']}")
                print(f"Mediana: {summary_matrix['median']}")
                print(f"Desv. estándar: {summary_matrix['std']}")

            plot_flat_scatter(
                valores,
                figsize=figsize_scatter,
                title=f"{df_name} | MATRIZ COMPLETA | Dispersión (incluye ceros)"
            )

            plot_histogram(
                valores,
                bins=bins,
                figsize=figsize_hist,
                title=f"{df_name} | MATRIZ COMPLETA | Histograma (incluye ceros)",
                xlabel="Valor"
            )

            if plot_positive_hist:
                if len(valores_pos) > 0:
                    plot_histogram(
                        valores_pos,
                        bins=bins,
                        figsize=figsize_hist,
                        title=f"{df_name} | MATRIZ COMPLETA | Histograma X > 0",
                        xlabel="Valor (positivo)"
                    )
                else:
                    print("MATRIZ COMPLETA: No hay valores positivos para graficar el histograma de X|X>0.")

        result["summary_full_matrix"] = pd.DataFrame([summary_matrix])

    return result

def _prepare_numeric_vector(values):
    values = np.asarray(values, dtype=float)
    values = values[np.isfinite(values)]
    return values

def _run_shapiro_test(values, alpha):
    values = _prepare_numeric_vector(values)

    if len(values) < 3:
        return {
            "shapiro_statistic": np.nan,
            "shapiro_p_value": np.nan,
            "shapiro_reject_h0": np.nan,
            "shapiro_decision": "No se puede ejecutar (n < 3)"
        }

    if len(np.unique(values)) < 2:
        return {
            "shapiro_statistic": np.nan,
            "shapiro_p_value": np.nan,
            "shapiro_reject_h0": np.nan,
            "shapiro_decision": "No se puede ejecutar (varianza cero / valores constantes)"
        }

    try:
        with warnings.catch_warnings():
            warnings.simplefilter("ignore", category=RuntimeWarning)
            warnings.simplefilter("ignore", category=UserWarning)
            stat, pval = shapiro(values)

        reject = bool(pval < alpha)

        return {
            "shapiro_statistic": float(stat),
            "shapiro_p_value": float(pval),
            "shapiro_reject_h0": reject,
            "shapiro_decision": "Se rechaza H0 de normalidad" if reject else "No se rechaza H0 de normalidad"
        }

    except Exception as e:
        return {
            "shapiro_statistic": np.nan,
            "shapiro_p_value": np.nan,
            "shapiro_reject_h0": np.nan,
            "shapiro_decision": f"Error: {e}"
        }

def _run_anderson_distribution_test(values, dist_code, alpha, prefix, null_label):
    values = _prepare_numeric_vector(values)

    if len(values) < 3:
        return {
            f"{prefix}_statistic": np.nan,
            f"{prefix}_critical_value": np.nan,
            f"{prefix}_level_used_pct": np.nan,
            f"{prefix}_reject_h0": np.nan,
            f"{prefix}_decision": "No se puede ejecutar (n < 3)"
        }

    if len(np.unique(values)) < 2:
        return {
            f"{prefix}_statistic": np.nan,
            f"{prefix}_critical_value": np.nan,
            f"{prefix}_level_used_pct": np.nan,
            f"{prefix}_reject_h0": np.nan,
            f"{prefix}_decision": "No se puede ejecutar (varianza cero / valores constantes)"
        }

    try:
        with warnings.catch_warnings():
            warnings.simplefilter("ignore", category=RuntimeWarning)
            warnings.simplefilter("ignore", category=UserWarning)
            ad = anderson(values, dist=dist_code)

        alpha_pct = 100 * alpha
        levels = np.asarray(ad.significance_level, dtype=float)
        crits = np.asarray(ad.critical_values, dtype=float)

        idx_near = int(np.argmin(np.abs(levels - alpha_pct)))
        level_used = float(levels[idx_near])
        crit_used = float(crits[idx_near])

        reject = bool(ad.statistic > crit_used)

        return {
            f"{prefix}_statistic": float(ad.statistic),
            f"{prefix}_critical_value": crit_used,
            f"{prefix}_level_used_pct": level_used,
            f"{prefix}_reject_h0": reject,
            f"{prefix}_decision": f"Se rechaza H0 de {null_label}" if reject else f"No se rechaza H0 de {null_label}"
        }

    except Exception as e:
        return {
            f"{prefix}_statistic": np.nan,
            f"{prefix}_critical_value": np.nan,
            f"{prefix}_level_used_pct": np.nan,
            f"{prefix}_reject_h0": np.nan,
            f"{prefix}_decision": f"Error: {e}"
        }

def _run_lognormal_test(values_pos, alpha):
    values_pos = _prepare_numeric_vector(values_pos)
    values_pos = values_pos[values_pos > 0]

    if len(values_pos) < 3:
        return {
            "ad_lognormal_statistic": np.nan,
            "ad_lognormal_critical_value": np.nan,
            "ad_lognormal_level_used_pct": np.nan,
            "ad_lognormal_reject_h0": np.nan,
            "ad_lognormal_decision": "No se puede ejecutar (n < 3 o sin positivos)"
        }

    log_vals = np.log(values_pos)
    return _run_anderson_distribution_test(
        values=log_vals,
        dist_code="norm",
        alpha=alpha,
        prefix="ad_lognormal",
        null_label="lognormalidad"
    )

def _run_gamma_gof(values_pos, alpha):
    values_pos = _prepare_numeric_vector(values_pos)
    values_pos = values_pos[values_pos > 0]

    if len(values_pos) < 3:
        return {
            "gamma_shape": np.nan,
            "gamma_loc": np.nan,
            "gamma_scale": np.nan,
            "gamma_ks_statistic": np.nan,
            "gamma_ks_p_value": np.nan,
            "gamma_ks_reject_h0": np.nan,
            "gamma_ks_decision": "No se puede ejecutar (n < 3 o sin positivos)",
            "gamma_cvm_statistic": np.nan,
            "gamma_cvm_p_value": np.nan,
            "gamma_cvm_reject_h0": np.nan,
            "gamma_cvm_decision": "No se puede ejecutar (n < 3 o sin positivos)"
        }

    try:
        a, loc, scale = stats.gamma.fit(values_pos, floc=0)

        ks = stats.kstest(values_pos, "gamma", args=(a, loc, scale))
        ks_reject = bool(ks.pvalue < alpha)

        cvm = stats.cramervonmises(values_pos, "gamma", args=(a, loc, scale))
        cvm_reject = bool(cvm.pvalue < alpha)

        return {
            "gamma_shape": float(a),
            "gamma_loc": float(loc),
            "gamma_scale": float(scale),
            "gamma_ks_statistic": float(ks.statistic),
            "gamma_ks_p_value": float(ks.pvalue),
            "gamma_ks_reject_h0": ks_reject,
            "gamma_ks_decision": "Se rechaza H0 de ajuste gamma (KS)" if ks_reject else "No se rechaza H0 de ajuste gamma (KS)",
            "gamma_cvm_statistic": float(cvm.statistic),
            "gamma_cvm_p_value": float(cvm.pvalue),
            "gamma_cvm_reject_h0": cvm_reject,
            "gamma_cvm_decision": "Se rechaza H0 de ajuste gamma (CvM)" if cvm_reject else "No se rechaza H0 de ajuste gamma (CvM)"
        }

    except Exception as e:
        return {
            "gamma_shape": np.nan,
            "gamma_loc": np.nan,
            "gamma_scale": np.nan,
            "gamma_ks_statistic": np.nan,
            "gamma_ks_p_value": np.nan,
            "gamma_ks_reject_h0": np.nan,
            "gamma_ks_decision": f"Error: {e}",
            "gamma_cvm_statistic": np.nan,
            "gamma_cvm_p_value": np.nan,
            "gamma_cvm_reject_h0": np.nan,
            "gamma_cvm_decision": f"Error: {e}"
        }

def _initialize_distribution_row(variable, subset_label):
    return {
        "variable": variable,
        "subset": subset_label,
        "status": "OK",

        "shapiro_statistic": np.nan,
        "shapiro_p_value": np.nan,
        "shapiro_reject_h0": np.nan,
        "shapiro_decision": "No ejecutado",

        "ad_norm_statistic": np.nan,
        "ad_norm_critical_value": np.nan,
        "ad_norm_level_used_pct": np.nan,
        "ad_norm_reject_h0": np.nan,
        "ad_norm_decision": "No ejecutado",

        "ad_logistic_statistic": np.nan,
        "ad_logistic_critical_value": np.nan,
        "ad_logistic_level_used_pct": np.nan,
        "ad_logistic_reject_h0": np.nan,
        "ad_logistic_decision": "No ejecutado",

        "ad_gumbel_l_statistic": np.nan,
        "ad_gumbel_l_critical_value": np.nan,
        "ad_gumbel_l_level_used_pct": np.nan,
        "ad_gumbel_l_reject_h0": np.nan,
        "ad_gumbel_l_decision": "No ejecutado",

        "ad_gumbel_r_statistic": np.nan,
        "ad_gumbel_r_critical_value": np.nan,
        "ad_gumbel_r_level_used_pct": np.nan,
        "ad_gumbel_r_reject_h0": np.nan,
        "ad_gumbel_r_decision": "No ejecutado",

        "ad_expon_statistic": np.nan,
        "ad_expon_critical_value": np.nan,
        "ad_expon_level_used_pct": np.nan,
        "ad_expon_reject_h0": np.nan,
        "ad_expon_decision": "No aplica",

        "ad_lognormal_statistic": np.nan,
        "ad_lognormal_critical_value": np.nan,
        "ad_lognormal_level_used_pct": np.nan,
        "ad_lognormal_reject_h0": np.nan,
        "ad_lognormal_decision": "No aplica",

        "gamma_shape": np.nan,
        "gamma_loc": np.nan,
        "gamma_scale": np.nan,
        "gamma_ks_statistic": np.nan,
        "gamma_ks_p_value": np.nan,
        "gamma_ks_reject_h0": np.nan,
        "gamma_ks_decision": "No aplica",
        "gamma_cvm_statistic": np.nan,
        "gamma_cvm_p_value": np.nan,
        "gamma_cvm_reject_h0": np.nan,
        "gamma_cvm_decision": "No aplica"
    }

def _run_distribution_tests(values, variable, subset_label, alpha, test_method="both"):
    values = _prepare_numeric_vector(values)

    if test_method not in ["shapiro", "anderson", "both"]:
        raise ValueError("test_method debe ser 'shapiro', 'anderson' o 'both'.")

    row = _initialize_distribution_row(variable, subset_label)

    if len(values) == 0:
        row["status"] = "Sin valores numéricos finitos"
        return row

    if test_method in ["shapiro", "both"]:
        row.update(_run_shapiro_test(values, alpha))

    if test_method in ["anderson", "both"]:
        
        row.update(_run_anderson_distribution_test(values, "norm", alpha, "ad_norm", "normalidad"))
        row.update(_run_anderson_distribution_test(values, "logistic", alpha, "ad_logistic", "logística"))
        row.update(_run_anderson_distribution_test(values, "gumbel_l", alpha, "ad_gumbel_l", "Gumbel izquierda"))
        row.update(_run_anderson_distribution_test(values, "gumbel_r", alpha, "ad_gumbel_r", "Gumbel derecha"))

        if subset_label == "positive":
            row.update(_run_anderson_distribution_test(values, "expon", alpha, "ad_expon", "exponencialidad"))
            row.update(_run_lognormal_test(values, alpha))
            row.update(_run_gamma_gof(values, alpha))

    return row

def normality_tests_from_loaded(
    dfs,
    df_name,
    numeric_cols=None,
    analysis_mode="by_column",   # "by_column", "full_matrix", "both"
    value_mode="both",           # "all", "positive", "both"
    test_method="both",          # "shapiro", "anderson", "both"
    alpha=0.05,
    verbose=True
):
    if df_name not in dfs:
        raise KeyError(f"No existe '{df_name}' en dfs. Disponibles: {list(dfs.keys())}")

    if analysis_mode not in ["by_column", "full_matrix", "both"]:
        raise ValueError("analysis_mode debe ser 'by_column', 'full_matrix' o 'both'.")

    if value_mode not in ["all", "positive", "both"]:
        raise ValueError("value_mode debe ser 'all', 'positive' o 'both'.")

    if test_method not in ["shapiro", "anderson", "both"]:
        raise ValueError("test_method debe ser 'shapiro', 'anderson' o 'both'.")

    df = dfs[df_name].copy()
    df_num = get_numeric_df(df, numeric_cols=numeric_cols)

    if df_num.empty:
        raise ValueError("El DataFrame no contiene columnas numéricas para analizar.")

    if verbose:
        print(f"DataFrame analizado: {df_name}")
        print(f"Shape original: {df.shape}")
        print(f"Shape numérico: {df_num.shape}")
        print(f"Modo de análisis: {analysis_mode}")
        print(f"Modo de valores: {value_mode}")
        print(f"Método de prueba: {test_method}")
        print(f"Alpha: {alpha}")

    result = {
        "df_name": df_name,
        "df_numeric": df_num
    }

    if analysis_mode in ["by_column", "both"]:
        rows = []

        for col in df_num.columns:
            serie = pd.to_numeric(df_num[col], errors="coerce")
            valores = _prepare_numeric_vector(serie.to_numpy(dtype=float))
            valores_pos = valores[valores > 0]

            if value_mode in ["all", "both"]:
                rows.append(
                    _run_distribution_tests(
                        values=valores,
                        variable=col,
                        subset_label="all",
                        alpha=alpha,
                        test_method=test_method
                    )
                )

            if value_mode in ["positive", "both"]:
                rows.append(
                    _run_distribution_tests(
                        values=valores_pos,
                        variable=col,
                        subset_label="positive",
                        alpha=alpha,
                        test_method=test_method
                    )
                )

        result["summary_by_column"] = pd.DataFrame(rows)

    if analysis_mode in ["full_matrix", "both"]:
        rows_matrix = []

        valores = _prepare_numeric_vector(df_num.to_numpy(dtype=float).ravel())
        valores_pos = valores[valores > 0]

        if value_mode in ["all", "both"]:
            rows_matrix.append(
                _run_distribution_tests(
                    values=valores,
                    variable="FULL_MATRIX",
                    subset_label="all",
                    alpha=alpha,
                    test_method=test_method
                )
            )

        if value_mode in ["positive", "both"]:
            rows_matrix.append(
                _run_distribution_tests(
                    values=valores_pos,
                    variable="FULL_MATRIX",
                    subset_label="positive",
                    alpha=alpha,
                    test_method=test_method
                )
            )

        result["summary_full_matrix"] = pd.DataFrame(rows_matrix)

    return result
