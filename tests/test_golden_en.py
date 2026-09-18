"""English golden master regression (requires the English ROM)."""
from __future__ import annotations

import os
import subprocess
import sys
import unittest

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from helpers import ROOT, require_rom  # noqa: E402


class GoldenTest(unittest.TestCase):
    def test_english_output_unchanged(self):
        require_rom("en")
        script = os.path.join(ROOT, "tools", "check_golden_en.sh")
        env = dict(os.environ)
        env["PYTHONHASHSEED"] = "0"
        proc = subprocess.run(["bash", script], capture_output=True, text=True, env=env)
        self.assertEqual(proc.returncode, 0, proc.stdout + proc.stderr)
        self.assertIn("OK", proc.stdout)


if __name__ == "__main__":
    unittest.main()
