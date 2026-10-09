"""Analyze a wifi-mapper session: heatmaps, localization error, path-loss, k-walls.

Usage (from host/):
    python -m wifi_map.analyze --session ../data/sessions/walk1
    python -m wifi_map.analyze --session ../data/derived/sim --out ../data/derived/sim_report
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Dict, List, Optional, Tuple

import numpy as np

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402

from .geometry import assign_k, fit_path_loss, k_thresholds  # noqa: E402
from .sessions import MISSING_RSSI, ap_stats, ap_table, labels, load_session  # noqa: E402


def knn_loo(X: np.ndarray, pos: np.ndarray, k: int = 3) -> np.ndarray:
    """Leave-one-out kNN prediction. X: [n x features], pos: [n x 2]."""
    n = X.shape[0]
    pred = np.full_like(pos, np.nan, dtype=float)
    for i in range(n):
        d = np.linalg.norm(X - X[i], axis=1)
        d[i] = np.inf
        kk = min(k, n - 1)
        if kk < 1:
            continue
        idx = np.argsort(d)[:kk]
        w = 1.0 / (d[idx] + 1e-6)
        pred[i] = np.sum(w[:, None] * pos[idx], axis=0) / np.sum(w)
    return pred


def error_stats(pred: np.ndarray, true: np.ndarray) -> Dict[str, float]:
    err = np.linalg.norm(pred - true, axis=1)
    err = err[np.isfinite(err)]
    if err.size == 0:
        return {}
    return {"median_m": float(np.median(err)), "mean_m": float(np.mean(err)),
            "p90_m": float(np.percentile(err, 90)), "max_m": float(err.max()),
            "n": int(err.size)}


def render_heatmaps(xs, ys, X, bssids, M, out_dir: Path, top: int = 6) -> List[str]:
    out_dir.mkdir(parents=True, exist_ok=True)
    order = np.argsort(-M.sum(axis=0))[:top]
    written = []
    for j in order:
        obs = M[:, j]
        if obs.sum() < 3:
            continue
        px, py, pr = xs[obs], ys[obs], X[obs, j]
        fig, ax = plt.subplots(figsize=(4.2, 3.4), dpi=120)
        if len({(round(a, 3), round(b, 3)) for a, b in zip(px, py)}) >= 3:
            try:
                tcf = ax.tricontourf(px, py, pr, levels=12, cmap="viridis")
                fig.colorbar(tcf, ax=ax, label="RSSI (dBm)")
            except Exception:
                pass
        sc = ax.scatter(px, py, c=pr, cmap="viridis", s=22, edgecolors="k", linewidths=0.3)
        ax.set_title(bssids[j], fontsize=9)
        ax.set_xlabel("x (m)")
        ax.set_ylabel("y (m)")
        ax.set_aspect("equal", adjustable="datalim")
        name = bssids[j].replace(":", "") + ".png"
        fig.tight_layout()
        fig.savefig(out_dir / name)
        plt.close(fig)
        written.append(name)
    return written


def analyze(session: str, out_dir: Optional[Path] = None, k: int = 3,
            ref: Optional[Tuple[str, float, float]] = None) -> Dict:
    data = load_session(session)
    scans = data["scans"]
    meta = data.get("meta", {})
    if ref:
        ap_pos = dict(meta.get("ap_positions") or {})
        ap_pos[ref[0]] = [ref[1], ref[2]]
        meta = {**meta, "ap_positions": ap_pos}
    if out_dir is None:
        base = Path(data["path"])
        name = base.name if base.is_dir() else base.stem
        out_dir = Path("data/derived") / name
    out_dir = Path(out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)

    bssids, X, M = ap_table(scans)
    xs, ys, labeled = labels(scans)
    stats = ap_stats(scans)

    result: Dict = {
        "session": str(data["path"]),
        "samples": len(scans),
        "unique_aps": len(bssids),
        "sniff_frames": len(data["sniff"]),
        "boot": data.get("boot"),
        "ap_stats": stats[:20],
        "ap_count": len(stats),
    }

    # strongest AP by presence -> k-wall thresholds
    if stats:
        strongest = stats[0]["bssid"]
        col = bssids.index(strongest) if strongest in bssids else None
        if col is not None:
            rssis = X[M[:, col], col]
            thr = k_thresholds(rssis, k_max=3)
            result["k_walls"] = {"bssid": strongest, "thresholds": thr,
                                 "k_histogram": np.bincount(
                                     [assign_k(float(r), thr) for r in rssis],
                                     minlength=len(thr) + 1).tolist()}

    # path-loss fit if we know AP positions
    ap_pos = meta.get("ap_positions")
    if labeled and ap_pos:
        fits = {}
        for b, (ax, ay) in ap_pos.items():
            if b not in bssids:
                continue
            j = bssids.index(b)
            obs = M[:, j]
            d = np.linalg.norm(np.stack([xs[obs], ys[obs]], axis=1) - np.array([ax, ay]), axis=1)
            p0, n = fit_path_loss(d, X[obs, j])
            if np.isfinite(n):
                fits[b] = {"p0": p0, "n": n, "n_samples": int(obs.sum())}
        if fits:
            result["path_loss_fits"] = fits
            result["path_loss_n_mean"] = float(np.mean([v["n"] for v in fits.values()]))

    if labeled:
        pos = np.stack([xs, ys], axis=1)
        good = np.isfinite(pos).all(axis=1)
        Xg, posg = X[good], pos[good]
        pred = knn_loo(Xg, posg, k=k)
        result["localization"] = {"k": k, **error_stats(pred, posg)}
        result["figures"] = render_heatmaps(xs, ys, X, bssids, M, out_dir / "heatmaps")
        # predicted vs true overview
        fig, ax = plt.subplots(figsize=(4.6, 3.8), dpi=120)
        ax.scatter(posg[:, 0], posg[:, 1], c="k", s=14, label="true")
        m = np.isfinite(pred).all(axis=1)
        ax.scatter(pred[m, 0], pred[m, 1], c="crimson", s=18, marker="x", label="kNN pred")
        for a, b2 in zip(posg[m], pred[m]):
            ax.plot([a[0], b2[0]], [a[1], b2[1]], "-", color="gray", lw=0.5, alpha=0.6)
        ax.set_aspect("equal", adjustable="datalim")
        ax.legend(fontsize=8)
        ax.set_title(f"localization LOO (k={k}) median {result['localization']['median_m']:.2f} m", fontsize=9)
        fig.tight_layout()
        fig.savefig(out_dir / "localization_loo.png")
        plt.close(fig)
    else:
        # unlabeled (real static) capture: RSSI distribution figure
        fig, ax = plt.subplots(figsize=(5.0, 3.4), dpi=120)
        top = stats[:15]
        names = [(s["ssid"] or s["bssid"][-5:])[:12] for s in top]
        ax.barh([str(n) for n in names][::-1],
                [s["median"] for s in top][::-1], color="#3b6ea5")
        ax.set_xlabel("median RSSI (dBm)")
        ax.set_title("median RSSI per AP (static capture)", fontsize=9)
        fig.tight_layout()
        fig.savefig(out_dir / "rssi_by_ap.png")
        plt.close(fig)
        result["figures"] = ["rssi_by_ap.png"]

    (out_dir / "metrics.json").write_text(json.dumps(result, indent=2, default=float))

    if "localization" in result:
        loc = result["localization"]
        print(f"ANALYSIS OK samples={result['samples']} aps={result['unique_aps']} "
              f"median_error_m={loc['median_m']:.3f} p90_m={loc['p90_m']:.3f} "
              f"out={out_dir}")
    else:
        print(f"ANALYSIS OK unlabeled=1 samples={result['samples']} "
              f"aps={result['unique_aps']} out={out_dir}")
    return result


def main(argv=None) -> int:
    p = argparse.ArgumentParser(description="Analyze a wifi-mapper session.")
    p.add_argument("--session", required=True)
    p.add_argument("--out", default=None)
    p.add_argument("--k", type=int, default=3, help="kNN neighbours for LOO")
    p.add_argument("--ref", default=None,
                   help="known reference transmitter position: BSSID,X,Y (room metres)")
    args = p.parse_args(argv)
    ref = None
    if args.ref:
        b, xs, ys = args.ref.split(",")
        ref = (b.strip(), float(xs), float(ys))
    analyze(args.session, Path(args.out) if args.out else None, k=args.k, ref=ref)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
