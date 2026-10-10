# ADR-0003: Live server on stdlib HTTP + SSE

- Status: Accepted
- Date: 2026-10-10

## Context
We want a live dashboard (position, APs, motion, map staleness) instead of
post-hoc files. RuView runs a Rust server with REST + WebSocket. We stay Python
and want no heavy dependencies.

## Decision
Use `http.server.ThreadingHTTPServer` for static files, `GET /api/state`, and
`GET /events` as a Server-Sent Events stream (text/event-stream). No WebSocket
library required; SSE is one-directional, which matches a status dashboard.

## Consequences
- Zero new core dependencies; runs anywhere with the standard library.
- Server pushes a JSON snapshot on a fixed tick; the browser uses `EventSource`.
- If bidirectional control is needed later, add a small POST endpoint rather
  than switching to WebSocket.
