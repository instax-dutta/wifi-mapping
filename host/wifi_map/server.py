"""Live server: ingest frames, maintain state, serve the UI, SSE, and API.

Usage (from the repo root):
    PYTHONPATH=host .venv/bin/python -m wifi_map.server \
        --session data/sessions/room1 --source udp --udp-port 5005 --port 3000

Then open http://localhost:3000 . See docs/adr/0003-live-server-sse.md.
"""

from __future__ import annotations

import argparse
import json
import queue
import threading
import time
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from typing import Any, Dict, List, Optional

import numpy as np

from . import features, envmap
from .index import FingerprintIndex, vectorize
from .mqtt import Publisher
from .records import ScanFrame
from .sessions import ap_stats, ap_table, labels, load_session
from .stream import FrameQueue, SerialSource, UDPSource

WEB_DIR = Path(__file__).resolve().parents[2] / "web"


class LiveState:
    def __init__(self, session: Optional[str] = None, history_len: int = 30,
                 mqtt_host: Optional[str] = None):
        self.lock = threading.Lock()
        self.subs: set = set()
        self.index = FingerprintIndex()
        self.bssids: List[str] = []
        self.history: List[List[float]] = []
        self.latest_aps: List[Dict[str, Any]] = []
        self.position: Optional[Dict[str, float]] = None
        self.pos_err: Optional[float] = None
        self.baseline = envmap.EnvBaseline()
        self.env: Dict[str, Any] = {"score": 0.0, "changed": False, "per_ap": {}}
        self.motion: Dict[str, Any] = {"score": 0.0, "moving": False, "level": "low"}
        self.samples = 0
        self.source = "udp"
        self.connected = False
        self.history_len = history_len
        self.mqtt = Publisher(mqtt_host)
        self._recent: Dict[str, List[int]] = {}
        if session:
            self._fit(session)

    def _fit(self, session: str) -> None:
        data = load_session(session)
        scans = data["scans"]
        if not scans:
            return
        b, X, M = ap_table(scans)
        xs, ys, lab = labels(scans)
        self.bssids = b
        if lab:
            pos = np.stack([xs, ys], axis=1)
            good = np.isfinite(pos).all(axis=1)
            self.index.fit(b, X[good], pos[good])
        self.baseline.build(ap_stats(scans))

    def _stats(self, aps) -> List[Dict[str, Any]]:
        for a in aps:
            v = self._recent.setdefault(a.bssid, [])
            v.append(a.rssi)
            del v[:-50]
        out = []
        for b, v in self._recent.items():
            out.append({"bssid": b, "median": float(np.median(v)), "n": len(v),
                        "min": int(min(v)), "max": int(max(v))})
        return out

    def on_frame(self, frame) -> None:
        if not isinstance(frame, ScanFrame):
            with self.lock:
                self.connected = True
            return
        with self.lock:
            self.samples += 1
            self.connected = True
            self.latest_aps = [{"bssid": a.bssid, "ssid": a.ssid, "rssi": a.rssi,
                                "channel": a.channel} for a in frame.aps]
            if not self.bssids:
                self.bssids = sorted({a.bssid for a in frame.aps})
            if self.bssids:
                v = vectorize(frame.aps, self.bssids)
                self.history.append(v.tolist())
                del self.history[:-self.history_len]
            if self.index.X.shape[0]:
                xy, err = self.index.query(vectorize(frame.aps, self.index.bssids))
                if np.isfinite(xy).all():
                    self.position = {"x": float(xy[0]), "y": float(xy[1])}
                    self.pos_err = err
            if self.history:
                score = features.motion_score(self.history)
                self.motion = {"score": score, "moving": features.presence(self.history),
                               "level": features.motion_level(score)}
            self.env = self.baseline.drift(self._stats(frame.aps))
            snap = self.snapshot_locked()
        self._publish(snap)

    def snapshot_locked(self) -> Dict[str, Any]:
        extent = None
        if self.index.pos.shape[0]:
            extent = {"x": [float(self.index.pos[:, 0].min()), float(self.index.pos[:, 0].max())],
                      "y": [float(self.index.pos[:, 1].min()), float(self.index.pos[:, 1].max())]}
        return {"ts": time.time(), "source": self.source, "connected": self.connected,
                "samples": self.samples, "aps": self.latest_aps,
                "position": self.position, "pos_err": self.pos_err,
                "motion": self.motion, "env": self.env, "bssids": self.bssids,
                "extent": extent}

    def snapshot(self) -> Dict[str, Any]:
        with self.lock:
            return self.snapshot_locked()

    def _publish(self, snap: Dict[str, Any]) -> None:
        self.mqtt.publish(snap)
        msg = json.dumps(snap)
        for q in list(self.subs):
            try:
                q.put_nowait(msg)
            except queue.Full:
                pass

    def subscribe(self) -> "queue.Queue":
        q: "queue.Queue" = queue.Queue(maxsize=200)
        self.subs.add(q)
        return q

    def unsubscribe(self, q) -> None:
        self.subs.discard(q)


class Handler(BaseHTTPRequestHandler):
    state: LiveState = None  # set before serving

    def log_message(self, *args) -> None:  # silence
        pass

    def _send(self, code: int, body: bytes, ctype: str) -> None:
        self.send_response(code)
        self.send_header("Content-Type", ctype)
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def _file(self, name: str, ctype: str) -> None:
        f = WEB_DIR / name
        if not f.exists():
            return self._send(404, b"missing", "text/plain")
        return self._send(200, f.read_bytes(), ctype)

    def do_GET(self) -> None:  # noqa: N802
        p = self.path.split("?", 1)[0]
        if p in ("/", "/index.html"):
            return self._file("index.html", "text/html; charset=utf-8")
        if p.startswith("/static/"):
            name = p[len("/static/"):]
            ctype = ("text/css" if name.endswith(".css")
                     else "application/javascript" if name.endswith(".js")
                     else "image/svg+xml" if name.endswith(".svg")
                     else "application/octet-stream")
            return self._file("static/" + name, ctype)
        if p == "/api/state":
            return self._send(200, json.dumps(self.state.snapshot()).encode(), "application/json")
        if p == "/api/health":
            return self._send(200, b'{"ok":true}', "application/json")
        if p == "/events":
            return self._sse()
        self._send(404, b"not found", "text/plain")

    def _sse(self) -> None:
        self.send_response(200)
        self.send_header("Content-Type", "text/event-stream")
        self.send_header("Cache-Control", "no-cache")
        self.send_header("Connection", "keep-alive")
        self.end_headers()
        q = self.state.subscribe()
        try:
            self.wfile.write(("data: " + json.dumps(self.state.snapshot()) + "\n\n").encode())
            self.wfile.flush()
            while True:
                try:
                    msg = q.get(timeout=15)
                except queue.Empty:
                    self.wfile.write(b": ping\n\n")
                    self.wfile.flush()
                    continue
                self.wfile.write(("data: " + msg + "\n\n").encode())
                self.wfile.flush()
        except (BrokenPipeError, ConnectionResetError, OSError):
            pass
        finally:
            self.state.unsubscribe(q)


def main(argv=None) -> int:
    p = argparse.ArgumentParser(description="Live WiFi-map server.")
    p.add_argument("--source", choices=["udp", "serial"], default="udp")
    p.add_argument("--udp-port", type=int, default=5005)
    p.add_argument("--serial", default="/dev/cu.usbserial-0001")
    p.add_argument("--session", default=None, help="fingerprint session for localization")
    p.add_argument("--port", type=int, default=3000)
    p.add_argument("--mqtt", default=None, help="MQTT broker host (optional)")
    p.add_argument("--history", type=int, default=30)
    args = p.parse_args(argv)

    state = LiveState(session=args.session, history_len=args.history, mqtt_host=args.mqtt)
    state.source = args.source
    q = FrameQueue()
    src = UDPSource(q, port=args.udp_port) if args.source == "udp" else SerialSource(q, args.serial)
    src.start()

    def pump() -> None:
        while True:
            frame = q.get(timeout=1.0)
            if frame is not None:
                state.on_frame(frame)

    threading.Thread(target=pump, daemon=True).start()
    Handler.state = state
    httpd = ThreadingHTTPServer(("0.0.0.0", args.port), Handler)
    print(f"SERVER OK http://localhost:{args.port} source={args.source} "
          f"udp_port={args.udp_port} session={args.session}")
    try:
        httpd.serve_forever()
    except KeyboardInterrupt:
        pass
    finally:
        httpd.shutdown()
        src.stop()
        state.mqtt.close()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
