# ADR-0005: Motion/presence from RSSI temporal variance

- Status: Accepted
- Date: 2026-10-10

## Context
RuView derives motion from CSI variance. We have RSSI only, but a moving person
or object still perturbs received power over time.

## Decision
Compute a motion score as the mean per-AP RSSI variance over a short window
(dB^2), with a threshold for presence and a coarse level (low/medium/high).

## Consequences
- Gives the robot a "something is moving" signal without extra hardware.
- It is coarse and location-agnostic: it flags disturbance, not where it is.
- Thresholds need per-room calibration; exposed as parameters.
