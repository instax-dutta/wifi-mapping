"""RSSI-derived motion and presence features.

RuView gets motion from CSI variance; with RSSI we use the temporal variance of
each AP's signal over a short window - people/objects moving in the path perturb
it measurably. Score is in dB^2.
"""

from __future__ import annotations

from typing import Sequence

import numpy as np


def motion_score(history: Sequence[Sequence[float]], min_samples: int = 6) -> float:
    """Mean per-AP RSSI variance over the window. history is [t x aps]."""
    X = np.asarray(history, dtype=float)
    if X.ndim != 2 or X.shape[0] < min_samples:
        return 0.0
    var = np.nanvar(X, axis=0)
    if not np.isfinite(var).any():
        return 0.0
    return float(np.nanmean(var))


def presence(history: Sequence[Sequence[float]], threshold: float = 2.0,
             min_samples: int = 6) -> bool:
    """True when the signal is disturbed enough to suggest someone is present."""
    return motion_score(history, min_samples) >= threshold


def motion_level(score: float) -> str:
    if score >= 8.0:
        return "high"
    if score >= 2.0:
        return "medium"
    return "low"


def sliding_median_filter(history, window=11):
    """Apply a sliding median filter per-AP across the time window.

    history is [t x aps]. For each time step, each AP's output is the median of
    that AP's RSSI over [t-half, t+half]; edges use the available samples.
    Suppresses impulse outliers. Returns a filtered [t x aps] array."""
    X = np.asarray(history, dtype=float)
    if X.ndim != 2 or X.shape[0] == 0:
        return X
    t = X.shape[0]
    half = max(1, int(window)) // 2
    out = np.empty_like(X)
    for i in range(t):
        lo = max(0, i - half)
        hi = min(t, i + half + 1)
        out[i] = np.median(X[lo:hi], axis=0)
    return out


def mad_filter(history, threshold=3.0):
    """Median absolute deviation outlier rejection.

    Per AP, points farther than threshold * MAD from the AP median are
    replaced with that AP's median. Returns cleaned [t x aps] array."""
    X = np.asarray(history, dtype=float)
    if X.ndim != 2:
        return X
    med = np.median(X, axis=0)
    mad = np.median(np.abs(X - med), axis=0)
    mad = np.where(mad == 0.0, 1.0, mad)
    z = np.abs(X - med) / mad
    out = X.copy()
    out[z > threshold] = np.broadcast_to(med, X.shape)[z > threshold]
    return out


def ema_smooth(prev, curr, alpha):
    """Exponential moving average: smooth = alpha * curr + (1 - alpha) * prev.

    prev/curr may be a dict with "x"/"y" or an array-like of length 2.
    Returns {"x": float, "y": float}; if prev is None returns curr as a dict."""
    def _xy(p):
        if p is None:
            return None
        if isinstance(p, dict):
            return np.array([float(p["x"]), float(p["y"])], dtype=float)
        return np.asarray(p, dtype=float).reshape(-1)[:2]
    a = _xy(prev)
    b = _xy(curr)
    if a is None:
        return {"x": float(b[0]), "y": float(b[1])}
    out = alpha * b + (1.0 - alpha) * a
    return {"x": float(out[0]), "y": float(out[1])}


def median_filter_2d(points, window=5):
    """Median filter over a sequence of 2D points.

    points: iterable of (x, y) pairs or dicts with "x"/"y". window: number of
    points in the sliding window (edges use the available samples).
    Returns a list of {"x", "y"} filtered points, same length as input."""
    def _xy(p):
        if isinstance(p, dict):
            return np.array([float(p["x"]), float(p["y"])], dtype=float)
        return np.asarray(p, dtype=float).reshape(-1)[:2]
    pts = np.asarray([_xy(p) for p in points], dtype=float)
    if pts.ndim != 2 or pts.shape[0] == 0:
        return [{"x": float(p[0]), "y": float(p[1])} for p in pts]
    t = pts.shape[0]
    half = max(1, int(window)) // 2
    out = []
    for i in range(t):
        lo = max(0, i - half)
        hi = min(t, i + half + 1)
        m = np.median(pts[lo:hi], axis=0)
        out.append({"x": float(m[0]), "y": float(m[1])})
    return out
