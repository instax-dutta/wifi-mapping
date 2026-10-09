# host

## Purpose

The laptop half: capture the board's JSONL stream and turn WiFi RSSI into
fingerprint maps, heatmaps, localization estimates, path-loss fits, and a coarse
wall sketch.

## Ownership

- `host/wifi_map/` - the `wifi_map` package.
- `host/tests/` - pytest suite.
- `host/requirements.txt`, `host/conftest.py`.

## Local Contracts

- Protocol parsing lives only in `wifi_map/records.py`; capture and analysis both
  use it. Do not re-implement the wire format elsewhere.
- Dependencies are limited to `pyserial`, `numpy`, `matplotlib`, `pytest`. No
  scikit-learn / torch.
- Raw session data is append-only and never mutated; analysis writes only under
  `data/derived/`.
- `analyze.py` always prints a success-only marker beginning `ANALYSIS OK`.

## Work Guidance

- Run commands from the `host/` directory so `wifi_map` is importable, or set
  `PYTHONPATH=host`.
- Without a board, exercise the pipeline with `wifi_map.simulate` then
  `wifi_map.analyze`.

## Verification

- `python -m pytest -q tests` (run from `host/`). Gate: `tools/checks/c5-tests.mjs`.
- Analysis pipeline gate: `tools/checks/c6-analyze.mjs`.

## Child DOX Index

None.
