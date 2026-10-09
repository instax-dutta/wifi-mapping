"""Protocol records for the wifi-mapper serial JSONL stream.

Single source of truth for the wire format described in docs/architecture.md.
`parse_line` is used by both capture and analysis so the two never drift.
"""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional, Union


@dataclass
class Ap:
    bssid: str
    ssid: str = ""
    rssi: int = -127
    channel: int = 0
    enc: int = 0
    hidden: bool = False


@dataclass
class ScanFrame:
    seq: int
    ms: int
    aps: List[Ap] = field(default_factory=list)
    x: Optional[float] = None
    y: Optional[float] = None
    label: Optional[str] = None
    host_ms: Optional[float] = None
    t: str = "scan"


@dataclass
class SniffFrame:
    seq: int
    ms: int
    bssid: str
    rssi: int
    channel: int = 0
    length: int = 0
    host_ms: Optional[float] = None
    t: str = "pk"


Frame = Union[ScanFrame, SniffFrame, Dict[str, Any]]


def _ap_from(d: Dict[str, Any]) -> Ap:
    return Ap(
        bssid=str(d.get("b", "")),
        ssid=str(d.get("s", "")),
        rssi=int(d.get("r", -127)),
        channel=int(d.get("c", 0)),
        enc=int(d.get("e", 0)),
        hidden=bool(d.get("h", 0)),
    )


def parse_line(line: str) -> Optional[Frame]:
    """Parse one protocol line. Returns None for blank/non-JSON noise.

    Raises ValueError if a line looks like a frame (starts with '{') but is
    not valid JSON, so callers can decide whether to skip or fail.
    """
    line = line.strip()
    if not line or not line.startswith("{"):
        return None
    obj = json.loads(line)
    t = obj.get("t")
    if t == "scan":
        return ScanFrame(
            seq=int(obj.get("seq", 0)),
            ms=int(obj.get("ms", 0)),
            aps=[_ap_from(a) for a in obj.get("aps", [])],
            x=obj.get("x"),
            y=obj.get("y"),
            label=obj.get("label"),
        )
    if t == "pk":
        return SniffFrame(
            seq=int(obj.get("seq", 0)),
            ms=int(obj.get("ms", 0)),
            bssid=str(obj.get("b", "")),
            rssi=int(obj.get("r", -127)),
            channel=int(obj.get("c", 0)),
            length=int(obj.get("len", 0)),
        )
    return obj  # boot / ready / info / ack / err / pong


def to_wire(frame: Frame) -> Dict[str, Any]:
    """Serialise back to the compact wire format (used by simulate.py)."""
    if isinstance(frame, ScanFrame):
        d: Dict[str, Any] = {
            "t": "scan",
            "seq": frame.seq,
            "ms": frame.ms,
            "n": len(frame.aps),
            "aps": [
                {"b": a.bssid, "s": a.ssid, "r": a.rssi, "c": a.channel,
                 "e": a.enc, "h": 1 if a.hidden else 0}
                for a in frame.aps
            ],
        }
        for key in ("x", "y", "label"):
            if getattr(frame, key) is not None:
                d[key] = getattr(frame, key)
        return d
    if isinstance(frame, SniffFrame):
        return {
            "t": "pk", "seq": frame.seq, "ms": frame.ms, "b": frame.bssid,
            "r": frame.rssi, "c": frame.channel, "len": frame.length,
        }
    return frame
