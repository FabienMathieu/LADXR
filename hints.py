from locations.items import *
from utils import formatText
import utils
import french


hint_text_ids = [
    # Overworld owl statues
    0x1B6, 0x1B7, 0x1B9, 0x1BA, 0x1BB, 0x1BC, 0x1BD, 0x1BE, 0x22D,

    0x288, 0x280,  # D1
    0x28A, 0x289, 0x281,  # D2
    0x282, 0x28C, 0x28B,  # D3
    0x283,  # D4
    0x28D, 0x284,  # D5
    0x285, 0x28F, 0x28E,  # D6
    0x291, 0x290, 0x286,  # D7
    0x293, 0x287, 0x292,  # D8
    0x263,  # D0

    # Hint books
    0x267,  # color dungeon
    0x201,  # Pre open: 0x200
    0x203,  # Pre open: 0x202
    0x205,  # Pre open: 0x204
    0x207,  # Pre open: 0x206
    0x209,  # Pre open: 0x208
    0x20B,  # Pre open: 0x20A
]

hint_items = {POWER_BRACELET, SHIELD, BOW, HOOKSHOT, MAGIC_ROD, PEGASUS_BOOTS, OCARINA, FEATHER, SHOVEL,
              MAGIC_POWDER, BOMB, SWORD, FLIPPERS, TAIL_KEY, ANGLER_KEY, FACE_KEY,
              BIRD_KEY, SLIME_KEY, GOLD_LEAF, BOOMERANG, BOWWOW, ROOSTER, SONG1, SONG2, SONG3}

hints = [
    "{0} is at {1}",
    "If you want {0} start looking in {1}",
    "{1} holds {0}",
    "They say that {0} is at {1}",
    "You might want to look in {1} for a secret",
]

hints_fr = [
    "{0} se trouve à {1}",
    "Pour {0}, cherche à {1}",
    "{1} renferme {0}",
    "On dit que {0} est à {1}",
    "Cherche un secret à {1}",
]

useless_hint = [
    ("Egg", "Mt. Tamaranch"),
    ("Marin", "Mabe Village"),
    ("Marin", "Mabe Village"),
    ("Witch", "Koholint Prairie"),
    ("Mermaid", "Martha's Bay"),
    ("Nothing", "Tabahl Wasteland"),
    ("Animals", "Animal Village"),
    ("Sand", "Yarna Desert"),
]

useless_hint_fr = [
    ("l'Oeuf", "Mont Tamaranch"),
    ("Marin", "Village de Mabe"),
    ("Marin", "Village de Mabe"),
    ("la Sorcière", "Prairie de Koholint"),
    ("la Sirène", "Baie de Martha"),
    ("rien", "Terres Désolées de Tabahl"),
    ("les Animaux", "Village des Animaux"),
    ("le Sable", "Désert de Yarna"),
]


def addHints(rom, rnd, spots):
    lang = utils.getLanguage()
    active_hints = hints_fr if lang == "fr" else hints
    active_useless = useless_hint_fr if lang == "fr" else useless_hint
    spots = list(sorted(filter(lambda spot: spot.item in hint_items, spots), key=lambda spot: spot.nameId))
    text_ids = hint_text_ids.copy()
    rnd.shuffle(text_ids)
    for text_id in text_ids:
        if len(spots) > 0:
            spot_index = rnd.randint(0, len(spots) - 1)
            spot = spots.pop(spot_index)
            area = french.areaName(spot.metadata.area) if lang == "fr" else spot.metadata.area
            hint = rnd.choice(active_hints).format("{%s}" % (spot.item), area)
        else:
            hint = rnd.choice(active_hints).format(*rnd.choice(active_useless))
        rom.texts[text_id] = formatText(hint)

    for text_id in range(0x200, 0x20C, 2):
        rom.texts[text_id] = formatText("Read this book?", ask="YES  NO")
