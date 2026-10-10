# ADR-0007: Optional MQTT with graceful degradation

- Status: Accepted
- Date: 2026-10-10

## Context
The future robot/controller and home automation want a standard integration bus.
RuView publishes over MQTT (Home Assistant discovery).

## Decision
Provide an optional `Publisher` that publishes the state JSON to an MQTT topic.
It is import-safe and a no-op when `paho-mqtt` is absent or no broker host is
configured.

## Consequences
- Zero impact on the core system.
- Enables Home Assistant / robot integration with a `pip install paho-mqtt`.
