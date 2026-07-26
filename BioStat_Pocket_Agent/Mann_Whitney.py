import pandas as pd
import numpy as np

from scipy.stats import mannwhitneyu


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

def mannwhitney_effect_size(x, y, u_stat):

    if x is None or y is None:
        return np.nan

    n1 = len(x)
    n2 = len(y)

    if pd.isna(u_stat) or n1 == 0 or n2 == 0:
        return np.nan

    effect = (2 * u_stat) / (n1 * n2) - 1
    return effect

def interpret_mannwhitney_effect(effect_size):
    
    if pd.isna(effect_size):
        return np.nan

    abs_effect = abs(effect_size)

    if abs_effect < 0.10:
        return "muy pequeño"
    elif abs_effect < 0.30:
        return "pequeño"
    elif abs_effect < 0.50:
        return "mediano"
    else:
        return "grande"
    
def mann_whitney_from_loaded(
    dfs,
    alpha,
    group_df_name,
    value_df_name,
    group_col,
    groups_to_compare=None,
    id_col_group="ID",
    id_col_value="ID",
    value_cols=None,
    min_group_size=3,
    alternative="two-sided",
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

    unique_groups = merged_df[group_col].dropna().unique().tolist()

    if groups_to_compare is None:
        if len(unique_groups) != 2:
            raise ValueError(
                f"La columna '{group_col}' tiene {len(unique_groups)} grupos únicos "
                f"({unique_groups}). Debes especificar exactamente dos en groups_to_compare."
            )
        groups_to_compare = tuple(unique_groups)

    if len(groups_to_compare) != 2:
        raise ValueError("groups_to_compare debe tener exactamente 2 grupos.")

    g1, g2 = groups_to_compare

    results = []

    for col in value_cols:
        temp = merged_df[[group_col, col]].copy()
        temp[col] = pd.to_numeric(temp[col], errors="coerce")
        temp = temp.dropna(subset=[group_col, col])
        temp = temp[temp[group_col].isin([g1, g2])]

        x = temp.loc[temp[group_col] == g1, col].values
        y = temp.loc[temp[group_col] == g2, col].values

        n1 = len(x)
        n2 = len(y)

        if n1 < min_group_size or n2 < min_group_size:
            results.append({
                "variable": col,
                "group_1": g1,
                "group_2": g2,
                "n_group_1": n1,
                "n_group_2": n2,
                "median_group_1": np.nan if n1 == 0 else np.median(x),
                "median_group_2": np.nan if n2 == 0 else np.median(y),
                "u_statistic": np.nan,
                "p_value": np.nan,
                "effect_size": np.nan,
                "effect_size_method": "mannwhitney_effect",
                "effect_interpretation_cohen": np.nan,
                "significant": np.nan,
                "status": "Tamaño insuficiente en uno o ambos grupos"
            })
            continue

        try:
            u_stat, pval = mannwhitneyu(x, y, alternative=alternative)

            med1 = np.median(x)
            med2 = np.median(y)

            if med1 > med2:
                direction = f"{g1} > {g2}"
            elif med1 < med2:
                direction = f"{g1} < {g2}"
            else:
                direction = f"{g1} = {g2}"

            effect_size = mannwhitney_effect_size(x, y, u_stat)
            effect_label = interpret_mannwhitney_effect(effect_size)

            results.append({
                "variable": col,
                "group_1": g1,
                "group_2": g2,
                "n_group_1": n1,
                "n_group_2": n2,
                "median_group_1": med1,
                "median_group_2": med2,
                "direction_by_median": direction,
                "u_statistic": u_stat,
                "p_value": pval,
                "effect_size": effect_size,
                "effect_size_method": "mannwhitney_effect",
                "effect_interpretation_cohen": effect_label,
                "significant": pval < alpha,
                "status": "OK"
            })

        except Exception as e:
            results.append({
                "variable": col,
                "group_1": g1,
                "group_2": g2,
                "n_group_1": n1,
                "n_group_2": n2,
                "median_group_1": np.nan if n1 == 0 else np.median(x),
                "median_group_2": np.nan if n2 == 0 else np.median(y),
                "u_statistic": np.nan,
                "p_value": np.nan,
                "effect_size": np.nan,
                "effect_size_method": "mannwhitney_effect",
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
        print(f"Columna de grupo: {group_col}")
        print(f"Grupos comparados: {g1} vs {g2}")
        print(f"Observaciones tras merge: {merged_df.shape[0]}")
        print(f"Variables evaluadas: {len(value_cols)}")

    return merged_df, results_df