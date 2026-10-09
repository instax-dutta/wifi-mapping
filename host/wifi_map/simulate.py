"""Generate a synthetic labelled fingerprint session for pipeline testing.

Produces the same JSONL wire format the real board emits, so analyze.py can be
exercised end to end without moving the board. The model is a log-distance path
loss plus log-normal shadowing and a single attenuating wall, so geometry.py
has something real to find.
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import List, Tuple

import numpy as np

from .records import Ap, ScanFrame, to_wire

DEFAULT_SEED = 7


def _seg_crosses_wall(p: np.ndarray, q: np.ndarray, wall_x: float,
                      y0: float, y1: float) -> bool:
    if (p[0] - wall_x) * (q[0] - wall_x) > 0:
        return False
    if p[0] == q[0]:
        return False
    t = (wall_x - p[0]) / (q[0] - p[0])
    y = p[1] + t * (q[1] - p[1])
    return y0 <= y <= y1


def generate(out_dir: Path, points: int = 6, n_aps: int = 4, seed: int = DEFAULT_SEED,
             room: Tuple[float, float] = (8.0, 6.0), p0: float = -30.0,
             n_exp: float = 2.6, sigma: float = 3.5, wall_db: float = 9.0) -> dict:
    rng = np.random.default_rng(seed)
    w, h = room
    wall_x, wall_y0, wall_y1 = w / 2.0, 0.0, h * 0.6

    aps: List[np.ndarray] = []
    corners = [(0.5, 0.5), (w - 0.5, 0.5), (0.5, h - 0.5), (w - 0.5, h - 0.5)]
    for i in range(n_aps):
        if i < len(corners):
            aps.append(np.array(corners[i], dtype=float))
        else:
            aps.append(np.array([rng.uniform(1, w - 1), rng.uniform(1, h - 1)]))

    xs = np.linspace(0.5, w - 0.5, points)
    ys = np.linspace(0.5, h - 0.5, points)

    out_dir.mkdir(parents=True, exist_ok=True)
    seq = 0
    with (out_dir / "scans.jsonl").open("w") as fh:
        for gy in ys:
            for gx in xs:
                pos = np.array([gx, gy])
                frames_aps = []
                for j, a in enumerate(aps):
                    d = float(np.linalg.norm(pos - a))
                    rssi = p0 - 10.0 * n_exp * np.log10(max(d, 0.5))
                    if _seg_crosses_wall(pos, a, wall_x, wall_y0, wall_y1):
                        rssi -= wall_db
                    rssi += float(rng.normal(0, sigma))
                    rssi = int(np.clip(round(rssi), -97, -20))
                    bssid = "aa:bb:cc:00:00:%02x" % j
                    frames_aps.append(Ap(bssid=bssid, ssid=f"AP{j}", rssi=rssi,
                                         channel=6 if j % 2 == 0 else 11, enc=3))
                frame = ScanFrame(seq=seq, ms=seq * 1500, aps=frames_aps,
                                  x=float(gx), y=float(gy), label="grid")
                fh.write(json.dumps(to_wire(frame), separators=(",", ":")) + "\n")
                seq += 1

    meta = {
        "synthetic": True, "seed": seed, "room": list(room), "points": points,
        "ap_positions": {f"aa:bb:cc:00:00:{j:02x}": [float(a[0]), float(a[1])]
                         for j, a in enumerate(aps)},
        "wall": {"x": wall_x, "y0": wall_y0, "y1": wall_y1, "attenuation_db": wall_db},
        "path_loss": {"p0": p0, "n": n_exp, "sigma": sigma},
    }
    (out_dir / "meta.json").write_text(json.dumps(meta, indent=2))
    (out_dir / "ground_truth.json").write_text(json.dumps(meta, indent=2))
    return meta


def main(argv=None) -> int:
    p = argparse.ArgumentParser(description="Generate a synthetic fingerprint session.")
    p.add_argument("--out", required=True)
    p.add_argument("--points", type=int, default=6, help="grid points per side")
    p.add_argument("--aps", dest="n_aps", type=int, default=4)
    p.add_argument("--seed", type=int, default=DEFAULT_SEED)
    args = p.parse_args(argv)
    out = Path(args.out).expanduser()
    meta = generate(out, points=args.points, n_aps=args.n_aps, seed=args.seed)
    print(f"SIMULATE OK samples={meta['points'] ** 2} aps={len(meta['ap_positions'])} out={out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
