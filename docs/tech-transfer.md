# Technology transfer: ruvnet/RuView -> this project

Source: [ruvnet/RuView](https://github.com/ruvnet/RuView) ("WiFi DensePose"),
**MIT licensed**. Surveyed 2026-10-10.

## What RuView is

A WiFi sensing platform that turns radio into "spatial intelligence": presence,
motion, breathing, heart rate, fall detection, 17-keypoint pose, through-wall
sensing, and environment mapping. Sensors are **ESP32-S3** nodes streaming
**CSI** (per-subcarrier amplitude/phase) over UDP to a Rust sensing server with
REST/WebSocket/MQTT APIs and a web UI. There is a simulated mode and a
consumer-WiFi **RSSI-only** mode.

## The hard constraint

RuView's own capability matrix is explicit: pose, vitals, through-wall, and
multi-person all require **CSI**, which needs an ESP32-S3 (or a research NIC).
ESP8266 is not supported, and even ESP32-C3/original ESP32 are excluded. Their
**RSSI-only** mode does only **coarse presence and motion**. We are RSSI-only, so
we do not chase pose/vitals - that would need an ESP32-S3, which is out of scope
for now.

## What IS transferable (prioritised)

| # | Transfer | Why it helps us | Effort |
| --- | --- | --- | --- |
| T1 | **UDP streaming from the board** (RuView streams CSI over UDP to a server) | Removes our USB tether: the sensor roams on a power bank and streams over WiFi. Biggest workflow win, and the robot will need it anyway. | Low |
| T2 | **Live server + WebSocket dashboard** (their localhost:3000 UI) | Live map + current position while surveying/driving instead of post-hoc files. Big iteration speed-up. | Medium |
| T3 | **RSSI motion/presence features** (they do motion from signal variance / band power) | Turn our fast sniff stream into a "something is moving" channel - dynamic obstacle awareness for the robot. | Low-Med |
| T4 | **Environment change detection** (their `env_fingerprint`: rooms, moved furniture, new objects) | Detect when the room changed since mapping, so the robot knows the fingerprint map is stale. | Medium |
| T5 | **ADRs + honest capability matrix** (they publish decision records and a "what's real vs not" table) | Our docs become trustworthy and contributor-friendly; MIT-friendly practice. | Low |
| T6 | **Vector index for fingerprint lookup** (their `micro-hnsw` is ~12 KB on-device) | Fast kNN on large maps; numpy is fine now, HNSW later. | Medium |
| T7 | **MQTT integration** (HA-DISCO, Mosquitto) | Clean hook for the future robot/controller and home automation. | Low |
| T8 | **Deterministic golden test** (their `verify.py` reference signal) | A reference fixture that proves our pipeline did not regress. | Low |

**Status (2026-10-10):** T1-T8 are built and gated (`.unlazy/wifimap-v2/`),
adapted to RSSI. T1 (UDP) and T2/T3 (server + dashboard + motion) are the
headline; T5 ADRs live in `docs/adr/`, and the capability matrix in
`docs/capability-matrix.md`.

## What is NOT transferable

- CSI pipeline: phase sanitization, subcarrier fusion, multistatic
  attention-weighted cross-viewpoint embedding, Hampel/SpotFi/Fresnel - all need
  CSI.
- Vitals (breathing/heart rate) and pose - CSI only.
- Their Rust server stack: we stay Python; no need to port.

## Licence note

RuView is MIT, so code and ideas may be reused with attribution. Add an
attribution line wherever we borrow concretely (e.g. the UDP frame idea, the
motion-feature method, ADR style).

## Suggested next build

T1 + T2 together give the most speed: the board streams RSSI over UDP, a small
Python server ingests it and serves a live WebSocket dashboard (map + estimated
position + a motion indicator from T3). That turns our file-based, tethered
pipeline into a live system - the same leap RuView made, adapted to RSSI.
