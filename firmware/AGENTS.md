# firmware

## Purpose

The ESP8266 Arduino firmware that turns the board into a WiFi radio-mapping
sensor: ambient AP scans and single-target promiscuous RSSI capture, emitted as
line-delimited JSON over serial.

## Ownership

- `firmware/wifi_mapper/wifi_mapper.ino` - the sensor (Board A): scan + sniff.
- `firmware/ref_beacon/ref_beacon.ino` - the fixed reference AP (Board B).

## Local Contracts

- Wire protocol is defined in `docs/architecture.md` and parsed in
  `host/wifi_map/records.py`; keep all three in sync.
- Target board is `esp8266:esp8266:nodemcuv2` (4 MB). No other board is assumed.
- ESP8266 has no CSI: do not add CSI features. RSSI only.
- One radio: scan and sniff are mutually exclusive by design (`setSniff` disables
  scanning).
- The promiscuous callback is IRAM and short: it only pushes to the ring buffer,
  never prints.
- No long `delay()`; the loop stays responsive to serial commands.

## Work Guidance

- Compile before flashing: `arduino-cli compile -b esp8266:esp8266:nodemcuv2 firmware/wifi_mapper`.
- Flash with the project venv's esptool, not arduino-cli's bundled esptool v3.0,
  which fails on this macOS (see `tools/AGENTS.md`).
- Keep JSON frames under ~1 KB and never print partial lines.

## Verification

- Compile gate: `tools/checks/c3-compile.mjs` (runs `arduino-cli compile`).
- Hardware gate: `tools/checks/c4-hwscan.mjs` (flash + capture a real scan).

## Child DOX Index

None.
