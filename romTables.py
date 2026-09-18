from typing import Any, Dict, Optional

from rom import ROM
from pointerTable import PointerTable
from assembler import ASM


class Texts(PointerTable):
    END_OF_DATA = (0xfe, 0xff)

    DEFAULT_INFO: Dict[str, Any] = {
        "count": 0x2B0,
        "pointers_addr": 1,
        "pointers_bank": 0x1C,
        "banks_addr": 0x741,
        "banks_bank": 0x1C,
    }

    def __init__(self, rom, info: Optional[Dict[str, Any]] = None):
        super().__init__(rom, info or dict(self.DEFAULT_INFO))


class Entities(PointerTable):
    DEFAULT_INFO: Dict[str, Any] = {
        "count": 0x320,
        "pointers_addr": 0,
        "pointers_bank": 0x16,
        "data_bank": 0x16,
    }

    def __init__(self, rom, info: Optional[Dict[str, Any]] = None):
        super().__init__(rom, info or dict(self.DEFAULT_INFO))


class RoomsTable(PointerTable):
    HEADER = 2

    def _readData(self, rom, bank_nr, pointer):
        bank = rom.banks[bank_nr]
        start = pointer
        pointer += self.HEADER
        while bank[pointer] != 0xFE:
            obj_type = (bank[pointer] & 0xF0)
            if obj_type == 0xE0:
                pointer += 5
            elif obj_type == 0xC0 or obj_type == 0x80:
                pointer += 3
            else:
                pointer += 2
        pointer += 1
        self._addStorage(bank_nr, start, pointer)
        return bank[start:pointer]


class RoomsOverworldTop(RoomsTable):
    DEFAULT_INFO: Dict[str, Any] = {
        "count": 0x080,
        "pointers_addr": 0x000,
        "pointers_bank": 0x09,
        "data_bank": 0x09,
        "alt_pointers": {
            "Alt06": (0x00, 0x31FD),
            "Alt0E": (0x00, 0x31CD),
            "Alt1B": (0x00, 0x320D),
            "Alt2B": (0x00, 0x321D),
            "Alt79": (0x00, 0x31ED),
        }
    }

    def __init__(self, rom, info: Optional[Dict[str, Any]] = None):
        super().__init__(rom, info or dict(self.DEFAULT_INFO))


class RoomsOverworldBottom(RoomsTable):
    DEFAULT_INFO: Dict[str, Any] = {
        "count": 0x080,
        "pointers_addr": 0x100,
        "pointers_bank": 0x09,
        "data_bank": 0x1A,
        "alt_pointers": {
            "Alt8C": (0x00, 0x31DD),
        }
    }

    def __init__(self, rom, info: Optional[Dict[str, Any]] = None):
        super().__init__(rom, info or dict(self.DEFAULT_INFO))


class RoomsIndoorA(RoomsTable):
    # TODO: The color dungeon tables are in the same bank, but the pointer table is after the room data.
    DEFAULT_INFO: Dict[str, Any] = {
        "count": 0x100,
        "pointers_addr": 0x000,
        "pointers_bank": 0x0A,
        "data_bank": 0x0A,
        "alt_pointers": {
            "Alt1F5": (0x00, 0x31A1),
        }
    }

    def __init__(self, rom, info: Optional[Dict[str, Any]] = None):
        super().__init__(rom, info or dict(self.DEFAULT_INFO))


class RoomsIndoorB(RoomsTable):
    # Most likely, this table can be expanded all the way to the end of the bank,
    # giving a few 100 extra bytes to work with.
    DEFAULT_INFO: Dict[str, Any] = {
        "count": 0x0FF,
        "pointers_addr": 0x000,
        "pointers_bank": 0x0B,
        "data_bank": 0x0B,
    }

    def __init__(self, rom, info: Optional[Dict[str, Any]] = None):
        super().__init__(rom, info or dict(self.DEFAULT_INFO))


class RoomsColorDungeon(RoomsTable):
    DEFAULT_INFO: Dict[str, Any] = {
        "count": 0x016,
        "pointers_addr": 0x3B77,
        "pointers_bank": 0x0A,
        "data_bank": 0x0A,
        "expand_to_end_of_bank": True
    }

    def __init__(self, rom, info: Optional[Dict[str, Any]] = None):
        super().__init__(rom, info or dict(self.DEFAULT_INFO))


class BackgroundTable(PointerTable):
    def _readData(self, rom, bank_nr, pointer):
        bank = rom.banks[bank_nr]
        start = pointer
        while bank[pointer] != 0x00:
            addr = bank[pointer] << 8 | bank[pointer + 1]
            amount = (bank[pointer + 2] & 0x3F) + 1
            repeat = (bank[pointer + 2] & 0x40) == 0x40
            vertical = (bank[pointer + 2] & 0x80) == 0x80
            pointer += 3
            if not repeat:
                pointer += amount
            if repeat:
                pointer += 1
        pointer += 1
        self._addStorage(bank_nr, start, pointer)
        return bank[start:pointer]


class BackgroundTilesTable(BackgroundTable):
    DEFAULT_INFO: Dict[str, Any] = {
        "count": 0x26,
        "pointers_addr": 0x052B,
        "pointers_bank": 0x20,
        "data_bank": 0x08,
        "expand_to_end_of_bank": True
    }

    def __init__(self, rom, info: Optional[Dict[str, Any]] = None):
        super().__init__(rom, info or dict(self.DEFAULT_INFO))


class BackgroundAttributeTable(BackgroundTable):
    DEFAULT_INFO: Dict[str, Any] = {
        "count": 0x26,
        "pointers_addr": 0x1C4B,
        "pointers_bank": 0x24,
        "data_bank": 0x24,
        "expand_to_end_of_bank": True
    }

    def __init__(self, rom, info: Optional[Dict[str, Any]] = None):
        super().__init__(rom, info or dict(self.DEFAULT_INFO))


class OverworldRoomSpriteData(PointerTable):
    DEFAULT_INFO: Dict[str, Any] = {
        "count": 0x100,
        "pointers_addr": 0x30D3,
        "pointers_bank": 0x20,
        "data_bank": 0x20,
        "data_addr": 0x33F3,
        "data_size": 4,
        "claim_storage_gaps": True,
    }

    def __init__(self, rom, info: Optional[Dict[str, Any]] = None):
        super().__init__(rom, info or dict(self.DEFAULT_INFO))


class IndoorRoomSpriteData(PointerTable):
    DEFAULT_INFO: Dict[str, Any] = {
        "count": 0x220,
        "pointers_addr": 0x31D3,
        "pointers_bank": 0x20,
        "data_bank": 0x20,
        "data_addr": 0x363B,
        "data_size": 4,
        "claim_storage_gaps": True,
    }

    def __init__(self, rom, info: Optional[Dict[str, Any]] = None):
        super().__init__(rom, info or dict(self.DEFAULT_INFO))


class ROMWithTables(ROM):
    def __init__(self, filestream, *, profile=None):
        super().__init__(filestream, profile=profile)
        p = self.profile

        # Ability to patch any text in the game with different text
        self.texts = Texts(self, p.table_config("texts"))
        # Ability to modify rooms
        self.entities = Entities(self, p.table_config("entities"))
        self.rooms_overworld_top = RoomsOverworldTop(self, p.table_config("rooms_overworld_top"))
        self.rooms_overworld_bottom = RoomsOverworldBottom(self, p.table_config("rooms_overworld_bottom"))
        self.rooms_indoor_a = RoomsIndoorA(self, p.table_config("rooms_indoor_a"))
        self.rooms_indoor_b = RoomsIndoorB(self, p.table_config("rooms_indoor_b"))
        self.rooms_color_dungeon = RoomsColorDungeon(self, p.table_config("rooms_color_dungeon"))
        self.room_sprite_data_overworld = OverworldRoomSpriteData(self, p.table_config("overworld_sprite_data"))
        self.room_sprite_data_indoor = IndoorRoomSpriteData(self, p.table_config("indoor_sprite_data"))

        # Backgrounds for things like the title screen.
        self.background_tiles = BackgroundTilesTable(self, p.table_config("background_tiles"))
        self.background_attributes = BackgroundAttributeTable(self, p.table_config("background_attributes"))

    def save(self, filename, *, name=None):
        self.texts.store(self)
        self.entities.store(self)
        self.rooms_overworld_top.store(self)
        self.rooms_overworld_bottom.store(self)
        self.rooms_indoor_a.store(self)
        self.rooms_indoor_b.store(self)
        self.rooms_color_dungeon.store(self)
        leftover_storage = self.room_sprite_data_overworld.store(self)
        self.room_sprite_data_indoor.addStorage(leftover_storage)
        self.patch(0x00, 0x0DFA, ASM("ld hl, $763B"), ASM("ld hl, $%04x" % (leftover_storage[0]["start"] | 0x4000)))
        self.room_sprite_data_indoor.adjustDataStart(leftover_storage[0]["start"])
        self.room_sprite_data_indoor.store(self)
        self.background_tiles.store(self)
        self.background_attributes.store(self)
        super().save(filename, name=name)
