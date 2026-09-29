"""Endgame: skoki do nowych sektorów (prestiż), relikty, artefakty i kontrakty."""
import math
import random

from balance import *
from config import *


# --------------------
# Endgame: sektory (prestiż), relikty, kontrakty i artefakty
# --------------------
JUMP_MIN_RELICS = 3        # skok do nowego sektora jest możliwy, gdy da co najmniej tyle reliktów
RELIC_DIVISOR = 50000      # relikty za skok = sqrt(zarobione kredyty / RELIC_DIVISOR)
SECTOR_ORE_BONUS = 0.25    # każdy kolejny sektor: rudy droższe o 25%...
SECTOR_HP_BONUS = 0.35     # ...ale asteroidy twardsze o 35%
ARTIFACT_CHANCE = 0.10     # szansa na artefakt z kolosa (+2 pkt. proc. za każdy kolejny sektor)
DUPLICATE_RELICS = 3       # znaleziony duplikat artefaktu zamienia się w relikty

RELIC_PERKS = [  # stałe ulepszenia za relikty (zostają po skoku)
    dict(key="legacy", name="PROSPECTOR LEGACY", costs=(1, 2, 4, 7, 12), info="ORE PRICE +15% PER LEVEL"),
    dict(key="holds", name="BIG HOLDS", costs=(1, 2, 4, 7, 12), info="CARGO HOLD +15% PER LEVEL"),
    dict(key="auto", name="AUTOMATION", costs=(2, 3, 5, 8, 13), info="PASSIVE INCOME + DRONE LOADS +25% PER LEVEL"),
    dict(key="pilot", name="VETERAN PILOT", costs=(1, 3, 5, 8, 12), info="ENGINE + FIRE RATE +6% PER LEVEL"),
    dict(key="start", name="HEAD START", costs=(2, 4, 7, 11, 16), info="START EVERY NEW SECTOR WITH CREDITS"),
    dict(key="charter", name="FLEET CHARTER", costs=(10,), info="KEEP YOUR SHIPS AFTER A SECTOR JUMP"),
]
HEAD_START = (0, 5000, 20000, 80000, 300000, 1000000)

ARTIFACTS = [  # (id, nazwa, zestaw, statystyka, wartość)
    ("ion_coil", "ION COIL", "drive", "engine", 0.10),
    ("gyro", "GYRO CORE", "drive", "turn", 0.20),
    ("chrono", "CHRONO SHARD", "drive", "cooldown", 0.15),
    ("lens", "STARFORGE LENS", "forge", "fire", 0.10),
    ("aegis", "AEGIS PLATE", "forge", "shield", 1),
    ("fang", "COLOSSUS FANG", "forge", "loot", 0.20),
    ("pocket", "POCKET SPACE", "core", "cargo", 0.20),
    ("bit", "CORE DRILL BIT", "core", "mine", 1),
    ("hive", "HIVE MIND CHIP", "core", "drone", 0.25),
    ("ledger", "GUILD LEDGER", "guild", "price", 0.10),
    ("lodestone", "LODESTONE", "guild", "magnet", 0.40),
    ("seal", "MERCHANT SEAL", "guild", "income", 0.30),
]
ARTIFACT_SETS = {  # komplet 3 artefaktów z zestawu daje dodatkowy bonus
    "drive": ("PRECURSOR DRIVE", "warp", 1),
    "forge": ("STARFORGE ARMS", "fire", 0.15),
    "core": ("DEEP CORE", "cargo", 0.25),
    "guild": ("TRADE GUILD", "price", 0.15),
}
STAT_LABEL = {"engine": "ENGINE", "turn": "TURN RATE", "cooldown": "ABILITY COOLDOWN", "fire": "FIRE RATE",
              "shield": "SHIELD", "loot": "ASTEROID LOOT", "cargo": "CARGO HOLD", "mine": "ORE PER PLANET HIT",
              "drone": "DRONE LOADS", "price": "ORE PRICE", "magnet": "MAGNET RANGE", "income": "PASSIVE INCOME",
              "warp": "WARP HOME CHARGE"}


def stat_text(stat, val):
    if stat == "cooldown":
        return f"{STAT_LABEL[stat]} -{val:.0%}"
    if isinstance(val, int):
        return f"+{val} {STAT_LABEL[stat]}"
    return f"{STAT_LABEL[stat]} +{val:.0%}"


def artifact_by_id(aid):
    return next(a for a in ARTIFACTS if a[0] == aid)


def meta_bonus(save, stat):
    """Suma trwałych bonusów (artefakty, komplety zestawów, perki za relikty) dla danej statystyki."""
    found = set(save["artifacts"])
    v = sum(a[4] for a in ARTIFACTS if a[0] in found and a[3] == stat)
    for set_key, (_, s_stat, s_val) in ARTIFACT_SETS.items():
        if s_stat == stat and all(a[0] in found for a in ARTIFACTS if a[2] == set_key):
            v += s_val
    rl = save["relic_lv"]
    v += {"price": 0.15 * rl.get("legacy", 0), "cargo": 0.15 * rl.get("holds", 0),
          "income": 0.25 * rl.get("auto", 0), "drone": 0.25 * rl.get("auto", 0),
          "engine": 0.06 * rl.get("pilot", 0), "fire": 0.06 * rl.get("pilot", 0)}.get(stat, 0)
    return v


def refresh_meta(save):
    META_MULT["income"] = 1.0 + meta_bonus(save, "income")


def sector_ore_mult(save):
    return 1.0 + SECTOR_ORE_BONUS * (save["sector"] - 1)


def sector_hp_mult(save):
    return 1.0 + SECTOR_HP_BONUS * (save["sector"] - 1)


def relics_for(earned):
    return int(math.sqrt(max(0.0, earned) / RELIC_DIVISOR))


# kontrakty: (typ, sekundy lotu na wykonanie); czas biegnie tylko w locie
CONTRACT_TIME = {"deliver": 480, "planet": 480, "colossus": 600, "rocks": 360, "expedition": 420}


def new_contract(save):
    """Losowa oferta dopasowana do postępu gracza (znane surowce, ładownia, najdalszy lot)."""
    seen = [k for k in ORE_KINDS if k in save["seen"]] or ["iron"]
    cap = CARGO_CAP[save["levels"].get("cargo", 0)]
    best = max(ORE[k]["value"] for k in seen)
    wealth = max(cap, 60) * best * sector_ore_mult(save)   # mniej więcej wartość jednej pełnej ładowni
    typ = random.choice(("deliver", "deliver", "planet", "colossus", "rocks", "expedition"))
    c = dict(type=typ, kind=None, n=0, got=0, on=False, relics=1, art=random.random() < 0.25)
    if typ in ("deliver", "planet"):
        kind = random.choice(seen[-3:])   # raczej lepsze z poznanych surowców
        c["kind"] = kind
        c["n"] = max(10, int(round(cap * random.uniform(0.5, 1.1) / 10.0)) * 10)
        c["reward"] = int(c["n"] * ORE[kind]["value"] * sector_ore_mult(save) * (3.0 if typ == "deliver" else 2.5))
    elif typ == "colossus":
        c["n"] = random.randint(1, 3)
        c["reward"] = int(wealth * 1.5 * c["n"])
        c["relics"] = 1 + (c["n"] >= 2)
    elif typ == "rocks":
        c["n"] = random.choice((40, 60, 80, 120))
        c["reward"] = int(wealth * c["n"] / 40)
    else:
        c["n"] = int(max(PLANET_MIN_D * 1.4, save["far"] * 1.15) // 1000 * 1000)   # odległość od bazy (logika)
        c["reward"] = int(wealth * 2.5)
        c["relics"] = 2
    c["reward"] = max(200, c["reward"])
    c["left"] = c["time"] = CONTRACT_TIME[typ]
    return c


def contract_title(c):
    if c["type"] == "deliver":
        return f"DELIVER {c['n']} {ORE[c['kind']]['name']}"
    if c["type"] == "planet":
        return f"MINE {c['n']} {ORE[c['kind']]['name']} FROM PLANETS"
    if c["type"] == "colossus":
        return f"DESTROY {c['n']} COLOSS{'I' if c['n'] > 1 else 'US'}"
    if c["type"] == "rocks":
        return f"DESTROY {c['n']} ASTEROIDS"
    return f"REACH {c['n'] // 100}KM FROM BASE"


def contract_reward_text(c):
    s = f"{short_cr(c['reward'])} CR + {c['relics']} RELIC{'S' if c['relics'] > 1 else ''}"
    return s + (" + ARTIFACT" if c["art"] else "")


def mmss(secs):
    secs = max(0, int(secs))
    return f"{secs // 60}:{secs % 60:02d}"
