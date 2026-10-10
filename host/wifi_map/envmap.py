"""Environment change detection: is the fingerprint map still valid?

RuView's env_fingerprint notices moved furniture / new objects. With RSSI we
compare each AP's current median against a stored baseline; a large mean shift
means the radio environment changed and the map is stale.
"""

from __future__ import annotations

from typing import Any, Dict, List, Optional

import numpy as np


class EnvBaseline:
    def __init__(self, median: Optional[Dict[str, float]] = None):
        self.median: Dict[str, float] = dict(median or {})

    def build(self, stats: List[Dict[str, Any]]) -> "EnvBaseline":
        self.median = {s["bssid"]: float(s["median"]) for s in stats}
        return self

    def drift(self, stats: List[Dict[str, Any]], threshold: float = 6.0) -> Dict[str, Any]:
        per_ap: Dict[str, float] = {}
        for s in stats:
            b = s["bssid"]
            if b in self.median:
                per_ap[b] = abs(float(s["median"]) - self.median[b])
        if not per_ap:
            return {"score": 0.0, "changed": False, "per_ap": {}, "compared": 0}
        score = float(np.mean(list(per_ap.values())))
        return {"score": score, "changed": score >= threshold,
                "per_ap": per_ap, "compared": len(per_ap)}

    def to_dict(self) -> Dict[str, float]:
        return dict(self.median)

    @classmethod
    def from_dict(cls, d: Dict[str, float]) -> "EnvBaseline":
        return cls(d)
