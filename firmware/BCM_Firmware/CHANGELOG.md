# BCM Firmware Changelog

Version follows semver (`MAJOR.MINOR.PATCH`, in `VERSION`): bump PATCH for bug
fixes, MINOR for backward-compatible feature additions, MAJOR for breaking
protocol/behavior changes. `scripts/flash_bcm.py` refuses to flash if the
current `VERSION` has no matching entry here, so bump `VERSION` and add an
entry in the same change.

The version actually flashed to a board is this number plus build metadata
pinning the exact commit, e.g. `1.1.0+a55fe14` (`-dirty` appended if the
working tree had uncommitted changes at build time) — queryable live from any
board over UART via `CMD_GET_VERSION`.

## 1.1.0
- Add `CMD_GET_VERSION` / `RESP_VERSION` so the board reports its own
  compiled-in firmware version over UART. `flash_bcm.py` now checks the
  version before flashing (what's currently on the board) and after
  (confirms the new build actually took), instead of only trusting a
  host-side log of what was *supposed* to be flashed.

## 1.0.0
- Baseline: HIL-validated release (binary UART protocol, chip temperature
  telemetry, HSA/ABS/EBD safety logic). Retroactive tag predating
  per-release changelog entries.
