"""ROM profile detection and validation (requires reference ROMs)."""
from __future__ import annotations

import io
import os
import sys
import unittest

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from helpers import ROOT, require_rom  # noqa: E402
sys.path.insert(0, ROOT)

import romprofile  # noqa: E402
from romTables import ROMWithTables  # noqa: E402


class RomProfileTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.en_path = require_rom("en")
        cls.fr_path = require_rom("fr")
        cls.en = open(cls.en_path, "rb").read()
        cls.fr = open(cls.fr_path, "rb").read()

    def test_detect_by_sha(self):
        self.assertEqual(romprofile.detect_profile(self.en).name, "en")
        self.assertEqual(romprofile.detect_profile(self.fr).name, "fr")

    def test_detect_by_region_code(self):
        # Corrupt the SHA (flip a byte inside a bank) but keep the region code.
        modified = bytearray(self.fr)
        modified[0x8000] ^= 0xFF
        profile = romprofile.detect_profile(bytes(modified))
        self.assertEqual(profile.name, "fr")

    def test_profile_by_name(self):
        self.assertIsNone(romprofile.profile_by_name("auto"))
        self.assertEqual(romprofile.profile_by_name("en").name, "en")
        self.assertEqual(romprofile.profile_by_name("fr").name, "fr")
        with self.assertRaises(ValueError):
            romprofile.profile_by_name("de")

    def test_profile_mismatch(self):
        with self.assertRaises(ValueError):
            ROMWithTables(io.BytesIO(self.en), profile=romprofile.profile_by_name("fr"))

    def test_translate_unknown_is_none(self):
        profile = romprofile.profile_by_name("fr")
        # 0x01EB in bank 0 is a known unmapped site.
        self.assertIsNone(profile.translate_patch(0x00, 0x01EB))

    def test_strict_mode_raises(self):
        profile = romprofile.profile_by_name("fr")
        strict = romprofile.RomProfile(
            "fr",
            language=profile.language,
            patch_map=dict(profile.patch_map),
            identical_banks=set(profile.identical_banks),
            tables=profile.tables,
            symbols=dict(profile.symbols),
            code_addrs=dict(profile.code_addrs),
            verify_patches=False,
            strict=True,
        )
        rom = ROMWithTables(io.BytesIO(self.fr), profile=strict)
        with self.assertRaises(romprofile.UnmappedPatchError):
            rom.patch(0x00, 0x01EB, None, "00")


if __name__ == "__main__":
    unittest.main()
