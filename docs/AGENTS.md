# docs

## Purpose

Durable project documentation for the WiFi radio-mapping project.

## Ownership

- `docs/hardware.md` - measured facts about the board in hand.
- `docs/research.md` - prior-art survey with sources.
- `docs/architecture.md` - system design, serial protocol, phase plan, limitations.
- `docs/results.md` - measured results with provenance, updated per experiment.
- `docs/figures/` - tracked experiment figures (heatmaps, localization, HTML report) shown in the README.

## Local Contracts

- `hardware.md` records only measured values and names the command that produced each.
- `research.md` cites every external work by name (paper venue/arXiv id or repo).
- `architecture.md` is the single source for the wire protocol; firmware and host must match it.
- Document stable contracts, not a work diary.

## Work Guidance

- When the board profile changes, re-run the reproduction commands in `hardware.md`.
- When a new paper/repo becomes the basis for code, add it to `research.md`.

## Verification

- No automated checks. `tools/checks/c1-hardware.mjs` cross-checks `hardware.md` against the live board.

## Child DOX Index

None.
