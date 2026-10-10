# web

## Purpose

The live dashboard served by `host/wifi_map/server.py`: position on the room
grid, per-AP signal, motion, and map staleness, updated live.

## Ownership

- `web/index.html`, `web/static/styles.css`, `web/static/app.js`.

## Local Contracts

- No framework, no build step; plain files served statically by the stdlib server.
- Consumes `GET /events` (SSE) and renders the state schema from
  `host/wifi_map/server.py`.
- Visual world is the instrument panel in `docs/adr/0008-ui-direction.md`:
  single accent, no colored glow shadows, functional text at or above 11px.
- Accessible: `aria-live` status, text contrast at or above 4.5:1,
  `prefers-reduced-motion` honoured.

## Work Guidance

- After UI edits run the impeccable detector:
  `.agents/skills/impeccable/scripts/impeccable detect --json web/index.html web/static/styles.css web/static/app.js`.
- Product truth lives in `PRODUCT.md`; the visual direction in ADR-0008.

## Verification

- `tools/checks/c12-ui.mjs` (served + structurally complete) and a clean detector.

## Child DOX Index

None.
