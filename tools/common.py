"""Shared helpers for the French ROM relocation tooling.

This module is deliberately standalone: it only reads the repository and the
provided ROMs, and never writes to the ROMs themselves.
"""
from __future__ import annotations

import ast
import binascii
import hashlib
import os
import sys
from typing import Any, Dict, List, Optional, Tuple

REPO_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DISASSEMBLY_DIR = os.path.join(REPO_ROOT, "disassembly")
DATA_DIR = os.path.join(REPO_ROOT, "tools", "data")

# ROMs this tooling knows about, keyed by their SHA-1.
ROM_SHA1 = {
    "en": "d90ac17e9bf17b6c61624ad9f05447bdb5efc01a",
    "fr": "b5e4df1a67432c609fa0f23519315297c6dcdc1d",
}

BANK_SIZE = 0x4000
BANK_COUNT = 0x40

# Directories that never contain randomizer sources worth scanning.
SKIP_DIRS = {".git", "tools", "disassembly", "www", "gfx", "docs", "__pycache__", "tests"}


def ensure_repo_on_path() -> None:
    if REPO_ROOT not in sys.path:
        sys.path.insert(0, REPO_ROOT)


def sha1_file(path: str) -> str:
    h = hashlib.sha1()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(1 << 16), b""):
            h.update(chunk)
    return h.hexdigest()


def find_rom(kind: str) -> str:
    """Locate a ROM by its known SHA-1 in the disassembly directory."""
    expected = ROM_SHA1[kind]
    for name in sorted(os.listdir(DISASSEMBLY_DIR)):
        if not name.lower().endswith((".gbc", ".gb")):
            continue
        path = os.path.join(DISASSEMBLY_DIR, name)
        if sha1_file(path) == expected:
            return path
    raise FileNotFoundError(
        "Could not find the %s ROM (SHA-1 %s) in %s" % (kind, expected, DISASSEMBLY_DIR)
    )


def load_rom(path: str) -> bytes:
    with open(path, "rb") as f:
        data = f.read()
    if len(data) != BANK_SIZE * BANK_COUNT:
        raise ValueError("Unexpected ROM size: %d" % len(data))
    return data


def get_bank(rom: bytes, bank: int) -> bytes:
    return rom[bank * BANK_SIZE:(bank + 1) * BANK_SIZE]


def identical_banks(en: bytes, fr: bytes) -> List[int]:
    return [b for b in range(BANK_COUNT) if get_bank(en, b) == get_bank(fr, b)]


# ---------------------------------------------------------------------------
# AST extraction of rom.patch(...) call sites
# ---------------------------------------------------------------------------

class Unknown(Exception):
    pass


def _eval(node: ast.AST, env: Dict[str, Any]) -> Any:
    if isinstance(node, ast.Constant):
        return node.value
    if isinstance(node, ast.Name):
        if node.id in env:
            return env[node.id]
        raise Unknown(node.id)
    if isinstance(node, ast.BinOp):
        left = _eval(node.left, env)
        right = _eval(node.right, env)
        if isinstance(node.op, ast.Add):
            return left + right
        if isinstance(node.op, ast.Sub):
            return left - right
        if isinstance(node.op, ast.Mult):
            return left * right
        if isinstance(node.op, ast.FloorDiv):
            return left // right
        raise Unknown(type(node.op).__name__)
    if isinstance(node, ast.UnaryOp) and isinstance(node.op, ast.USub):
        return -_eval(node.operand, env)
    if isinstance(node, ast.Call):
        func = node.func
        if isinstance(func, ast.Name) and func.id == "ASM":
            if node.args and isinstance(node.args[0], ast.Constant) and isinstance(node.args[0].value, str):
                ensure_repo_on_path()
                from assembler import ASM  # type: ignore
                base = None
                if len(node.args) > 1:
                    try:
                        base = _eval(node.args[1], env)
                    except Unknown:
                        base = None
                return binascii.unhexlify(ASM(node.args[0].value, base_address=base))
        if isinstance(func, ast.Name) and func.id == "len":
            return len(_eval(node.args[0], env))
        if isinstance(func, ast.Name) and func.id in ("bytes", "bytearray"):
            return bytes(_eval(node.args[0], env))
    raise Unknown(ast.dump(node)[:60])


def _as_old_bytes(value: Any) -> Optional[bytes]:
    if value is None:
        return None
    if isinstance(value, int):
        return None
    if isinstance(value, (bytes, bytearray)):
        return bytes(value)
    if isinstance(value, str):
        try:
            return binascii.unhexlify(value)
        except (binascii.Error, ValueError):
            return None
    return None


def iter_rom_patch_calls(env: Optional[Dict[str, Any]] = None) -> List[Dict[str, Any]]:
    """Return every ``rom.patch(...)`` call site found in the repository.

    Each entry contains the source location plus, when statically resolvable,
    the bank, address, region length and new bytes.
    """
    env = env or {}
    sites: List[Dict[str, Any]] = []
    for root, dirs, files in os.walk(REPO_ROOT):
        dirs[:] = [d for d in dirs if d not in SKIP_DIRS]
        for name in files:
            if not name.endswith(".py"):
                continue
            path = os.path.join(root, name)
            rel = os.path.relpath(path, REPO_ROOT)
            try:
                tree = ast.parse(open(path, "rt", encoding="utf-8").read(), filename=rel)
            except (SyntaxError, UnicodeDecodeError):
                continue
            for node in ast.walk(tree):
                if not isinstance(node, ast.Call):
                    continue
                func = node.func
                if not (
                    isinstance(func, ast.Attribute)
                    and func.attr == "patch"
                    and isinstance(func.value, ast.Name)
                    and func.value.id in ("rom", "self")
                ):
                    continue
                if len(node.args) < 2:
                    continue

                old_node = node.args[2] if len(node.args) >= 3 else None
                new_node = node.args[3] if len(node.args) >= 4 else None
                for kw in node.keywords:
                    if kw.arg == "old":
                        old_node = kw.value
                    elif kw.arg == "new":
                        new_node = kw.value

                def try_eval(n: Optional[ast.AST]) -> Any:
                    if n is None:
                        return None
                    try:
                        return _eval(n, env)
                    except Unknown:
                        return _UNKNOWN
                    except Exception:
                        return _UNKNOWN

                bank = try_eval(node.args[0])
                addr = try_eval(node.args[1])
                old = _normalize_hex(try_eval(old_node))
                new = _normalize_hex(try_eval(new_node))

                site = {
                    "file": rel,
                    "line": node.lineno,
                    "bank": bank if isinstance(bank, int) else None,
                    "addr": addr if isinstance(addr, int) else None,
                    "old": old,
                    "new": new,
                }
                site["region_len"] = _region_len(site)
                sites.append(site)
    sites.sort(key=lambda s: (s["file"], s["line"]))
    return sites


class _Unknown:
    def __repr__(self) -> str:
        return "<unknown>"


_UNKNOWN = _Unknown()


def _normalize_hex(value: Any) -> Any:
    """Convert hex string literals (e.g. "FA4EDB") into raw bytes."""
    if isinstance(value, str):
        try:
            return binascii.unhexlify(value)
        except (binascii.Error, ValueError):
            return value
    return value


def _region_len(site: Dict[str, Any]) -> Optional[int]:
    old = site.get("old")
    new = site.get("new")
    addr = site.get("addr")
    if isinstance(old, int) and isinstance(addr, int):
        length = old - addr
        return length if length > 0 else None
    if isinstance(old, (bytes, bytearray)) and len(old):
        return len(old)
    if old is None and isinstance(new, (bytes, bytearray)) and len(new):
        return len(new)
    return None


def site_key(site: Dict[str, Any]) -> str:
    return "%s:%d" % (site["file"], site["line"])


FUZZY_ANCHOR = 8
FUZZY_MAX_CANDIDATES = 400


def best_fuzzy(fr_bank: bytes, signature: bytes, addr: int) -> Tuple[float, Optional[int]]:
    length = len(signature)
    candidates = {addr}
    step = max(1, length // 8)
    for w in range(0, max(1, length - FUZZY_ANCHOR + 1), step):
        anchor = signature[w:w + FUZZY_ANCHOR]
        if len(anchor) < FUZZY_ANCHOR or anchor.count(0) > FUZZY_ANCHOR // 2:
            continue
        start = 0
        while len(candidates) < FUZZY_MAX_CANDIDATES:
            p = fr_bank.find(anchor, start)
            if p < 0:
                break
            candidates.add(p - w)
            start = p + 1
    best_ratio = 0.0
    best_addr: Optional[int] = None
    for off in candidates:
        if off < 0 or off + length > len(fr_bank):
            continue
        same = sum(1 for i in range(length) if fr_bank[off + i] == signature[i])
        ratio = same / length
        if ratio > best_ratio:
            best_ratio = ratio
            best_addr = off
    return best_ratio, best_addr


def windowed_best(fr_bank: bytes, signature: bytes, addr: int, radius: int = 0x600) -> Tuple[float, Optional[int]]:
    """Best byte-similarity offset within a window around the English address."""
    length = len(signature)
    if length == 0:
        return 0.0, None
    lo = max(0, addr - radius)
    hi = min(len(fr_bank) - length, addr + radius)
    best_ratio = 0.0
    best_off: Optional[int] = None
    for off in range(lo, hi + 1):
        same = 0
        for i in range(length):
            if fr_bank[off + i] == signature[i]:
                same += 1
        ratio = same / length
        if ratio > best_ratio:
            best_ratio = ratio
            best_off = off
    return best_ratio, best_off
