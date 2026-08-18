import pandas as pd
import numpy as np
import matplotlib.pyplot as plt

from sklearn.preprocessing import StandardScaler
from sklearn.cluster import DBSCAN
from sklearn.neighbors import NearestNeighbors
from sklearn.decomposition import PCA, KernelPCA
from sklearn.manifold import Isomap, MDS, TSNE

umap = None
HAS_UMAP = None
UMAP_IMPORT_ERROR = None


def get_df_from_dfs(dfs, df_name):

    if df_name is None:
        return None

    if df_name not in dfs:
        raise KeyError(
            f"No existe '{df_name}' en dfs. "
            f"Disponibles: {list(dfs.keys())}"
        )

    return dfs[df_name].copy()


def _as_list(value):
    """
    Convierte None, string o listas/tuplas en lista normal.
    """
    if value is None:
        return None

    if isinstance(value, str):
        return [value]

    return list(value)

def clr_transform(X, pseudocount=1.0):


    X = np.asarray(X, dtype=float)

    if np.any(X < 0):
        raise ValueError(
            "La matriz contiene valores negativos; CLR no es apropiada así."
        )

    X_pc = X + pseudocount
    row_sums = X_pc.sum(axis=1, keepdims=True)

    if np.any(row_sums == 0):
        raise ValueError(
            "Hay filas con suma 0 incluso tras aplicar pseudocount."
        )

    X_closed = X_pc / row_sums
    log_X = np.log(X_closed)
    gm_log = log_X.mean(axis=1, keepdims=True)
    X_clr = log_X - gm_log

    return X_clr


def apply_feature_transform(X, method="none", pseudocount=1.0):

    method = str(method).lower()

    if method == "none":
        return X

    if method == "log1p":
        if np.any(X < 0):
            raise ValueError("log1p no admite valores negativos.")
        return np.log1p(X)

    if method == "clr":
        return clr_transform(X, pseudocount=pseudocount)

    raise ValueError(f"Transformación no soportada: {method}")

def apply_embedding(
    X_scaled,
    method="pca",
    n_components=10,
    random_state=42,
    **kwargs
):

    method = str(method).lower()

    if method == "none":
        return X_scaled, None

    n_samples, n_features = X_scaled.shape

    if n_samples < 2:
        raise ValueError("Se necesitan al menos 2 filas para aplicar embedding.")

    if method == "pca":
        max_components = min(n_components, n_samples - 1, n_features)

        if max_components < 2:
            raise ValueError("No hay suficientes dimensiones para PCA.")

        model = PCA(
            n_components=max_components,
            random_state=random_state
        )

        X_embed = model.fit_transform(X_scaled)

        return X_embed, model

    if method == "kpca":
        max_components = min(n_components, n_samples - 1, n_features)

        if max_components < 2:
            raise ValueError("No hay suficientes dimensiones para KernelPCA.")

        model = KernelPCA(
            n_components=max_components,
            kernel=kwargs.get("kernel", "rbf"),
            gamma=kwargs.get("gamma", None)
        )

        X_embed = model.fit_transform(X_scaled)

        return X_embed, model

    if method == "isomap":
        max_components = min(n_components, n_samples - 1, n_features)

        if max_components < 2:
            raise ValueError("No hay suficientes dimensiones para Isomap.")

        n_neighbors = kwargs.get("n_neighbors", 10)
        n_neighbors = min(n_neighbors, n_samples - 1)

        model = Isomap(
            n_components=max_components,
            n_neighbors=n_neighbors
        )

        X_embed = model.fit_transform(X_scaled)

        return X_embed, model

    if method == "mds":
        max_components = min(n_components, n_samples - 1)

        if max_components < 2:
            raise ValueError("No hay suficientes dimensiones para MDS.")

        model = MDS(
            n_components=max_components,
            random_state=random_state,
            n_init=kwargs.get("n_init", 4),
            max_iter=kwargs.get("max_iter", 300)
        )

        X_embed = model.fit_transform(X_scaled)

        return X_embed, model

    if method == "tsne":
        if n_samples < 3:
            raise ValueError("t-SNE requiere al menos 3 muestras.")

        max_components = min(n_components, 3)

        if max_components < 2:
            raise ValueError("t-SNE requiere al menos 2 componentes.")

        perplexity = kwargs.get("perplexity", 30)

        if perplexity >= n_samples:
            perplexity = max(2, n_samples - 1)

        model = TSNE(
            n_components=max_components,
            random_state=random_state,
            perplexity=perplexity,
            init=kwargs.get("init", "pca"),
            learning_rate=kwargs.get("learning_rate", "auto")
        )

        X_embed = model.fit_transform(X_scaled)

        return X_embed, model

    if method == "umap":
        global umap, HAS_UMAP, UMAP_IMPORT_ERROR

        if HAS_UMAP is not True:
            try:
                import umap as _umap
                umap = _umap
                HAS_UMAP = True
                UMAP_IMPORT_ERROR = None
            except Exception as exc:
                umap = None
                HAS_UMAP = False
                UMAP_IMPORT_ERROR = exc

        if HAS_UMAP is not True:
            raise ImportError(
                "UMAP no esta disponible en este entorno. "
                "Instala/repara umap-learn o usa otro embedding. "
                f"Detalle: {UMAP_IMPORT_ERROR}"
            )

        max_components = min(n_components, n_features)

        if max_components < 2:
            raise ValueError("UMAP requiere al menos 2 componentes.")

        n_neighbors = kwargs.get("n_neighbors", 15)
        n_neighbors = min(n_neighbors, n_samples - 1)

        model = umap.UMAP(
            n_components=max_components,
            n_neighbors=n_neighbors,
            min_dist=kwargs.get("min_dist", 0.1),
            metric=kwargs.get("metric", "euclidean"),
            random_state=random_state
        )

        X_embed = model.fit_transform(X_scaled)

        return X_embed, model

    raise ValueError(f"Embedding no soportado: {method}")

def prepare_data_for_dbscan(
    df,
    id_col=None,
    feature_cols=None,
    drop_non_numeric=True,
    missing_strategy="fill_zero",
    remove_zero_rows=False,
    min_prevalence=None,
    min_total_abundance=None,
    transform_method="none",
    pseudocount=1.0,
    scale=True,
    embedding_method="pca",
    n_components=10,
    random_state=42,
    embedding_kwargs=None,
    verbose=True
):

    work_df = df.copy()

    if id_col is not None and id_col not in work_df.columns:
        raise KeyError(f"La columna ID '{id_col}' no existe en el DataFrame.")

    if feature_cols is None:
        feature_cols = [c for c in work_df.columns if c != id_col]
    else:
        feature_cols = _as_list(feature_cols)
        missing_cols = [c for c in feature_cols if c not in work_df.columns]

        if missing_cols:
            raise KeyError(
                f"Estas columnas no existen en el DataFrame: {missing_cols}"
            )

    if id_col is not None:
        ids = work_df[id_col].astype(str).str.strip().reset_index(drop=True)
        ids.name = id_col
    else:
        ids = pd.Series(
            np.arange(len(work_df)).astype(str),
            name="row_id"
        )

    X_source = work_df[feature_cols].copy()

    numeric_data = pd.DataFrame(index=X_source.index)
    removed_cols = []

    for col in X_source.columns:
        converted_col = pd.to_numeric(X_source[col], errors="coerce")

        if drop_non_numeric and converted_col.notna().sum() == 0:
            removed_cols.append(col)
        else:
            numeric_data[col] = converted_col

    X_df = numeric_data.reset_index(drop=True)
    ids = ids.reset_index(drop=True)

    if X_df.shape[1] == 0:
        raise ValueError(
            "No quedaron columnas numéricas para clustering. "
            "Revisa feature_cols o usa drop_non_numeric=False."
        )

    if missing_strategy == "fill_zero":
        X_df = X_df.fillna(0)

    elif missing_strategy == "drop_rows":
        valid_mask = X_df.notna().all(axis=1)
        X_df = X_df.loc[valid_mask].reset_index(drop=True)
        ids = ids.loc[valid_mask].reset_index(drop=True)

    elif missing_strategy == "median":
        X_df = X_df.fillna(X_df.median(numeric_only=True))

    else:
        raise ValueError(
            "missing_strategy debe ser 'fill_zero', 'drop_rows' o 'median'."
        )

    if remove_zero_rows:
        row_sums = X_df.sum(axis=1)
        valid_rows = row_sums > 0
        X_df = X_df.loc[valid_rows].reset_index(drop=True)
        ids = ids.loc[valid_rows].reset_index(drop=True)

    if X_df.shape[0] == 0:
        raise ValueError("No quedaron filas válidas para clustering.")

    if min_prevalence is not None:
        prevalence = (X_df > 0).mean(axis=0)
        X_df = X_df.loc[:, prevalence >= min_prevalence]

    if min_total_abundance is not None:
        total_abundance = X_df.sum(axis=0)
        X_df = X_df.loc[:, total_abundance >= min_total_abundance]

    if X_df.shape[1] == 0:
        raise ValueError("No quedaron columnas tras los filtros aplicados.")

    X_raw = X_df.values.astype(float)

    X_transformed = apply_feature_transform(
        X_raw,
        method=transform_method,
        pseudocount=pseudocount
    )

    if scale:
        scaler = StandardScaler()
        X_scaled = scaler.fit_transform(X_transformed)
    else:
        scaler = None
        X_scaled = X_transformed

    if embedding_kwargs is None:
        embedding_kwargs = {}

    X_embed, embedding_model = apply_embedding(
        X_scaled=X_scaled,
        method=embedding_method,
        n_components=n_components,
        random_state=random_state,
        **embedding_kwargs
    )

    if verbose:
        print("=== Preparación general para DBSCAN ===")
        print(f"Filas válidas: {X_df.shape[0]}")
        print(f"Variables retenidas: {X_df.shape[1]}")
        print(f"Transformación: {transform_method}")
        print(f"Escalado: {scale}")
        print(f"Embedding: {embedding_method}")
        print(f"Dimensiones embedding: {X_embed.shape[1]}")

        if removed_cols:
            print(f"Columnas removidas por no numéricas: {removed_cols}")

        if embedding_method == "pca" and hasattr(
            embedding_model,
            "explained_variance_ratio_"
        ):
            explained_var = embedding_model.explained_variance_ratio_
            print(
                "Varianza explicada acumulada PCA: "
                f"{explained_var.cumsum()[-1]:.4f}"
            )

    filtered_df = pd.concat(
        [
            ids.reset_index(drop=True),
            X_df.reset_index(drop=True)
        ],
        axis=1
    )

    prepared = {
        "ids": ids.reset_index(drop=True),
        "feature_names": X_df.columns.tolist(),
        "X_raw": X_raw,
        "X_transformed": X_transformed,
        "X_scaled": X_scaled,
        "X_embed": X_embed,
        "transform_method": transform_method,
        "scale": scale,
        "scaler": scaler,
        "embedding_method": embedding_method,
        "embedding_model": embedding_model,
        "filtered_df": filtered_df,
        "removed_cols": removed_cols
    }

    if embedding_method == "pca" and hasattr(
        embedding_model,
        "explained_variance_ratio_"
    ):
        prepared["explained_variance_ratio"] = (
            embedding_model.explained_variance_ratio_
        )

    return prepared

def plot_k_distance(
    X,
    min_samples=8,
    figsize=(8, 5),
    show_plot=True
):

    if min_samples < 2:
        raise ValueError("min_samples debe ser al menos 2.")

    if min_samples > X.shape[0]:
        raise ValueError(
            "min_samples no puede ser mayor que el número de filas disponibles."
        )

    nn = NearestNeighbors(n_neighbors=min_samples)
    nn.fit(X)

    distances, _ = nn.kneighbors(X)

    k_distances = np.sort(distances[:, -1])

    if show_plot:
        plt.figure(figsize=figsize)
        plt.plot(k_distances)
        plt.xlabel("Muestras ordenadas")
        plt.ylabel(f"Distancia al vecino #{min_samples}")
        plt.title("K-distance plot para elegir eps")
        plt.grid(True, alpha=0.3)
        plt.show()

    return k_distances

def run_dbscan(
    prepared,
    eps,
    min_samples=8,
    id_col="ID",
    meta_df=None,
    meta_id_col="ID",
    verbose=True
):

    if eps <= 0:
        raise ValueError("eps debe ser mayor que 0.")

    if min_samples < 1:
        raise ValueError("min_samples debe ser al menos 1.")

    X = prepared["X_embed"]
    ids = prepared["ids"].reset_index(drop=True).astype(str)

    model = DBSCAN(
        eps=eps,
        min_samples=min_samples
    )

    labels = model.fit_predict(X)

    result_df = pd.DataFrame({
        id_col: ids,
        "dbscan_cluster": labels
    })

    result_df["dbscan_is_noise"] = result_df["dbscan_cluster"] == -1

    if meta_df is not None:
        meta = meta_df.copy()

        if meta_id_col not in meta.columns:
            raise KeyError(f"La columna '{meta_id_col}' no existe en meta_df.")

        meta[meta_id_col] = meta[meta_id_col].astype(str).str.strip()
        result_df[id_col] = result_df[id_col].astype(str).str.strip()

        reserved_cols = ["dbscan_cluster", "dbscan_is_noise"]
        cols_to_drop = [
            c for c in reserved_cols
            if c in meta.columns and c != meta_id_col
        ]

        if cols_to_drop:
            meta = meta.drop(columns=cols_to_drop)

        merged = pd.merge(
            result_df,
            meta,
            left_on=id_col,
            right_on=meta_id_col,
            how="left"
        )

        if meta_id_col != id_col and meta_id_col in merged.columns:
            merged = merged.drop(columns=[meta_id_col])

        result_df = merged

    if verbose:
        counts = pd.Series(labels).value_counts().sort_index()

        print("=== Resultado DBSCAN ===")
        print(counts)

        n_noise = int((labels == -1).sum())
        n_clusters = len(set(labels)) - (1 if -1 in labels else 0)

        print(f"Ruido (-1): {n_noise}")
        print(f"Clusters reales: {n_clusters}")

    return result_df, model

def plot_dbscan_embedding(
    prepared,
    cluster_df,
    id_col="ID",
    label_col="dbscan_cluster",
    figsize=(8, 6)
):

    X_embed = prepared["X_embed"]
    method = prepared.get("embedding_method", "embedding")

    if X_embed.shape[1] < 2:
        raise ValueError("Se necesitan al menos 2 dimensiones para graficar.")

    plot_df = pd.DataFrame(
        X_embed[:, :2],
        columns=["Dim1", "Dim2"]
    )

    plot_df[id_col] = prepared["ids"].astype(str).values

    aux = cluster_df[[id_col, label_col]].copy()
    aux[id_col] = aux[id_col].astype(str).str.strip()
    plot_df[id_col] = plot_df[id_col].astype(str).str.strip()

    plot_df = plot_df.merge(
        aux,
        on=id_col,
        how="left"
    )

    plt.figure(figsize=figsize)

    for cluster_id in sorted(plot_df[label_col].dropna().unique()):
        subset = plot_df[plot_df[label_col] == cluster_id]
        label = "Ruido" if cluster_id == -1 else f"Cluster {cluster_id}"

        plt.scatter(
            subset["Dim1"],
            subset["Dim2"],
            label=label,
            alpha=0.7
        )

    plt.xlabel("Dim1")
    plt.ylabel("Dim2")
    plt.title(f"DBSCAN sobre {method.upper()}")
    plt.legend()
    plt.grid(True, alpha=0.3)
    plt.show()

def build_dbscan_cluster_summary(
    result_df,
    label_col="dbscan_cluster",
    numeric_cols=None,
    categorical_cols=None,
    numeric_aggs=("median",)
):

    if label_col not in result_df.columns:
        raise KeyError(f"No existe la columna de cluster '{label_col}'.")

    numeric_cols = _as_list(numeric_cols)
    categorical_cols = _as_list(categorical_cols)

    summary = {}

    cluster_counts = (
        result_df[label_col]
        .value_counts(dropna=False)
        .sort_index()
        .reset_index()
    )

    cluster_counts.columns = [label_col, "n"]

    summary["cluster_counts"] = cluster_counts

    if numeric_cols:
        valid_numeric_cols = [
            c for c in numeric_cols
            if c in result_df.columns
        ]

        missing_numeric_cols = [
            c for c in numeric_cols
            if c not in result_df.columns
        ]

        if missing_numeric_cols:
            print(
                "Advertencia: estas columnas numéricas no existen "
                f"en result_df y serán omitidas: {missing_numeric_cols}"
            )

        if valid_numeric_cols:
            num_df = result_df[[label_col] + valid_numeric_cols].copy()

            for col in valid_numeric_cols:
                num_df[col] = pd.to_numeric(num_df[col], errors="coerce")

            agg_dict = {
                col: list(numeric_aggs)
                for col in valid_numeric_cols
            }

            numeric_summary = num_df.groupby(label_col).agg(agg_dict)

            numeric_summary.columns = [
                f"{col}_{agg}"
                for col, agg in numeric_summary.columns
            ]

            numeric_summary = numeric_summary.reset_index()

            summary["numeric_summary"] = numeric_summary
        else:
            summary["numeric_summary"] = None
    else:
        summary["numeric_summary"] = None

    if categorical_cols:
        categorical_frames = []

        valid_categorical_cols = [
            c for c in categorical_cols
            if c in result_df.columns
        ]

        missing_categorical_cols = [
            c for c in categorical_cols
            if c not in result_df.columns
        ]

        if missing_categorical_cols:
            print(
                "Advertencia: estas columnas categóricas no existen "
                f"en result_df y serán omitidas: {missing_categorical_cols}"
            )

        for col in valid_categorical_cols:
            temp = (
                result_df
                .groupby(label_col, dropna=False)[col]
                .value_counts(dropna=False)
                .rename("count")
                .reset_index()
            )

            temp = temp.rename(columns={col: "category_value"})
            temp.insert(1, "variable", col)

            categorical_frames.append(temp)

        if categorical_frames:
            categorical_summary = pd.concat(
                categorical_frames,
                ignore_index=True
            )

            summary["categorical_summary"] = categorical_summary
        else:
            summary["categorical_summary"] = None
    else:
        summary["categorical_summary"] = None

    return summary

def dbscan_from_loaded(
    dfs,
    data_df_name,
    id_col="ID",
    feature_cols=None,

    meta_df_name=None,
    meta_id_col=None,

    eps=1.0,
    min_samples=3,

    calculate_k_distance=True,
    k_distance_min_samples=8,

    drop_non_numeric=True,
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

    plot_k_distance_graph=True,
    plot_embedding_graph=True,
    k_distance_figsize=(8, 5),
    embedding_figsize=(8, 6),

    summary_numeric_cols=None,
    summary_categorical_cols=None,
    summary_numeric_aggs=("median",),

    verbose=True
):

    data_df = get_df_from_dfs(dfs, data_df_name)

    if meta_df_name is not None:
        meta_df = get_df_from_dfs(dfs, meta_df_name)
    else:
        meta_df = None

    if meta_id_col is None:
        meta_id_col = id_col

    prepared = prepare_data_for_dbscan(
        df=data_df,
        id_col=id_col,
        feature_cols=feature_cols,
        drop_non_numeric=drop_non_numeric,
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
        embedding_kwargs=embedding_kwargs,
        verbose=verbose
    )

    if calculate_k_distance:
        k_distances = plot_k_distance(
            X=prepared["X_embed"],
            min_samples=k_distance_min_samples,
            figsize=k_distance_figsize,
            show_plot=plot_k_distance_graph
        )
    else:
        k_distances = None

    dbscan_result, dbscan_model = run_dbscan(
        prepared=prepared,
        eps=eps,
        min_samples=min_samples,
        id_col=id_col,
        meta_df=meta_df,
        meta_id_col=meta_id_col,
        verbose=verbose
    )

    if plot_embedding_graph:
        plot_dbscan_embedding(
            prepared=prepared,
            cluster_df=dbscan_result,
            id_col=id_col,
            label_col="dbscan_cluster",
            figsize=embedding_figsize
        )

    cluster_summary = build_dbscan_cluster_summary(
        result_df=dbscan_result,
        label_col="dbscan_cluster",
        numeric_cols=summary_numeric_cols,
        categorical_cols=summary_categorical_cols,
        numeric_aggs=summary_numeric_aggs
    )

    if verbose:
        print("=== Resumen de salida ===")
        print("Objeto 1: dbscan_result")
        print("Objeto 2: dbscan_model")
        print("Objeto 3: prepared")
        print("Objeto 4: k_distances")
        print("Objeto 5: cluster_summary")

    return (
        dbscan_result,
        dbscan_model,
        prepared,
        k_distances,
        cluster_summary
    )
