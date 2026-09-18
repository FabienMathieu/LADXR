#!/usr/bin/env bash
# English golden master regression check for phase B.
#
# Generating a ROM must be byte-for-byte identical to the pre-refactor output
# for the same seed and settings. PYTHONHASHSEED must be fixed because some
# randomizer code iterates over sets/dicts.
set -euo pipefail

cd "$(dirname "$0")/.."

EN="disassembly/Legend of Zelda, The - Link's Awakening DX (USA, Europe) (SGB Enhanced) (GB Compatible).gbc"
SEED="05C5CC462DF29F3DB8A6836470CA42A6"
EXPECTED="74631cca289339a80fa31abdd21a263ccf5bb341"
OUT="$(mktemp /tmp/ladxr_golden_en.XXXXXX.gbc)"

PYTHONHASHSEED=0 python3 main.py "$EN" -o "$OUT" -s "seed=$SEED" --spoilerformat none >/dev/null

ACTUAL="$(sha1sum "$OUT" | cut -d' ' -f1)"
rm -f "$OUT"

if [ "$ACTUAL" = "$EXPECTED" ]; then
    echo "OK: English golden master matches ($ACTUAL)"
else
    echo "FAIL: English golden master changed" >&2
    echo "  expected $EXPECTED" >&2
    echo "  actual   $ACTUAL" >&2
    exit 1
fi
