"""Fingerprint index for fast nearest-neighbour localization.

numpy kNN by default; uses hnswlib when available (RuView-style on-device /
vector-index idea), falling back silently if the library is absent.
"""

from __future__ import annotations

from typing import Iterable, List, Sequence, Tuple

import numpy as np

from .sessions import MISSING_RSSI


def vectorize(aps: Iterable, bssids: Sequence[str]) -> np.ndarray:
    """Map a live set of APs (objects with .bssid/.rssi or (bssid,rssi)) onto the
    training bssid order, filling missing APs with MISSING_RSSI."""
    idx = {b: i for i, b in enumerate(bssids)}
    v = np.full(len(bssids), MISSING_RSSI, dtype=float)
    for a in aps:
        b = getattr(a, "bssid", None) or a[0]
        r = getattr(a, "rssi", None)
        if r is None:
            r = a[1]
        if b in idx:
            v[idx[b]] = float(r)
    return v


def _rankdata(x: np.ndarray) -> np.ndarray:
    """Average-ties rank of a 1-D array (1-based)."""
    x = np.asarray(x, dtype=float)
    order = np.argsort(x, kind="mergesort")
    sorted_x = x[order]
    ranks_sorted = np.empty(x.size, dtype=float)
    i = 0
    n = x.size
    while i < n:
        j = i
        while j + 1 < n and sorted_x[j + 1] == sorted_x[i]:
            j += 1
        ranks_sorted[i:j + 1] = 0.5 * (i + j) + 1.0
        i = j + 1
    ranks = np.empty(x.size, dtype=float)
    ranks[order] = ranks_sorted
    return ranks


def exponential_transform(v, alpha=0.1):
    """exp(alpha * v): compresses strong-signal differences (UJI 2023).

    Applied to RSSI vectors before distance computation so differences among
    strong signals are penalized less than among weak ones."""
    return np.exp(alpha * np.asarray(v, dtype=float))


def power_transform(v, gamma=0.5):
    """Sign-preserving power law |v|^gamma (UJI 2023)."""
    v = np.asarray(v, dtype=float)
    return np.sign(v) * np.abs(v) ** gamma


def spearman_distance(a, b):
    """1 - Spearman rank correlation between two RSSI vectors.

    Positions where either value is MISSING_RSSI are excluded from ranking, so
    non-detected APs do not distort the correlation (IEEE LSP 2016)."""
    a = np.asarray(a, dtype=float)
    b = np.asarray(b, dtype=float)
    mask = (a != MISSING_RSSI) & (b != MISSING_RSSI)
    if int(mask.sum()) < 2:
        return 1.0
    ra = _rankdata(a[mask])
    rb = _rankdata(b[mask])
    ra_c = ra - ra.mean()
    rb_c = rb - rb.mean()
    denom = np.sqrt(np.dot(ra_c, ra_c) * np.dot(rb_c, rb_c))
    if denom == 0.0:
        return 1.0
    rho = float(np.dot(ra_c, rb_c) / denom)
    return 1.0 - rho


class FingerprintIndex:
    def __init__(self, k: int = 3, backend: str = "numpy"):
        self.k = k
        self.backend = backend
        self.bssids: List[str] = []
        self.X: np.ndarray = np.zeros((0, 0))
        self.pos: np.ndarray = np.zeros((0, 2))
        self._hnsw = None

    def fit(self, bssids: Sequence[str], X: np.ndarray, pos: np.ndarray) -> "FingerprintIndex":
        self.bssids = list(bssids)
        self.X = np.asarray(X, dtype=float)
        self.pos = np.asarray(pos, dtype=float)
        if self.backend == "hnsw" and self.X.shape[0]:
            try:
                import hnswlib  # type: ignore
                dim = self.X.shape[1]
                idx = hnswlib.Index(space="l2", dim=dim)
                idx.init_index(max_elements=self.X.shape[0], ef_construction=200, M=16)
                idx.add_items(self.X, np.arange(self.X.shape[0]))
                idx.set_ef(max(50, self.k * 10))
                self._hnsw = idx
            except Exception:
                self._hnsw = None
        return self

    def query(self, vec: np.ndarray, distance: str = "euclidean") -> Tuple[np.ndarray, float]:
        """Return (xy_estimate, nearest_distance) for a query vector already in
        training bssid order.

        distance: "euclidean" (default, L2 norm) or "spearman". With
        "spearman" the exponential transform is applied before computing
        distances and the hnsw backend is ignored."""
        v = np.asarray(vec, dtype=float).reshape(1, -1)
        if self.X.shape[0] == 0:
            return np.array([np.nan, np.nan]), float("nan")
        k = min(self.k, self.X.shape[0])
        if distance == "spearman":
            vt = exponential_transform(v)
            Xt = exponential_transform(self.X)
            dist = np.array([spearman_distance(vt[0], x) for x in Xt])
        else:
            dist = np.linalg.norm(self.X - v, axis=1)
        idxs = np.argsort(dist)[:k]
        d = dist[idxs]
        w = 1.0 / (d + 1e-6)
        xy = np.sum(w[:, None] * self.pos[idxs], axis=0) / np.sum(w)
        return xy, float(d[0])

    def query_aps(self, aps: Iterable) -> Tuple[np.ndarray, float]:
        return self.query(vectorize(aps, self.bssids))
