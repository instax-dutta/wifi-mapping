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
