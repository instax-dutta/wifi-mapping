"""Frame sources: UDP datagrams and serial, both yielding parsed protocol frames.

UDP carries the same JSONL objects the firmware prints to serial (see
docs/adr/0001-udp-transport.md). One datagram may hold one or more lines.
"""

from __future__ import annotations

import queue
import socket
import threading
from typing import Optional

from .records import parse_line


class FrameQueue:
    def __init__(self, maxsize: int = 10000):
        self.q: "queue.Queue" = queue.Queue(maxsize=maxsize)

    def put(self, frame) -> None:
        try:
            self.q.put_nowait(frame)
        except queue.Full:
            pass

    def get(self, timeout: Optional[float] = None):
        try:
            return self.q.get(timeout=timeout)
        except queue.Empty:
            return None


def _feed_lines(text: str, q: FrameQueue) -> None:
    for line in text.splitlines():
        line = line.strip()
        if not line.startswith("{"):
            continue
        try:
            frame = parse_line(line)
        except Exception:
            continue
        if frame is not None:
            q.put(frame)


class UDPSource(threading.Thread):
    def __init__(self, q: FrameQueue, port: int = 5005, host: str = "0.0.0.0"):
        super().__init__(daemon=True)
        self.q = q
        self.port = port
        self.running = True
        self.sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        self.sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        self.sock.setsockopt(socket.SOL_SOCKET, socket.SO_BROADCAST, 1)
        self.sock.bind((host, port))
        self.sock.settimeout(1.0)

    def run(self) -> None:
        while self.running:
            try:
                data, _ = self.sock.recvfrom(65535)
            except socket.timeout:
                continue
            except OSError:
                break
            _feed_lines(data.decode("utf-8", "replace"), self.q)

    def stop(self) -> None:
        self.running = False
        try:
            self.sock.close()
        except Exception:
            pass


class SerialSource(threading.Thread):
    def __init__(self, q: FrameQueue, port: str, baud: int = 115200):
        super().__init__(daemon=True)
        self.q = q
        self.running = True
        import serial  # pyserial
        self.ser = serial.Serial(port, baud, timeout=1.0)
        try:
            self.ser.setDTR(False)
            self.ser.setRTS(False)
        except Exception:
            pass

    def run(self) -> None:
        while self.running:
            try:
                raw = self.ser.readline()
            except Exception:
                break
            if raw:
                _feed_lines(raw.decode("utf-8", "replace"), self.q)

    def stop(self) -> None:
        self.running = False
        try:
            self.ser.close()
        except Exception:
            pass
