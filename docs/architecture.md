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

## Serial protocol v1 (line-delimited JSON wire contract)

Firmware prints one JSON object per `\n`. Host sends plain-text command lines.

Boot (once):
`{"t":"boot","fw":"wifi-mapper","v":"0.2.0","mac":"2c:f4:32:2e:d4:dc","chip":"esp8266"}`

Scan frame (one per scan):
`{"t":"scan","seq":123,"ms":45678,"n":24,"aps":[{"b":"a4:..","s":"MyAP","r":-63,"c":6,"e":3,"h":0}, ...]}`

Sniff frame (one per accepted packet, throttled):
`{"t":"pk","seq":124,"ms":45701,"b":"a4:..","r":-55,"c":6,"len":128}`

Ack/error:
`{"t":"ack","cmd":"scan on"}`
`{"t":"err","msg":"sniff needs bssid"}`
`{"t":"info","scan":1,"sniff":"a4:..","rate":200}`

Commands (host -> board): `scan on`, `scan off`, `sniff <bssid>`, `sniff off`,
`rate <ms>`, `period <ms>`, `info`, `ping`. Default on boot: `scan on`.

Design rules: never print partial lines; keep each frame under ~1 KB; a scan of
40 APs is ~3 KB and the host reads fast enough at 115200.

`host/wifi_map/records.py` (`parse_line()`) is the single source of truth for
this protocol; firmware and host must match it.

## Flash logging

Board A can log frames to on-board LittleFS so it can roam untethered on a
power bank, then replay them over serial with `dump`. Logging is off by default.

`log on` - mount LittleFS and open `/scan.log` for append; emit `ack` with the
path. `log off` - close the log file and stop logging. `log clear` - stop
logging and delete `/scan.log`. `log status` - emit an `info` frame with
`log`, `log_count`, `log_bytes`, and `log_path`. `dump` - echo every non-empty
line in `/scan.log` to Serial, then emit an `ack` with the line count.

Frames written to flash are byte-identical to the serial wire format (the same
`{"t":"scan",...}` / `{"t":"pk",...}` JSONL frames streamed live), so the host
can reuse `wifi_map.records.parse_line` without a separate parser. The log is
capped at 256 KB; when full, logging stops and an `err` frame is emitted.

Operator flow:
1. Flash the updated firmware to Board A.
2. Power Board A on a power bank and roam the survey grid.
3. Bring it back, connect USB, and run
   `wifi_map.survey --port /dev/cu.usbserial-0001 --out data/sessions/<name>
   --duration <seconds>`.
4. Analyze with `wifi_map.analyze --session data/sessions/<name>`.

## Firmware: `firmware/wifi_mapper/wifi_mapper.ino` + `firmware/ref_beacon/ref_beacon.ino`

Board A (`wifi_mapper`):
- `WiFi.mode(WIFI_STA); WiFi.disconnect();` then loop.
- Scan path: `WiFi.scanNetworks(false, true)` (sync, include hidden), serialize.
- Sniff path: `wifi_set_promiscuous_rx_cb` via `user_interface.h`; in the
  callback capture `rx_ctrl->rssi`, `rx_ctrl->channel`, length, and the source
  MAC from the 802.11 header; enqueue if it matches the target BSSID; drain the
  ring in `loop()` respecting the rate limit and serial buffer.
- LED heartbeat on scan/sniff so a human can see it working.
- Non-blocking: serial command parse in `loop()`, never `delay()` long.
- Flash logging to LittleFS (`/scan.log`, 256 KB cap): every emitted scan /
  sniff frame is appended to flash; `log on/off/clear/status/dump` control it,
  `dump` replays the log over serial.

Board B (`ref_beacon`): fixed soft-AP, SSID `mq-ref`, ch 6, max TX, powered by
a power bank. Sits at a known position so the sensor has a reference
transmitter for path-loss fitting and k-wall geometry.

## Host package: `host/wifi_map/`

- `records.py` - dataclasses + `parse_line()`; single source of truth for the
  protocol, used by both capture and analysis.
- `sessions.py` - load a session directory into arrays / a pandas-free structure
  (numpy only), pivot APs into a feature matrix with an observed-mask.
- `capture.py` - CLI. Opens the port, sends commands, timestamps on arrival,
  writes JSONL, optional `--x/--y` label appended to each scan, `--duration`, plus `--label`, `--baud`, `--period`, `--sniff`, `--sniff-channel`, `--rate`, `--meta`.
- `survey.py` - CLI. Dumps Board A's LittleFS flash log (`/scan.log`) over serial
  to a session JSONL, so the board can roam untethered and data can be retrieved
  later. Commands used: `log clear`, `log on`, `log off`, `dump`.
- `point.py` - CLI. Capture one survey point at x, y and print an immediate AP
  summary (incl. the reference beacon's RSSI).
- `analyze.py` - CLI. Heatmaps, kNN localization with leave-one-out error,
  path-loss fit, summary metrics JSON.
- `geometry.py` - SfW-lite: k-means over RSSI -> k (wall-count) thresholds ->
  free/occupied sketch along rays from a reference transmitter.
- `occupancy.py` - `build_occupancy` / `run_occupancy`: save the k-visibility
  grid as .npy/.png plus metadata.json.
- `simulate.py` - generate a synthetic labelled fingerprint dataset so the whole
  analysis path can be tested without moving the board.
- `report.py` - render a self-contained HTML report from an analysis output
  directory.
- `stream.py` - frame sources: UDP datagrams and serial, both yielding parsed
  protocol frames.
- `server.py` - live server: ingest frames (UDP or serial), rolling-window
  median fingerprint, kNN localization, motion gating, envmap drift, serve the
  web dashboard plus SSE and API; optional MQTT.
- `index.py` - fingerprint index for fast nearest-neighbour localization
  (numpy kNN default; hnswlib optional, graceful fallback).
- `features.py` - RSSI-derived motion and presence features: temporal variance
  scoring, sliding median filter, MAD filter.
- `envmap.py` - environment change detection: compare current per-AP median
  RSSI against a stored baseline to flag map drift.
- `mqtt.py` - optional MQTT publisher for live state; no-op and import-safe when
  paho-mqtt is not installed.

Dependencies: `pyserial`, `numpy`, `matplotlib`. No scikit-learn (kNN is a few
lines of numpy), no torch. Keeps the venv small and portable. The live server
is standard-library only (HTTP + SSE); `hnswlib` and `paho-mqtt` are optional
and degrade gracefully.

## Data quality

Per-AP signal cleaning before fingerprinting and localization, applied by
`wifi_map.analyze`:

- Sliding median filter (window=11): per-AP median filtering across time to
  suppress impulse outliers; research shows RMSE reduction up to 82× in dynamic
  conditions. `features.sliding_median_filter`.
- MAD filter: median absolute deviation outlier rejection per AP.
  `features.mad_filter`.
- Spearman distance KNN: 1 - Spearman rank correlation, excludes MISSING_RSSI
  positions from ranking; better handles multipath and signal attenuation
  (IEEE LSP 2016). `index.spearman_distance`, via `--distance spearman`.
- Exponential transform: exp(alpha * v) compresses strong-signal differences
  (UJI 2023). `index.exponential_transform`.
- Power transform: `index.power_transform`.
- Keep-strongest-APs filtering: reduces dimensionality, focuses on stable strong
  APs. `sessions.filter_strongest`, via `--keep-aps N`.

New analyze CLI options: `--distance {euclidean,spearman}`, `--median-filter`,
`--keep-aps N`.

## P2 Geometry: sparse inverse k-visibility

Sparse inverse k-visibility (Kim et al. 2024, arXiv 2403.02235/2408.07757):
turns per-point wall counts (k) into a free-space/occupancy grid. Reference:
`geometry.k_thresholds`/`assign_k` compute per-point k-values from RSSI
thresholds.

`geometry.sparse_inverse_k_visibility(points, k_values, router_pos, bounds,
resolution)` - sparse inverse k-visibility: turns per-point wall counts (k)
into a free-space/occupancy grid.

Free-space rules:
- trajectory is free
- k=0 → ray from router to point is free
- same-k segment intersections are free

Occupied space:
- Δk=1 → unimodal Gaussian wall at ray midpoint
- Δk>1 → multimodal
- noisy-or combination

`occupancy.build_occupancy` / `occupancy.run_occupancy` - save grid as .npy/.png
+ metadata.json.

New analyze CLI options: `--occupancy`, `--resolution`.

Operator flow: labeled survey → `wifi_map.occupancy --session ... --ref BSSID,X,Y --out ...` → occupancy_grid.png/wall_probability.png/metadata.json.

## P4 Continuous localization

Live (untethered) localization: the server keeps a rolling window of recent
frames, builds a sliding-window median fingerprint, localizes against the
index, gates position updates on motion score, and smooths the position
estimate exponentially.

- Sliding-window median fingerprint over the rolling window (`--window INT`,
  default 5) so a single noisy scan can't jump the position.
- Motion gating: `wifi_map.features.motion_score` / `presence()` scores RSSI
  variance; position updates are gated behind `--motion-gate FLOAT` (default
  2.0) so the estimate only moves when the signal is disturbed enough to
  indicate motion.
- Exponential smoothing: `--smooth-alpha FLOAT` (default 0.3) smooths
  successive position estimates.
- CLI options: `--motion-gate`, `--smooth-alpha`, `--window`. Served by
  `wifi_map.server` with the web dashboard, SSE (`GET /events`), and
  `GET /api/state`; optional MQTT via `wifi_map.mqtt`.

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

## Getting started for new agents

WiFi radio mapping on a single ESP8266: the board senses RSSI while it moves,
and the laptop turns those measurements into a fingerprint map with heatmaps,
localization, and a coarse wall sketch.

**The two boards**
- Board A (ESP8266, `wifi_mapper`): the sensor. Runs scan mode (ambient APs)
  or sniff mode (one target transmitter), prints JSONL frames over serial, and
  can log to flash for untethered roaming.
- Board B (ESP8266, `ref_beacon`): fixed reference AP (SSID `mq-ref`, ch 6,
  max TX) at a known position, which makes path-loss fitting and the k-wall
  geometry tractable.

**Without a board (simulate → analyze)**
1. `PYTHONPATH=host .venv/bin/python -m wifi_map.simulate` — generate a
   synthetic labelled fingerprint dataset.
2. `PYTHONPATH=host .venv/bin/python -m wifi_map.analyze --session
   data/sessions/<name> --distance spearman --median-filter --keep-aps 8` —
   heatmaps, kNN localization with LOO error, path-loss fit.

**With a board (flash → survey → analyze → optional occupancy/server)**
1. Flash `firmware/wifi_mapper/wifi_mapper.ino` to Board A and
   `firmware/ref_beacon/ref_beacon.ino` to Board B.
2. `wifi_map.capture --port /dev/cu.usbserial-0001 --out data/sessions/<name>
   --duration <seconds>` (or survey untethered: `log on`, roam, `log off`,
   then `wifi_map.survey --port <port> --out <session>` to dump the flash log).
3. `wifi_map.analyze --session data/sessions/<name>`.
4. Optional: `wifi_map.occupancy --session <session> --ref BSSID,X,Y --out
   <dir>` for the wall sketch, or `wifi_map.server --session <session> --source
   serial --port 3000` for the live dashboard.

**Wire protocol** — single source of truth: `host/wifi_map/records.py`
(`parse_line()`). Firmware and host must match it; docs/architecture.md is the
contract.

**Gates** — `GATES.md` (G0–G9) and `.unlazy/wifimap-v2/` (live gates c10,
c11, c12, c14, c15). Run `node tools/checks/c*.mjs`.

**Key CLI commands**
- `wifi_map.simulate` — synthetic dataset
- `wifi_map.capture --port <port> --out <session> --duration ` — live capture
- `wifi_map.survey --port <port> --out <session> --duration ` — dump flash log
- `wifi_map.analyze --session <session> [--distance spearman] [--median-filter] [--keep-aps N]`
- `wifi_map.occupancy --session <session> --ref BSSID,X,Y --out <dir>`
- `wifi_map.server --session <session> --source serial --port 3000` — live UI
