"""Coarse occupancy grid from sparse inverse k-visibility (Structure from WiFi).

Turns per-point wall counts (k) into a free-space / occupancy grid plus a
per-cell wall probability map.

Usage (from host/):
    python -m wifi_map.occupancy --session data/sessions/room1 --ref BSSID,X,Y --out data/derived/room1/occupancy
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Optional, Tuple

import numpy as np

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402

from .geometry import (  # noqa: E402
    assign_k,
    grid_to_world,
    k_thresholds,
    sparse_inverse_k_visibility,
    world_to_grid,
)
from .sessions import ap_table, labels, load_session  # noqa: E402


def compute_k_values(
    scans, bssids: list, X: np.ndarray, M: np.ndarray, ref_bssid: str,
    k_max: int = 3,
) -> Tuple[Optional[np.ndarray], Optional[list]]:
    """Wall count k per scan for the reference BSSID.

    Returns (k_values, thresholds) where k_values[i] is -1 when the reference
    BSSID was not observed at scan i (unknown).
    """
    if ref_bssid not in bssids:
        return None, None
    col = bssids.index(ref_bssid)
    rssis = X[:, col].astype(float)
    observed = M[:, col]
    thr = k_thresholds(rssis[observed].tolist(), k_max=k_max) if observed.any() else []
    k = np.full(rssis.shape, -1, dtype=int)
    for i in range(rssis.shape[0]):
        if observed[i]:
            k[i] = assign_k(float(rssis[i]), thr)
    return k, thr


def _default_bounds(points: np.ndarray, router_pos: np.ndarray,
                    margin: float = 1.0) -> Tuple[float, float, float, float]:
    pts = np.vstack([points, router_pos.reshape(1, 2)])
    xmin = float(pts[:, 0].min()) - margin
    xmax = float(pts[:, 0].max()) + margin
    ymin = float(pts[:, 1].min()) - margin
    ymax = float(pts[:, 1].max()) + margin
    return xmin, xmax, ymin, ymax


def _render_occupancy(occupancy: np.ndarray, path: Path) -> None:
    fig, ax = plt.subplots(figsize=(5, 4), dpi=120)
    rgb = np.full((occupancy.shape[0], occupancy.shape[1], 3), 0.5, dtype=float)  # unknown = gray
    rgb[occupancy == 1] = [0.2, 0.7, 0.2]  # free = green
    rgb[occupancy == 0] = [0.1, 0.1, 0.1]  # occupied = near-black
    ax.imshow(rgb, origin="lower", interpolation="nearest")
    ax.set_title("occupancy grid (green=free, black=occupied, gray=unknown)", fontsize=8)
    ax.set_xlabel("grid x")
    ax.set_ylabel("grid y")
    fig.tight_layout()
    fig.savefig(path)
    plt.close(fig)


def _render_wall_prob(wall_prob: np.ndarray, path: Path) -> None:
    fig, ax = plt.subplots(figsize=(5, 4), dpi=120)
    im = ax.imshow(wall_prob, origin="lower", interpolation="nearest",
                   cmap="magma", vmin=0.0, vmax=1.0)
    fig.colorbar(im, ax=ax, fraction=0.046, pad=0.04, label="wall probability")
    ax.set_title("wall probability map", fontsize=8)
    ax.set_xlabel("grid x")
    ax.set_ylabel("grid y")
    fig.tight_layout()
    fig.savefig(path)
    plt.close(fig)


def build_occupancy(points: np.ndarray, k_values: np.ndarray, router_pos,
                    bounds, resolution: float, out_dir: Path,
                    gaussian_sigma_m: float | None = None,
                    occupied_threshold: float = 0.5) -> dict:
    """Run sparse inverse k-visibility and save grid artefacts.

    Writes occupancy_grid.npy, wall_probability.npy, metadata.json,
    occupancy_grid.png and wall_probability.png into out_dir.
    """
    out_dir = Path(out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)

    points = np.asarray(points, dtype=float).reshape(-1, 2)
    k_values = np.asarray(k_values, dtype=int).ravel()
    router_pos = np.asarray(router_pos, dtype=float).ravel()

    occupancy, wall_prob, metadata = sparse_inverse_k_visibility(
        points, k_values, router_pos, bounds, resolution,
        gaussian_sigma_m=gaussian_sigma_m,
        occupied_threshold=occupied_threshold,
    )

    np.save(out_dir / "occupancy_grid.npy", occupancy)
    np.save(out_dir / "wall_probability.npy", wall_prob)
    (out_dir / "metadata.json").write_text(json.dumps(metadata, indent=2))
    _render_occupancy(occupancy, out_dir / "occupancy_grid.png")
    _render_wall_prob(wall_prob, out_dir / "wall_probability.png")
    return metadata


def run_occupancy(session: str, ref: Optional[Tuple[str, float, float]],
                  out_dir: Path, resolution: float = 0.5,
                  k_max: int = 3,
                  gaussian_sigma_m: float | None = None,
                  occupied_threshold: float = 0.5) -> dict:
    """Load a session and build its occupancy grid.

    ``ref`` is ``(bssid, rx, ry)``. Falls back to ``ap_positions`` in session
    meta when only a BSSID is needed, but a router position is required.
    """
    data = load_session(session)
    scans = data["scans"]
    meta = data.get("meta", {})
    bssids, X, M = ap_table(scans)
    xs, ys, labeled = labels(scans)
    if not labeled:
        raise ValueError("session has no labeled (x, y) scans; cannot build occupancy grid")

    if ref is None:
        ap_pos = meta.get("ap_positions") or {}
        if not ap_pos:
            raise ValueError("--ref BSSID,X,Y is required (or ap_positions in session meta)")
        bssid = next(iter(ap_pos))
        rx, ry = ap_pos[bssid]
        ref = (bssid, float(rx), float(ry))

    bssid, rx, ry = ref
    if bssid not in bssids:
        raise ValueError(f"reference BSSID {bssid} not observed in session")
    router_pos = np.array([rx, ry], dtype=float)

    k, _thr = compute_k_values(scans, bssids, X, M, bssid, k_max=k_max)
    if k is None:
        raise ValueError(f"reference BSSID {bssid} not observed in session")

    points = np.stack([xs, ys], axis=1)
    good = np.isfinite(points).all(axis=1) & (k >= 0)
    pts = points[good]
    kvals = k[good]
    if pts.shape[0] == 0:
        raise ValueError("no labeled scans with a valid k-value; cannot build occupancy grid")

    bounds = meta.get("bounds")
    if bounds is None:
        bounds = _default_bounds(pts, router_pos)
    else:
        bounds = tuple(float(v) for v in bounds)

    metadata = build_occupancy(
        pts, kvals, router_pos, bounds, resolution, out_dir,
        gaussian_sigma_m=gaussian_sigma_m,
        occupied_threshold=occupied_threshold,
    )
    metadata["session"] = str(data["path"])
    metadata["ref_bssid"] = bssid
    metadata["router_pos"] = [float(rx), float(ry)]
    metadata["bounds"] = [float(bounds[0]), float(bounds[1]), float(bounds[2]), float(bounds[3])]
    (out_dir / "metadata.json").write_text(json.dumps(metadata, indent=2))
    return metadata


def main(argv=None) -> int:
    p = argparse.ArgumentParser(
        description="Build a coarse occupancy grid from a session via sparse inverse k-visibility.")
    p.add_argument("--session", required=True, help="session .jsonl or session directory")
    p.add_argument("--ref", default=None,
                   help="reference transmitter: BSSID,X,Y (room metres)")
    p.add_argument("--out", required=True, help="output directory for grid artefacts")
    p.add_argument("--resolution", type=float, default=0.5,
                   help="grid resolution in metres per cell (default: 0.5)")
    p.add_argument("--k-max", type=int, default=3,
                   help="max wall count for k-threshold estimation (default: 3)")
    args = p.parse_args(argv)

    ref = None
    if args.ref:
        parts = args.ref.split(",")
        if len(parts) != 3:
            p.error("--ref must be BSSID,X,Y")
        ref = (parts[0].strip(), float(parts[1]), float(parts[2]))

    metadata = run_occupancy(args.session, ref, Path(args.out),
                             resolution=args.resolution, k_max=args.k_max)
    print(f"OCCUPANCY OK session={metadata['session']} ref={metadata['ref_bssid']} "
          f"router={metadata['router_pos']} "
          f"free={metadata['n_free']} occupied={metadata['n_occupied']} "
          f"unknown={metadata['n_unknown']} out={args.out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
