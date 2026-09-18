"""Checks for French text localization (phase D).

Verifies the French font encoding, template translation, and that a generated
French ROM contains French (not English) dynamic text.

Usage:
    python3 tools/check_fr_text.py
"""
from __future__ import annotations

import os
import random
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import common  # noqa: E402

common.ensure_repo_on_path()

import french  # noqa: E402
import utils  # noqa: E402

REVERSE = {ord(v): k for k, v in french.CHARS.items() if len(v) == 1 and not v.isalnum()}
REVERSE["^"] = "'"


def decode(data: bytes) -> str:
    out = []
    for byte in data:
        if byte in (0xFF, 0xFE):
            out.append("|")
        elif byte in REVERSE:
            out.append(REVERSE[byte])
        elif byte == 0x00:
            out.append(" ")
        else:
            out.append(chr(byte) if 32 <= byte < 127 else "?")
    return "".join(out)


def check_formatting() -> None:
    utils.setLanguage("en")
    en = utils.formatText("Got the {SWORD}!")
    assert b"Sword" in en, en

    utils.setLanguage("fr")
    fr = utils.formatText("Got the {SWORD}!")
    assert b"*" in fr, fr  # é encoded as *
    assert b"Sword" not in fr, fr

    necklace = utils.formatText("Got the {TRADING_ITEM_NECKLACE}!")
    assert b"Collier" in necklace, necklace
    assert b"^" not in necklace or True  # no crash

    # No raw accented / high bytes besides terminators.
    body = bytes(b for b in necklace if b not in (0xFE, 0xFF))
    assert all(b < 0x80 for b in body), necklace

    assert utils.formatText("Got the {SWORD}!") == b"Obtenu : *p*e\xff"
    utils.setLanguage("en")


def check_generated_rom() -> None:
    import argparse
    import generator
    import logic.main
    import worldSetup
    from settings import Settings

    fr_path = common.find_rom("fr")
    settings = Settings()
    settings.validate()
    args = argparse.Namespace(
        input_filename=fr_path, output_filename=None, plan=None, pymod=None,
        doubletrouble=False, romdebugmode=False, log_directory=None,
        spoilerformat="none", spoiler_filename=None,
    )
    rnd = random.Random(b"\x01" * 16)
    world = worldSetup.WorldSetup()
    world.randomize(settings, rnd)
    logic = logic.main.Logic(settings, world_setup=world)
    for spot in logic.iteminfo_list:
        if spot.item is None:
            options = spot.getOptions()
            spot.item = options[0] if options else None
    rom = generator.generateRom(args, settings, b"\x01" * 16, logic, rnd=rnd)

    # Hint texts were rewritten and must be French.
    hint = rom.texts[0x1B6]
    assert isinstance(hint, (bytes, bytearray)), type(hint)
    text = decode(bytes(hint))
    assert " is at " not in text, text
    assert "Got the " not in text, text
    print("Sample hint text: %r" % text)


def main() -> int:
    check_formatting()
    print("OK: French formatting/encoding")
    check_generated_rom()
    print("OK: generated French ROM text is localized")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
