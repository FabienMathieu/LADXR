"""Build a French translation map for ROM addresses referenced by injected code.

Injected assembly contains absolute 16-bit operands (``call $5B9F``,
``jp nz, $7B4B``, ``ld hl, $763B`` ...). These refer to functions and data in
the bank of the patch site and must be translated for the French ROM.

The map is built from:
* the relocated patch sites (exact matches),
* the relocated ``assembler.const`` labels,
* a byte-signature search of the English bytes at the referenced address,
* the piecewise-constant address shift as a last resort.

Usage:
    python3 tools/code_addr_fr.py [--out tools/data/code_addr_fr.json]
"""
from __future__ import annotations

import argparse
import ast
import glob
import json
import os
import re
import sys
from typing import Any, Dict, List, Optional, Set, Tuple

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import common  # noqa: E402
import symbols_fr  # noqa: E402

common.ensure_repo_on_path()

REF = re.compile(r"\$([0-9A-Fa-f]{4})")
DELTA_WINDOW = 0x400
DELTA_NEIGHBOURS = 4
SIGNATURE_LEN = 12
FUZZY_MIN = 0.75


def is_rom(addr: int) -> bool:
    return 0x0000 <= addr < 0x8000


def target_bank(site_bank: int, value: int) -> int:
    """Addresses below 0x4000 always map to the fixed bank 0."""
    return 0 if value < 0x4000 else site_bank


def collect_rom_refs() -> Set[Tuple[int, int]]:
    refs: Set[Tuple[int, int]] = set()
    for root, dirs, files in os.walk(common.REPO_ROOT):
        dirs[:] = [d for d in dirs if d not in common.SKIP_DIRS]
        for name in files:
            if not name.endswith(".py"):
                continue
            path = os.path.join(root, name)
            try:
                tree = ast.parse(open(path, "rt", encoding="utf-8").read())
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
                if len(node.args) < 2 or not isinstance(node.args[0], ast.Constant):
                    continue
                bank = node.args[0].value
                if not isinstance(bank, int):
                    continue
                for arg in node.args[2:5]:
                    if (
                        isinstance(arg, ast.Call)
                        and getattr(arg.func, "id", None) == "ASM"
                        and arg.args
                        and isinstance(arg.args[0], ast.Constant)
                        and isinstance(arg.args[0].value, str)
                    ):
                        for match in REF.finditer(arg.args[0].value):
                            value = int(match.group(1), 16)
                            if is_rom(value):
                                refs.add((target_bank(bank, value), value))
    return refs


def build_delta_map(rommap: Dict[str, Any]) -> Dict[int, List[Tuple[int, int]]]:
    per_bank: Dict[int, List[Tuple[int, int]]] = {}
    for r in rommap.get("patches", []):
        if r["status"] in ("exact", "identical", "low_entropy", "translated_old") and r.get("fr_addr") is not None:
            per_bank.setdefault(r["bank"], []).append((r["en_addr"], r["fr_addr"] - r["en_addr"]))
    for bank in per_bank:
        per_bank[bank].sort()
    return per_bank


def predict_delta(per_bank: Dict[int, List[Tuple[int, int]]], bank: int, addr: int) -> Optional[int]:
    entries = per_bank.get(bank)
    if not entries:
        return None
    nearby = sorted((abs(a - addr), d) for a, d in entries if abs(a - addr) <= DELTA_WINDOW)[:DELTA_NEIGHBOURS]
    if not nearby:
        return None
    deltas = [d for _, d in nearby]
    if len(set(deltas)) == 1:
        return deltas[0]
    counts: Dict[int, int] = {}
    for d in deltas:
        counts[d] = counts.get(d, 0) + 1
    best, count = max(counts.items(), key=lambda kv: kv[1])
    return best if count >= 2 else None


def to_abs(bank: int, offset: int) -> int:
    return offset if bank == 0 else (offset | 0x4000)


def translate_target(
    en: bytes,
    fr: bytes,
    patch_map: Dict[Tuple[int, int], int],
    label_map: Dict[Tuple[int, int], int],
    identical: Set[int],
    per_bank: Dict[int, List[Tuple[int, int]]],
    bank: int,
    addr: int,
) -> Tuple[Optional[int], str]:
    if (bank, addr) in patch_map:
        return patch_map[(bank, addr)], "patch_map"
    if (bank, addr) in label_map:
        return label_map[(bank, addr)], "label"
    if bank in identical or bank in common_scratch():
        return addr, "identical"

    offset = addr & 0x3FFF
    en_bank = common.get_bank(en, bank)
    fr_bank = common.get_bank(fr, bank)
    sig_len = min(SIGNATURE_LEN, len(en_bank) - offset)
    if sig_len < 4:
        return None, "out_of_range"
    signature = en_bank[offset:offset + sig_len]

    # Free space used by LADXR-injected code: same address in both ROMs.
    if len(set(signature)) <= 1:
        return addr, "free_space"

    loc = fr_bank.find(signature)
    if loc >= 0 and fr_bank.count(signature) == 1:
        return to_abs(bank, loc), "exact"

    ratio, found = common.best_fuzzy(fr_bank, signature, offset)
    if found is not None and ratio >= FUZZY_MIN:
        return to_abs(bank, found), "fuzzy"

    ratio, found = common.windowed_best(fr_bank, signature, offset)
    if found is not None and ratio >= 0.66:
        return to_abs(bank, found), "windowed"

    delta = predict_delta(per_bank, bank, offset)
    if delta is not None:
        predicted = offset + delta
        if 0 <= predicted + sig_len <= len(fr_bank):
            same = sum(1 for i in range(sig_len) if fr_bank[predicted + i] == signature[i])
            if same / sig_len >= 0.60:
                return to_abs(bank, predicted), "delta"
    return None, "unresolved"


def common_scratch() -> Set[int]:
    return {0x3E, 0x3F}


def collect_instrumented_operands(path: str) -> Set[Tuple[int, int]]:
    refs: Set[Tuple[int, int]] = set()
    if not os.path.exists(path):
        return refs
    with open(path, "rt", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            rec = json.loads(line)
            bank = rec.get("bank")
            if bank is None:
                continue
            for operand in rec.get("operands", []):
                if is_rom(operand):
                    refs.add((target_bank(bank, operand), operand))
    return refs


def build_code_addrs(en_path: str, fr_path: str, rommap: Dict[str, Any]) -> Dict[str, Any]:
    en = common.load_rom(en_path)
    fr = common.load_rom(fr_path)
    patch_map = {
        (r["bank"], r["en_addr"]): r["fr_addr"]
        for r in rommap.get("patches", [])
        if r.get("fr_addr") is not None and r.get("bank") is not None and r.get("en_addr") is not None
    }
    identical = {int(b, 16) for b in rommap.get("identical_banks", [])}
    per_bank = build_delta_map(rommap)

    label_map: Dict[Tuple[int, int], int] = {}
    for name, entry in rommap.get("symbols", {}).get("labels", {}).items():
        fr_addr = entry.get("fr")
        bank = entry.get("bank")
        if fr_addr is not None and bank is not None and fr_addr != entry.get("en"):
            label_map[(bank, entry["en"])] = fr_addr

    targets: Set[Tuple[int, int]] = set(collect_rom_refs())
    targets |= collect_instrumented_operands(os.path.join(common.DATA_DIR, "en_patches.jsonl"))
    for name, addr in symbols_fr.parse_labels():
        if symbols_fr.is_wram(addr):
            continue
        bank = symbols_fr.label_bank(name, addr)
        if bank is not None:
            targets.add((bank, addr))

    result: Dict[str, Any] = {}
    statuses: Dict[str, int] = {}
    for bank, addr in sorted(targets):
        translated, status = translate_target(en, fr, patch_map, label_map, identical, per_bank, bank, addr)
        key = "%02x:%04x" % (bank, addr)
        result[key] = {"fr": translated, "status": status}
        statuses[status] = statuses.get(status, 0) + 1
    return {"addrs": result, "stats": statuses}


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--en", default=None)
    parser.add_argument("--fr", default=None)
    parser.add_argument("--rommap", default=os.path.join(common.REPO_ROOT, "rommap_fr.json"))
    parser.add_argument("--out", default=os.path.join(common.DATA_DIR, "code_addr_fr.json"))
    args = parser.parse_args()

    en_path = args.en or common.find_rom("en")
    fr_path = args.fr or common.find_rom("fr")
    rommap = json.load(open(args.rommap, "rt", encoding="utf-8"))
    result = build_code_addrs(en_path, fr_path, rommap)

    os.makedirs(os.path.dirname(args.out), exist_ok=True)
    with open(args.out, "wt", encoding="utf-8") as f:
        json.dump(result, f, indent=1)
        f.write("\n")

    print("Code address targets: %d" % len(result["addrs"]))
    for status, count in sorted(result["stats"].items()):
        print("  %-12s %d" % (status, count))
    print("Wrote %s" % args.out)


if __name__ == "__main__":
    main()
