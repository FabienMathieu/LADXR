"""Relocate the ROM pointer tables (romTables.py) for the French ROM.

Only a few tables actually need a French-specific configuration:

* Texts      : the text bank table lives at 0x1C:0x841 instead of 0x1C:0x741.
* Room tables: the ``alt_pointers`` (stored in bank 0x00) moved by 5 bytes.

Everything else is validated against the French ROM with the English config.

Usage:
    python3 tools/tables_fr.py [--en <rom>] [--fr <rom>] [--out tools/data/tables_fr.json]
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

# English table definitions (mirrors romTables.py) used as the baseline.
EN_TABLES: Dict[str, Dict[str, Any]] = {
    "texts": {"count": 0x2B0, "pointers_addr": 0x001, "pointers_bank": 0x1C, "banks_addr": 0x741, "banks_bank": 0x1C},
    "entities": {"count": 0x320, "pointers_addr": 0x000, "pointers_bank": 0x16, "data_bank": 0x16},
    "rooms_overworld_top": {
        "count": 0x080, "pointers_addr": 0x000, "pointers_bank": 0x09, "data_bank": 0x09,
        "alt_pointers": {"Alt06": (0x00, 0x31FD), "Alt0E": (0x00, 0x31CD), "Alt1B": (0x00, 0x320D),
                          "Alt2B": (0x00, 0x321D), "Alt79": (0x00, 0x31ED)},
    },
    "rooms_overworld_bottom": {
        "count": 0x080, "pointers_addr": 0x100, "pointers_bank": 0x09, "data_bank": 0x1A,
        "alt_pointers": {"Alt8C": (0x00, 0x31DD)},
    },
    "rooms_indoor_a": {
        "count": 0x100, "pointers_addr": 0x000, "pointers_bank": 0x0A, "data_bank": 0x0A,
        "alt_pointers": {"Alt1F5": (0x00, 0x31A1)},
    },
    "rooms_indoor_b": {"count": 0x0FF, "pointers_addr": 0x000, "pointers_bank": 0x0B, "data_bank": 0x0B},
    "rooms_color_dungeon": {"count": 0x016, "pointers_addr": 0x3B77, "pointers_bank": 0x0A, "data_bank": 0x0A,
                            "expand_to_end_of_bank": True},
    "background_tiles": {"count": 0x26, "pointers_addr": 0x052B, "pointers_bank": 0x20, "data_bank": 0x08,
                         "expand_to_end_of_bank": True},
    "background_attributes": {"count": 0x26, "pointers_addr": 0x1C4B, "pointers_bank": 0x24, "data_bank": 0x24,
                              "expand_to_end_of_bank": True},
    "overworld_sprite_data": {"count": 0x100, "pointers_addr": 0x30D3, "pointers_bank": 0x20, "data_bank": 0x20,
                              "data_addr": 0x33F3, "data_size": 4, "claim_storage_gaps": True},
    "indoor_sprite_data": {"count": 0x220, "pointers_addr": 0x31D3, "pointers_bank": 0x20, "data_bank": 0x20,
                           "data_addr": 0x363B, "data_size": 4, "claim_storage_gaps": True},
}

# The French text bank table was found by validating every text pointer.
FR_TEXTS_BANKS_ADDR = 0x841


def rd16(rom: bytes, bank: int, addr: int) -> int:
    data = common.get_bank(rom, bank)
    return data[addr] | (data[addr + 1] << 8)


def room_data(rom: bytes, bank: int, pointer: int) -> bytes:
    data = common.get_bank(rom, bank)
    off = pointer & 0x3FFF
    p = off + 2
    while data[p] != 0xFE:
        obj_type = data[p] & 0xF0
        if obj_type == 0xE0:
            p += 5
        elif obj_type in (0xC0, 0x80):
            p += 3
        else:
            p += 2
    return data[off:p + 1]


def relocate_alt_pointer(en: bytes, fr: bytes, ptr_bank: int, ptr_addr: int, data_bank: int) -> Dict[str, Any]:
    """Relocate one alt pointer (location + value) from EN to FR."""
    en_value = rd16(en, ptr_bank, ptr_addr)
    try:
        data = room_data(en, data_bank, en_value)
    except IndexError:
        return {"en": [ptr_bank, ptr_addr], "status": "not_found"}
    fr_data_bank = common.get_bank(fr, data_bank)
    offset = fr_data_bank.find(data)
    if offset < 0:
        return {"en": [ptr_bank, ptr_addr], "status": "not_found"}
    fr_value = offset | 0x4000

    # Locate where the pointer is stored in the French ROM.
    pattern = bytes([fr_value & 0xFF, fr_value >> 8])
    fr_ptr_bank = common.get_bank(fr, ptr_bank)
    locations = [m.start() for m in re.finditer(re.escape(pattern), fr_ptr_bank)]
    fr_addr: Optional[int] = None
    if len(locations) == 1:
        fr_addr = locations[0]
    elif locations:
        # Disambiguate using the English context around the pointer.
        en_ctx = common.get_bank(en, ptr_bank)[max(0, ptr_addr - 6):ptr_addr + 8]
        best = (-1, None)
        for loc in locations:
            ctx = fr_ptr_bank[max(0, loc - 6):loc + 8]
            score = sum(1 for a, b in zip(en_ctx, ctx) if a == b)
            if score > best[0]:
                best = (score, loc)
        fr_addr = best[1]
    return {
        "en": [ptr_bank, ptr_addr],
        "en_value": en_value,
        "fr_value": fr_value,
        "fr": [ptr_bank, fr_addr] if fr_addr is not None else None,
        "status": "exact" if fr_addr is not None else "value_only",
    }


def build_fr_config(en: bytes, fr: bytes) -> Dict[str, Any]:
    config: Dict[str, Any] = {}
    notes: Dict[str, Any] = {}

    for name, info in EN_TABLES.items():
        fr_info = dict(info)
        if name == "texts":
            fr_info["banks_addr"] = FR_TEXTS_BANKS_ADDR
            notes["texts"] = {"banks_addr": {"en": info["banks_addr"], "fr": FR_TEXTS_BANKS_ADDR}}
        if "alt_pointers" in info:
            relocated: Dict[str, Any] = {}
            alt_notes: Dict[str, Any] = {}
            for key, (pb, pa) in info["alt_pointers"].items():
                result = relocate_alt_pointer(en, fr, pb, pa, info["data_bank"])
                if result["status"] == "exact":
                    relocated[key] = [result["fr"][0], result["fr"][1]]
                alt_notes[key] = result
            fr_info["alt_pointers"] = relocated
            notes.setdefault(name, {})["alt_pointers"] = alt_notes
        config[name] = fr_info

    return {"config": config, "notes": notes}


def validate(fr_path: str, config: Dict[str, Any]) -> Dict[str, Any]:
    """Construct every table on the French ROM using the discovered config."""
    import romTables  # type: ignore
    from pointerTable import PointerTable  # type: ignore

    rom = romTables.ROM(open(fr_path, "rb"))
    results: Dict[str, Any] = {}

    class RoomsTable(PointerTable):
        HEADER = 2

        def _readData(self, rom, bank_nr, pointer):  # type: ignore
            bank = rom.banks[bank_nr]
            start = pointer
            pointer += self.HEADER
            while bank[pointer] != 0xFE:
                obj_type = bank[pointer] & 0xF0
                if obj_type == 0xE0:
                    pointer += 5
                elif obj_type in (0xC0, 0x80):
                    pointer += 3
                else:
                    pointer += 2
            pointer += 1
            self._addStorage(bank_nr, start, pointer)
            return bank[start:pointer]

    class TextTable(PointerTable):
        END_OF_DATA = (0xFE, 0xFF)

    for name, info in config.items():
        try:
            if name.startswith("rooms_"):
                table = RoomsTable(rom, info)
            elif name == "texts":
                table = TextTable(rom, info)
            elif name == "background_tiles":
                table = romTables.BackgroundTilesTable(rom)
            elif name == "background_attributes":
                table = romTables.BackgroundAttributeTable(rom)
            elif name == "entities":
                table = romTables.Entities(rom)
            elif name == "overworld_sprite_data":
                table = romTables.OverworldRoomSpriteData(rom)
            elif name == "indoor_sprite_data":
                table = romTables.IndoorRoomSpriteData(rom)
            else:
                table = PointerTable(rom, info)
            results[name] = {"status": "ok", "count": len(table)}
        except Exception as exc:  # noqa: BLE001
            results[name] = {"status": "failed", "error": "%s: %s" % (type(exc).__name__, exc)}
    return results


def discover_tables(en_path: str, fr_path: str) -> Dict[str, Any]:
    en = common.load_rom(en_path)
    fr = common.load_rom(fr_path)
    built = build_fr_config(en, fr)
    validation = validate(fr_path, built["config"])
    return {
        "config": built["config"],
        "notes": built["notes"],
        "validation": validation,
    }


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--en", default=None)
    parser.add_argument("--fr", default=None)
    parser.add_argument("--out", default=os.path.join(common.DATA_DIR, "tables_fr.json"))
    args = parser.parse_args()

    en_path = args.en or common.find_rom("en")
    fr_path = args.fr or common.find_rom("fr")
    result = discover_tables(en_path, fr_path)

    os.makedirs(os.path.dirname(args.out), exist_ok=True)
    with open(args.out, "wt", encoding="utf-8") as f:
        json.dump(result, f, indent=1)
        f.write("\n")

    print("Table validation on French ROM:")
    for name, status in result["validation"].items():
        line = "  %-24s %s" % (name, status["status"])
        if status["status"] == "ok":
            line += " (count=%d)" % status["count"]
        else:
            line += " - %s" % status.get("error")
        print(line)
    print("Wrote %s" % args.out)


if __name__ == "__main__":
    main()
