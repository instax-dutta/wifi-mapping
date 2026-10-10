# Architecture Decision Records

Short records of the decisions behind this system. Newest context first in
`PLAN`/docs; each ADR is immutable once accepted and superseded by a new one.

| ADR | Decision |
| --- | --- |
| [0001](0001-udp-transport.md) | UDP transport for untethered sensing |
| [0002](0002-rssi-only-scope.md) | RSSI-only scope; no CSI on ESP8266 |
| [0003](0003-live-server-sse.md) | Live server on stdlib HTTP + SSE (no WebSocket dep) |
| [0004](0004-fingerprint-index.md) | Fingerprint index: numpy default, hnswlib optional |
| [0005](0005-motion-from-rssi.md) | Motion/presence from RSSI temporal variance |
| [0006](0006-environment-change.md) | Environment change detection via median drift |
| [0007](0007-optional-mqtt.md) | Optional MQTT with graceful degradation |
| [0008](0008-ui-direction.md) | Live dashboard UI direction |
