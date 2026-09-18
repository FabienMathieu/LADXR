"""French localization data and helpers.

The French ROM renders accented characters using punctuation glyphs of the
original font, so text must be encoded to those byte codes. The mapping below
was derived from the French ROM's own text table (e.g. ``*``=é, ``+``=è,
``<``=ê, ``%``=à, ``^``=apostrophe, ``_``=ç).
"""
from __future__ import annotations

import re
import unicodedata
from typing import Dict, Optional

# Accented character -> French ROM font byte code.
CHARS: Dict[str, str] = {
    "é": "*", "è": "+", "ê": "<", "à": "%", "â": "$", "ô": "]",
    "î": "/", "ï": "[", "û": "\\", "ù": "=", "ç": "_",
    "É": "*", "È": "+", "Ê": "<", "À": "%", "Â": "$", "Ô": "]",
    "Î": "/", "Ï": "[", "Û": "\\", "Ù": "=", "Ç": "_",
    "'": "^", "\u2019": "^",
    "œ": "oe", "Œ": "OE",
    "ë": "e", "ä": "a", "ö": "o", "ü": "u",
}

NAMES: Dict[str, str] = {
    "SWORD": "Épée",
    "BOMB": "Bombes",
    "POWER_BRACELET": "Bracelet de Force",
    "SHIELD": "Bouclier",
    "BOW": "Arc",
    "HOOKSHOT": "Grappin",
    "MAGIC_ROD": "Baguette Magique",
    "PEGASUS_BOOTS": "Bottes de Pégase",
    "OCARINA": "Ocarina",
    "FEATHER": "Plume de Roc",
    "SHOVEL": "Pelle",
    "MAGIC_POWDER": "Poudre Magique",
    "BOOMERANG": "Boomerang",
    "ROOSTER": "Coq Volant",
    "HAMMER": "Marteau",
    "FLIPPERS": "Palmes",

    "SLIME_KEY": "Clé de Gelée",
    "TAIL_KEY": "Clé de la Queue",
    "ANGLER_KEY": "Clé du Poisson",
    "FACE_KEY": "Clé du Visage",
    "BIRD_KEY": "Clé de l'Oiseau",
    "GOLD_LEAF": "Feuille Dorée",

    "RUPEE": "Rubis",
    "RUPEES": "Rubis",
    "RUPEES_50": "50 Rubis",
    "RUPEES_20": "20 Rubis",
    "RUPEES_100": "100 Rubis",
    "RUPEES_200": "200 Rubis",
    "RUPEES_500": "500 Rubis",
    "SEASHELL": "Coquillage",

    "KEY": "Petite Clé",
    "KEY1": "Clé de la Caverne de la Queue",
    "KEY2": "Clé de la Grotte des Flacons",
    "KEY3": "Clé de la Caverne des Clés",
    "KEY4": "Clé du Tunnel du Poisson",
    "KEY5": "Clé de la Gueule du Silure",
    "KEY6": "Clé du Sanctuaire du Visage",
    "KEY7": "Clé de la Tour de l'Aigle",
    "KEY8": "Clé du Rocher de la Tortue",
    "KEY0": "Clé du Donjon Couleur",

    "MAP": "Carte",
    "MAP1": "Carte de la Caverne de la Queue",
    "MAP2": "Carte de la Grotte des Flacons",
    "MAP3": "Carte de la Caverne des Clés",
    "MAP4": "Carte du Tunnel du Poisson",
    "MAP5": "Carte de la Gueule du Silure",
    "MAP6": "Carte du Sanctuaire du Visage",
    "MAP7": "Carte de la Tour de l'Aigle",
    "MAP8": "Carte du Rocher de la Tortue",
    "MAP0": "Carte du Donjon Couleur",

    "COMPASS": "Boussole",
    "COMPASS1": "Boussole de la Caverne de la Queue",
    "COMPASS2": "Boussole de la Grotte des Flacons",
    "COMPASS3": "Boussole de la Caverne des Clés",
    "COMPASS4": "Boussole du Tunnel du Poisson",
    "COMPASS5": "Boussole de la Gueule du Silure",
    "COMPASS6": "Boussole du Sanctuaire du Visage",
    "COMPASS7": "Boussole de la Tour de l'Aigle",
    "COMPASS8": "Boussole du Rocher de la Tortue",
    "COMPASS0": "Boussole du Donjon Couleur",

    "STONE_BEAK": "Bec de Pierre",
    "STONE_BEAK1": "Bec de Pierre de la Caverne de la Queue",
    "STONE_BEAK2": "Bec de Pierre de la Grotte des Flacons",
    "STONE_BEAK3": "Bec de Pierre de la Caverne des Clés",
    "STONE_BEAK4": "Bec de Pierre du Tunnel du Poisson",
    "STONE_BEAK5": "Bec de Pierre de la Gueule du Silure",
    "STONE_BEAK6": "Bec de Pierre du Sanctuaire du Visage",
    "STONE_BEAK7": "Bec de Pierre de la Tour de l'Aigle",
    "STONE_BEAK8": "Bec de Pierre du Rocher de la Tortue",
    "STONE_BEAK0": "Bec de Pierre du Donjon Couleur",

    "NIGHTMARE_KEY": "Clé du Cauchemar",
    "NIGHTMARE_KEY1": "Clé du Cauchemar de la Caverne de la Queue",
    "NIGHTMARE_KEY2": "Clé du Cauchemar de la Grotte des Flacons",
    "NIGHTMARE_KEY3": "Clé du Cauchemar de la Caverne des Clés",
    "NIGHTMARE_KEY4": "Clé du Cauchemar du Tunnel du Poisson",
    "NIGHTMARE_KEY5": "Clé du Cauchemar de la Gueule du Silure",
    "NIGHTMARE_KEY6": "Clé du Cauchemar du Sanctuaire du Visage",
    "NIGHTMARE_KEY7": "Clé du Cauchemar de la Tour de l'Aigle",
    "NIGHTMARE_KEY8": "Clé du Cauchemar du Rocher de la Tortue",
    "NIGHTMARE_KEY0": "Clé du Cauchemar du Donjon Couleur",

    "HEART_PIECE": "Quart de Coeur",
    "BOWWOW": "BowWow",
    "ARROWS_10": "10 Flèches",
    "SINGLE_ARROW": "une Flèche",
    "MEDICINE": "Médicament",

    "MAX_POWDER_UPGRADE": "Poudre Magique (capacité)",
    "MAX_BOMBS_UPGRADE": "Bombes (capacité)",
    "MAX_ARROWS_UPGRADE": "Flèches (capacité)",

    "RED_TUNIC": "Tunique Rouge",
    "BLUE_TUNIC": "Tunique Bleue",

    "HEART_CONTAINER": "Coeur de Vie",
    "BAD_HEART_CONTAINER": "Coeur Maudit",

    "TOADSTOOL": "Champignon",

    "SONG1": "Ballade du Poisson-Rêve",
    "SONG2": "Mambo de Manbo",
    "SONG3": "Chant de l'Âme",

    "INSTRUMENT1": "Violoncelle de la Pleine Lune",
    "INSTRUMENT2": "Cor de Conque",
    "INSTRUMENT3": "Cloche du Lys de Mer",
    "INSTRUMENT4": "Harpe des Vagues",
    "INSTRUMENT5": "Marimba des Vents",
    "INSTRUMENT6": "Triangle de Corail",
    "INSTRUMENT7": "Orgue du Calme du Soir",
    "INSTRUMENT8": "Tambour de Tonnerre",

    "TRADING_ITEM_YOSHI_DOLL": "Poupée Yoshi",
    "TRADING_ITEM_RIBBON": "Ruban",
    "TRADING_ITEM_DOG_FOOD": "Pâtée",
    "TRADING_ITEM_BANANAS": "Bananes",
    "TRADING_ITEM_STICK": "Bâton",
    "TRADING_ITEM_HONEYCOMB": "Rayon de Miel",
    "TRADING_ITEM_PINEAPPLE": "Ananas",
    "TRADING_ITEM_HIBISCUS": "Hibiscus",
    "TRADING_ITEM_LETTER": "Lettre",
    "TRADING_ITEM_BROOM": "Balai",
    "TRADING_ITEM_FISHING_HOOK": "Hameçon",
    "TRADING_ITEM_NECKLACE": "Collier",
    "TRADING_ITEM_SCALE": "Écaille",
    "TRADING_ITEM_MAGNIFYING_GLASS": "Loupe",

    "TAIL_CAVE_OPENED": "Caverne de la Queue ouverte",
    "KEY_CAVERN_OPENED": "Caverne des Clés ouverte",
    "ANGLER_TUNNEL_OPENED": "Tunnel du Poisson ouvert",
    "FACE_SHRINE_OPENED": "Sanctuaire du Visage ouvert",
    "CASTLE_GATE_OPENED": "Porte du Château ouverte",
    "EAGLE_TOWER_OPENED": "Tour de l'Aigle ouverte",
}

AREA_NAMES: Dict[str, str] = {
    "Angler's Tunnel": "Tunnel du Poisson",
    "Animal Village": "Village des Animaux",
    "Bottle Grotto": "Grotte des Flacons",
    "Catfish's Maw": "Gueule du Silure",
    "Color Dungeon": "Donjon Couleur",
    "Death Mountain": "Mont de la Mort",
    "Desert": "Désert",
    "Desert Shelf": "Plateau du Désert",
    "Donut Plains": "Plaines Donut",
    "Eagle's Tower": "Tour de l'Aigle",
    "Eastern Palace": "Palais de l'Est",
    "Face Shrine": "Sanctuaire du Visage",
    "Goponga Swamp": "Marais Goponga",
    "Graveyard": "Cimetière",
    "Kakariko Village": "Village de Kakariko",
    "Kanalet Castle": "Château de Kanalet",
    "Key Cavern": "Caverne des Clés",
    "Koholint Prairie": "Prairie de Koholint",
    "Lost Woods": "Bois Perdu",
    "Mabe Village": "Village de Mabe",
    "Martha's Bay": "Baie de Martha",
    "Mysterious Woods": "Bois Mystérieux",
    "Pothole Field": "Plaine des Nids-de-Poule",
    "Rapids Ride": "Rapides",
    "Southern Face Shrine": "Sanctuaire du Visage Sud",
    "Swamp": "Marais",
    "Tail Cave": "Caverne de la Queue",
    "Tal Tal Heights": "Hauteurs de Tal Tal",
    "Tal Tal Mountains": "Montagnes de Tal Tal",
    "Toronbo Shores": "Rivages de Toronbo",
    "Turtle Rock": "Rocher de la Tortue",
    "Ukuku Prairie": "Prairie d'Ukuku",
    "Yarna Desert": "Désert de Yarna",
}

# Exact translations for dynamic templates that are not plain item-get messages.
TEMPLATES: Dict[str, str] = {
    "You lost a heart!": "Vous perdez un coeur!",
    "Got BowWow!": "Vous trouvez BowWow!",
    "You can now carry more Magic Powder!": "Vous pouvez porter plus de Poudre Magique!",
    "You can now carry more Bombs!": "Vous pouvez porter plus de Bombes!",
    "You can now carry more Arrows!": "Vous pouvez porter plus de Flèches!",
    "Just sail away.": "Il suffit de naviguer.",
    "BINGO!\nPress any button to finish.": "BINGO!\nAppuyez sur un bouton!",
    "Everybody hates me... Want something?": "Tout le monde me déteste... Tu veux quelque chose?",
    "Good for you.": "Tant mieux pour toi.",
    "Welcome, #####. This is the tunic\nfairy.": "Bienvenue, #####. Je suis la fée\ndes tuniques.",
    "Okay, let's do it!": "Bon, allons-y!",
    "The item came back to you. You returned the other item.": "L'objet t'est revenu. Tu as rendu l'autre.",
    "It's a secret to everybody.": "C'est un secret pour tout le monde.",
    "I found a good item washed up on the beach... Want to have it?": "J'ai trouvé un bon objet échoué sur la plage... Tu le veux?",
    "Read this book?": "Lire ce livre?",
    "Everything is normal.": "Tout est normal.",
    # Shop / evil shop / miscellaneous dynamic messages
    "Welcome, #####. I admire you for coming this far.": "Bienvenue, #####. Je t'admire d'être venu si loin.",
    "#####, it is dangerous to go alone!\nTake this!": "#####, c'est dangereux d'y aller seul!\nPrends ceci!",
    "Everybody hates me, so I give away free things in the hope people will love me. Want something?": "Tout le monde me déteste, alors j'offre des cadeaux en espérant être aimé. Tu veux quelque chose?",
    "1 to 3 Seashells": "1 à 3 Coquillages",
    "100 to 200 Rupees": "100 à 200 Rubis",
    "Angler Tunnel opened!": "Tunnel du Poisson ouvert!",
    "Castle gate opened!": "Porte du Château ouverte!",
    "Eagle tower opened!": "Tour de l'Aigle ouverte!",
    "Face Shrine opened!": "Sanctuaire du Visage ouvert!",
    "Key Cavern opened!": "Caverne des Clés ouverte!",
    "Tail Cave opened!": "Caverne de la Queue ouverte!",
    "DX key for you! He he he...": "Une clé DX pour toi! Hi hi hi...",
    "Got ... nothing?": "Rien obtenu...?",
    "He he he. Want to buy something with your life?": "Hi hi hi. Tu veux acheter quelque chose au prix de ta vie?",
    "I cannot take your last heart.": "Je ne peux pas prendre ton dernier coeur.",
    "Nothing?": "Rien?",
    "Random key": "Clé au hasard",
    "Seashells for you, enjoy. He he he...": "Des coquillages pour toi, profite. Hi hi hi...",
    "Some rupees for you, enjoy. He he he...": "Des rubis pour toi, profite. Hi hi hi...",
    "Only 100 {RUPEES}? _ _ Buy  No Way": "Seulement 100 {RUPEES}?    Acheter Non",
    "Only 200 {RUPEES}? _ _ Buy  No Way": "Seulement 200 {RUPEES}?    Acheter Non",
    # Shop answer prompts
    "Buy  No Way": "Acheter  Non",
    "Buy  Don't": "Acheter  Non",
    "Yes  No!": "Oui  Non!",
    "Yes  No": "Oui  Non",
    "Fine No...": "D'accord Non...",
    "Okay Not Now": "Oui  Plus tard",
    "Okay No": "Oui  Non",
    "Pay Leave": "Payer  Partir",
    "Give Don't": "Donner  Non",
    "Fish Not Now": "Pêcher  Plus tard",
    "Cast Not Now": "Lancer  Plus tard",
    "YES  NO": "OUI  NON",
}

_ITEM_GET = re.compile(
    r"^(?:You've got|You've found|You got|You found|You received|Found|Got|Obtained)"
    r"\s+(?:a\s+|an\s+|the\s+|some\s+)?(\d+\s+)?(\{[A-Za-z0-9_]+\})"
)
_NEED_INSTRUMENTS = re.compile(r"^You need (\d+) instruments?$")
_NEED_SEASHELLS = re.compile(r"^You need (\d+) \{SEASHELL\}s$")
_NEED_LIST = re.compile(r"^You need:\n")
_ONLY_RUPEES = re.compile(r"^Only (\d+) \{RUPEES\}!$")
_DELUXE_RUPEES = re.compile(r"^Deluxe (\{[A-Za-z0-9_]+\}) (\d+) \{RUPEES\}!$")
_ITEM_ONLY_RUPEES = re.compile(r"^(\{[A-Za-z0-9_]+\}) Only (\d+) \{RUPEES\}!$")


def translate(text: str) -> str:
    """Return a French rendering of an English randomizer template."""
    if text in TEMPLATES:
        return TEMPLATES[text]
    match = _ITEM_GET.match(text)
    if match:
        return "Obtenu : %s%s" % (match.group(1) or "", match.group(2))
    match = _NEED_INSTRUMENTS.match(text)
    if match:
        return "Il faut %s instruments" % match.group(1)
    match = _NEED_SEASHELLS.match(text)
    if match:
        return "Il faut %s {SEASHELL}" % match.group(1)
    match = _ONLY_RUPEES.match(text)
    if match:
        return "Seulement %s {RUPEES}!" % match.group(1)
    match = _DELUXE_RUPEES.match(text)
    if match:
        return "Super %s %s {RUPEES}!" % (match.group(1), match.group(2))
    match = _ITEM_ONLY_RUPEES.match(text)
    if match:
        return "%s %s {RUPEES}!" % (match.group(1), match.group(2))
    if _NEED_LIST.match(text):
        return _NEED_LIST.sub("Il te faut :\n", text)
    return text


def areaName(area: str) -> str:
    return AREA_NAMES.get(area, area)


def encode(text: str) -> bytes:
    """Encode text to the French ROM font byte codes."""
    out = []
    for char in text:
        if char in CHARS:
            out.append(CHARS[char])
        elif ord(char) < 128:
            out.append(char)
        else:
            decomposed = unicodedata.normalize("NFKD", char)
            out.append("".join(c for c in decomposed if ord(c) < 128) or "?")
    return "".join(out).encode("ascii")
