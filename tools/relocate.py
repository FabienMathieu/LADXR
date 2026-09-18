"""Relocate every ``rom.patch`` call site from the English ROM to the French ROM.

The signature used is the *pristine* English ROM bytes at the patched address,
over the exact region that is overwritten. This is more robust than the ``old``
value written in the source, which can be context dependent (patches applied on
top of earlier patches).

Usage:
    python3 tools/relocate.py [--en <rom>] [--fr <rom>]
                              [--instrumented tools/data/en_patches.jsonl]
                              [--out rommap_fr.json]
"""
from __future__ import annotations

import argparse
import binascii
import json
import os
import sys
from typing import Any, Dict, List, Optional, Tuple

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import common  # noqa: E402

CONTEXT = 8
MIN_SCORE = 2
FUZZY_THRESHOLD = 0.70

# LADXR uses these banks as scratch space and defines the addresses itself, so
# patch sites there must not be relocated by content.
SCRATCH_BANKS = {0x3E, 0x3F}
LOW_ENTROPY_MIN_LEN = 4


def load_instrumented(path: str) -> Dict[str, Dict[str, Any]]:
    records: Dict[str, Dict[str, Any]] = {}
    if not os.path.exists(path):
        return records
    with open(path, "rt", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            rec = json.loads(line)
            key = "%s:%d" % (rec["file"], rec["line"])
            records[key] = rec
    return records


def overlay(sites: List[Dict[str, Any]], instrumented: Dict[str, Dict[str, Any]]) -> None:
    """Fill bank/addr/region_len from instrumented records and mark execution."""
    for site in sites:
        site["executed"] = False
        rec = instrumented.get(common.site_key(site))
        if rec is None:
            continue
        site["executed"] = True
        if site.get("bank") is None and rec.get("bank") is not None:
            site["bank"] = rec["bank"]
        if site.get("addr") is None and rec.get("addr") is not None:
            site["addr"] = rec["addr"]
        if site.get("region_len") is None and rec.get("region_len"):
            site["region_len"] = rec["region_len"]


def context_score(en_bank: bytes, en_addr: int, fr_bank: bytes, fr_addr: int, length: int) -> int:
    """Count matching surrounding bytes between the two locations."""
    score = 0
    for delta in range(1, CONTEXT + 1):
        if en_addr - delta < 0 or fr_addr - delta < 0:
            break
        if en_bank[en_addr - delta] == fr_bank[fr_addr - delta]:
            score += 1
    for delta in range(length, length + CONTEXT):
        if en_addr + delta >= len(en_bank) or fr_addr + delta >= len(fr_bank):
            break
        if en_bank[en_addr + delta] == fr_bank[fr_addr + delta]:
            score += 1
    return score


def relocate_site(en: bytes, fr: bytes, site: Dict[str, Any], identical: List[int]) -> Dict[str, Any]:
    bank = site.get("bank")
    addr = site.get("addr")
    length = site.get("region_len")
    result = {
        "file": site["file"],
        "line": site["line"],
        "bank": bank,
        "en_addr": addr,
        "region_len": length,
        "fr_addr": None,
        "status": "unknown",
        "candidates": 0,
        "executed": site.get("executed", False),
    }
    if bank is None or addr is None or not length:
        return result
    if bank in identical or bank in SCRATCH_BANKS:
        result["fr_addr"] = addr
        result["status"] = "identical"
        return result

    en_bank = common.get_bank(en, bank)
    fr_bank = common.get_bank(fr, bank)
    if addr + length > len(en_bank):
        return result
    signature = en_bank[addr:addr + length]
    if not signature:
        return result

    # Low-entropy (e.g. all-zero) regions cannot be located by content; they
    # are LADXR-injected data or fixed vectors, so keep the address.
    if length >= LOW_ENTROPY_MIN_LEN and len(set(signature)) <= 1:
        result["fr_addr"] = addr
        result["status"] = "low_entropy"
        result["resolved_by"] = "identity_heuristic"
        return result

    matches: List[int] = []
    start = 0
    while True:
        loc = fr_bank.find(signature, start)
        if loc < 0:
            break
        matches.append(loc)
        start = loc + 1

    result["candidates"] = len(matches)
    if len(matches) == 1:
        result["fr_addr"] = matches[0]
        result["status"] = "exact"
        return result
    if not matches:
        ratio, fuzzy_addr = common.best_fuzzy(fr_bank, signature, addr)
        if fuzzy_addr is not None and ratio >= FUZZY_THRESHOLD:
            result["fr_addr"] = fuzzy_addr
            result["status"] = "fuzzy"
            result["similarity"] = round(ratio, 3)
            return result
        ratio2, windowed_addr = common.windowed_best(fr_bank, signature[:64], addr, radius=0x800)
        if windowed_addr is not None and ratio2 >= 0.75:
            result["fr_addr"] = windowed_addr
            result["status"] = "windowed"
            result["similarity"] = round(ratio2, 3)
            return result
        # Short signatures whose bytes mostly match at the same address: the
        # location is unchanged, only a nearby operand differs.
        same = sum(1 for i in range(length) if fr_bank[addr + i] == signature[i]) / length
        if same >= 0.5:
            result["fr_addr"] = addr
            result["status"] = "same_addr"
            result["similarity"] = round(same, 3)
            return result
        result["status"] = "not_found"
        result["similarity"] = round(max(ratio, ratio2, same), 3)
        return result

    scored = sorted(
        ((context_score(en_bank, addr, fr_bank, m, length), m) for m in matches),
        reverse=True,
    )
    best_score, best_addr = scored[0]
    second_score = scored[1][0] if len(scored) > 1 else -1
    if best_score >= MIN_SCORE and best_score > second_score:
        result["fr_addr"] = best_addr
        result["status"] = "exact"
        result["resolved_by"] = "context"
        return result
    result["status"] = "ambiguous"
    result["candidate_addrs"] = [m for _, m in scored]
    return result


def _ondemand_translate(en: bytes, fr: bytes, bank: int, value: int) -> Optional[int]:
    """Translate a single ROM target by signature search, without a prebuilt map."""
    if value < 0x4000:
        target_bank = 0
    elif value < 0x8000:
        target_bank = bank
    else:
        return None
    offset = value & 0x3FFF
    en_bank = common.get_bank(en, target_bank)
    fr_bank = common.get_bank(fr, target_bank)
    sig_len = min(12, len(en_bank) - offset)
    if sig_len < 4:
        return None
    signature = en_bank[offset:offset + sig_len]
    if len(set(signature)) <= 1:
        return value
    loc = fr_bank.find(signature)
    if loc >= 0 and fr_bank.count(signature) == 1:
        return loc if target_bank == 0 else loc | 0x4000
    ratio, found = common.best_fuzzy(fr_bank, signature, offset)
    if found is not None and ratio >= 0.75:
        return found if target_bank == 0 else found | 0x4000
    ratio, found = common.windowed_best(fr_bank, signature, offset)
    if found is not None and ratio >= 0.66:
        return found if target_bank == 0 else found | 0x4000
    return None


def _resolve_by_translated_old(
    results: List[Dict[str, Any]],
    sites: List[Dict[str, Any]],
    en: bytes,
    fr: bytes,
    code_map: Dict[Tuple[int, int], int],
) -> None:
    """Resolve remaining sites by translating the operands of their signature.

    The pristine English bytes at the site are translated two ways: as
    instructions (absolute operands) and as 16-bit pointer words. If the
    translated signature appears uniquely in the French bank, the site is
    mapped.
    """
    from codebytes import iter_abs16_operands

    for result, site in zip(results, sites):
        if result["status"] not in ("not_found", "unknown"):
            continue
        bank = result["bank"]
        addr = result["en_addr"]
        length = result["region_len"]
        if bank is None or addr is None or not length:
            continue
        en_bank = common.get_bank(en, bank)
        fr_bank = common.get_bank(fr, bank)
        if addr + length > len(en_bank):
            continue
        signature = en_bank[addr:addr + length]

        candidates: List[bytes] = []

        # (a) instruction operands
        code_sig = bytearray(signature)
        changed = False
        for index, operand in iter_abs16_operands(signature):
            if operand < 0x4000:
                target_bank = 0
            elif operand < 0x8000:
                target_bank = bank
            else:
                continue
            translated = code_map.get((target_bank, operand))
            if translated is None:
                translated = _ondemand_translate(en, fr, bank, operand)
            if translated is not None:
                code_sig[index + 1] = translated & 0xFF
                code_sig[index + 2] = (translated >> 8) & 0xFF
                changed = True
        if changed:
            candidates.append(bytes(code_sig))

        # (b) 16-bit pointer words
        if length % 2 == 0:
            word_sig = bytearray(signature)
            changed = False
            for i in range(0, length, 2):
                value = signature[i] | (signature[i + 1] << 8)
                if value < 0x4000:
                    target_bank = 0
                elif value < 0x8000:
                    target_bank = bank
                else:
                    continue
                translated = code_map.get((target_bank, value))
                if translated is None:
                    translated = _ondemand_translate(en, fr, bank, value)
                if translated is not None:
                    word_sig[i] = translated & 0xFF
                    word_sig[i + 1] = (translated >> 8) & 0xFF
                    changed = True
            if changed:
                candidates.append(bytes(word_sig))

        for candidate in candidates:
            loc = fr_bank.find(candidate)
            if loc < 0:
                continue
            if fr_bank.count(candidate) == 1:
                result["fr_addr"] = loc
                result["status"] = "translated_old"
                result["resolved_by"] = "translated_signature"
                break
            # Disambiguate multiple occurrences by surrounding context.
            locations = []
            start = 0
            while True:
                found = fr_bank.find(candidate, start)
                if found < 0:
                    break
                locations.append(found)
                start = found + 1
            scored = sorted(
                ((context_score(en_bank, addr, fr_bank, found, length), found) for found in locations),
                reverse=True,
            )
            best_score, best_loc = scored[0]
            second = scored[1][0] if len(scored) > 1 else -1
            if best_score >= 4 and best_score > second:
                result["fr_addr"] = best_loc
                result["status"] = "translated_old"
                result["resolved_by"] = "translated_signature+context"
                break


def build_rommap(en_path: str, fr_path: str, instrumented_path: str) -> Dict[str, Any]:
    en = common.load_rom(en_path)
    fr = common.load_rom(fr_path)
    identical = common.identical_banks(en, fr)

    sites = common.iter_rom_patch_calls()
    instrumented = load_instrumented(instrumented_path)
    overlay(sites, instrumented)

    results = [relocate_site(en, fr, s, identical) for s in sites]

    # Ordering tie-break: within a bank, relocated addresses should mostly be
    # monotonic with respect to the English addresses. Use it to resolve
    # remaining ambiguous entries when a unique monotonic assignment exists.
    _monotonic_resolve(results)
    _delta_predict(results, en, fr)

    counts: Dict[str, int] = {}
    for r in results:
        counts[r["status"]] = counts.get(r["status"], 0) + 1

    import code_addr_fr  # noqa: E402
    import symbols_fr  # noqa: E402
    import tables_fr  # noqa: E402

    rommap: Dict[str, Any] = {
        "rom": {
            "en_sha1": common.sha1_file(en_path),
            "fr_sha1": common.sha1_file(fr_path),
        },
        "identical_banks": ["%02x" % b for b in identical],
        "stats": counts,
        "patches": results,
    }

    # Two-pass: build the code address map, then use it to resolve remaining
    # sites whose signature contains translatable operands/pointers.
    rommap["code_addrs"] = code_addr_fr.build_code_addrs(en_path, fr_path, rommap)
    code_map: Dict[Tuple[int, int], int] = {}
    for key, entry in rommap["code_addrs"]["addrs"].items():
        if entry.get("fr") is not None:
            bank_str, addr_str = key.split(":")
            code_map[(int(bank_str, 16), int(addr_str, 16))] = entry["fr"]
    _resolve_by_translated_old(results, sites, en, fr, code_map)

    counts = {}
    for r in results:
        counts[r["status"]] = counts.get(r["status"], 0) + 1
    rommap["stats"] = counts

    rommap["tables"] = tables_fr.discover_tables(en_path, fr_path)
    rommap["symbols"] = symbols_fr.build_symbols(en_path, fr_path, rommap)
    rommap["code_addrs"] = code_addr_fr.build_code_addrs(en_path, fr_path, rommap)
    return rommap


def _monotonic_resolve(results: List[Dict[str, Any]]) -> None:
    by_bank: Dict[int, List[Dict[str, Any]]] = {}
    for r in results:
        if r["status"] == "ambiguous" and r.get("candidate_addrs"):
            by_bank.setdefault(r["bank"], []).append(r)
    for bank, items in by_bank.items():
        items.sort(key=lambda r: r["en_addr"])
        # Greedy monotonic assignment: pick the smallest candidate that is
        # greater than the previously assigned French address.
        last = -1
        ok = True
        for r in items:
            cands = sorted(r["candidate_addrs"])
            chosen = next((c for c in cands if c > last), None)
            if chosen is None:
                ok = False
                break
            r["fr_addr"] = chosen
            last = chosen
        if ok:
            for r in items:
                r["status"] = "exact"
                r["resolved_by"] = "monotonic"


DELTA_WINDOW = 0x400
DELTA_NEIGHBOURS = 4
DELTA_MIN_SIMILARITY = 0.60


def _delta_predict(results: List[Dict[str, Any]], en: bytes, fr: bytes) -> None:
    """Predict unresolved addresses using the piecewise-constant address shift.

    In the French revision, code was moved in blocks; the delta
    ``fr_addr - en_addr`` is constant over each block. We interpolate it from
    already-mapped neighbours and verify the prediction by byte similarity.
    """
    per_bank: Dict[int, List[Tuple[int, int]]] = {}
    for r in results:
        if r["status"] in ("exact", "identical", "low_entropy", "translated_old") and r["fr_addr"] is not None:
            per_bank.setdefault(r["bank"], []).append((r["en_addr"], r["fr_addr"] - r["en_addr"]))
    for bank in per_bank:
        per_bank[bank].sort()

    for r in results:
        if r["status"] not in ("not_found", "unknown"):
            continue
        bank = r["bank"]
        addr = r["en_addr"]
        length = r["region_len"]
        if bank is None or addr is None or not length or bank not in per_bank:
            continue
        neighbours = sorted(
            ((abs(a - addr), d) for a, d in per_bank[bank] if abs(a - addr) <= DELTA_WINDOW)
        )[:DELTA_NEIGHBOURS]
        if not neighbours:
            continue
        deltas = [d for _, d in neighbours]
        delta = deltas[0] if len(set(deltas)) == 1 else None
        if delta is None:
            # Majority vote among the nearest neighbours.
            counts: Dict[int, int] = {}
            for d in deltas:
                counts[d] = counts.get(d, 0) + 1
            best, count = max(counts.items(), key=lambda kv: kv[1])
            if count < 2:
                continue
            delta = best

        predicted = addr + delta
        en_bank = common.get_bank(en, bank)
        fr_bank = common.get_bank(fr, bank)
        if predicted < 0 or predicted + length > len(fr_bank) or addr + length > len(en_bank):
            continue
        signature = en_bank[addr:addr + length]
        same = sum(1 for i in range(length) if fr_bank[predicted + i] == signature[i])
        ratio = same / length
        if ratio >= DELTA_MIN_SIMILARITY:
            r["fr_addr"] = predicted
            r["status"] = "predicted"
            r["resolved_by"] = "delta"
            r["similarity"] = round(ratio, 3)


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--en", default=None, help="English reference ROM")
    parser.add_argument("--fr", default=None, help="French ROM")
    parser.add_argument(
        "--instrumented",
        default=os.path.join(common.DATA_DIR, "en_patches.jsonl"),
        help="Instrumented English patch log",
    )
    parser.add_argument("--out", default=os.path.join(common.REPO_ROOT, "rommap_fr.json"))
    args = parser.parse_args()

    en_path = args.en or common.find_rom("en")
    fr_path = args.fr or common.find_rom("fr")

    rommap = build_rommap(en_path, fr_path, args.instrumented)
    with open(args.out, "wt", encoding="utf-8") as f:
        json.dump(rommap, f, indent=1)
        f.write("\n")

    manual_path = os.path.join(common.DATA_DIR, "manual_queue.jsonl")
    with open(manual_path, "wt", encoding="utf-8") as f:
        for r in rommap["patches"]:
            if r["status"] in ("ambiguous", "not_found", "unknown"):
                f.write(json.dumps(r) + "\n")

    review_path = os.path.join(common.DATA_DIR, "review_queue.jsonl")
    with open(review_path, "wt", encoding="utf-8") as f:
        for r in rommap["patches"]:
            if r["status"] in ("fuzzy", "predicted", "windowed", "same_addr"):
                f.write(json.dumps(r) + "\n")

    total = len(rommap["patches"])
    stats = rommap["stats"]
    high = stats.get("exact", 0) + stats.get("identical", 0) + stats.get("low_entropy", 0) + stats.get("translated_old", 0)
    probable = stats.get("predicted", 0) + stats.get("windowed", 0)
    fuzzy = stats.get("fuzzy", 0) + stats.get("same_addr", 0)
    unresolved = stats.get("not_found", 0) + stats.get("unknown", 0) + stats.get("ambiguous", 0)
    print("Sites: %d" % total)
    for status, count in sorted(stats.items()):
        print("  %-10s %d" % (status, count))
    print("High confidence (exact+identical+low_entropy): %d (%.1f%%)" % (high, 100.0 * high / total))
    print("Probable (predicted+windowed):     %d (%.1f%%)" % (probable, 100.0 * probable / total))
    print("Fuzzy (needs review):             %d (%.1f%%)" % (fuzzy, 100.0 * fuzzy / total))
    print("Resolved total:                   %d (%.1f%%)" % (high + probable + fuzzy, 100.0 * (high + probable + fuzzy) / total))
    print("Unresolved:                       %d" % unresolved)
    print("Wrote %s" % args.out)
    print("Manual queue: %s" % manual_path)
    print("Review queue: %s" % review_path)

    tables = rommap.get("tables", {}).get("validation", {})
    ok_tables = sum(1 for v in tables.values() if v["status"] == "ok")
    print("Tables validated: %d/%d" % (ok_tables, len(tables)))
    labels = rommap.get("symbols", {}).get("labels", {})
    bad_labels = sum(1 for v in labels.values() if v["status"] in ("unknown", "low_confidence"))
    print("Labels relocated: %d/%d" % (len(labels) - bad_labels, len(labels)))


if __name__ == "__main__":
    main()
