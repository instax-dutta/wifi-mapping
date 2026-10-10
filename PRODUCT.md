# Product

<!-- impeccable:product-schema 1 -->

## Platform

web

## Stack

Python standard-library HTTP server (`wifi_map.server`) + vanilla HTML/CSS/JS,
live updates over Server-Sent Events. No framework, no build step.

## Users

Operators and developers of a camera-free robot. While mapping a room or
debugging the localization, they watch a phone or laptop to see where the sensor
thinks it is, whether the radio environment is stable, and whether anything is
moving.

## Product Purpose

Turn commodity WiFi RSSI into live spatial awareness: localize inside a surveyed
room, detect motion, and flag when the fingerprint map has gone stale. Success is
that at a glance you know position, signal health, and whether the room changed.

## Positioning

RSSI-only, running on a $3 ESP8266 with no camera or lidar. A neighbouring
CSI-based system needs ESP32-class hardware; this makes radio mapping work on the
cheapest board and streams untethered over UDP.

## Operating Context

Board A (sensor) scans and sniffs, streaming line-delimited JSON over UDP; Board
B is a fixed reference access point. The laptop runs `wifi_map.server` and serves
this dashboard. Used while walking a survey grid or driving a prototype.

## Capabilities and Constraints

Live: per-AP RSSI, kNN fingerprint position with nearest-distance uncertainty,
motion score from RSSI temporal variance, and environment drift against a stored
baseline. Constraints: RSSI only (no CSI), metre-level accuracy, and coarse
motion (it reports disturbance, not where). See `docs/capability-matrix.md`.

## Evidence on Hand

A real room survey (11 points) with measured localization median 0.16 tiles and
a fitted path-loss exponent of n = 0.77; see `docs/results.md`. All displayed
data comes from the real boards; synthetic data is labelled as synthetic.

## Product Principles

- Truthful radio: show RSSI and uncertainty, never invent precision.
- Glanceable: legible across a room; the task outranks decoration.
- Fail visible: disconnected, stale map, and disturbance are loud states.

## Accessibility & Inclusion

Status changes announced via `aria-live`; text contrast at or above 4.5:1;
honours `prefers-reduced-motion`.
