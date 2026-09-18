"""English/French placement parity (requires both reference ROMs).

The item placement logic is ROM independent, so the same seed must produce the
same item locations for both ROMs.
"""
from __future__ import annotations

import argparse
import binascii
import json
import os
import sys
import tempfile
import unittest

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from helpers import ROOT, require_rom  # noqa: E402
sys.path.insert(0, ROOT)

import randomizer  # noqa: E402
from settings import Settings  # noqa: E402

SEED = binascii.unhexlify("05C5CC462DF29F3DB8A6836470CA42A6")


def _placements(path: str) -> dict:
    settings = Settings()
    settings.validate()
    with tempfile.TemporaryDirectory() as tmp:
        out_rom = os.path.join(tmp, "out.gbc")
        out_json = os.path.join(tmp, "spoiler.json")
        args = argparse.Namespace(
            input_filename=path,
            output_filename=out_rom,
            plan=None,
            pymod=None,
            doubletrouble=False,
            romdebugmode=False,
            log_directory=None,
            spoilerformat="json",
            spoiler_filename=out_json,
            dump=None,
            test=False,
        )
        randomizer.Randomizer(args, settings, seed=SEED)
        with open(out_json, "rt", encoding="utf-8") as f:
            log = json.load(f)
    # Key by the unique item id: several locations share a display name (e.g.
    # the shuffled bosses), and spoiler ordering is not stable across processes.
    return {item["id"]: item["itemName"] for item in log["accessibleItems"]}


class ParityTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.en_path = require_rom("en")
        cls.fr_path = require_rom("fr")

    def test_placement_matches(self):
        en = _placements(self.en_path)
        fr = _placements(self.fr_path)
        self.assertTrue(en)
        self.assertEqual(en, fr)


if __name__ == "__main__":
    unittest.main()
