"""Map assembler.const ROM labels and inline ``$XXXX`` references to French.

Only 36 of the 264 assembler.const labels are actual ROM addresses; the rest
are WRAM/HRAM and are version independent. ROM labels are relocated using the
piecewise-constant address shift observed in the patch map, then verified by
byte similarity at the predicted location.

Usage:
    python3 tools/symbols_fr.py [--out tools/data/symbols_fr.json]
"""
from __future__ import annotations

import argparse
import json
import os
import re
import sys
from typing import Any, Dict, List, Optional, Tuple

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import common  # noqa: E402

common.ensure_repo_on_path()

DELTA_WINDOW = 0x400
DELTA_NEIGHBOURS = 4
SIMILARITY_WINDOW = 24


def parse_labels() -> List[Tuple[str, int]]:
    labels: List[Tuple[str, int]] = []
    path = os.path.join(common.REPO_ROOT, "assembler.const")
    for line in open(path, "rt", encoding="utf-8"):
        if ":" not in line or line.strip().startswith(";"):
            continue
        value, _, key = line.strip().partition(":")
        key = key.split(";")[0].strip()
        try:
            labels.append((key, int(value, 16)))
        except ValueError:
            continue
    return labels


def is_wram(addr: int) -> bool:
    return 0xC000 <= addr < 0xE000 or 0xFF00 <= addr < 0x10000


def label_bank(name: str, addr: int) -> Optional[int]:
    match = re.search(r"_([0-9a-fA-F]{2})$", name)
    if match and addr >= 0x4000:
        return int(match.group(1), 16)
    if addr < 0x4000:
        return 0
    return None


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


def relocate_labels(en: bytes, fr: bytes, per_bank: Dict[int, List[Tuple[int, int]]]) -> Dict[str, Any]:
    result: Dict[str, Any] = {}
    for name, addr in parse_labels():
        if is_wram(addr):
            result[name] = {"en": addr, "fr": addr, "status": "fixed"}
            continue
        bank = label_bank(name, addr)
        entry: Dict[str, Any] = {"en": addr, "bank": bank, "fr": None, "status": "unknown"}
        if bank is None:
            result[name] = entry
            continue

        offset = addr & 0x3FFF
        en_bank = common.get_bank(en, bank)
        fr_bank = common.get_bank(fr, bank)
        signature = en_bank[offset:offset + SIMILARITY_WINDOW]
        ratio, found = common.best_fuzzy(fr_bank, signature, offset)
        if found is not None and ratio >= 0.70:
            entry["fr_offset"] = found
            entry["fr"] = found + (0x4000 if addr >= 0x4000 else 0)
            entry["similarity"] = round(ratio, 3)
            entry["status"] = "exact" if ratio == 1.0 else "predicted"
            result[name] = entry
            continue

        delta = predict_delta(per_bank, bank, offset)
        if delta is not None:
            predicted = offset + delta
            if 0 <= predicted + SIMILARITY_WINDOW <= len(fr_bank):
                same = sum(1 for i in range(SIMILARITY_WINDOW) if fr_bank[predicted + i] == signature[i])
                entry["fr_offset"] = predicted
                entry["fr"] = predicted + (0x4000 if addr >= 0x4000 else 0)
                entry["similarity"] = round(same / SIMILARITY_WINDOW, 3)
                entry["status"] = "predicted" if same >= SIMILARITY_WINDOW // 2 else "low_confidence"
        result[name] = entry
    return result


INLINE_REF = re.compile(r"\$([0-9A-Fa-f]{4})")


def collect_inline_refs() -> Dict[str, int]:
    refs: Dict[str, int] = {}
    for root, dirs, files in os.walk(common.REPO_ROOT):
        dirs[:] = [d for d in dirs if d not in common.SKIP_DIRS]
        for name in files:
            if not name.endswith(".py"):
                continue
            path = os.path.join(root, name)
            try:
                text = open(path, "rt", encoding="utf-8").read()
            except (UnicodeDecodeError, OSError):
                continue
            for match in INLINE_REF.finditer(text):
                ref = int(match.group(1), 16)
                key = "%04x" % ref
                refs[key] = refs.get(key, 0) + 1
    return refs


def build_symbols(en_path: str, fr_path: str, rommap: Dict[str, Any]) -> Dict[str, Any]:
    en = common.load_rom(en_path)
    fr = common.load_rom(fr_path)
    per_bank = build_delta_map(rommap)
    labels = relocate_labels(en, fr, per_bank)
    inline = collect_inline_refs()
    return {
        "labels": labels,
        "inline_refs": inline,
        "inline_refs_note": "Inline $XXXX references are bank-relative and must be mapped per patch site in phase C.",
    }


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--en", default=None)
    parser.add_argument("--fr", default=None)
    parser.add_argument("--rommap", default=os.path.join(common.REPO_ROOT, "rommap_fr.json"))
    parser.add_argument("--out", default=os.path.join(common.DATA_DIR, "symbols_fr.json"))
    args = parser.parse_args()

    en_path = args.en or common.find_rom("en")
    fr_path = args.fr or common.find_rom("fr")
    rommap = json.load(open(args.rommap, "rt", encoding="utf-8"))
    result = build_symbols(en_path, fr_path, rommap)

    os.makedirs(os.path.dirname(args.out), exist_ok=True)
    with open(args.out, "wt", encoding="utf-8") as f:
        json.dump(result, f, indent=1)
        f.write("\n")

    statuses: Dict[str, int] = {}
    for entry in result["labels"].values():
        statuses[entry["status"]] = statuses.get(entry["status"], 0) + 1
    print("Label relocation:")
    for status, count in sorted(statuses.items()):
        print("  %-14s %d" % (status, count))
    print("Distinct inline $XXXX refs: %d" % len(result["inline_refs"]))
    print("Wrote %s" % args.out)


if __name__ == "__main__":
    main()
