# Results: 2026-10-09 (stage P0/P1)

Everything below was measured on the real boards on this date, unless marked
synthetic. Commands and firmware versions are recorded for provenance.

## Boards

| Role | Firmware | Identity |
| --- | --- | --- |
| Board A - sensor | `wifi_mapper` v0.1.0 | ESP8266EX, 4 MB, MAC `2c:f4:32:2e:d4:dc` |
| Board B - reference AP | `ref_beacon` v0.1.0 | SSID `mq-ref`, ch 6, MAC `52:02:91:DA:F8:B1` |

## Firmware footprint

- `wifi_mapper`: 36% of RAM, 23% of flash (248 KB IROM).
- `ref_beacon`: 22% of flash (241 KB IROM).

## Completion ledger

`GATES.md`: ALL MET (10 gates), re-verified with the final code. G0-G7 run on
the board or host, G8 manual review, G9 the reference beacon.

## Measured radio results

| Run | Result |
| --- | --- |
| Ambient scan, static 15 s | 1 AP `home-router` (ch 11), median -59 dBm, scan-to-scan jitter 1 dB |
| Promiscuous sniff of that AP, 8 s | 40 packets, RSSI -66..-37 dBm, median -62 |
| Reference beacon at close range | scan -48..-50 dBm; sniff 41 packets, median -52 dBm |
| Sensor view with B powered | 2 APs: `mq-ref` -50.5, `home-router` -64 |
| Synthetic pipeline (8x8 grid, 4 APs) | kNN leave-one-out median 0.95 m, p90 1.72 m |

The path-loss fit on synthetic data recovered exponent n = 3.5 against a
generated truth of n = 2.6; the gap is the 9 dB wall term the fit cannot see.
That is expected and is exactly why geometry needs the k-wall step.

## Room survey (2026-10-10)

First real fingerprint grid. Board B (`mq-ref`) at a floor-tile intersection =
origin `(0,0)`; Board A carried point by point. Coordinates are **tile units**
(the path-loss exponent is scale-invariant, so tiles are fine; P0 is referenced
to 1 tile). 11 points, x in 0..3, y in 0..2 (origin omitted).

`mq-ref` median RSSI per point (dBm):

| y\x | 0 | 1 | 2 | 3 |
| --- | --- | --- | --- | --- |
| 0 | - | -60 | -64 | -66 |
| 1 | -71 | -81 | -68 | -79 |
| 2 | -73 | -72 | -70 | -74 |

Findings:

- **Fingerprint localization works**: kNN leave-one-out median error 0.16 tiles,
  p90 1.41, max 2.24 (a small, well-separated grid, so this is optimistic).
- **Pure distance ranging does not**: the fitted path-loss exponent is **n = 0.77**
  (P0 = -68 dBm at 1 tile). Real indoor n is 2-4; 0.77 means RSSI here is
  dominated by direction/obstacles, not distance. Same-distance points differ by
  up to ~11 dB (e.g. `(1,0)` = -60 vs `(0,1)` = -71; `(1,1)` = -81).
- **Shadowing is real and local**: `(3,1)` and `(1,1)` are deep fades (-79/-81)
  relative to neighbours - exactly the structure the k-wall/geometry step wants.
- **k-wall thresholds** for `mq-ref`: [-61.9, -67.7, -75.0] dBm; k-histogram
  [4, 8, 22, 10] over the 44 samples. This is a coarse proxy, not literal wall
  counts, until it is combined with a trajectory.

Artifacts: `data/derived/room1/report.html` (self-contained report with heatmaps
and the localization figure), `data/derived/room1/metrics.json`.

Provenance: `wifi_map.point X Y` per point (10 s, period 800 ms), then
`wifi_map.analyze --session data/sessions/room1 --ref 52:02:91:DA:F8:B1,0,0`,
then `wifi_map.report --dir data/derived/room1`.

## Live system (v0.2, 2026-10-10)

Built the RuView-inspired transfers adapted to RSSI (see `docs/tech-transfer.md`):
UDP streaming firmware, a standard-library live server (SSE + `/api/state`) with
live fingerprint localization, motion/presence from RSSI variance,
environment-drift detection, an optional fingerprint index (hnswlib) and MQTT
publisher, a redesigned instrument-panel dashboard (`web/`), ADRs, and a
deterministic golden fixture.

Verified: 13 host tests pass; the golden fixture reproduces its reference; the
impeccable detector reports 0 findings on the UI; the end-to-end gate
(UDP -> server -> SSE -> position/motion) passes against the golden fixture.
Ledger: `.unlazy/wifimap-v2/` (untracked working state). One handoff: the on-air
UDP test (board -> laptop over a real network) needs a network choice and has not
been run.

## Provenance

- Board identity: `.venv/bin/esptool --port /dev/cu.usbserial-0001 flash-id`.
- Flash: `tools/flash.sh` (venv esptool v5; arduino-cli's bundled esptool v3.0
  fails on this mac).
- Capture: `python -m wifi_map.capture ...`; analysis: `python -m wifi_map.analyze`.
- Synthetic: `python -m wifi_map.simulate --points 8`.
- Gate run: `node ~/.claude/skills/unlazy/scripts/gate-check.mjs --reverify --approve GATES.md`.

## Known limitations

- Only one ambient AP is in range at the desk, so a real fingerprint map needs
  the reference beacon (Board B) or a room with more APs.
- Untethered walking is not supported yet: the board has no on-flash logging, so
  the sensor must stay USB-tethered (or the laptop moves with it).
- ESP8266 exposes RSSI only, no CSI.

## Next (P1 proper)

In a less cluttered room: tape a grid, run the point-by-point survey from the
README, and analyze with `--ref 52:02:91:DA:F8:B1,X,Y` to get the real
path-loss exponent, k-wall thresholds, and localization error. Then P2 geometry
or P3 motion (sniff time series), or build untethered flash-logging.
