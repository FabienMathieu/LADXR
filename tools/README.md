# French ROM relocation tooling (Phase A)

This directory contains the tooling used to relocate every `rom.patch` call
site, pointer table and code label from the English reference ROM to the
French ROM. It is the foundation for adding French ROM support to LADXR.

The tools only **read** the ROMs. They never modify or redistribute them.

## Reference ROMs

The scripts locate the ROMs in `disassembly/` by SHA-1:

| Profile | SHA-1 |
|---|---|
| English (USA, Europe v1.0) | `d90ac17e9bf17b6c61624ad9f05447bdb5efc01a` |
| French (France Rev 1) | `b5e4df1a67432c609fa0f23519315297c6dcdc1d` |

## Optional developer tools

The relocation is byte-signature based and does not require any external
disassembler. For phase C (manual resolution of the remaining sites and for
rewriting absolute operands) the following tools are useful and documented
here only (not vendored):

* [mgbdis](https://github.com/mattcurrie/mgbdis) v3.0 - RGBDS compatible Game
  Boy disassembler. It supports `.sym` files to mark code/data/text/image
  blocks (the equivalent of the missing `mgbdis.cfg`) and
  `--character-map-path` for custom text encodings.
* [RGBDS](https://rgbds.gbdev.io) >= 0.8 - assembler/linker used to rebuild the
  disassembly (`make` inside the disassembly directory).

The existing `disassembly/*.sym` was produced by Beaten Dying Moon and marks
the code blocks that were actually executed while playing.

## Pipeline

```sh
# 1. Instrument an English generator run across a settings matrix.
python3 tools/instrument_en.py

# 2. Relocate everything and write rommap_fr.json (+ queues + report).
python3 tools/relocate.py
```

The individual steps can also be run standalone:

```sh
python3 tools/tables_fr.py    # pointer table discovery/validation
python3 tools/symbols_fr.py   # assembler.const labels + inline $XXXX inventory
```

## How relocation works

1. **Signatures are pristine English ROM bytes**, read at the patched address
   over the exact overwritten length. The `old` value written in the source is
   not used, because some patches are applied on top of earlier patches and are
   therefore context dependent.
2. For each site, the signature is searched in the corresponding French bank.
3. Ambiguous matches are resolved by surrounding-byte context and, as a last
   resort, by the monotonic ordering of addresses within a bank.
4. Remaining sites are resolved with the **piecewise-constant address shift**
   (`fr_addr - en_addr`), which is verified by byte similarity.
5. Sites whose bytes differ because of the engine revision are matched with a
   fuzzy anchor search and reported as `fuzzy` for review.

Banks that are byte-identical between the two ROMs are mapped directly.

## Artifacts

| Path | Committed | Content |
|---|---|---|
| `rommap_fr.json` | yes | Patch mapping, table config and label mapping (addresses only, no ROM bytes) |
| `tools/data/en_patches.jsonl` | no | Instrumented English patch log (intermediate) |
| `tools/data/manual_queue.jsonl` | no | Sites still unresolved (`not_found`, `unknown`) |
| `tools/data/review_queue.jsonl` | no | Sites resolved heuristically (`fuzzy`, `predicted`) |
| `tools/data/tables_fr.json` | no | Table discovery details |
| `tools/data/symbols_fr.json` | no | Label relocation details |

## Statuses

| Status | Meaning |
|---|---|
| `identical` | Bank is byte-identical, address unchanged |
| `exact` | Signature found uniquely (or disambiguated by context/order) |
| `predicted` | Address inferred from the block address shift, similarity verified |
| `fuzzy` | Bytes differ (engine revision); best anchor match, needs review |
| `low_entropy` | All-same-byte region (LADXR scratch/vectors); address kept |
| `not_found` / `unknown` | Unresolved, listed in the manual queue |

## Phase B - ROM profile layer

`rommap_fr.json` is consumed at runtime by `romprofile.py`:

* `romprofile.detect_profile(bytes)` selects the profile from the ROM SHA-1
  (falling back to the header region code `AZLF`).
* `rom.py` translates every `rom.patch(bank, addr, ...)` through the active
  profile. The English profile is an identity profile, so behaviour is
  unchanged. For the French profile the `old` byte assertion is relaxed
  (the bytes legitimately differ between revisions).
* `romTables.py` builds every pointer table from the profile's table config.
* `generator.generateRom` calls `assembler.resetConsts(profile.symbol_overrides())`
  so assembled code resolves the relocated `assembler.const` labels.

### Checks

```sh
# English output must stay byte-for-byte identical (golden master).
tools/check_golden_en.sh

# French profile detection, table construction and save.
python3 tools/check_fr_profile.py

# French generation completes and produces a valid 1MB ROM.
tools/check_fr_generation.sh
```

## Phase C - injected code and residual sites

* Injected assembly is tagged (`codebytes.Code`) so `rom.patch` can rewrite its
  absolute 16-bit operands. Operands below `0x4000` resolve against the fixed
  bank 0, the others against the patch site's bank.
* `tools/code_addr_fr.py` builds a translation map for every ROM target
  referenced by injected code (functions, labels, free-space trampolines and
  data pointers). It combines the patch map, the relocated labels, exact and
  fuzzy byte-signature search, a windowed similarity scan and the block address
  shift.
* Patch sites whose signature contains translatable operands or pointer words
  are resolved by translating the signature and matching it in the French ROM
  (`translated_old`).

### Current result (default seed)

* Patch sites resolved: 811/815 (99.5%).
* Code operands translated: 152/153.
* Remaining: 1 patch site (`patches/aesthetics.py` at bank 0 `0x01EB`, whose
  byte pattern is absent from the French ROM) falls back to the English
  address. `roomInfo.py` base addresses are still not relocated (used only by
  `--exportmap`, not by core generation).

Gameplay correctness of the generated French ROM must be validated in an
emulator; the automated checks only cover structure and non-regression.

## Phase D - Text localization

The French ROM renders accented characters with punctuation glyphs of its own
font (``*``=é, ``+``=è, ``<``=ê, ``%``=à, ``^``=apostrophe, ``_``=ç, ...),
**not** the ``0x80-0x8C`` codes used by the English engine. `french.py` holds
this encoding plus the French item/area names and template translations.

* `utils.setLanguage(language)` selects the active names and encoding; it is
  called from `generator.generateRom` based on the ROM profile.
* `utils.formatText` translates item-get templates ("Got the ..."), substitutes
  French item names and encodes accents for French.
* Original French static text is preserved: `reduceMessageLengths` (which
  rewrites ~60 texts with English) is only applied to the English profile, so
  the French ROM keeps its own item messages, Marin intro, etc.
* Dynamic texts are localized: item-get messages, hints (templates and area
  names), goal texts, shop prices, trade sequence and boomerang dialogs, evil
  shop and the bingo ending.

### Checks

```sh
python3 tools/check_fr_text.py
```

Known residual: the bingo board objective labels and the ending credits are
generated from hardcoded tile/glyph data and are not localized.

## Phase E - Integration

* The ROM profile is detected automatically everywhere (`main.py`, `generator.py`,
  the dump/export paths). `--romprofile auto|en|fr` forces a profile and a
  mismatch against the ROM raises a clear error.
* The saved ROM keeps its region code (`AZLF`) so a generated French ROM is
  detected again when re-read (e.g. `--test`, `--dump`).
* The web UI (`www/js/ui.js`) accepts the French checksum (`89757956`) in
  addition to the English one, and the in-browser bundle (`/js/ladxr.tar.gz`)
  excludes `.git`, `disassembly`, `tools`, `www` and any ROM/asm artifacts.
* `--exportmap` reports a clear message on non-English ROMs (its room metadata
  tables are not relocated yet).

### Checks

```sh
tools/check_golden_en.sh
python3 tools/check_fr_profile.py
tools/check_fr_generation.sh
python3 tools/check_fr_text.py
```

## Phase F - Test suite

Run everything with:

```sh
tools/run_tests.sh
```

The suite lives in `tests/` and uses `unittest` (no extra dependency). Tests
that need a reference ROM are skipped automatically when the ROM is not found
in `disassembly/`, so the suite also runs in CI where ROMs are absent.

| Module | Coverage |
|---|---|
| `test_rommap.py` | committed `rommap_fr.json` schema, >=99% resolution, no ROM bytes, table/label/code coverage |
| `test_text.py` | French font encoding, template translation, name coverage, font-safe output |
| `test_romprofile.py` | SHA/region detection, profile selection, mismatch error, strict mode |
| `test_tables_fr.py` | French pointer table construction and validation |
| `test_golden_en.py` | English golden master (byte-identical output) |
| `test_parity.py` | same seed produces the same placement for English and French |

CI runs `PYTHONHASHSEED=0 python3 -m unittest discover -s tests` (see
`.github/workflows/python-parse-test.yml`) and the runner is also invoked from
`.tinyci`.
