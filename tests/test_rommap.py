"""Validate the committed French relocation map (no ROM required)."""
from __future__ import annotations

import json
import os
import re
import sys
import unittest
from collections import Counter

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from helpers import ROOT  # noqa: E402

REQUIRED_STATUSES = {
    "exact", "identical", "low_entropy", "translated_old",
    "predicted", "windowed", "fuzzy", "same_addr",
}


class RommapTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.path = os.path.join(ROOT, "rommap_fr.json")
        if not os.path.exists(cls.path):
            raise unittest.SkipTest("rommap_fr.json not present")
        with open(cls.path, "rt", encoding="utf-8") as f:
            cls.data = json.load(f)

    def test_schema(self):
        self.assertIn("rom", self.data)
        self.assertIn("patches", self.data)
        self.assertIn("tables", self.data)
        self.assertIn("symbols", self.data)
        self.assertIn("code_addrs", self.data)
        self.assertEqual(self.data["rom"]["en_sha1"], "d90ac17e9bf17b6c61624ad9f05447bdb5efc01a")
        self.assertEqual(self.data["rom"]["fr_sha1"], "b5e4df1a67432c609fa0f23519315297c6dcdc1d")

    def test_resolution_ratio(self):
        statuses = Counter(p["status"] for p in self.data["patches"])
        resolved = sum(statuses[s] for s in REQUIRED_STATUSES)
        total = len(self.data["patches"])
        self.assertGreaterEqual(resolved / total, 0.99, statuses)

    def test_no_rom_bytes_stored(self):
        # Only the SHA-1 hashes may look like long hex strings.
        text = open(self.path, "rt", encoding="utf-8").read()
        hex_strings = re.findall(r'"([0-9a-fA-F]{41,})"', text)
        self.assertEqual(hex_strings, [], "rommap must not embed ROM data")

    def test_tables_validated(self):
        validation = self.data["tables"]["validation"]
        self.assertTrue(validation)
        for name, status in validation.items():
            self.assertEqual(status["status"], "ok", name)

    def test_labels_relocated(self):
        labels = self.data["symbols"]["labels"]
        self.assertEqual(len(labels), 264)
        unresolved = [n for n, e in labels.items() if e["status"] in ("unknown", "low_confidence")]
        self.assertEqual(unresolved, [])

    def test_code_addrs_coverage(self):
        stats = self.data["code_addrs"]["stats"]
        unresolved = stats.get("unresolved", 0) + stats.get("out_of_range", 0)
        self.assertLessEqual(unresolved, 6, stats)

    def test_identical_banks(self):
        banks = set(self.data["identical_banks"])
        self.assertIn("3e", banks)  # LADXR scratch bank is identical
        self.assertIn("0a", banks)


if __name__ == "__main__":
    unittest.main()
