"""Load a capture session and turn scans into numpy arrays."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

import numpy as np

from .records import ScanFrame, SniffFrame, parse_line

MISSING_RSSI = -100.0


def _jsonl_files(p: Path) -> List[Path]:
    """A session is a .jsonl file, or a dir of .jsonl files (merged in name order)."""
    if p.is_dir():
        files = sorted(p.glob("*.jsonl"))
        if files:
            return files
        single = p / "scans.jsonl"
        return [single] if single.exists() else []
    return [p]


def load_session(path: str | Path) -> Dict[str, Any]:
    """Read one session file, or every .jsonl in a session directory."""
    p = Path(path)
    files = _jsonl_files(p)
    scans: List[ScanFrame] = []
    sniff: List[SniffFrame] = []
    events: List[Dict[str, Any]] = []
    boot: Optional[Dict[str, Any]] = None
    skipped = 0

    for f in files:
        for line in f.read_text(errors="replace").splitlines():
            try:
                fr = parse_line(line)
            except Exception:
                skipped += 1
                continue
            if fr is None:
                continue
            if isinstance(fr, ScanFrame):
                scans.append(fr)
            elif isinstance(fr, SniffFrame):
                sniff.append(fr)
            else:
                events.append(fr)
                if isinstance(fr, dict) and fr.get("t") == "boot":
                    boot = fr

    meta = {}
    meta_path = (p / "meta.json") if p.is_dir() else p.parent / "meta.json"
    if meta_path.exists():
        meta = json.loads(meta_path.read_text())

    return {"scans": scans, "sniff": sniff, "events": events,
            "boot": boot, "meta": meta, "skipped": skipped,
            "path": str(p), "files": [str(f) for f in files]}



def ap_table(scans: List[ScanFrame]) -> Tuple[List[str], np.ndarray, np.ndarray]:
    """Return (bssids, RSSI matrix [n_samples x n_aps], observed mask)."""
    bssids = sorted({ap.bssid for s in scans for ap in s.aps})
    idx = {b: i for i, b in enumerate(bssids)}
    X = np.full((len(scans), len(bssids)), MISSING_RSSI, dtype=float)
    M = np.zeros((len(scans), len(bssids)), dtype=bool)
    for i, s in enumerate(scans):
        for ap in s.aps:
            X[i, idx[ap.bssid]] = ap.rssi
            M[i, idx[ap.bssid]] = True
    return bssids, X, M


def labels(scans: List[ScanFrame]) -> Tuple[np.ndarray, np.ndarray, bool]:
    xs = np.array([s.x if s.x is not None else np.nan for s in scans], dtype=float)
    ys = np.array([s.y if s.y is not None else np.nan for s in scans], dtype=float)
    labeled = bool(np.isfinite(xs).any() and np.isfinite(ys).any())
    return xs, ys, labeled


def ap_stats(scans: List[ScanFrame]) -> List[Dict[str, Any]]:
    """Per-BSSID summary: how often seen, median/min/max RSSI, channel, ssid."""
    agg: Dict[str, Dict[str, Any]] = {}
    for s in scans:
        for ap in s.aps:
            a = agg.setdefault(ap.bssid, {"bssid": ap.bssid, "ssid": ap.ssid,
                                          "channel": ap.channel, "rs": []})
            a["rs"].append(ap.rssi)
            if ap.ssid:
                a["ssid"] = ap.ssid
            a["channel"] = ap.channel
    out = []
    for a in agg.values():
        r = np.array(a["rs"])
        out.append({"bssid": a["bssid"], "ssid": a["ssid"], "channel": a["channel"],
                    "n": int(r.size), "median": float(np.median(r)),
                    "min": int(r.min()), "max": int(r.max()),
                    "jitter": float(r.max() - r.min())})
    out.sort(key=lambda d: -d["n"])
    return out
