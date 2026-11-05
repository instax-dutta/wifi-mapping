"""Local web form to point the sensor at a Wi-Fi network and verify UDP.

Open http://127.0.0.1:8099, enter the SSID and password, submit. The password is
used only to send the `join` command to the board over serial; it is never
logged, printed, or written to disk. The serial port is held open for the life
of the server so the board is not reset between actions, and a "listen again"
button re-checks the UDP stream without re-entering the password.

Run (from the repo root):
    .venv/bin/python tools/wifi_join.py
"""

from __future__ import annotations

import json
import socket
import threading
import time
import urllib.parse
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

import serial

SERIAL_PORT = "/dev/cu.usbserial-0001"
BAUD = 115200
HTTP_PORT = 8099
DEFAULT_UDP_PORT = 5005
DEFAULT_SSID = "SatyamNivas"
LISTEN_SECONDS = 15
_lock = threading.Lock()
_ser = None


def laptop_ip() -> str:
    try:
        s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        s.connect(("8.8.8.8", 80))
        ip = s.getsockname()[0]
        s.close()
        return ip
    except Exception:
        return "127.0.0.1"


def get_ser():
    global _ser
    if _ser is None:
        _ser = serial.Serial(SERIAL_PORT, BAUD, timeout=1)
        _ser.setDTR(False)
        _ser.setRTS(False)
        time.sleep(1.5)
        _ser.reset_input_buffer()
    return _ser


def _listen(port: int) -> dict:
    out = {"frames": 0, "types": {}, "sample": None}
    sk = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    sk.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
    sk.bind(("0.0.0.0", port))
    sk.settimeout(1.0)
    t0 = time.time()
    while time.time() - t0 < LISTEN_SECONDS:
        try:
            data, _ = sk.recvfrom(65535)
        except socket.timeout:
            continue
        for ln in data.decode("utf-8", "replace").splitlines():
            if not ln.startswith("{"):
                continue
            try:
                d = json.loads(ln)
            except Exception:
                continue
            out["frames"] += 1
            out["types"][d.get("t")] = out["types"].get(d.get("t"), 0) + 1
            if out["sample"] is None and d.get("t") == "scan":
                out["sample"] = {"n": d.get("n"),
                                 "aps": [a.get("s") or a.get("b") for a in d.get("aps", [])][:5]}
    sk.close()
    return out


def board_join(ssid: str, pw: str, target_ip: str, target_port: int) -> dict:
    out = {"joined": False, "board_ip": None, "error": None, "wifi": None,
           "target": f"{target_ip}:{target_port}"}
    with _lock:
        try:
            ser = get_ser()
            # scanning and connecting conflict on the ESP8266: stop scans first
            ser.write(b"scan off\n")
            time.sleep(0.4)
            ser.reset_input_buffer()
            ser.write(f"join {ssid} {pw}\n".encode())
            t0 = time.time()
            while time.time() - t0 < 12:
                line = ser.readline().decode("utf-8", "replace").strip()
                if not line.startswith("{"):
                    continue
                try:
                    d = json.loads(line)
                except Exception:
                    continue
                if d.get("t") == "ack" and d.get("cmd") == "join":
                    out["joined"] = True
                    out["board_ip"] = d.get("ip")
                    break
                if d.get("t") == "err":
                    out["error"] = d.get("msg")
                    break
            # ask the board for its wifi status either way
            ser.write(b"info\n")
            t1 = time.time()
            while time.time() - t1 < 2:
                line = ser.readline().decode("utf-8", "replace").strip()
                if line.startswith("{") and '"t":"info"' in line:
                    try:
                        out["wifi"] = json.loads(line).get("wifi")
                    except Exception:
                        pass
                    break
            if out["joined"]:
                ser.write(f"udp {target_ip} {target_port}\n".encode())
                ser.write(b"period 800\nscan on\n")
                time.sleep(1.5)
                out.update(_listen(target_port))
        except Exception as e:  # noqa: BLE001
            out["error"] = str(e)
    print(f"JOIN result joined={out['joined']} board_ip={out.get('board_ip')} "
          f"wifi={out.get('wifi')} frames={out.get('frames')} types={out.get('types')} "
          f"error={out.get('error')}", flush=True)
    return out


def board_listen() -> dict:
    with _lock:
        try:
            get_ser().write(b"scan on\n")
            time.sleep(1.0)
            return _listen(DEFAULT_UDP_PORT)
        except Exception as e:  # noqa: BLE001
            return {"frames": 0, "types": {}, "sample": None, "error": str(e)}


def _verdict(res: dict) -> str:
    if res.get("error") and not res.get("joined"):
        return (f'<div class="res"><span class="bad">Join failed</span>: {res["error"]} '
                f'(board wifi={res.get("wifi") or "none"}). Check the password/2.4GHz SSID, then retry.</div>')
    if not res.get("joined") and "board_ip" in res:
        return f'<div class="res"><span class="bad">Join failed</span>: {res.get("error") or "no ack"}</div>'
    if res.get("frames", 0) > 0 and res.get("types", {}).get("scan"):
        return (f'<div class="res"><span class="ok">UDP on-air OK</span> - {res["frames"]} frames '
                f'{json.dumps(res["types"])} from {res.get("board_ip")}\nsample: {json.dumps(res["sample"])}</div>')
    if res.get("frames", 0) > 0:
        return (f'<div class="res"><span class="ok">UDP link OK</span> - {res["frames"]} frames '
                f'{json.dumps(res["types"])} (no scan frames yet - click listen again)</div>')
    return '<div class="res"><span class="bad">0 UDP frames</span> - click listen again</div>'


PAGE = """<!doctype html><meta charset=utf-8><title>Point the sensor at Wi-Fi</title>
<style>
 body{{font:14px/1.5 -apple-system,Segoe UI,Roboto,sans-serif;max-width:560px;margin:48px auto;
   padding:0 18px;background:#0a0b0d;color:#e9e7e2}}
 h1{{font-size:15px;letter-spacing:.14em;text-transform:uppercase}}
 p.sub{{color:#8a8f98;margin-top:0}}
 label{{display:block;margin:14px 0 4px;color:#8a8f98;font-size:12px;letter-spacing:.05em;text-transform:uppercase}}
 input{{width:100%;padding:10px 12px;background:#101317;border:1px solid #2b3038;border-radius:8px;
   color:#e9e7e2;font:14px ui-monospace,Menlo,monospace}}
 button{{margin-top:18px;padding:10px 18px;background:#ffb454;border:0;border-radius:8px;color:#101317;
   font-weight:600;letter-spacing:.04em;cursor:pointer}}
 button.ghost{{background:transparent;border:1px solid #2b3038;color:#e9e7e2}}
 .res{{margin-top:20px;padding:14px;border:1px solid #2b3038;border-radius:8px;background:#101317;
   font-family:ui-monospace,Menlo,monospace;font-size:13px;white-space:pre-wrap}}
 .ok{{color:#57d9a3}} .bad{{color:#ff6b6b}}
</style>
<h1>Point the sensor at Wi-Fi</h1>
<p class="sub">Enter the network the board should join. The password is sent to the board only and never stored.</p>
<form method="post" action="/join">
  <label>SSID</label><input name="ssid" value="{ssid}" autocomplete="off">
  <label>Wi-Fi password</label><input name="pw" type="password" autocomplete="off">
  <label>Laptop UDP target</label><input name="target" value="{ip}:{port}">
  <button type="submit">Join and test UDP</button>
</form>
<form method="post" action="/listen">
  <button class="ghost" type="submit">Listen again (15s)</button>
</form>
{result}
"""


class Handler(BaseHTTPRequestHandler):
    def log_message(self, *a):
        pass

    def _send(self, body: str, code: int = 200):
        b = body.encode()
        self.send_response(code)
        self.send_header("Content-Type", "text/html; charset=utf-8")
        self.send_header("Content-Length", str(len(b)))
        self.end_headers()
        self.wfile.write(b)

    def do_GET(self):  # noqa: N802
        if self.path.split("?")[0] != "/":
            return self._send("not found", 404)
        self._send(PAGE.format(ssid=DEFAULT_SSID, ip=laptop_ip(), port=DEFAULT_UDP_PORT, result=""))

    def do_POST(self):  # noqa: N802
        path = self.path.split("?")[0]
        if path not in ("/join", "/listen"):
            return self._send("not found", 404)
        n = int(self.headers.get("Content-Length", "0"))
        form = urllib.parse.parse_qs(self.rfile.read(n).decode("utf-8", "replace"))
        if path == "/listen":
            res = board_listen()
        else:
            ssid = (form.get("ssid") or [DEFAULT_SSID])[0].strip() or DEFAULT_SSID
            pw = (form.get("pw") or [""])[0]
            target = (form.get("target") or [f"{laptop_ip()}:{DEFAULT_UDP_PORT}"])[0]
            ip, _, port = target.partition(":")
            res = board_join(ssid, pw, ip or laptop_ip(), int(port or DEFAULT_UDP_PORT))
        self._send(PAGE.format(ssid=DEFAULT_SSID, ip=laptop_ip(),
                               port=DEFAULT_UDP_PORT, result=_verdict(res)))


def main() -> int:
    get_ser()  # open once; resets the board here, not per request
    httpd = ThreadingHTTPServer(("127.0.0.1", HTTP_PORT), Handler)
    print(f"JOIN SERVER http://127.0.0.1:{HTTP_PORT}  (laptop ip {laptop_ip()})", flush=True)
    httpd.serve_forever()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
