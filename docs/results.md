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
