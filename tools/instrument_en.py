"""Instrument an English randomizer run to record every ROM patch that executes.

Running the generator (not the full item placer) is enough to exercise all
patch code paths. Each ``rom.patch`` call is logged with its real bank,
address, overwritten length and call site, which lets the relocator resolve
statically-computed addresses and region lengths.

Output (intermediate, not committed):
    tools/data/en_patches.jsonl

Usage:
    python3 tools/instrument_en.py [--en <rom>] [--out <jsonl>]
"""
from __future__ import annotations

import argparse
import binascii
import json
import os
import random
import sys
from typing import Any, Dict, List, Optional

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import common  # noqa: E402

common.ensure_repo_on_path()

# Settings profiles. Mutually exclusive options live in separate runs; the
# union of all records maximises patch coverage.
PROFILES: Dict[str, List[str]] = {
    "base": [],
    "keysanity": [
        "dungeon_keys=keysanity",
        "nightmare_keys=keysanity",
        "dungeon_beaks=keysanity",
        "dungeon_maps=keysanity",
        "owlstatues=both",
    ],
    "shopsanity": ["shopsanity=important"],
    "entrances_madness": [
        "entranceshuffle=madness",
        "shufflejunk",
        "shuffleannoying",
        "shufflewater",
        "randomstartlocation",
        "dungeonshuffle",
    ],
    "hardmode_hero": ["hardmode=hero", "hpmode=inverted"],
    "hardmode_oracle": ["hardmode=oracle"],
    "hardmode_ohko": ["hardmode=ohko"],
    "bowwow": ["bowwow=always", "follower=fox"],
    "superweapons": ["superweapons", "quickswap=a", "textmode=none"],
    "enemies": ["enemies=overworld", "music=random"],
    "itempool_pain": ["itempool=pain"],
    "itempool_casual": ["itempool=casual"],
    "goal_seashells": ["goal=seashells"],
    "goal_open": ["goal=open"],
    "goal_bingo": ["goal=bingo", "boss=shuffle", "miniboss=shuffle"],
    "goal_maze": ["goal=maze"],
    "goal_specific": ["goal=specific", "goalcount=4"],
    "steal": ["steal=always"],
    "witch_off": ["witch"],
    "rooster_off": ["rooster"],
    "trade_off": ["tradequest"],
    "overworld_dungeondive": ["overworld=dungeondive"],
    "overworld_nodungeons": ["overworld=nodungeons"],
    "overworld_dungeonchain": ["overworld=dungeonchain"],
    "overworld_alttp": ["overworld=alttp"],
    "overworld_random": ["overworld=random"],
}

_records: Dict[str, Dict[str, Any]] = {}


def _region_len(old: Any, addr: int, new: Any) -> Optional[int]:
    try:
        if old is None:
            return len(binascii.unhexlify(new))
        if isinstance(old, int):
            length = old - addr
            return length if length > 0 else None
        if isinstance(old, str):
            return len(binascii.unhexlify(old))
        if isinstance(old, (bytes, bytearray)):
            return len(old)
    except (binascii.Error, TypeError, ValueError):
        return None
    return None


def install_hook() -> None:
    import rom  # type: ignore
    from codebytes import Code, iter_abs16_operands  # type: ignore

    original = rom.ROM.patch

    def logged_patch(self, bank_nr, addr, old, new, *, fill_nop=False):  # type: ignore
        frame = sys._getframe(1)
        filename = os.path.relpath(frame.f_code.co_filename, common.REPO_ROOT)
        if filename.startswith(".."):
            filename = frame.f_code.co_filename
        key = "%s:%d" % (filename, frame.f_lineno)
        length = _region_len(old, addr, new)

        operands = []
        if isinstance(new, Code):
            raw = binascii.unhexlify(new)
            operands = sorted({a for _, a in iter_abs16_operands(raw) if 0x0000 <= a < 0x8000})

        rec = _records.get(key)
        if rec is None:
            _records[key] = {
                "file": filename,
                "line": frame.f_lineno,
                "bank": bank_nr,
                "addr": addr,
                "region_len": length,
                "new_len": len(binascii.unhexlify(new)) if isinstance(new, str) else len(new or b""),
                "count": 1,
                "operands": operands,
            }
        else:
            rec["count"] += 1
            if length and (rec["region_len"] is None or length > rec["region_len"]):
                rec["region_len"] = length
            rec["operands"] = sorted(set(rec.get("operands", [])) | set(operands))
        return original(self, bank_nr, addr, old, new, fill_nop=fill_nop)

    rom.ROM.patch = logged_patch  # type: ignore


def run_profile(name: str, settings_strings: List[str], en_path: str, seed: bytes) -> None:
    import argparse as _argparse

    import generator  # type: ignore
    import logic.main  # type: ignore
    import worldSetup  # type: ignore
    from settings import Settings  # type: ignore

    settings = Settings()
    for s in settings_strings:
        settings.set(s)
    settings.validate()

    args = _argparse.Namespace(
        input_filename=en_path,
        output_filename=None,
        plan=None,
        pymod=None,
        doubletrouble=False,
        romdebugmode=False,
        log_directory=None,
        spoilerformat="none",
        spoiler_filename=None,
    )

    rnd = random.Random(seed + name.encode("ascii"))
    world_setup = worldSetup.WorldSetup()
    world_setup.randomize(settings, rnd)
    if settings.overworld == "random":
        import mapgen  # type: ignore
        world_setup.map = mapgen.generate(en_path, 8, 8)
        if world_setup.map is None:
            raise RuntimeError("mapgen failed")

    logic = logic.main.Logic(settings, world_setup=world_setup)
    for spot in logic.iteminfo_list:
        if spot.item is None:
            options = spot.getOptions()
            spot.item = options[0] if options else None

    generator.generateRom(args, settings, seed, logic, rnd=rnd)


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--en", default=None, help="English reference ROM")
    parser.add_argument("--out", default=os.path.join(common.DATA_DIR, "en_patches.jsonl"))
    parser.add_argument("--seed", default="4c414458522d4652", help="hex seed")
    args = parser.parse_args()

    en_path = args.en or common.find_rom("en")
    seed = binascii.unhexlify(args.seed)

    install_hook()

    ok = 0
    failed: List[str] = []
    for name, strings in PROFILES.items():
        try:
            run_profile(name, strings, en_path, seed)
            ok += 1
        except Exception as exc:  # noqa: BLE001 - best effort coverage
            failed.append("%s: %s" % (name, exc))

    os.makedirs(os.path.dirname(args.out), exist_ok=True)
    with open(args.out, "wt", encoding="utf-8") as f:
        for rec in sorted(_records.values(), key=lambda r: (r["file"], r["line"])):
            f.write(json.dumps(rec) + "\n")

    print("Profiles OK: %d/%d" % (ok, len(PROFILES)))
    if failed:
        print("Failed profiles:")
        for line in failed:
            print("  " + line)
    print("Recorded %d patch call sites -> %s" % (len(_records), args.out))


if __name__ == "__main__":
    main()
