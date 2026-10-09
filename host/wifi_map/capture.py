"""Capture wifi-mapper serial output to a JSONL session.

Usage (from the host/ directory so the package is importable):
    python -m wifi_map.capture --port /dev/cu.usbserial-0001 \
        --out ../data/sessions/walk1/scans.jsonl --duration 30 --x 1.0 --y 2.0
"""

from __future__ import annotations

import argparse
import json
import sys
import time
from pathlib import Path

import serial  # pyserial

from .records import ScanFrame, parse_line


def main(argv=None) -> int:
    p = argparse.ArgumentParser(description="Capture ESP8266 wifi-mapper JSONL.")
    p.add_argument("--port", required=True)
    p.add_argument("--out", required=True, help="path to scans.jsonl")
    p.add_argument("--baud", type=int, default=115200)
    p.add_argument("--duration", type=float, default=0.0, help="seconds; 0 = until Ctrl-C")
    p.add_argument("--x", type=float, default=None, help="label: known x (m)")
    p.add_argument("--y", type=float, default=None, help="label: known y (m)")
    p.add_argument("--label", default=None, help="free-form label")
    p.add_argument("--period", type=int, default=None, help="scan period ms (board)")
    p.add_argument("--sniff", default=None, help="BSSID to sniff instead of scanning")
    p.add_argument("--sniff-channel", type=int, default=None, help="target channel for sniff")
    p.add_argument("--rate", type=int, default=None, help="sniff emit interval ms (board)")
    p.add_argument("--meta", default=None, help="meta.json path")
    args = p.parse_args(argv)

    out = Path(args.out).expanduser()
    out.parent.mkdir(parents=True, exist_ok=True)

    try:
        ser = serial.Serial(args.port, args.baud, timeout=1.0)
    except Exception as e:  # noqa: BLE001
        print(f"CAPTURE FAILED cannot open {args.port}: {e}", file=sys.stderr)
        return 2
    # Avoid resetting the board via the auto-reset circuit while we talk to it.
    try:
        ser.setDTR(False)
        ser.setRTS(False)
    except Exception:
        pass
    time.sleep(0.3)

    if args.sniff:
        cmd = f"sniff {args.sniff}"
        if args.sniff_channel:
            cmd += f" {args.sniff_channel}"
        ser.write((cmd + "\n").encode())
    else:
        if args.period:
            ser.write(f"period {args.period}\n".encode())
        ser.write(b"scan on\n")
    if args.rate:
        ser.write(f"rate {args.rate}\n".encode())
    ser.write(b"info\n")

    n_scans = n_pk = 0
    boot = None
    t0 = time.time()
    last_report = t0

    try:
        with out.open("w") as fh:
            while True:
                if args.duration and (time.time() - t0) >= args.duration:
                    break
                raw = ser.readline()
                if not raw:
                    continue
                line = raw.decode("utf-8", "replace").strip()
                if not line.startswith("{"):
                    continue
                try:
                    frame = parse_line(line)
                    d = json.loads(line)
                except Exception:
                    continue
                if frame is None:
                    continue
                if isinstance(frame, ScanFrame):
                    n_scans += 1
                    if args.x is not None:
                        d["x"] = args.x
                    if args.y is not None:
                        d["y"] = args.y
                    if args.label is not None:
                        d["label"] = args.label
                else:
                    if d.get("t") == "pk":
                        n_pk += 1
                    elif d.get("t") == "boot":
                        boot = d
                d["host_ms"] = round((time.time() - t0) * 1000.0, 1)
                fh.write(json.dumps(d, separators=(",", ":")) + "\n")
                fh.flush()
                now = time.time()
                if now - last_report >= 2.0:
                    last_report = now
                    print(f"[capture] scans={n_scans} pk={n_pk} ({now - t0:.0f}s)",
                          file=sys.stderr)
    except KeyboardInterrupt:
        pass
    finally:
        try:
            ser.write(b"scan off\nsniff off\n")
            ser.close()
        except Exception:
            pass

    meta = {
        "port": args.port, "baud": args.baud, "out": str(out),
        "scans": n_scans, "pk": n_pk, "duration_s": round(time.time() - t0, 1),
        "x": args.x, "y": args.y, "label": args.label,
        "sniff": args.sniff, "period": args.period, "rate": args.rate, "boot": boot,
    }
    meta_path = Path(args.meta).expanduser() if args.meta else out.parent / "meta.json"
    meta_path.write_text(json.dumps(meta, indent=2))
    print(f"CAPTURE OK scans={n_scans} pk={n_pk} out={out}")
    return 0 if (n_scans or n_pk) else 1


if __name__ == "__main__":
    raise SystemExit(main())
