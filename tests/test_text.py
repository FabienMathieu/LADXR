"""French text encoding and translation (no ROM required)."""
from __future__ import annotations

import os
import sys
import unittest

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from helpers import ROOT  # noqa: E402
sys.path.insert(0, ROOT)

import french  # noqa: E402
import utils  # noqa: E402


class TextTest(unittest.TestCase):
    def tearDown(self):
        utils.setLanguage("en")

    def test_english_unchanged(self):
        utils.setLanguage("en")
        self.assertEqual(utils.formatText("Got the {SWORD}!"), b"Got the Sword!\xff")

    def test_french_encoding(self):
        utils.setLanguage("fr")
        # é -> *, apostrophe -> ^, ç -> _
        self.assertEqual(utils.formatText("Got the {SWORD}!"), b"Obtenu : *p*e\xff")

    def test_french_output_is_font_safe(self):
        utils.setLanguage("fr")
        samples = [
            "Got the {SWORD}!",
            "Got the {TRADING_ITEM_MAGNIFYING_GLASS}!",
            "Got the {INSTRUMENT3}!",
            "You need 20 {SEASHELL}s",
            "Only 100 {RUPEES}!",
            "Welcome, #####. I admire you for coming this far.",
        ]
        for sample in samples:
            out = utils.formatText(sample)
            body = bytes(b for b in out if b not in (0xFE, 0xFF))
            self.assertTrue(all(b < 0x80 for b in body), (sample, out))

    def test_names_coverage(self):
        missing = set(utils._NAMES) - set(french.NAMES)
        self.assertEqual(missing, set(), "missing French translations")

    def test_area_names(self):
        self.assertEqual(french.areaName("Mabe Village"), "Village de Mabe")
        self.assertEqual(french.areaName("Unknown Area"), "Unknown Area")

    def test_ask_prompt_translated(self):
        utils.setLanguage("fr")
        out = utils.formatText("Only 100 {RUPEES}!", ask="Buy  No Way")
        self.assertIn(b"Acheter", out)
        self.assertTrue(out.endswith(b"\xfe"))


if __name__ == "__main__":
    unittest.main()
