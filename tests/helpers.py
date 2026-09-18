"""Shared helpers for the test suite."""
from __future__ import annotations

import os
import sys
import unittest

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
TOOLS = os.path.join(ROOT, "tools")
for _path in (ROOT, TOOLS):
    if _path not in sys.path:
        sys.path.insert(0, _path)


def require_rom(kind: str) -> str:
    """Return the path to a reference ROM or skip the test if unavailable."""
    import common  # noqa: E402  (tools/common.py, on sys.path)

    try:
        return common.find_rom(kind)
    except FileNotFoundError:
        raise unittest.SkipTest("reference %s ROM not available" % kind)
