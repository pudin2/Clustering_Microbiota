import math

import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
import seaborn as sns

from scipy import stats
from sklearn.decomposition import PCA
from sklearn.metrics import (
    calinski_harabasz_score,
    davies_bouldin_score,
    silhouette_score,
)

try:
    from sklearn.manifold import trustworthiness
except Exception:
    trustworthiness = None

from modules.dbscan import prepare_data_for_dbscan


def _as_list(value):
    if value is None:
        return None
    if isinstance(value, str):
        items = [item.strip() for item in value.replace(";", ",").split(",")]
        return [item for item in items if item] or None
    return list(value)


def _get_df(dfs, df_name):
    if df_name not in dfs:
        raise KeyError(f"No existe '{df_name}' en dfs. Disponibles: {list(dfs.keys())}")
    return dfs[df_name].copy()


def _numeric_frame(df, columns=None, min_non_null=2):
    columns = _as_list(columns)
    if columns is None:
        columns = list(df.columns)
    missing = [col for col in columns if col not in df.columns]
    if missing:
        raise KeyError(f"Estas columnas no existen en el DataFrame: {missing}")

    converted = {}
    for col in columns:
        values = pd.to_numeric(df[col], errors="coerce")
        if values.notna().sum() >= min_non_null and values.nunique(dropna=True) >= 2:
            converted[col] = values

    if not converted:
        raise ValueError("No hay columnas numericas suficientes para analizar.")

    return pd.DataFrame(converted)


def benjamini_hochberg(pvalues):
    pvalues = np.asarray(pvalues, dtype=float)
    n = len(pvalues)
    if n == 0:
        return np.array([])

    order = np.argsort(pvalues)
    ranked = pvalues[order]
    adjusted = np.empty(n, dtype=float)
    prev = 1.0

    for i in range(n - 1, -1, -1):
        rank = i + 1
        prev = min(prev, ranked[i] * n / rank)
        adjusted[i] = prev

    result = np.empty(n, dtype=float)
    result[order] = np.clip(adjusted, 0, 1)
    return result


def _estimate_bins(values):
    values = np.asarray(values, dtype=float)
    values = values[np.isfinite(values)]
    n = values.size

    if n < 2:
        return {
            "bins_sturges": 1,
            "bins_sqrt": 1,
            "bins_rice": 1,
            "bins_fd": 1,
            "bins_scott": 1,
            "bins_doane": 1,
            "chosen_bin_method": "insufficient_data",
            "chosen_bins": 1,
        }

    data_range = float(np.max(values) - np.min(values))
    sturges = int(math.ceil(np.log2(n) + 1))
    sqrt_bins = int(math.ceil(np.sqrt(n)))
    rice = int(math.ceil(2 * np.cbrt(n)))

    q75, q25 = np.percentile(values, [75, 25])
    iqr = float(q75 - q25)
    if iqr > 0 and data_range > 0:
        fd_width = 2 * iqr * (n ** (-1 / 3))
        fd = int(math.ceil(data_range / fd_width)) if fd_width > 0 else sturges
    else:
        fd = sturges

    std = float(np.std(values, ddof=1)) if n > 1 else 0.0
    if std > 0 and data_range > 0:
        scott_width = 3.5 * std * (n ** (-1 / 3))
        scott = int(math.ceil(data_range / scott_width)) if scott_width > 0 else sturges
    else:
        scott = sturges

    try:
        skewness = float(stats.skew(values, bias=False))
        sigma_g1 = math.sqrt((6 * (n - 2)) / ((n + 1) * (n + 3))) if n > 2 else np.nan
        if np.isfinite(skewness) and np.isfinite(sigma_g1) and sigma_g1 > 0:
            doane = int(math.ceil(1 + np.log2(n) + np.log2(1 + abs(skewness) / sigma_g1)))
        else:
            doane = sturges
    except Exception:
        doane = sturges

    unique_count = int(pd.Series(values).nunique(dropna=True))
    unique_ratio = unique_count / n
    integer_like = bool(np.all(np.isclose(values, np.round(values), atol=1e-9)))
    skew_abs = 0.0
    if n > 2:
        try:
            skew_abs = abs(float(stats.skew(values, bias=False)))
        except Exception:
            skew_abs = 0.0

    if unique_count <= 2:
        method, chosen = "binary_or_constant", max(1, unique_count)
    elif not integer_like and iqr > 0:
        method, chosen = "freedman_diaconis", fd
    elif skew_abs > 1:
        method, chosen = "doane", doane
    elif unique_ratio < 0.10:
        method, chosen = "unique_count", unique_count
    else:
        method, chosen = "sturges", sturges

    return {
        "bins_sturges": max(1, sturges),
        "bins_sqrt": max(1, sqrt_bins),
        "bins_rice": max(1, rice),
        "bins_fd": max(1, fd),
        "bins_scott": max(1, scott),
        "bins_doane": max(1, doane),
        "chosen_bin_method": method,
        "chosen_bins": int(max(1, min(chosen, 500))),
    }


def _continuity_diagnostics(values):
    values = np.asarray(values, dtype=float)
    values = values[np.isfinite(values)]
    n = values.size

    if n == 0:
        return {
            "continuity_score": np.nan,
            "continuity_label": "sin_datos",
            "unique_count": 0,
            "unique_ratio": np.nan,
            "integer_like": np.nan,
            "max_frequency_pct": np.nan,
            "tie_ratio": np.nan,
        }

    unique_values = np.unique(values)
    unique_count = unique_values.size
    unique_ratio = unique_count / n
    integer_like = bool(np.all(np.isclose(values, np.round(values), atol=1e-9)))
    counts = pd.Series(values).value_counts(dropna=True)
    max_frequency_pct = float(counts.iloc[0] / n) if len(counts) else np.nan
    tie_ratio = 1 - unique_ratio

    score = 0.0
    score += min(unique_count / 30, 1.0) * 35
    score += min(unique_ratio / 0.25, 1.0) * 35
    score += 20 if not integer_like else 0
    score += 10 if max_frequency_pct < 0.20 else 0
    score = float(round(min(score, 100), 2))

    if unique_count <= 2:
        label = "binaria"
    elif score >= 70:
        label = "continua_probable"
    elif score >= 45:
        label = "mixta_o_ordinal"
    else:
        label = "discreta_conteo_probable"

    return {
        "continuity_score": score,
        "continuity_label": label,
        "unique_count": int(unique_count),
        "unique_ratio": float(unique_ratio),
        "integer_like": integer_like,
        "max_frequency_pct": max_frequency_pct,
        "tie_ratio": float(tie_ratio),
    }


def dataset_profile_from_loaded(
    dfs,
    df_name,
    numeric_cols=None,
    max_category_values=12,
    verbose=True,
):
    df = _get_df(dfs, df_name)
    requested_numeric = set(_as_list(numeric_cols) or [])
    rows = []
    numeric_rows = []
    categorical_rows = []
    continuity_rows = []

    for col in df.columns:
        series = df[col]
        non_null = int(series.notna().sum())
        missing = int(series.isna().sum())
        unique_count = int(series.nunique(dropna=True))
        converted = pd.to_numeric(series, errors="coerce")
        numeric_non_null = int(converted.notna().sum())
        numeric_ratio = numeric_non_null / non_null if non_null else 0.0
        is_numeric = pd.api.types.is_numeric_dtype(series) or numeric_ratio >= 0.85 or col in requested_numeric

        if is_numeric:
            role = "numeric"
        elif unique_count <= max(20, int(0.05 * max(len(df), 1))):
            role = "categorical"
        elif unique_count == non_null and non_null > 0:
            role = "id_like"
        else:
            role = "text_or_mixed"

        example_values = [
            str(value)[:60]
            for value in series.dropna().astype(str).head(3).tolist()
        ]

        rows.append({
            "column": col,
            "pandas_dtype": str(series.dtype),
            "inferred_role": role,
            "non_null": non_null,
            "missing": missing,
            "missing_pct": float(missing / len(df)) if len(df) else np.nan,
            "unique_count": unique_count,
            "unique_pct": float(unique_count / non_null) if non_null else np.nan,
            "numeric_parse_pct": float(numeric_ratio),
            "examples": " | ".join(example_values),
        })

        if is_numeric:
            values = converted.to_numpy(dtype=float)
            values = values[np.isfinite(values)]
            summary = {
                "column": col,
                "n": int(values.size),
                "min": float(np.min(values)) if values.size else np.nan,
                "q1": float(np.percentile(values, 25)) if values.size else np.nan,
                "median": float(np.median(values)) if values.size else np.nan,
                "mean": float(np.mean(values)) if values.size else np.nan,
                "q3": float(np.percentile(values, 75)) if values.size else np.nan,
                "max": float(np.max(values)) if values.size else np.nan,
                "std": float(np.std(values, ddof=1)) if values.size > 1 else np.nan,
                "zeros": int(np.sum(values == 0)) if values.size else 0,
                "negatives": int(np.sum(values < 0)) if values.size else 0,
            }
            bins = _estimate_bins(values)
            continuity = _continuity_diagnostics(values)
            numeric_rows.append({**summary, **bins})
            continuity_rows.append({"column": col, **continuity, **bins})
        else:
            counts = series.astype(str).replace("nan", np.nan).dropna().value_counts().head(max_category_values)
            for value, count in counts.items():
                categorical_rows.append({
                    "column": col,
                    "value": value,
                    "count": int(count),
                    "pct_non_null": float(count / non_null) if non_null else np.nan,
                })

    column_profile = pd.DataFrame(rows)
    numeric_profile = pd.DataFrame(numeric_rows)
    categorical_profile = pd.DataFrame(categorical_rows)
    continuity_profile = pd.DataFrame(continuity_rows)
    role_counts = (
        column_profile["inferred_role"]
        .value_counts()
        .rename_axis("role")
        .reset_index(name="columns")
    )

    if verbose:
        print(f"Dataset perfilado: {df_name}")
        print(f"Shape: {df.shape[0]} filas x {df.shape[1]} columnas")
        print(role_counts.to_string(index=False))

    return {
        "column_profile": column_profile,
        "role_counts": role_counts,
        "numeric_profile": numeric_profile,
        "categorical_profile": categorical_profile,
        "continuity_profile": continuity_profile,
    }


def _pvalue_matrices(df_num):
    columns = list(df_num.columns)
    pearson_corr = pd.DataFrame(np.eye(len(columns)), index=columns, columns=columns)
    pearson_p = pd.DataFrame(np.zeros((len(columns), len(columns))), index=columns, columns=columns)
    spearman_corr = pd.DataFrame(np.eye(len(columns)), index=columns, columns=columns)
    spearman_p = pd.DataFrame(np.zeros((len(columns), len(columns))), index=columns, columns=columns)
    rows = []

    for i, col_a in enumerate(columns):
        for j, col_b in enumerate(columns):
            if j <= i:
                continue
            pair = df_num[[col_a, col_b]].dropna()
            n = int(pair.shape[0])
            if n < 3:
                pcorr = pp = scorr = sp = np.nan
            else:
                try:
                    pcorr, pp = stats.pearsonr(pair[col_a], pair[col_b])
                except Exception:
                    pcorr = pp = np.nan
                try:
                    scorr, sp = stats.spearmanr(pair[col_a], pair[col_b])
                except Exception:
                    scorr = sp = np.nan

            pearson_corr.loc[col_a, col_b] = pearson_corr.loc[col_b, col_a] = pcorr
            pearson_p.loc[col_a, col_b] = pearson_p.loc[col_b, col_a] = pp
            spearman_corr.loc[col_a, col_b] = spearman_corr.loc[col_b, col_a] = scorr
            spearman_p.loc[col_a, col_b] = spearman_p.loc[col_b, col_a] = sp

            rows.append({
                "var_1": col_a,
                "var_2": col_b,
                "n_pairwise": n,
                "pearson_r": pcorr,
                "pearson_p": pp,
                "spearman_rho": scorr,
                "spearman_p": sp,
            })

    return pearson_corr, pearson_p, spearman_corr, spearman_p, pd.DataFrame(rows)


def _add_significance_columns(pairwise, alpha):
    out = pairwise.copy()

    for prefix, p_col in [("pearson", "pearson_p"), ("spearman", "spearman_p")]:
        mask = out[p_col].notna()
        adjusted_bh = np.full(len(out), np.nan)
        adjusted_bonf = np.full(len(out), np.nan)

        if mask.sum() > 0:
            values = out.loc[mask, p_col].to_numpy(dtype=float)
            adjusted_bh[mask] = benjamini_hochberg(values)
            adjusted_bonf[mask] = np.clip(values * mask.sum(), 0, 1)

        out[f"{prefix}_p_bh"] = adjusted_bh
        out[f"{prefix}_p_bonferroni"] = adjusted_bonf
        out[f"{prefix}_significant_raw"] = out[p_col] < alpha
        out[f"{prefix}_significant_bh"] = out[f"{prefix}_p_bh"] < alpha
        out[f"{prefix}_significant_bonferroni"] = out[f"{prefix}_p_bonferroni"] < alpha

    rows = []
    n_tests = int(len(out))
    for prefix in ["pearson", "spearman"]:
        rows.append({
            "method": prefix,
            "alpha": alpha,
            "n_tests": n_tests,
            "significant_raw": int(out[f"{prefix}_significant_raw"].sum()),
            "significant_bh": int(out[f"{prefix}_significant_bh"].sum()),
            "significant_bonferroni": int(out[f"{prefix}_significant_bonferroni"].sum()),
        })

    return out, pd.DataFrame(rows)


def correlation_from_loaded(
    dfs,
    df_name,
    numeric_cols=None,
    alpha=0.05,
    min_non_null=3,
    max_plot_vars=25,
    verbose=True,
):
    df = _get_df(dfs, df_name)
    df_num = _numeric_frame(df, numeric_cols, min_non_null=min_non_null)
    pearson_corr, pearson_p, spearman_corr, spearman_p, pairwise = _pvalue_matrices(df_num)
    pairwise, significance_summary = _add_significance_columns(pairwise, alpha)

    plot_cols = list(df_num.columns[:max_plot_vars])
    if plot_cols:
        fig, axes = plt.subplots(1, 2, figsize=(15, 6))
        sns.heatmap(pearson_corr.loc[plot_cols, plot_cols], cmap="vlag", center=0, ax=axes[0])
        axes[0].set_title("Matriz de correlacion Pearson")
        sns.heatmap(spearman_corr.loc[plot_cols, plot_cols], cmap="vlag", center=0, ax=axes[1])
        axes[1].set_title("Matriz de correlacion Spearman")
        fig.tight_layout()
        plt.show()

    if verbose:
        print(f"Correlacion: {df_name}")
        print(f"Variables evaluadas: {df_num.shape[1]}")
        print(significance_summary.to_string(index=False))

    return {
        "numeric_data": df_num,
        "pearson_corr": pearson_corr.reset_index().rename(columns={"index": "variable"}),
        "pearson_p_values": pearson_p.reset_index().rename(columns={"index": "variable"}),
        "spearman_corr": spearman_corr.reset_index().rename(columns={"index": "variable"}),
        "spearman_p_values": spearman_p.reset_index().rename(columns={"index": "variable"}),
        "pairwise_significance": pairwise,
        "significance_summary": significance_summary,
    }


def dimensionality_from_loaded(
    dfs,
    data_df_name,
    id_col="ID",
    feature_cols=None,
    missing_strategy="fill_zero",
    remove_zero_rows=False,
    min_prevalence=None,
    min_total_abundance=None,
    transform_method="none",
    pseudocount=1.0,
    scale=True,
    embedding_method="pca",
    n_components=3,
    random_state=42,
    embedding_kwargs=None,
    variance_thresholds=(0.8, 0.9, 0.95),
    verbose=True,
):
    data_df = _get_df(dfs, data_df_name)
    prepared = prepare_data_for_dbscan(
        df=data_df,
        id_col=id_col,
        feature_cols=feature_cols,
        drop_non_numeric=True,
        missing_strategy=missing_strategy,
        remove_zero_rows=remove_zero_rows,
        min_prevalence=min_prevalence,
        min_total_abundance=min_total_abundance,
        transform_method=transform_method,
        pseudocount=pseudocount,
        scale=scale,
        embedding_method=embedding_method,
        n_components=n_components,
        random_state=random_state,
        embedding_kwargs=embedding_kwargs or {},
        verbose=verbose,
    )

    X_embed = np.asarray(prepared["X_embed"], dtype=float)
    embedding_cols = [f"Dim{i}" for i in range(1, X_embed.shape[1] + 1)]
    embedding_df = pd.DataFrame(X_embed, columns=embedding_cols)
    embedding_df.insert(0, id_col or "row_id", prepared["ids"].astype(str).values)

    criteria_rows = [{
        "criterion": "samples",
        "value": int(X_embed.shape[0]),
        "message": "filas usadas tras preprocesamiento",
    }, {
        "criterion": "features_retained",
        "value": int(len(prepared["feature_names"])),
        "message": "variables numericas retenidas",
    }, {
        "criterion": "embedding_dimensions",
        "value": int(X_embed.shape[1]),
        "message": f"dimensiones generadas por {embedding_method}",
    }]

    pca_variance = pd.DataFrame()
    if "explained_variance_ratio" in prepared:
        ratios = np.asarray(prepared["explained_variance_ratio"], dtype=float)
        cumulative = np.cumsum(ratios)
        pca_variance = pd.DataFrame({
            "component": np.arange(1, len(ratios) + 1),
            "explained_variance_ratio": ratios,
            "cumulative_variance_ratio": cumulative,
        })
        for threshold in variance_thresholds:
            reached = np.where(cumulative >= float(threshold))[0]
            criteria_rows.append({
                "criterion": f"pca_components_for_{threshold:.0%}",
                "value": int(reached[0] + 1) if len(reached) else np.nan,
                "message": "componentes necesarios para alcanzar el umbral",
            })

        fig, ax = plt.subplots(figsize=(8, 4))
        ax.plot(pca_variance["component"], pca_variance["cumulative_variance_ratio"], marker="o")
        ax.set_ylim(0, 1.02)
        ax.set_xlabel("Componente")
        ax.set_ylabel("Varianza acumulada")
        ax.set_title("Criterio PCA: varianza acumulada")
        ax.grid(True, alpha=0.25)
        fig.tight_layout()
        plt.show()

    if trustworthiness is not None and X_embed.shape[0] > 6:
        try:
            neighbors = min(5, X_embed.shape[0] - 1)
            trust = trustworthiness(prepared["X_scaled"], X_embed, n_neighbors=neighbors)
            criteria_rows.append({
                "criterion": "trustworthiness",
                "value": float(trust),
                "message": "preservacion local de vecindarios; mas alto es mejor",
            })
        except Exception as exc:
            criteria_rows.append({
                "criterion": "trustworthiness",
                "value": np.nan,
                "message": f"no calculado: {exc}",
            })

    if X_embed.shape[1] >= 2:
        fig, ax = plt.subplots(figsize=(7, 6))
        ax.scatter(X_embed[:, 0], X_embed[:, 1], alpha=0.75)
        ax.set_xlabel("Dim1")
        ax.set_ylabel("Dim2")
        ax.set_title(f"Reduccion dimensional: {embedding_method}")
        ax.grid(True, alpha=0.25)
        fig.tight_layout()
        plt.show()

    preprocessing_summary = pd.DataFrame([{
        "data_df_name": data_df_name,
        "id_col": id_col,
        "missing_strategy": missing_strategy,
        "remove_zero_rows": remove_zero_rows,
        "min_prevalence": min_prevalence,
        "min_total_abundance": min_total_abundance,
        "transform_method": transform_method,
        "scale": scale,
        "embedding_method": embedding_method,
        "n_components_requested": n_components,
        "n_components_returned": X_embed.shape[1],
        "features_retained": len(prepared["feature_names"]),
        "removed_cols": ", ".join(map(str, prepared.get("removed_cols", []))),
    }])

    feature_table = pd.DataFrame({"feature": prepared["feature_names"]})
    criteria = pd.DataFrame(criteria_rows)

    if verbose:
        print("Reduccion dimensional finalizada.")
        print(criteria.to_string(index=False))

    return {
        "preprocessing_summary": preprocessing_summary,
        "feature_table": feature_table,
        "embedding": embedding_df,
        "pca_variance": pca_variance,
        "criteria": criteria,
    }


def cluster_review_from_loaded(
    dfs,
    df_name,
    label_col,
    feature_cols=None,
    ignore_noise=True,
    noise_label="-1",
    min_cluster_size=3,
    verbose=True,
):
    df = _get_df(dfs, df_name)
    if label_col not in df.columns:
        raise KeyError(f"La columna de cluster '{label_col}' no existe en '{df_name}'")

    df_num = _numeric_frame(df, feature_cols)
    labels = df[label_col].astype(str).str.strip()
    valid = labels.notna() & (labels != "") & df_num.notna().all(axis=1)

    if ignore_noise:
        valid = valid & (labels != str(noise_label))

    X = df_num.loc[valid].to_numpy(dtype=float)
    y = labels.loc[valid].to_numpy()
    unique_labels = sorted(pd.unique(y).tolist())
    n_clusters = len(unique_labels)

    counts = (
        pd.Series(y, name=label_col)
        .value_counts()
        .rename_axis(label_col)
        .reset_index(name="n")
        .sort_values(label_col)
        .reset_index(drop=True)
    )

    original_labels = labels.dropna().astype(str)
    noise_count = int((original_labels == str(noise_label)).sum())
    noise_fraction = float(noise_count / len(original_labels)) if len(original_labels) else np.nan

    metrics_rows = []
    if n_clusters >= 2 and X.shape[0] > n_clusters:
        try:
            metrics_rows.append({"metric": "silhouette", "value": float(silhouette_score(X, y)), "direction": "higher_better"})
        except Exception as exc:
            metrics_rows.append({"metric": "silhouette", "value": np.nan, "direction": f"error: {exc}"})
        try:
            metrics_rows.append({"metric": "calinski_harabasz", "value": float(calinski_harabasz_score(X, y)), "direction": "higher_better"})
        except Exception as exc:
            metrics_rows.append({"metric": "calinski_harabasz", "value": np.nan, "direction": f"error: {exc}"})
        try:
            metrics_rows.append({"metric": "davies_bouldin", "value": float(davies_bouldin_score(X, y)), "direction": "lower_better"})
        except Exception as exc:
            metrics_rows.append({"metric": "davies_bouldin", "value": np.nan, "direction": f"error: {exc}"})
    else:
        metrics_rows.append({
            "metric": "cluster_metrics",
            "value": np.nan,
            "direction": "requiere al menos 2 clusters no vacios y menos clusters que muestras",
        })

    metrics = pd.DataFrame(metrics_rows)
    smallest_cluster = int(counts["n"].min()) if not counts.empty else 0
    largest_pct = float(counts["n"].max() / counts["n"].sum()) if not counts.empty else np.nan
    silhouette_value = metrics.loc[metrics["metric"] == "silhouette", "value"]
    silhouette_value = float(silhouette_value.iloc[0]) if len(silhouette_value) else np.nan

    if n_clusters < 2:
        recommendation = "No hay suficientes clusters para comparar."
    elif smallest_cluster < min_cluster_size:
        recommendation = "Hay clusters demasiado pequenos; revisar parametros o preprocesamiento."
    elif np.isfinite(silhouette_value) and silhouette_value >= 0.50:
        recommendation = "Separacion fuerte segun silhouette; revisar estabilidad e interpretabilidad."
    elif np.isfinite(silhouette_value) and silhouette_value >= 0.25:
        recommendation = "Separacion moderada; comparar contra otros parametros."
    else:
        recommendation = "Separacion debil; revisar transformacion, variables o criterio de clusterizacion."

    criteria = pd.DataFrame([{
        "n_samples_used": int(X.shape[0]),
        "n_features": int(X.shape[1]) if X.ndim == 2 else 0,
        "n_clusters": int(n_clusters),
        "noise_count": noise_count,
        "noise_fraction": noise_fraction,
        "smallest_cluster": smallest_cluster,
        "largest_cluster_pct": largest_pct,
        "recommendation": recommendation,
    }])

    if not counts.empty:
        fig, ax = plt.subplots(figsize=(8, 4))
        ax.bar(counts[label_col].astype(str), counts["n"])
        ax.set_title("Tamanos de clusters")
        ax.set_xlabel("Cluster")
        ax.set_ylabel("n")
        ax.grid(True, axis="y", alpha=0.25)
        fig.tight_layout()
        plt.show()

    if X.shape[0] >= 3 and X.shape[1] >= 2 and n_clusters >= 2:
        pca = PCA(n_components=2, random_state=42)
        coords = pca.fit_transform(X)
        plot_df = pd.DataFrame({"Dim1": coords[:, 0], "Dim2": coords[:, 1], label_col: y})
        plt.figure(figsize=(7, 6))
        sns.scatterplot(data=plot_df, x="Dim1", y="Dim2", hue=label_col, alpha=0.8)
        plt.title("Vista PCA para revision de clusters")
        plt.grid(True, alpha=0.25)
        plt.tight_layout()
        plt.show()

    if verbose:
        print("Revision de clusterizacion")
        print(criteria.to_string(index=False))
        print(metrics.to_string(index=False))

    return {
        "cluster_counts": counts,
        "cluster_metrics": metrics,
        "cluster_criteria": criteria,
        "numeric_data_used": df_num.loc[valid].reset_index(drop=True),
    }
