"""French pointer tables (requires reference ROMs)."""
from __future__ import annotations

import io
import os
import sys
import unittest

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from helpers import ROOT, require_rom  # noqa: E402
sys.path.insert(0, ROOT)
sys.path.insert(0, os.path.join(ROOT, "tools"))

import tables_fr  # noqa: E402
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


class TablesTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.en_path = require_rom("en")
        cls.fr_path = require_rom("fr")

    def test_table_counts(self):
        rom = ROMWithTables(open(self.fr_path, "rb"))
        self.assertEqual(rom.profile.name, "fr")
        for name, expected in EXPECTED_COUNTS.items():
            self.assertEqual(len(getattr(rom, name)), expected, name)

    def test_discovery_validation(self):
        result = tables_fr.discover_tables(self.en_path, self.fr_path)
        for name, status in result["validation"].items():
            self.assertEqual(status["status"], "ok", (name, status))

    def test_texts_bank_table(self):
        result = tables_fr.discover_tables(self.en_path, self.fr_path)
        self.assertEqual(result["config"]["texts"]["banks_addr"], 0x841)


if __name__ == "__main__":
    unittest.main()
