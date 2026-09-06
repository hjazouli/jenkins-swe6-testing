#!/bin/bash
set -e

# Thin wrapper kept as the stable entry point for Jenkins/muscle memory.
# All the real logic (build, flash, verify) now lives in flash_bcm.py,
# which gives us proper stage logging and a post-flash UART sanity check
# that this script never had.
cd "$(dirname "$0")/.."

if [ -x ".venv/bin/python3" ]; then
  PYTHON=".venv/bin/python3"
else
  PYTHON="python3"
fi

exec "$PYTHON" scripts/flash_bcm.py "$@"
