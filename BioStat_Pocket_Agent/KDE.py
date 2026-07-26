import pandas as pd
import numpy as np
import matplotlib.pyplot as plt
import time
import math

from scipy.stats import gaussian_kde
from sklearn.model_selection import KFold
from sklearn.neighbors import KernelDensity


def get_otu_positive_values(dfs, data_df_name="otu_data_converted"):
    if data_df_name not in dfs:
        raise KeyError(f"No existe '{data_df_name}' en dfs. Disponibles: {list(dfs.keys())}")

    df = dfs[data_df_name].copy()
    values = df.select_dtypes(include=[np.number]).to_numpy(dtype=float).ravel()
    values = values[np.isfinite(values)]
    positives = values[values > 0]

    if positives.size == 0:
        raise ValueError(f"'{data_df_name}' no contiene valores numericos positivos.")

    return positives


def suggest_grid_size(n_values):
    if n_values <= 250_000:
        return 1000
    if n_values <= 1_000_000:
        return 1500
    return 2000


def make_log_grid(values, grid_size, bandwidth):
    positives = np.asarray(values, dtype=float).ravel()
    positives = positives[np.isfinite(positives)]
    positives = positives[positives > 0]

    if positives.size == 0:
        raise ValueError("Se requiere al menos un valor positivo.")
    if bandwidth <= 0:
        raise ValueError("El bandwidth debe ser positivo.")

    lower = max(float(np.min(positives)) * 1e-3, 1e-12)
    upper = float(np.max(positives) + 8.0 * bandwidth)
    return np.logspace(np.log10(lower), np.log10(upper), int(grid_size))


def evaluate_grid(values, grid_size, bandwidth):
    x_grid = make_log_grid(values, grid_size, bandwidth)
    grid_summary = pd.DataFrame([{
        "grid_sugerido": suggest_grid_size(len(values)),
        "grid_usado": grid_size,
        "minimo_grid": float(x_grid.min()),
        "maximo_grid": float(x_grid.max()),
        "minimo_datos": float(np.min(values)),
        "maximo_datos": float(np.max(values)),
    }])
    return x_grid, grid_summary


def show_dataframe(df):
    try:
        from IPython import get_ipython
        from IPython.display import display as ipython_display

        if get_ipython() is not None:
            ipython_display(df)
            return
    except ImportError:
        pass

    print(df.to_string(index=False))


def prepare_values(values):
    arr = np.asarray(values, dtype=float).ravel()
    arr = arr[np.isfinite(arr)]

    if arr.size < 2:
        raise ValueError("Se requieren al menos 2 valores finitos.")
    if np.nanstd(arr, ddof=1) <= 0:
        raise ValueError("No se puede estimar bandwidth con varianza cero.")

    return arr


def get_kernels():
    return (
        "gaussian",
        "epanechnikov",
        "tophat",
        "exponential",
        "linear",
        "cosine",
        "quartic",
        "triweight",
        "tricube",
        "logistic",
        "sigmoid",
        "cauchy",
    )


def get_color_map():
    return {
        "gaussian": "#4c78a8",
        "epanechnikov": "#e45756",
        "tophat": "#f58518",
        "exponential": "#54a24b",
        "linear": "#b279a2",
        "cosine": "#9d755d",
        "quartic": "#72b7b2",
        "triweight": "#ff9da6",
        "tricube": "#b5cf6b",
        "logistic": "#eeca3b",
        "sigmoid": "#17becf",
        "cauchy": "#9467bd",
    }

def scott_h(values):
    values = prepare_values(values)
    std = float(np.std(values, ddof=1))
    return float(gaussian_kde(values, bw_method="scott").factor * std)


def silverman_h(values):
    values = prepare_values(values)
    std = float(np.std(values, ddof=1))
    return float(gaussian_kde(values, bw_method="silverman").factor * std)


def cv_loglik(
    values,
    kernel="gaussian",
    cv_folds=3,
    n_subsample=1000,
    n_bw=8,
    bw_lo_factor=0.02,
    bw_hi_factor=3.0,
    seed=42,
    min_bandwidth=1.0,
    expansion_factor=4.0,
    max_expansions=4,
):
    values = prepare_values(values)
    rng = np.random.default_rng(seed)
    k = min(int(n_subsample), len(values))
    folds = min(int(cv_folds), k)
    n_bw = max(3, int(n_bw))

    if folds < 2:
        raise ValueError("Se requieren al menos 2 observaciones para validacion cruzada.")
    if min_bandwidth <= 0:
        raise ValueError("min_bandwidth debe ser positivo.")
    if expansion_factor <= 1:
        raise ValueError("expansion_factor debe ser mayor que 1.")

    sample = values[rng.choice(len(values), size=k, replace=False)].reshape(-1, 1)
    bw_scott_abs = scott_h(values)
    lo_factor = float(bw_lo_factor)
    hi_factor = float(bw_hi_factor)
    status = "interior"

    kf = KFold(n_splits=folds, shuffle=True, random_state=seed)

    for _ in range(int(max_expansions) + 1):
        bw_min = max(float(min_bandwidth), bw_scott_abs * lo_factor)
        bw_max = max(bw_min * 1.01, bw_scott_abs * hi_factor)
        bw_grid = np.geomspace(bw_min, bw_max, n_bw)
        scores = np.zeros(len(bw_grid))

        for i, bw in enumerate(bw_grid):
            fold_scores = []
            for train_idx, val_idx in kf.split(sample):
                pdf = evaluate_kde_fast(
                    sample[train_idx].ravel(),
                    sample[val_idx].ravel(),
                    bw,
                    kernel,
                )
                pdf = np.maximum(pdf, np.finfo(float).tiny)
                fold_scores.append(float(np.sum(np.log(pdf))))
            scores[i] = float(np.mean(fold_scores))

        best_idx = int(np.argmax(scores))

        if best_idx == 0:
            if bw_min <= float(min_bandwidth) * 1.0000001:
                status = "piso_minimo"
                break
            lo_factor /= expansion_factor
            status = "borde_inferior"
            continue

        if best_idx == len(bw_grid) - 1:
            hi_factor *= expansion_factor
            status = "borde_superior"
            continue

        status = "interior"
        break

    best_idx = int(np.argmax(scores))
    return float(bw_grid[best_idx]), bw_grid, scores, status


def estimate_bandwidths_by_kernel(values, cv_folds=3, n_subsample=1000, n_bw=8, min_bandwidth=1.0, max_expansions=4):
    rows = []
    score_curves = {}
    bandwidth_status = {}
    h_scott = scott_h(values)
    h_silverman = silverman_h(values)

    for kernel in get_kernels():
        best_bw, bw_grid, scores, status = cv_loglik(
            values,
            kernel=kernel,
            cv_folds=cv_folds,
            n_subsample=n_subsample,
            n_bw=n_bw,
            min_bandwidth=min_bandwidth,
            max_expansions=max_expansions,
        )
        best_idx = int(np.argmax(scores))
        rows.append({
            "kernel": kernel,
            "bandwidth_cv": best_bw,
            "score_cv": float(scores[best_idx]),
            "estado_cv": status,
            "bandwidth_scott": h_scott,
            "bandwidth_silverman": h_silverman,
        })
        score_curves[kernel] = (bw_grid, scores)
        bandwidth_status[kernel] = status

    bandwidth_summary = pd.DataFrame(rows)
    kernel_bandwidths = dict(zip(bandwidth_summary["kernel"], bandwidth_summary["bandwidth_cv"]))
    common_bandwidth = kernel_bandwidths["gaussian"]

    return bandwidth_summary, kernel_bandwidths, common_bandwidth, score_curves, bandwidth_status

def positive_mass(pdf, x_grid):
    return float(np.trapezoid(pdf, x_grid))


def normalize_conditional(pdf, x_grid):
    pdf = np.maximum(np.asarray(pdf, dtype=float), 0.0)
    mass = positive_mass(pdf, x_grid)

    if not np.isfinite(mass) or mass <= 0:
        raise ValueError("La densidad KDE tiene masa no positiva o no finita.")

    return pdf / mass, mass


def evaluate_kde_gaussian_fast(data, x_grid, bandwidth):
    kde = KernelDensity(kernel="gaussian", bandwidth=bandwidth, breadth_first=False)
    kde.fit(np.asarray(data, dtype=float).reshape(-1, 1))
    return np.exp(kde.score_samples(np.asarray(x_grid, dtype=float).reshape(-1, 1)))


def sorted_prefix(data, max_power=9):
    sorted_data = np.sort(np.asarray(data, dtype=float))
    prefixes = [np.concatenate(([0.0], np.cumsum(sorted_data ** p))) for p in range(max_power + 1)]
    return sorted_data, prefixes


def segment_moment(prefixes, left, right, power):
    return prefixes[power][right] - prefixes[power][left]


def centered_moment(x, prefixes, left, right, power):
    total = np.zeros_like(x, dtype=float)
    for j in range(power + 1):
        coef = math.comb(power, j) * ((-1.0) ** j)
        total += coef * (x ** (power - j)) * segment_moment(prefixes, left, right, j)
    return total


def abs_centered_moment(sorted_data, prefixes, x, left, right, power):
    mid = np.searchsorted(sorted_data, x, side="right")
    mid = np.minimum(np.maximum(mid, left), right)

    left_total = np.zeros_like(x, dtype=float)
    for j in range(power + 1):
        coef = math.comb(power, j) * ((-1.0) ** j)
        left_total += coef * (x ** (power - j)) * segment_moment(prefixes, left, mid, j)

    right_total = np.zeros_like(x, dtype=float)
    for j in range(power + 1):
        coef = math.comb(power, j) * ((-1.0) ** (power - j))
        right_total += coef * (x ** (power - j)) * segment_moment(prefixes, mid, right, j)

    return left_total + right_total


def evaluate_finite_support_fast(data, x_grid, bandwidth, kernel):
    sorted_data, prefixes = sorted_prefix(data, max_power=9)
    n = float(sorted_data.size)
    x = np.asarray(x_grid, dtype=float)
    left = np.searchsorted(sorted_data, x - bandwidth, side="left")
    right = np.searchsorted(sorted_data, x + bandwidth, side="right")
    count = (right - left).astype(float)

    if kernel == "tophat":
        return 0.5 * count / (n * bandwidth)

    if kernel == "epanechnikov":
        s2 = centered_moment(x, prefixes, left, right, 2)
        return 0.75 * (count - s2 / (bandwidth ** 2)) / (n * bandwidth)

    if kernel == "linear":
        s1_abs = abs_centered_moment(sorted_data, prefixes, x, left, right, 1)
        return (count - s1_abs / bandwidth) / (n * bandwidth)

    if kernel == "quartic":
        s2 = centered_moment(x, prefixes, left, right, 2)
        s4 = centered_moment(x, prefixes, left, right, 4)
        values = count - 2.0 * s2 / (bandwidth ** 2) + s4 / (bandwidth ** 4)
        return (15.0 / 16.0) * values / (n * bandwidth)

    if kernel == "triweight":
        s2 = centered_moment(x, prefixes, left, right, 2)
        s4 = centered_moment(x, prefixes, left, right, 4)
        s6 = centered_moment(x, prefixes, left, right, 6)
        values = count - 3.0 * s2 / (bandwidth ** 2) + 3.0 * s4 / (bandwidth ** 4) - s6 / (bandwidth ** 6)
        return (35.0 / 32.0) * values / (n * bandwidth)

    if kernel == "tricube":
        s3_abs = abs_centered_moment(sorted_data, prefixes, x, left, right, 3)
        s6 = centered_moment(x, prefixes, left, right, 6)
        s9_abs = abs_centered_moment(sorted_data, prefixes, x, left, right, 9)
        values = count - 3.0 * s3_abs / (bandwidth ** 3) + 3.0 * s6 / (bandwidth ** 6) - s9_abs / (bandwidth ** 9)
        return (70.0 / 81.0) * values / (n * bandwidth)

    if kernel == "cosine":
        c = np.pi / (2.0 * bandwidth)
        prefix_cos = np.concatenate(([0.0], np.cumsum(np.cos(c * sorted_data))))
        prefix_sin = np.concatenate(([0.0], np.cumsum(np.sin(c * sorted_data))))
        sum_cos = prefix_cos[right] - prefix_cos[left]
        sum_sin = prefix_sin[right] - prefix_sin[left]
        values = np.cos(c * x) * sum_cos + np.sin(c * x) * sum_sin
        return (np.pi / 4.0) * values / (n * bandwidth)

    raise ValueError(f"Kernel no soportado por el metodo rapido: {kernel}")


def evaluate_exponential_fast(data, x_grid, bandwidth):
    sorted_data = np.sort(np.asarray(data, dtype=float))
    n = float(sorted_data.size)
    x = np.asarray(x_grid, dtype=float)
    order = np.argsort(x)
    xs = x[order]

    left_sum = np.zeros_like(xs)
    acc = 0.0
    data_idx = 0
    previous_x = xs[0]

    for i, current_x in enumerate(xs):
        if i > 0:
            acc *= np.exp(-(current_x - previous_x) / bandwidth)
        while data_idx < sorted_data.size and sorted_data[data_idx] <= current_x:
            acc += np.exp((sorted_data[data_idx] - current_x) / bandwidth)
            data_idx += 1
        left_sum[i] = acc
        previous_x = current_x

    right_sum = np.zeros_like(xs)
    acc = 0.0
    data_idx = sorted_data.size - 1
    previous_x = xs[-1]

    for i in range(xs.size - 1, -1, -1):
        current_x = xs[i]
        if i < xs.size - 1:
            acc *= np.exp(-(previous_x - current_x) / bandwidth)
        while data_idx >= 0 and sorted_data[data_idx] > current_x:
            acc += np.exp((current_x - sorted_data[data_idx]) / bandwidth)
            data_idx -= 1
        right_sum[i] = acc
        previous_x = current_x

    out_sorted = 0.5 * (left_sum + right_sum) / (n * bandwidth)
    out = np.empty_like(out_sorted)
    out[order] = out_sorted
    return out


def evaluate_tricube_direct(data, x_grid, bandwidth, chunk_size=64):
    data = np.asarray(data, dtype=float).ravel()
    x = np.asarray(x_grid, dtype=float).ravel()
    n = float(data.size)
    out = np.zeros_like(x, dtype=float)

    for start in range(0, len(x), chunk_size):
        end = min(start + chunk_size, len(x))
        u = np.abs((x[start:end, None] - data[None, :]) / bandwidth)
        values = np.where(u <= 1.0, (1.0 - u ** 3) ** 3, 0.0)
        out[start:end] = (70.0 / 81.0) * values.sum(axis=1) / (n * bandwidth)

    return out


def evaluate_infinite_support_chunked(data, x_grid, bandwidth, kernel, chunk_size=64):
    data = np.asarray(data, dtype=float).ravel()
    x = np.asarray(x_grid, dtype=float).ravel()
    n = float(data.size)
    out = np.zeros_like(x, dtype=float)

    for start in range(0, len(x), chunk_size):
        end = min(start + chunk_size, len(x))
        u = (x[start:end, None] - data[None, :]) / bandwidth
        z = np.abs(u)

        if kernel == "logistic":
            ez = np.exp(-z)
            ku = ez / ((1.0 + ez) ** 2)
        elif kernel == "sigmoid":
            ez = np.exp(-z)
            ku = (2.0 * ez / (1.0 + ez * ez)) / np.pi
        elif kernel == "cauchy":
            ku = 1.0 / (np.pi * (1.0 + u * u))
        else:
            raise ValueError(f"Kernel de soporte real no soportado: {kernel}")

        out[start:end] = ku.sum(axis=1) / (n * bandwidth)

    return out


def evaluate_kde_fast(data, x_grid, bandwidth, kernel):
    finite_fast_kernels = {"epanechnikov", "tophat", "linear", "cosine", "quartic", "triweight"}
    infinite_chunked_kernels = {"logistic", "sigmoid", "cauchy"}
    data = np.asarray(data, dtype=float).ravel()
    data = data[np.isfinite(data)]

    if bandwidth <= 0:
        raise ValueError("El bandwidth debe ser positivo.")
    if kernel not in get_kernels():
        raise ValueError(f"Kernel desconocido: {kernel}")
    if kernel in finite_fast_kernels:
        return np.maximum(evaluate_finite_support_fast(data, x_grid, bandwidth, kernel), 0.0)
    if kernel == "tricube":
        return evaluate_tricube_direct(data, x_grid, bandwidth)
    if kernel == "exponential":
        return np.maximum(evaluate_exponential_fast(data, x_grid, bandwidth), 0.0)
    if kernel in infinite_chunked_kernels:
        return np.maximum(evaluate_infinite_support_chunked(data, x_grid, bandwidth, kernel), 0.0)

    return np.maximum(evaluate_kde_gaussian_fast(data, x_grid, bandwidth), 0.0)


def evaluate_kde_set(values, grid_size, bandwidths):
    densities = {}

    for kernel in get_kernels():
        bandwidth = bandwidths[kernel]
        x_grid = make_log_grid(values, grid_size, bandwidth)
        pdf = evaluate_kde_fast(values, x_grid, bandwidth, kernel)
        density, _ = normalize_conditional(pdf, x_grid)
        densities[kernel] = (x_grid, density)

    return densities

def plot_grid_evaluation(values, x_grid):
    fig, ax = plt.subplots(figsize=(10, 4))
    ax.hist(values, bins=80, density=True, alpha=0.35, label="Valores positivos")
    ax.scatter(x_grid, np.zeros_like(x_grid), s=4, alpha=0.25, label="Grilla")
    ax.set_xscale("log")
    ax.set_xlabel("Valor OTU positivo")
    ax.set_ylabel("Densidad empirica")
    ax.set_title("Evaluacion de grilla")
    ax.grid(True, alpha=0.25)
    ax.legend(fontsize=9)
    fig.tight_layout()
    plt.show()


def plot_cv_scores_by_kernel(score_curves, kernel_bandwidths, bandwidth_status=None):
    color_map = get_color_map()
    fig, axes = plt.subplots(3, 4, figsize=(16, 10), sharex=True)

    for ax, kernel in zip(axes.ravel(), get_kernels()):
        bw_grid, scores = score_curves[kernel]
        best_bw = kernel_bandwidths[kernel]
        status = "interior" if bandwidth_status is None else bandwidth_status.get(kernel, "interior")
        status_label = "" if status == "interior" else f" | {status}"
        ax.plot(bw_grid, scores, marker="o", linewidth=1.3, color=color_map[kernel])
        ax.axvline(best_bw, color="black", linestyle="--", linewidth=1.0)
        ax.set_xscale("log")
        ax.set_title(f"{kernel} | h={best_bw:.3g}{status_label}")
        ax.grid(True, alpha=0.25)

    for ax in axes[-1, :]:
        ax.set_xlabel("Bandwidth")
    for ax in axes[:, 0]:
        ax.set_ylabel("Score promedio")

    fig.suptitle("Seleccion de bandwidth por kernel", fontsize=13)
    fig.tight_layout()
    plt.show()


def plot_all_kernels(densities, bandwidths, title):
    color_map = get_color_map()
    fig, ax = plt.subplots(figsize=(10, 5))

    for kernel in get_kernels():
        x_grid, density = densities[kernel]
        ax.plot(
            x_grid,
            density,
            color=color_map[kernel],
            linewidth=1.8,
            label=f"{kernel} (h={bandwidths[kernel]:.3g})",
        )

    ax.set_xscale("log")
    ax.set_xlabel("Valor OTU positivo")
    ax.set_ylabel("Densidad condicional")
    ax.set_title(title)
    ax.grid(True, alpha=0.25)
    ax.legend(ncol=2, fontsize=9)
    fig.tight_layout()
    plt.show()


def plot_kernel_grid(densities, bandwidths, title):
    color_map = get_color_map()
    fig, axes = plt.subplots(3, 4, figsize=(16, 10), sharex=True)

    for ax, kernel in zip(axes.ravel(), get_kernels()):
        x_grid, density = densities[kernel]
        ax.plot(x_grid, density, color=color_map[kernel], linewidth=1.8)
        ax.set_xscale("log")
        ax.set_title(f"{kernel} | h={bandwidths[kernel]:.3g}")
        ax.grid(True, alpha=0.25)

    for ax in axes[-1, :]:
        ax.set_xlabel("Valor OTU positivo")
    for ax in axes[:, 0]:
        ax.set_ylabel("Densidad condicional")

    fig.suptitle(title, fontsize=13)
    fig.tight_layout()
    plt.show()

def kde_from_loaded(
    dfs,
    data_df_name="otu_data_converted",
    grid_size=1000,
    cv_subsample=1000,
    cv_folds=3,
    cv_bw_grid=8,
    min_bandwidth=1.0,
    cv_max_expansions=4,
    test_kernel_bandwidths=None,
    verbose=True
):
    values = get_otu_positive_values(dfs, data_df_name=data_df_name)

    start = time.perf_counter()
    bandwidth_summary, kernel_bandwidths, common_bandwidth, score_curves, bandwidth_status = estimate_bandwidths_by_kernel(
        values,
        cv_folds=cv_folds,
        n_subsample=cv_subsample,
        n_bw=cv_bw_grid,
        min_bandwidth=min_bandwidth,
        max_expansions=cv_max_expansions,
    )
    elapsed = time.perf_counter() - start

    x_grid, grid_summary = evaluate_grid(values, grid_size, common_bandwidth)

    if verbose:
        show_dataframe(grid_summary)
        show_dataframe(bandwidth_summary)
        print(f"DataFrame analizado: {data_df_name}")
        print(f"Grid usado: {grid_size}")
        print(f"Bandwidth minimo permitido: {min_bandwidth}")
        print(f"Tiempo de estimacion de bandwidths: {elapsed:.3f} s")
        print("Valores principales:")
        print(f"COMMON_BANDWIDTH = {common_bandwidth:.12g}")
        print("kernel_bandwidths = {")
        for kernel, bandwidth in kernel_bandwidths.items():
            print(f"    {kernel!r}: {bandwidth:.12g},")
        print("}")

    common_bandwidths = {kernel: common_bandwidth for kernel in get_kernels()}
    common_densities = evaluate_kde_set(values, grid_size, common_bandwidths)
    best_densities = evaluate_kde_set(values, grid_size, kernel_bandwidths)
    test_densities = None

    plot_grid_evaluation(values, x_grid)
    plot_cv_scores_by_kernel(score_curves, kernel_bandwidths, bandwidth_status)
    plot_all_kernels(common_densities, common_bandwidths, f"KDE de los 12 kernels (h comun={common_bandwidth:.3g})")
    plot_kernel_grid(common_densities, common_bandwidths, "KDE por kernel")
    plot_all_kernels(best_densities, kernel_bandwidths, "KDE de los 12 kernels con h particular")

    if test_kernel_bandwidths is not None:
        test_densities = evaluate_kde_set(values, grid_size, test_kernel_bandwidths)
        plot_kernel_grid(test_densities, test_kernel_bandwidths, "Pruebas particulares de bandwidth por kernel")

    result = {
        "values": values,
        "grid_summary": grid_summary,
        "bandwidth_summary": bandwidth_summary,
        "kernel_bandwidths": kernel_bandwidths,
        "common_bandwidth": common_bandwidth,
        "score_curves": score_curves,
        "bandwidth_status": bandwidth_status,
        "common_densities": common_densities,
        "best_densities": best_densities,
        "test_densities": test_densities,
    }

    return result
