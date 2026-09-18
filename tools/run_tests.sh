#!/usr/bin/env bash
# Run the LADXR test suite.
#
# Tests that need reference ROMs are skipped automatically when the ROMs are
# not present (the canonical SHA-1s are looked up in disassembly/).
set -euo pipefail

cd "$(dirname "$0")/.."

# Some randomizer code iterates over sets/dicts; fix the hash seed so results
# are reproducible.
export PYTHONHASHSEED=0

exec python3 -m unittest discover -s tests -p 'test_*.py' "$@"
