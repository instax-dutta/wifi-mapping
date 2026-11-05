"""Survey: dump the wifi-mapper flash log to a session JSONL.

The board logs scan/sniff frames continuously to LittleFS while roaming
untethered. This tool connects over serial, starts logging, waits for the
operator to roam, stops logging, then dumps all logged frames to
<out>/scans.jsonl for host-side analysis.

Usage (from the host/ directory so the package is importable):
    PYTHONPATH=host python -m wifi_map.survey --port /dev/cu.usbserial-0001         --out data/sessions/walk1 --duration 60
"""

from __future__ import annotations

import argparse
import json
import sys
import time
from pathlib import Path

import serial  # pyserial


def _readline(ser, timeout=1.0):
    ser.timeout = timeout
    raw = ser.readline()
    if not raw:
        return None
    return raw.decode("utf-8", "replace").strip()


def _send_and_ack(ser, cmd, expect=None, timeout=3.0):
    ser.write((cmd + "\n").encode())
    ser.flush()
    deadline = time.time() + timeout
    while time.time() < deadline:
        line = _readline(ser, 0.5)
        if line is None:
            continue
        if not line.startswith("{"):
            continue
        try:
            d = json.loads(line)
        except Exception:
            continue
        if d.get("t") == "err":
            return d
        if expect is None or d.get("cmd") == expect or d.get("t") == expect:
            return d
    return None


def main(argv=None) -> int:
    p = argparse.ArgumentParser(
        description="Dump wifi-mapper flash log to a session JSONL."
    )
    p.add_argument("--port", required=True, help="serial port of Board A")
    p.add_argument("--out", required=True, help="output session directory")
    p.add_argument("--baud", type=int, default=115200, help="serial baud rate")
    p.add_argument(
        "--duration",
        type=float,
        default=60.0,
        help="seconds to keep logging before dumping (default 60)",
    )
    args = p.parse_args(argv)

    out = Path(args.out).expanduser()
    out.mkdir(parents=True, exist_ok=True)

    try:
        ser = serial.Serial(args.port, args.baud, timeout=1.0)
    except Exception as e:  # noqa: BLE001
        print(f"SURVEY FAILED cannot open {args.port}: {e}", file=sys.stderr)
        return 2
    # Avoid resetting the board via the DTR/RTS auto-reset circuit while we talk.
    try:
        ser.setDTR(False)
        ser.setRTS(False)
    except Exception:
        pass
    time.sleep(0.3)
    # Drain boot/ready frames emitted right after connect.
    t_drain = time.time()
    while time.time() - t_drain < 0.5:
        _readline(ser, 0.1)

    r = _send_and_ack(ser, "log clear", expect="log clear")
    if r is None or r.get("t") == "err":
        print(f"SURVEY FAILED log clear: {r}", file=sys.stderr)
        ser.close()
        return 2
    r = _send_and_ack(ser, "log on", expect="log on")
    if r is None or r.get("t") == "err":
        print(f"SURVEY FAILED log on: {r}", file=sys.stderr)
        ser.close()
        return 2

    print(f"SURVEY logging for {args.duration:.0f}s ...", file=sys.stderr)
    time.sleep(args.duration)

    _send_and_ack(ser, "log off", expect="log off")

    # Dump the flash log: stream logged frames, stop at the dump ack.
    ser.write(b"dump\n")
    ser.flush()
    scans_path = out / "scans.jsonl"
    count = 0
    bytes_ = 0
    deadline = time.time() + 60.0
    with scans_path.open("w") as fh:
        while time.time() < deadline:
            line = _readline(ser, 1.0)
            if line is None:
                continue
            if not line.startswith("{"):
                continue
            try:
                d = json.loads(line)
            except Exception:
                continue
            if d.get("t") == "ack" and d.get("cmd") == "dump":
                break
            if d.get("t") == "err":
                print(f"SURVEY FAILED dump err: {d}", file=sys.stderr)
                ser.close()
                return 2
            fh.write(json.dumps(d, separators=(",", ":")) + "\n")
            count += 1
            bytes_ += len(line)

    ser.close()
    print(f"SURVEY OK frames={count} bytes={bytes_} out={scans_path}")
    return 0 if count else 1


if __name__ == "__main__":
    raise SystemExit(main())
