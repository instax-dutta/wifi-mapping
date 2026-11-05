# Results: 2026-10-09 (stage P0/P1)

Everything below was measured on the real boards on this date, unless marked
synthetic. Commands and firmware versions are recorded for provenance.

## Boards

| Role | Firmware | Identity |
| --- | --- | --- |
| Board A - sensor | `wifi_mapper` v0.2.0 | ESP8266EX, 4 MB, MAC `2c:f4:32:2e:d4:dc` |
| Board B - reference AP | `ref_beacon` v0.2.0 | SSID `mq-ref`, ch 6, MAC `52:02:91:DA:F8:B1` |

Firmware footprint:

- `wifi_mapper`: 36% of RAM, 23% of flash (248 KB IROM). LittleFS flash logging
  adds ~1 KB overhead.
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

## Phase 1-4 implementations (2026-11-05, code complete — not yet measured on real boards)

| Phase | Capability | Status | Details |
| --- | --- | --- | --- |
| P1 Fingerprint map | Labelled grid/walk survey, heatmaps, kNN localization, honest LOO error | Implemented | Room survey measured 2026-10-09 (see Room survey above); kNN LOO median error 0.16 tiles on that grid. |
| P2 Geometry | k-means wall thresholds + SfW-lite occupancy sketch | Implemented, not yet measured on real boards | `wifi_map.geometry` / `occupancy.build_occupancy`; occupancy grid output `.npy/.png` + metadata.json. Requires a labelled survey to exercise end-to-end. |
| P3 Motion | Sniff-based dense RSSI vs time; path-loss fit; change/obstacle detection by deviation from fitted model | Implemented, not yet measured on real boards | `wifi_map.features`, `wifi_map.envmap` drift detection. Requires a real sniff time-series on hardware. |
| P4 Multi-node / robot | Fixed reference transmitter (second ESP / phone hotspot); active ranging; motor loop out of scope | Out of scope | Blocked until P0-P3 are exhausted on one board; motor/collision stage stays out of scope until WiFi radio mapping is solid (root AGENTS.md). |

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
- ESP8266 exposes RSSI only, no CSI.
- Phase 2-4 implementations are code-complete but not yet measured on real
  boards; end-to-end results above (2026-10-09) cover P0/P1 sensing and P1
  fingerprint only.

## Phase plan

- **P0 Sensing** — done: firmware scan + sniff, capture, protocol tests (measured 2026-10-09).
- **P1 Fingerprint map** — done: labelled grid/walk survey, heatmaps, kNN localization, honest LOO error (room survey measured 2026-10-09).
- **P2 Geometry** — done code-complete: k-means wall thresholds + SfW-lite occupancy sketch; not yet measured on real boards.
- **P3 Motion** — done code-complete: sniff-based dense RSSI vs time; path-loss fit; change/obstacle detection by deviation from fitted model; not yet measured on real boards.
- **P4 Multi-node / robot** — out of scope: only after P0-P3 are exhausted on one board; the motor/collision stage stays out of scope until WiFi radio mapping is solid.
