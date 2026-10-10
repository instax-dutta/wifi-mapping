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

    def query(self, vec: np.ndarray) -> Tuple[np.ndarray, float]:
        """Return (xy_estimate, nearest_distance) for a query vector already in
        training bssid order."""
        v = np.asarray(vec, dtype=float).reshape(1, -1)
        if self.X.shape[0] == 0:
            return np.array([np.nan, np.nan]), float("nan")
        k = min(self.k, self.X.shape[0])
        if self._hnsw is not None:
            labels, dists = self._hnsw.knn_query(v, k=k)
            idxs = labels[0]
            d = np.sqrt(dists[0])
        else:
            dist = np.linalg.norm(self.X - v, axis=1)
            idxs = np.argsort(dist)[:k]
            d = dist[idxs]
        w = 1.0 / (d + 1e-6)
        xy = np.sum(w[:, None] * self.pos[idxs], axis=0) / np.sum(w)
        return xy, float(d[0])

    def query_aps(self, aps: Iterable) -> Tuple[np.ndarray, float]:
        return self.query(vectorize(aps, self.bssids))
