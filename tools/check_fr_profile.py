#!/usr/bin/env python3
"""Smoke check for the French ROM profile (phase B).

Verifies that the French ROM is detected, that every pointer table is built
with the French configuration, and that saving the table data works.

Usage:
    python3 tools/check_fr_profile.py
"""
from __future__ import annotations

import os
import sys
import tempfile

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import common  # noqa: E402

from romTables import ROMWithTables  # noqa: E402

EXPECTED_COUNTS = {
    "texts": 688,
    "entities": 800,
    "rooms_overworld_top": 128,
    "rooms_overworld_bottom": 128,
    "rooms_indoor_a": 256,
    "rooms_indoor_b": 255,
    "rooms_color_dungeon": 22,
    "background_tiles": 38,
    "background_attributes": 38,
    "room_sprite_data_overworld": 256,
    "room_sprite_data_indoor": 544,
}


def main() -> int:
    fr_path = common.find_rom("fr")
    rom = ROMWithTables(open(fr_path, "rb"))

    failures = []
    if rom.profile.name != "fr":
        failures.append("profile is %r, expected 'fr'" % rom.profile.name)

    for name, expected in EXPECTED_COUNTS.items():
        actual = len(getattr(rom, name))
        if actual != expected:
            failures.append("%s: count %d != %d" % (name, actual, expected))

    if failures:
        for failure in failures:
            print("FAIL: " + failure)
        return 1

    with tempfile.NamedTemporaryFile(suffix=".gbc", delete=True) as tmp:
        rom.save(tmp.name, name="LADXR")

    print("OK: French profile detected, %d tables built, save succeeded" % len(EXPECTED_COUNTS))
    print("    patch mappings: %d, symbol overrides: %d" % (
        len(rom.profile.patch_map), len(rom.profile.symbol_overrides())))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
