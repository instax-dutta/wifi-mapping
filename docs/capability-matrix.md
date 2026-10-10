# Capability matrix (RSSI-only, ESP8266)

Honest statement of what this system can and cannot do, adapted from RuView's
capability discipline. Our board has no CSI, so CSI-only rows are marked.

| Capability | RSSI (this project) | CSI (ESP32-S3, RuView) |
| --- | --- | --- |
| Presence (someone in the space) | Yes, coarse (signal disturbance) | Yes |
| Motion (still/moving) | Yes, coarse (RSSI variance) | Yes |
| Fingerprint localization in a surveyed area | Yes (~0.16 tiles in a small grid; optimistic) | Yes |
| Room-level identification / environment change | Yes, coarse (median drift) | Yes |
| Coarse free-space / wall sketch from shadowing | Research (P2, not yet built) | Marginal |
| Breathing / heart rate | No | Yes |
| 17-keypoint pose | No | First-cut (weak) |
| Through-wall sensing | No | Up to ~5 m, signal-dependent |
| Heading / fine motion | Needs odometry/IMU | Same |
| Last-centimetre collision avoidance | Needs a proximity sensor | Same |

## Notes
- RSSI accuracy is environment-dependent; expect metre-level, and only inside a
  surveyed area.
- Localization here is pattern matching (fingerprinting), not trilateration: our
  fitted path-loss exponent n = 0.77 showed distance alone explains little.
- "Coarse" means it reports that something changed or moved, not where.
