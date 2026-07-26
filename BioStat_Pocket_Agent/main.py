from Load import load_multiple_dataframes
from Caracterization import distribution_plots_from_loaded,normality_tests_from_loaded
from Kruscall_Wallis import kruskal_wallis_from_loaded
from Mann_Whitney import mann_whitney_from_loaded
from KDE import kde_from_loaded
from DB_Scan import dbscan_from_loaded

dfs = load_multiple_dataframes()
alpha  = 0.0003

if not dfs:
    print("No se cargó ningún archivo.")
else:
    for nombre, df in dfs.items():
        print(f"\nArchivo cargado: {nombre}")
        print(f"Shape del DataFrame: {df.shape}")
        print(f"Columnas: {df.columns.tolist()[:10]}{' ...' if len(df.columns) > 10 else ''}")
        
result_histogram_central_tendencies = distribution_plots_from_loaded(
    dfs=dfs,
    df_name="anthro_data",
    analysis_mode="both",
    numeric_cols=None,
    bins=80,
    plot_positive_hist=True,
    verbose=True
)

result_distribution = normality_tests_from_loaded(
    dfs=dfs,
    df_name="anthro_data",
    analysis_mode="both",
    value_mode="both",
    test_method="both",
    alpha=alpha,
    verbose=True
)

kde_outputs = kde_from_loaded(
    dfs=dfs,
    data_df_name="otu_data_converted",
    grid_size=1000,
    cv_subsample=1000,
    cv_folds=3,
    cv_bw_grid=8,
    min_bandwidth=1.0,
    cv_max_expansions=4,
    test_kernel_bandwidths=None,
    verbose=True,
)

merged_df_kruscall, kw_results = kruskal_wallis_from_loaded(
    dfs=dfs,
    alpha=alpha,
    group_df_name="anthro_data",
    value_df_name="anthro_data",
    group_col="bmi_class",
    id_col_group="ID",
    id_col_value="ID",
    value_cols=["glucose", "HDL", "LDL", "waist", "body_fat", "HOMA_IR"],
    min_group_size=3,
    apply_fdr=True,
    verbose=True
)

merged_df_mann_whitney, mw_results = mann_whitney_from_loaded(
    dfs=dfs,
    alpha=alpha,
    group_df_name="anthro_data",
    value_df_name="otu_data_converted",
    group_col="sex",
    groups_to_compare=("Male", "Female"),
    id_col_group="ID",
    id_col_value="ID",
    value_cols=None,
    min_group_size=3,
    alternative="two-sided",
    apply_fdr=True,
    verbose=True,
)

dbscan_result, dbscan_model, prepared, k_distances, cluster_summary = dbscan_from_loaded(
    dfs=dfs,
    data_df_name="anthro_data",
    meta_df_name="anthro_data",
    id_col="ID",
    meta_id_col="ID",
    feature_cols=["waist", "age", "HDL"],
    eps=1,
    min_samples=3,
    calculate_k_distance=True,
    k_distance_min_samples=8,
    drop_non_numeric=True,
    missing_strategy="fill_zero",
    remove_zero_rows=True,
    min_prevalence=None,
    min_total_abundance=None,
    transform_method="none",
    pseudocount=1.0,
    scale=True,
    embedding_method="pca",
    n_components=3,
    random_state=42,
    embedding_kwargs=None,
    plot_k_distance_graph=True,
    plot_embedding_graph=True,
    summary_numeric_cols=["glucose", "waist"],
    summary_categorical_cols=["bmi_class"],
    summary_numeric_aggs=("median",),
    verbose=True
)

