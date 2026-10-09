# Architecture: WiFi radio mapping on one ESP8266

## Objective

Turn a single ESP8266 into a WiFi radio-mapping instrument: collect radio
measurements while it moves, and build (1) a fingerprint map with heatmaps and
localization, and (2) a coarse wall/free-space sketch from signal shadowing.
Everything runs on the board already in hand, with the laptop as the compute and
storage half. The later motor/collision work is explicitly out of scope here.

## Constraints (from hardware.md)

- RSSI only. No CSI on ESP8266.
- One radio: scan ambient APs, **or** sniff one transmitter, not both at once.
- Serial at 115200 is the only bulk link (~11 KB/s).
- Host (this laptop) does all heavy math; the board stays a sensor.

## Topology

```
  Board B: ESP8266 ref_beacon        Board A: ESP8266 (sensor)     Laptop (compute + storage)
  -----------------------------      -----------------------      ---------------------------
  fixed soft-AP, SSID mq-ref   )))   scan mode  ──JSONL──►     capture.py ──► data/sessions/<id>/*.jsonl
  ch 6, max TX, power bank      )))   sniff mode ──JSONL──►               │
                                                                          ▼
                                                                 analyze.py ──► fingerprint map
                                                                              ├─► heatmaps (*.png)
                                                                              ├─► localization kNN + LOO error
                                                                              ├─► path-loss fit (vs ref position)
                                                                              └─► geometry.py k-wall sketch
```

Board B gives the sensor a transmitter at a **known position**, which is what
makes path-loss fitting and the k-wall geometry tractable. Ambient APs are still
scanned alongside it.

## Serial protocol v1 (line-delimited JSON)

Firmware prints one JSON object per `\n`. Host sends plain-text command lines.

Boot (once):
`{"t":"boot","fw":"wifi-mapper","v":"0.1.0","mac":"2c:f4:32:2e:d4:dc","chip":"esp8266"}`

Scan frame (one per scan):
`{"t":"scan","seq":123,"ms":45678,"n":24,"aps":[{"b":"a4:..","s":"MyAP","r":-63,"c":6,"e":3,"h":0}, ...]}`

Sniff frame (one per accepted packet, throttled):
`{"t":"pk","seq":124,"ms":45701,"b":"a4:..","r":-55,"c":6,"len":128}`

Ack/error:
`{"t":"ack","cmd":"scan on"}`
`{"t":"err","msg":"sniff needs bssid"}`
`{"t":"info","scan":1,"sniff":"a4:..","rate":200}`

Commands (host -> board): `scan on`, `scan off`, `sniff <bssid>`, `sniff off`,
`rate <ms>`, `info`, `ping`. Default on boot: `scan on`.

Design rules: never print partial lines; keep each frame under ~1 KB; a scan of
40 APs is ~3 KB and the host reads fast enough at 115200.

## Firmware: `firmware/wifi_mapper/wifi_mapper.ino`

- `WiFi.mode(WIFI_STA); WiFi.disconnect();` then loop.
- Scan path: `WiFi.scanNetworks(false, true)` (sync, include hidden), serialize.
- Sniff path: `wifi_set_promiscuous_rx_cb` via `user_interface.h`; in the
  callback capture `rx_ctrl->rssi`, `rx_ctrl->channel`, length, and the source
  MAC from the 802.11 header; enqueue if it matches the target BSSID; drain the
  ring in `loop()` respecting the rate limit and serial buffer.
- LED heartbeat on scan/sniff so a human can see it working.
- Non-blocking: serial command parse in `loop()`, never `delay()` long.

## Host package: `host/wifi_map/`

- `records.py` - dataclasses + `parse_line()`; single source of truth for the
  protocol, used by both capture and analysis.
- `capture.py` - CLI. Opens the port, sends commands, timestamps on arrival,
  writes JSONL, optional `--x/--y` label appended to each scan, `--duration`.
- `sessions.py` - load a session directory into arrays / a pandas-free structure
  (numpy only), pivot APs into a feature matrix with an observed-mask.
- `analyze.py` - CLI. Heatmaps, kNN localization with leave-one-out error,
  path-loss fit, summary metrics JSON.
- `geometry.py` - SfW-lite: k-means over RSSI -> k (wall-count) thresholds ->
  free/occupied sketch along rays from a reference transmitter.
- `simulate.py` - generate a synthetic labelled fingerprint dataset so the whole
  analysis path can be tested without moving the board.

Dependencies: `pyserial`, `numpy`, `matplotlib`. No scikit-learn (kNN is a few
lines of numpy), no torch. Keeps the venv small and portable.

## Data model

A session directory holds `meta.json` (port, firmware version, start/end, notes)
and `scans.jsonl` (protocol frames, each optionally carrying `x`,`y`). No
database yet. Raw data is never mutated; analysis writes only under
`data/derived/`.

## Phase plan

- **P0 Sensing** (this pass): firmware scan + sniff, capture, protocol tests.
- **P1 Fingerprint map**: labelled grid/walk survey, heatmaps, kNN localization,
  honest LOO error (`CoruHS` confirms the ~2 m RSSI floor).
- **P2 Geometry**: k-means wall thresholds + SfW-lite occupancy sketch.
- **P3 Motion**: sniff-based dense RSSI vs time; path-loss fit; change/obstacle
  detection by deviation from the fitted model.
- **P4 Multi-node / robot**: only after P0-P3 are exhausted on one board. A
  second ESP (or a phone hotspot) becomes a fixed reference transmitter; then
  real active ranging and the motor loop become possible.

## Honest limitations

- One board cannot be AP and STA on separate channels simultaneously.
- RSSI jitter (~35 dBm worst-case) caps static-fingerprint accuracy near ~2 m;
  geometry from RSSI is coarse (SfW reports "potential walls", not CAD).
- Without odometry, trajectory is either hand-labelled or interpolated on a
  straight walk. Real SLAM needs a motion source we do not have yet.
