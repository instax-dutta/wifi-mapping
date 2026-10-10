# tools

## Purpose

Build/flash helpers and the unlazy gate checks that prove the project's
outcomes.

## Ownership

- `tools/checks/` - one Node ESM script per gate (see `GATES.md`).
- `tools/flash.sh` - compile + flash helper.

## Local Contracts

- Every `tools/checks/*.mjs` exits non-zero on any failure and prints a
  success-only marker only after all assertions pass. It must run from the
  repository root.
- Checks shell out to `arduino-cli`, the project venv (`.venv/bin/...`), and the
  serial port. They are macOS/this-laptop specific and may declare that.
- Flash with `.venv/bin/esptool` (v5). arduino-cli's bundled esptool v3.0 (x86
  python under Rosetta) fails with `termios ... Invalid argument` on this mac.
  If the CP2102 wedges after a surprise disconnect, unplug/replug the board.

## Work Guidance

- Keep checks deterministic and avoid network access.
- Hardware checks should skip-with-failure, never hang: use timeouts.
- Live checks (`c10-server`, `c12-ui`, `c15-integration`) start
  `host/wifi_map.server` on test ports (3987-3989) and must kill it in a
  `finally`. If a run leaves a stale server bound to a port, the next run fails
  with "address already in use": `pkill -f wifi_map.server` and re-run.

## Verification

- The ledger itself: `GATES.md`, linted by the unlazy gate-lint script.

## Child DOX Index

None.
