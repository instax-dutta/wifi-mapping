"""Capture one survey point and print an immediate summary.

Usage (from the repo root):
    PYTHONPATH=host .venv/bin/python -m wifi_map.point 1 0

Writes data/sessions/<session>/p_<x>_<y>.jsonl and prints the APs heard there,
so you can see the reference beacon's RSSI before moving on.
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

from .capture import main as capture_main
from .sessions import ap_stats, load_session


def main(argv=None) -> int:
    p = argparse.ArgumentParser(description="Capture + summarize one survey point.")
    p.add_argument("x", type=float)
    p.add_argument("y", type=float)
    p.add_argument("--session", default="data/sessions/room1")
    p.add_argument("--port", default="/dev/cu.usbserial-0001")
    p.add_argument("--duration", type=float, default=10.0)
    p.add_argument("--period", type=int, default=800)
    p.add_argument("--ref-ssid", default="mq-ref")
    args = p.parse_args(argv)

    out = Path(args.session) / f"p_{args.x:g}_{args.y:g}.jsonl"
    rc = capture_main(["--port", args.port, "--out", str(out),
                       "--duration", str(args.duration), "--period", str(args.period),
                       "--x", str(args.x), "--y", str(args.y)])
    if rc != 0:
        print(f"POINT ({args.x:g},{args.y:g}) FAILED - no data", file=sys.stderr)
        return rc

    data = load_session(out)
    stats = ap_stats(data["scans"])
    ref = [s for s in stats if s["ssid"] == args.ref_ssid]
    print(f"POINT ({args.x:g},{args.y:g}) scans={len(data['scans'])} aps={len(stats)}")
    for s in stats[:8]:
        name = (s["ssid"] or s["bssid"][-5:])[:16]
        print(f"   {name:16s} ch{s['channel']:<2} n={s['n']:<3} median={s['median']:.0f} dBm")
    if ref:
        r = ref[0]
        print(f"   -> ref {args.ref_ssid}: median {r['median']:.0f} dBm, jitter {r['jitter']:.0f}")
    else:
        print(f"   -> WARNING: {args.ref_ssid} not seen here")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
