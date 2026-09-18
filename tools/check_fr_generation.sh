#!/usr/bin/env bash
# French generation smoke test (phase C).
#
# Generates a French ROM and checks that it completes and is a valid 1MB ROM.
# It does NOT verify gameplay; that is done manually in an emulator.
set -euo pipefail

cd "$(dirname "$0")/.."

FR="disassembly/Legend of Zelda, The - Link's Awakening DX (France) (Rev 1) (SGB Enhanced) (GB Compatible).gbc"
SEED="05C5CC462DF29F3DB8A6836470CA42A6"
OUT="$(mktemp /tmp/ladxr_fr.XXXXXX.gbc)"
LOG="$(mktemp /tmp/ladxr_fr_log.XXXXXX)"

PYTHONHASHSEED=0 python3 main.py "$FR" -o "$OUT" -s "seed=$SEED" --spoilerformat none >"$LOG" 2>&1

if ! grep -q "Saved:" "$LOG"; then
    echo "FAIL: French generation did not save a ROM" >&2
    cat "$LOG" >&2
    rm -f "$OUT" "$LOG"
    exit 1
fi

SIZE="$(stat -c %s "$OUT")"
if [ "$SIZE" != "1048576" ]; then
    echo "FAIL: unexpected output size $SIZE" >&2
    rm -f "$OUT" "$LOG"
    exit 1
fi

echo "OK: French ROM generated ($(sha1sum "$OUT" | cut -d' ' -f1))"
grep -E "Profile fr|Warning|bank " "$LOG" || true
rm -f "$OUT" "$LOG"
