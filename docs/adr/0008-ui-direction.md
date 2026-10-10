# ADR-0008: Live dashboard UI direction

- Status: Accepted
- Date: 2026-10-10

## Context
RuView ships a Three.js demo UI. We want our own, for our use case: watching a
robot localize in a room, live.

## Decision
Build a purpose-built **Operate**-mode dashboard (task completion outranks
expression) rather than a RuView clone:
- one dominant live view: the room grid with the estimated position and trail;
- a compact signal panel: per-AP RSSI bars;
- status chips: connection, motion, map staleness, sample rate;
- monochrome instrument aesthetic with a single accent, generous whitespace,
  legible at a glance across the room.

No 3D. No skeleton. RSSI truth only.

## Consequences
- Fast to read while walking or debugging; scales to phone screens.
- Distinct from RuView's visual world by design.
