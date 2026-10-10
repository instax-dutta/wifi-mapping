# ADR-0006: Environment change detection via median drift

- Status: Accepted
- Date: 2026-10-10

## Context
RuView's env_fingerprint detects moved furniture and new objects. A robot needs
to know when its map no longer matches the room.

## Decision
Store a per-BSSID median RSSI baseline from the survey. Compare live medians to
the baseline; the mean absolute shift is a drift score; above a threshold the map
is flagged stale, with a per-AP breakdown.

## Consequences
- The dashboard can warn "environment changed - re-survey".
- Coarse: it reports that something changed, not what or where.
