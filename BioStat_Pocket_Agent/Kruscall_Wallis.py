import pandas as pd
import numpy as np

from scipy.stats import kruskal


def benjamini_hochberg(pvalues):

    pvalues = np.asarray(pvalues, dtype=float)
    n = len(pvalues)

    if n == 0:
        return np.array([])

    order = np.argsort(pvalues)
    ranked_p = pvalues[order]

    adjusted = np.empty(n, dtype=float)
    prev = 1.0

    for i in range(n - 1, -1, -1):
        rank = i + 1
        adj = ranked_p[i] * n / rank
        prev = min(prev, adj)
        adjusted[i] = prev

    adjusted = np.clip(adjusted, 0, 1)

    result = np.empty(n, dtype=float)
    result[order] = adjusted
    return result

def bonferroni_correction(pvalues):

    pvalues = np.asarray(pvalues, dtype=float)
    n = len(pvalues)

    if n == 0:
        return np.array([])

    adjusted = pvalues * n
    adjusted = np.clip(adjusted, 0, 1)

    return adjusted

def kruskal_epsilon_squared(H, n, k):

    if any(pd.isna(x) for x in [H, n, k]):
        return np.nan
    
    if n <= k:
        return np.nan

    effect = (H - k + 1) / (n - k)
    return max(0, effect)

def interpret_kruskal_effect(effect_size):
    if pd.isna(effect_size):
        return np.nan
    if effect_size < 0.01:
        return "muy pequeño"
    elif effect_size < 0.08:
        return "pequeño"
    elif effect_size < 0.26:
        return "mediano"
    else:
        return "grande"
    
def kruskal_wallis_from_loaded(
    dfs,
    alpha,
    group_df_name,
    value_df_name,
    group_col,
    id_col_group="ID",
    id_col_value="ID",
    value_cols=None,
    min_group_size=3,
    apply_fdr=True,
    verbose=True
):
    if group_df_name not in dfs:
        raise KeyError(f"No existe '{group_df_name}' en dfs. Disponibles: {list(dfs.keys())}")

    if value_df_name not in dfs:
        raise KeyError(f"No existe '{value_df_name}' en dfs. Disponibles: {list(dfs.keys())}")

    group_df = dfs[group_df_name].copy()
    value_df = dfs[value_df_name].copy()

    if id_col_group not in group_df.columns:
        raise KeyError(f"La columna '{id_col_group}' no existe en '{group_df_name}'")

    if id_col_value not in value_df.columns:
        raise KeyError(f"La columna '{id_col_value}' no existe en '{value_df_name}'")

    if group_col not in group_df.columns:
        raise KeyError(f"La columna de grupo '{group_col}' no existe en '{group_df_name}'")

    group_df[id_col_group] = group_df[id_col_group].astype(str).str.strip()
    value_df[id_col_value] = value_df[id_col_value].astype(str).str.strip()

    group_subset = group_df[[id_col_group, group_col]].copy()

    if value_cols is None:
        numeric_cols = value_df.select_dtypes(include=[np.number]).columns.tolist()
        value_cols = [c for c in numeric_cols if c != id_col_value]
    else:
        missing = [c for c in value_cols if c not in value_df.columns]
        if missing:
            raise KeyError(f"Estas columnas no existen en '{value_df_name}': {missing}")

    if len(value_cols) == 0:
        raise ValueError(f"No se encontraron columnas numéricas para analizar en '{value_df_name}'")

    value_subset = value_df[[id_col_value] + value_cols].copy()

    merged_df = pd.merge(
        group_subset,
        value_subset,
        left_on=id_col_group,
        right_on=id_col_value,
        how="inner"
    )

    if id_col_group != id_col_value:
        merged_df.rename(columns={id_col_group: "ID"}, inplace=True)
        if id_col_value in merged_df.columns:
            merged_df.drop(columns=[id_col_value], inplace=True)
    else:
        merged_df.rename(columns={id_col_group: "ID"}, inplace=True)

    merged_df[group_col] = merged_df[group_col].astype(str).str.strip()
    merged_df = merged_df[merged_df[group_col].notna()]
    merged_df = merged_df[merged_df[group_col] != ""]
    merged_df = merged_df[merged_df[group_col].str.lower() != "nan"]

    results = []

    for col in value_cols:
        temp = merged_df[[group_col, col]].copy()
        temp[col] = pd.to_numeric(temp[col], errors="coerce")
        temp = temp.dropna(subset=[group_col, col])

        group_counts = temp[group_col].value_counts()
        valid_groups = group_counts[group_counts >= min_group_size].index.tolist()
        temp = temp[temp[group_col].isin(valid_groups)]

        groups = []
        group_sizes = {}

        for g in valid_groups:
            vals = temp.loc[temp[group_col] == g, col].values
            if len(vals) >= min_group_size:
                groups.append(vals)
                group_sizes[g] = len(vals)

        if len(groups) < 2:
            results.append({
                "variable": col,
                "n_total": len(temp),
                "n_groups": len(groups),
                "groups_used": list(group_sizes.keys()),
                "group_sizes": group_sizes,
                "statistic": np.nan,
                "p_value": np.nan,
                "effect_size": np.nan,
                "effect_size_method": "epsilon_squared",
                "effect_interpretation_cohen": np.nan,
                "significant": np.nan,
                "status": "Menos de 2 grupos válidos"
            })
            continue

        try:
            stat, pval = kruskal(*groups)
            effect_size = kruskal_epsilon_squared(stat, len(temp), len(groups))
            effect_label = interpret_kruskal_effect(effect_size)

            results.append({
                "variable": col,
                "n_total": len(temp),
                "n_groups": len(groups),
                "groups_used": list(group_sizes.keys()),
                "group_sizes": group_sizes,
                "statistic": stat,
                "p_value": pval,
                "effect_size": effect_size,
                "effect_size_method": "epsilon_squared",
                "effect_interpretation_cohen": effect_label,
                "significant": pval < alpha,
                "status": "OK"
            })

        except Exception as e:
            results.append({
                "variable": col,
                "n_total": len(temp),
                "n_groups": len(groups),
                "groups_used": list(group_sizes.keys()),
                "group_sizes": group_sizes,
                "statistic": np.nan,
                "p_value": np.nan,
                "effect_size": np.nan,
                "effect_size_method": "epsilon_squared",
                "effect_interpretation_cohen": np.nan,
                "significant": np.nan,
                "status": f"Error: {e}"
            })

    results_df = pd.DataFrame(results)

    if "p_value" in results_df.columns:
        mask = results_df["p_value"].notna()

        if apply_fdr and mask.sum() > 0:
            adjusted_bh = np.full(len(results_df), np.nan)
            adjusted_bh_vals = benjamini_hochberg(results_df.loc[mask, "p_value"].values)
            adjusted_bh[mask] = adjusted_bh_vals

            results_df["Benjamini_Hochberg"] = adjusted_bh
            results_df["significant_BH"] = results_df["Benjamini_Hochberg"] < alpha
        else:
            results_df["Benjamini_Hochberg"] = np.nan
            results_df["significant_BH"] = np.nan

        if mask.sum() > 0:
            adjusted_bonf = np.full(len(results_df), np.nan)
            adjusted_bonf_vals = bonferroni_correction(results_df.loc[mask, "p_value"].values)
            adjusted_bonf[mask] = adjusted_bonf_vals

            results_df["Bonferroni"] = adjusted_bonf
            results_df["significant_BonF"] = results_df["Bonferroni"] < alpha
        else:
            results_df["Bonferroni"] = np.nan
            results_df["significant_BonF"] = np.nan

    results_df = results_df.sort_values(by="p_value", na_position="last").reset_index(drop=True)

    if verbose:
        print(f"DataFrame de grupos: {group_df_name}")
        print(f"DataFrame de variables: {value_df_name}")
        print(f"Grupo evaluado: {group_col}")
        print(f"Observaciones tras merge: {merged_df.shape[0]}")
        print(f"Variables evaluadas: {len(value_cols)}")

    return merged_df, results_df