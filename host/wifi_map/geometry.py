"""SfW-lite geometry: turn RSSI into wall counts (k) via unsupervised thresholds.

Follows Fafoutis et al. (WF-IoT 2015) and the SfW paper (arXiv 2403.02235):
k-means over RSSI yields K+1 centroids; midpoints between consecutive centroids
are the thresholds that map a measurement to a wall count k.
"""

from __future__ import annotations

from typing import List, Sequence, Tuple

import numpy as np


def kmeans_1d(values: np.ndarray, k: int, iters: int = 100, seed: int = 0) -> np.ndarray:
    """Return k ascending 1D k-means centroids."""
    v = np.asarray(values, dtype=float).ravel()
    if v.size == 0:
        return np.array([], dtype=float)
    k = max(1, min(k, v.size))
    rng = np.random.default_rng(seed)
    centroids = np.sort(rng.choice(v, size=k, replace=False))
    for _ in range(iters):
        assign = np.argmin(np.abs(v[:, None] - centroids[None, :]), axis=1)
        new = centroids.copy()
        for i in range(k):
            members = v[assign == i]
            if members.size:
                new[i] = members.mean()
        if np.allclose(new, centroids):
            break
        centroids = new
    return np.sort(centroids)


def k_thresholds(rssis: Sequence[float], k_max: int = 3, seed: int = 0) -> List[float]:
    """Thresholds separating k=0..k_max. Descending RSSI means fewer walls."""
    v = np.asarray(rssis, dtype=float).ravel()
    if v.size < k_max + 1:
        return []
    centroids = kmeans_1d(v, k_max + 1, seed=seed)   # ascending
    desc = centroids[::-1]                            # strongest -> weakest
    return [float((desc[i] + desc[i + 1]) / 2.0) for i in range(len(desc) - 1)]


def assign_k(rssi: float, thresholds: Sequence[float]) -> int:
    """Number of walls crossed for a measurement, given descending thresholds."""
    k = 0
    for t in thresholds:
        if rssi <= t:
            k += 1
    return k


def fit_path_loss(distances: Sequence[float], rssis: Sequence[float]) -> Tuple[float, float]:
    """Fit rssi = P0 - 10 n log10(d). Returns (P0, n)."""
    d = np.asarray(distances, dtype=float).ravel()
    r = np.asarray(rssis, dtype=float).ravel()
    mask = np.isfinite(d) & np.isfinite(r) & (d > 0)
    d, r = d[mask], r[mask]
    if d.size < 2:
        return float("nan"), float("nan")
    slope, intercept = np.polyfit(np.log10(d), r, 1)
    return float(intercept), float(-slope / 10.0)
