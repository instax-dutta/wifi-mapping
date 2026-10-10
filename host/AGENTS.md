# host

## Purpose

The laptop half: capture the board's JSONL stream and turn WiFi RSSI into
fingerprint maps, heatmaps, localization estimates, path-loss fits, and a coarse
wall sketch.

## Ownership

- `host/wifi_map/` - the `wifi_map` package:
  `records`, `sessions`, `capture`, `point`, `analyze`, `geometry`, `simulate`,
  `report` (batch), and `stream`, `server`, `index`, `features`, `envmap`,
  `mqtt` (live).
- `host/tests/` - pytest suite.
- `host/requirements.txt`, `host/conftest.py`.

## Local Contracts

- Protocol parsing lives only in `wifi_map/records.py`; capture, stream, and
  analysis all use it. Do not re-implement the wire format elsewhere.
- Core dependencies are limited to `pyserial`, `numpy`, `matplotlib`, `pytest`.
  The live server is standard-library only (HTTP + SSE). `hnswlib` and
  `paho-mqtt` are optional and must degrade gracefully.
- Raw session data is append-only and never mutated; analysis writes only under
  `data/derived/`.
- `analyze.py` prints a success-only marker beginning `ANALYSIS OK`;
  `server.py` prints `SERVER OK`.

## Work Guidance

- Run commands from the `host/` directory so `wifi_map` is importable, or set
  `PYTHONPATH=host`.
- Without a board, exercise the pipeline with `wifi_map.simulate` then
  `wifi_map.analyze`.

## Verification

- `python -m pytest -q tests` (run from `host/`). Gate: `tools/checks/c5-tests.mjs`.
- Analysis pipeline gate: `tools/checks/c6-analyze.mjs`.
- Live gates: `c10-server`, `c10-index`, `c11-features`, `c11-envmap`,
  `c11-mqtt`, `c12-ui`, `c14-golden`, `c15-integration` (see `.unlazy/wifimap-v2/`).

## Child DOX Index

None.
