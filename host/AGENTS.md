# host

## Purpose

The laptop half: capture the board's JSONL stream and turn WiFi RSSI into
fingerprint maps, heatmaps, localization estimates, path-loss fits, and a coarse
wall sketch.

## Ownership

- `host/wifi_map/` - the `wifi_map` package:
  `records`, `sessions`, `capture`, `survey`, `point`, `analyze`, `geometry`,
  `occupancy`, `simulate`, `report` (batch), and `stream`, `server`, `index`,
  `features`, `envmap`, `mqtt` (live). New data-quality functions:
  `features.sliding_median_filter`, `features.mad_filter`,
  `index.spearman_distance`, `index.exponential_transform`,
  `index.power_transform`, `sessions.filter_strongest`.
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
- New analyze CLI options: `--distance {euclidean,spearman}`, `--median-filter`,
  `--keep-aps N`, `--occupancy` (with `--resolution`).
- `wifi_map.occupancy` is a standalone CLI for the Phase 3 P2 Geometry sparse
  inverse k-visibility grid: `--session`, `--ref BSSID,X,Y`, `--out`.
- New server CLI options: `--motion-gate FLOAT` (motion score threshold for gating position updates, default 2.0), `--smooth-alpha FLOAT` (exponential smoothing factor for position, default 0.3), `--window INT` (sliding window size for median fingerprint, default 5).

## Verification

- `python -m pytest -q tests` (run from `host/`). Gate: `tools/checks/c5-tests.mjs`.
- Analysis pipeline gate: `tools/checks/c6-analyze.mjs`.
- Live gates: `c10-server`, `c10-index`, `c11-features`, `c11-envmap`,
  `c11-mqtt`, `c12-ui`, `c14-golden`, `c15-integration` (see `.unlazy/wifimap-v2/`).

## Child DOX Index

None.
