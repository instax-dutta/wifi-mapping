# wifi-mapping

Turning a single NodeMCU **ESP8266** into a WiFi radio-mapping instrument: it
scans ambient access points (and can sniff one transmitter at high rate), streams
RSSI measurements over USB serial, and the laptop builds fingerprint maps,
heatmaps, and a coarse wall sketch from signal shadowing.

This is stage one of a self-driving car idea - map the surroundings from WiFi
radio first, drive without collisions later. No extra hardware is bought; we push
the one ESP8266 as far as it goes.

## What is here

- `docs/` - hardware profile, prior-art survey, architecture and serial protocol.
- `firmware/` - Arduino sketches: `wifi_mapper` (sensor) and `ref_beacon` (fixed reference AP).
- `host/` - Python capture + analysis pipeline (`wifi_map` package) and tests.
- `tools/` - flash/build helpers and the unlazy gate checks.
- `GATES.md` - the completion ledger for the current scope.

## Quick start

```bash
# one-time host env
python3 -m venv .venv
.venv/bin/pip install -r host/requirements.txt

# build + flash the firmware (uses the venv esptool; see tools/AGENTS.md for why)
./tools/flash.sh /dev/cu.usbserial-0001

# capture a labelled sample (stand at x=1.0, y=2.0)
PYTHONPATH=host .venv/bin/python -m wifi_map.capture --port /dev/cu.usbserial-0001 \
  --out data/sessions/demo/scans.jsonl --duration 10 --x 1.0 --y 2.0

# analyze (heatmaps + localization error + path-loss fit)
PYTHONPATH=host .venv/bin/python -m wifi_map.analyze --session data/sessions/demo
```

Run the pipeline end-to-end on simulated data first (no board needed):

```bash
PYTHONPATH=host .venv/bin/python -m wifi_map.simulate --out data/derived/sim --points 8
PYTHONPATH=host .venv/bin/python -m wifi_map.analyze  --session data/derived/sim
```

## Board

ESP8266EX, 4 MB flash, CP2102 bridge on `/dev/cu.usbserial-0001`, MAC
`2c:f4:32:2e:d4:dc`. See `docs/hardware.md` for the full measured profile.

## Status

Stage P0/P1 done: sensing firmware, capture, fingerprint analysis, and the
reference-beacon setup, all verified on the real boards. `GATES.md` is ALL MET
(10 gates); measured numbers are in `docs/results.md`; the phase plan and honest
limitations are in `docs/architecture.md`.

Two boards are used: **Board A** runs `wifi_mapper` (tethered sensor), **Board B**
runs `ref_beacon` (fixed reference AP on a power bank). Next: the point-by-point
room survey (below) to build a real fingerprint map.
