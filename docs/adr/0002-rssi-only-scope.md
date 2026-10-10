# ADR-0002: RSSI-only scope; no CSI on ESP8266

- Status: Accepted
- Date: 2026-10-10

## Context
RuView's headline features (pose, breathing, heart rate, through-wall) require
Channel State Information, which needs an ESP32-S3. Our board is an ESP8266,
which exposes RSSI only. ESP8266 CSI is not available in the SDK.

## Decision
Scope the system to what RSSI supports: fingerprint localization, motion and
presence from signal variance, coarse environment change detection, and coarse
geometry. Do not attempt CSI-based pose/vitals. See `docs/capability-matrix.md`.

## Consequences
- We reuse RuView's *platform* ideas, not its CSI signal pipeline.
- If CSI features become essential later, an ESP32-S3 node is the upgrade path
  (documented, not purchased now).
