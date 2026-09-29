"""Balans gry: statki, ulepszenia, koszty, moduły bazy, drony i opisy do menu."""
import math

from config import *


# --------------------
# Tempo progresji: mnożniki kosztów (zwiększ, żeby gra trwała dłużej, zmniejsz, żeby szła szybciej)
# --------------------
COST_MULT = 2.6        # kredyty: ulepszenia statku i statki
DRONE_COST_MULT = 1.9  # kredyty: drony i technologia dronów
BUILD_MULT = 8.0       # surowce potrzebne do rozbudowy bazy (jednostek jest teraz ok. 5x więcej niż kiedyś)
LEVEL_STEEP = 0.12     # każdy kolejny poziom drożeje dodatkowo o tyle
MINE_YIELD = 5         # ile jednostek surowca daje jedno trafienie w planetę (razy obrażenia pocisku)
FIELD_TARGET = 34      # ile asteroid utrzymuje się w skupisku wokół planety
COLOSSUS_R = 140       # promień kolosalnej asteroidy (logika)
ROCK_UNITS = {  # ile jednostek surowca zostawia zniszczona asteroida (traktor-beam daje 2x więcej)
    "iron": {"small": 3, "large": 6, "colossus": 40},
    "gold": {"small": 3, "large": 9, "colossus": 25},
    "titanium": {"small": 2, "large": 4, "colossus": 28},
}


def round10(x):
    return max(10, int(x / 10 + 0.5) * 10)


def scaled(costs, mult):
    """Koszty kolejnych poziomów: baza * mnożnik * (1 + LEVEL_STEEP * numer poziomu)."""
    return [round10(c * mult * (1 + LEVEL_STEEP * i)) for i, c in enumerate(costs)]


def scaled_build(costs):
    """To samo dla kosztów w surowcach (słowniki)."""
    return [{k: max(1, int(round(n * BUILD_MULT * (1 + LEVEL_STEEP * i)))) for k, n in c.items()}
            for i, c in enumerate(costs)]


# --------------------
# Dane: statki i ulepszenia (za kredyty)
# --------------------
SHIPS = [
    dict(id="scout", name="SCOUT", cost=0, radius=24, speed=1.0, turn=3.0, fire=1.0, shields=0, dmg=1,
         ability="repair", reactive=False, beam=False, cargo_mult=1, mine_bonus=0, magnet=1.0,
         missiles=False, missile_reload=1.0, missile_dmg=0,
         sheet="fr_ship.png", stats=(3, 3, 3, 3),
         perk=("BALANCED ALL-ROUNDER", "SHIFT: FIELD REPAIR", "RESTORES SHIELD CHARGES")),
    dict(id="interceptor", name="INTERCEPTOR", cost=round10(450 * COST_MULT), radius=17, speed=1.35, turn=4.5,
         fire=1.25, shields=0, dmg=1, ability="dash", reactive=False, beam=False, cargo_mult=1, mine_bonus=0,
         magnet=1.0, missiles=False, missile_reload=1.0, missile_dmg=0,
         sheet="fr_ship_interceptor.png", stats=(5, 5, 2, 2),
         perk=("SHIFT: PHASE DASH", "EXCLUSIVE: SHOCKWAVE [E]", "TINY HITBOX, GUNS -25%")),
    dict(id="striker", name="STRIKER", cost=round10(700 * COST_MULT), radius=22, speed=1.15, turn=3.6,
         fire=0.85, shields=0, dmg=1, ability="overdrive", reactive=False, beam=False, cargo_mult=1, mine_bonus=0,
         magnet=1.0, missiles=True, missile_reload=0.6, missile_dmg=0,
         sheet="fr_ship_striker.png", stats=(4, 4, 5, 1),
         perk=("SHIFT: OVERDRIVE", "EXCLUSIVE: HOMING MISSILES", "GLASS CANNON, FAST RELOAD")),
    dict(id="heavy", name="BRUISER", cost=round10(800 * COST_MULT), radius=32, speed=0.8, turn=2.0, fire=0.8,
         shields=1, dmg=2, ability=None, reactive=True, beam=False, cargo_mult=1, mine_bonus=0, magnet=1.0,
         missiles=True, missile_reload=1.0, missile_dmg=2,
         sheet="fr_ship_heavy.png", stats=(2, 1, 4, 5),
         perk=("2X DMG BULLETS, +1 SHIELD", "TURRET + MISSILE CLUSTERS", "SHIELD HIT = BLAST")),
    dict(id="surveyor", name="SURVEYOR", cost=round10(1000 * COST_MULT), radius=20, speed=1.1, turn=3.4, fire=1.35,
         shields=0, dmg=1, ability="scan", reactive=False, beam=False, cargo_mult=1, mine_bonus=1, magnet=1.0,
         missiles=False, missile_reload=1.0, missile_dmg=0,
         sheet="fr_ship_surveyor.png", stats=(3, 4, 1, 2),
         perk=("SHIFT: DEEP SCAN", "MAP X2 + PLANET ARROWS", "MINING LASER: +ORE/HIT")),
    dict(id="harvester", name="HARVESTER", cost=round10(1400 * COST_MULT), radius=26, speed=0.9, turn=2.6, fire=1.6,
         shields=0, dmg=1, ability=None, reactive=False, beam=True, cargo_mult=2, mine_bonus=0, magnet=1.0,
         missiles=False, missile_reload=1.0, missile_dmg=0,
         sheet="fr_ship_harvester.png", stats=(3, 3, 1, 2),
         perk=("AUTO TRACTOR BEAM:", "PULLS ASTEROIDS INTO CARGO", "CARGO HOLD X2, MORE BEAMS")),
    dict(id="hauler", name="HAULER", cost=round10(1800 * COST_MULT), radius=34, speed=0.7, turn=1.8, fire=1.5,
         shields=1, dmg=1, ability="pulse", reactive=False, beam=False, cargo_mult=4, mine_bonus=0, magnet=1.6,
         missiles=False, missile_reload=1.0, missile_dmg=0,
         sheet="fr_ship_hauler.png", stats=(1, 1, 2, 4),
         perk=("CARGO HOLD X4, +1 SHIELD", "SHIFT: GRAVITY WELL", "PULLS + CRUSHES, KNOCKBACK")),
]
# płomienie silników: wymiary korpusu (px sprite'a), pozycje dysz (x w px korpusu), szerokość i długość płomienia, paleta
SHIP_FX = {
    "scout": dict(body=(21, 25), nozzles=(8, 12), w=5, L=14, pal="blue"),
    "interceptor": dict(body=(17, 29), nozzles=(7, 9), w=4, L=16, pal="blue"),
    "striker": dict(body=(23, 27), nozzles=(9, 13), w=5, L=14, pal="fire"),
    "heavy": dict(body=(33, 28), nozzles=(11, 16, 21), w=6, L=15, pal="fire"),
    "surveyor": dict(body=(21, 27), nozzles=(10,), w=7, L=14, pal="green"),
    "harvester": dict(body=(29, 27), nozzles=(10, 14, 18), w=5, L=13, pal="fire"),
    "hauler": dict(body=(35, 30), nozzles=(13, 17, 21), w=6, L=16, pal="fire"),
}
ABILITY_NAME = {"dash": "DASH", "overdrive": "OVERDRIVE", "scan": "DEEP SCAN", "pulse": "GRAVITY WELL",
                "repair": "REPAIR"}
STAT_NAMES = ("SPEED", "TURN", "FIRE", "ARMOR")

UPGRADES = [  # wspólne dla wszystkich statków
    dict(key="cargo", name="CARGO HOLD", costs=scaled([80, 160, 300, 520, 850, 1400, 2400, 4000, 6500, 10000, 16000,
                                                       22000, 34000, 52000, 80000, 120000, 180000, 270000, 400000,
                                                       600000, 900000, 1300000], COST_MULT)),
    dict(key="fire", name="FIRE RATE", costs=scaled([40, 60, 90, 130, 180, 250, 350], COST_MULT)),
    dict(key="engine", name="ENGINE", costs=scaled([30, 45, 65, 90, 120, 160, 210, 270], COST_MULT)),
    dict(key="double", name="DOUBLE SHOT", costs=scaled([400], COST_MULT)),
    dict(key="shield", name="SHIELD", costs=scaled([150, 280, 450], COST_MULT)),
]

# ulepszenia specjalne: każdy statek ma własne linie rozwoju (rakiety dzielą Bruiser i Striker)
SPECIAL_DEFS = {
    "repair": ("FIELD REPAIR", [300, 700, 1500, 3200, 7000, 15000]),
    "salvage": ("SALVAGE CREW", [500, 1100, 2400, 5200, 11000]),
    "autorepair": ("NANO REGEN", [700, 1600, 3600, 8000]),
    "dash": ("PHASE DASH", [500, 1000, 2000, 4200, 9000, 19000]),
    "wave": ("SHOCKWAVE", [250, 420, 650, 1400, 2600]),
    "guns": ("TWIN-LINK GUNS", [600, 1300, 2800, 6000]),
    "overdrive": ("OVERDRIVE", [600, 1200, 2400, 5000, 10500, 22000]),
    "combo": ("KILL COMBO", [800, 1800, 4000, 9000]),
    "missile": ("HOMING MISSILES", [250, 420, 650, 1100, 1800, 3200]),
    "turret": ("AUTO TURRET", [600, 1000, 1600, 3800, 7500, 15000]),
    "reactive": ("REACTIVE ARMOR", [500, 1100, 2200, 4800, 10000]),
    "scan": ("DEEP SCAN", [500, 1100, 2200, 4600, 9500, 20000]),
    "prospect": ("MINING LASER", [700, 1500, 3000, 6200, 13000]),
    "optics": ("LONG OPTICS", [600, 1300, 2800, 6000]),
    "beam": ("TRACTOR BEAM", [700, 1600, 3400, 6500, 12500, 24000, 48000]),
    "silo": ("CARGO SILO", [700, 1500, 3200, 7000, 15000]),
    "refine": ("ORE REFINER", [900, 2000, 4500, 10000]),
    "pulse": ("GRAVITY WELL", [600, 1200, 2400, 4800, 9000, 17000, 32000, 60000]),
    "megahold": ("MEGA HOLD", [800, 1800, 4000, 9000, 20000]),
    "coils": ("MAGNET COILS", [500, 1100, 2400, 5200, 11000]),
}
SPECIALS = {  # statek -> klucze ulepszeń (każdy ma 3 linie)
    "scout": ("repair", "salvage", "autorepair"),
    "interceptor": ("dash", "wave", "guns"),
    "striker": ("overdrive", "missile", "combo"),
    "heavy": ("turret", "missile", "reactive"),
    "surveyor": ("scan", "prospect", "optics"),
    "harvester": ("beam", "silo", "refine"),
    "hauler": ("pulse", "megahold", "coils"),
}
SPECIAL_ROWS = {key: dict(key=key, name=n, costs=scaled(c, COST_MULT)) for key, (n, c) in SPECIAL_DEFS.items()}
ALL_UPGRADE_COSTS = {u["key"]: u["costs"] for u in UPGRADES}
ALL_UPGRADE_COSTS.update({k: r["costs"] for k, r in SPECIAL_ROWS.items()})

# --- Scout: Field Repair
REPAIR_CD = (60.0, 45.0, 30.0, 20.0, 16.0, 12.0, 9.0)
REPAIR_N = (1, 1, 2, 3, 3, 4, 5)        # poziom 5+: dodatkowo chwila nietykalności
SALVAGE_BONUS = 0.20                    # Salvage Crew (Scout): dodatek do łupów z asteroid na poziom
AUTOREPAIR_SECS = (0.0, 40.0, 30.0, 20.0, 12.0)   # Nano Regen (Scout): co ile s wraca 1 ładunek tarczy
# --- Interceptor: Phase Dash (poziom 2 = taranowanie, 3 = dłuższy dash) i Shockwave (poziom 4/5 = kilka uderzeń)
DASH_CD = (3.5, 2.6, 2.2, 1.8, 1.6, 1.4, 1.2)
DASH_SPEED_MULT = (1.0, 1.0, 1.0, 1.3, 1.3, 1.3, 1.5)
DASH_RAM_DMG = 8
DASH_TRAIL_DMG = 3         # poziom 4: sunąca za dashem smuga rani asteroidy
GUNS_BONUS = 0.07          # Twin-Link Guns (Interceptor): o tyle mniejsza kara do szybkostrzelności na poziom
WAVE_RADIUS = [320, 400, 480, 480, 520]
WAVE_COOLDOWN = [18.0, 14.0, 10.0, 10.0, 9.0]
WAVE_DAMAGE = [8, 12, 16, 16, 18]
WAVE_PULSES = [1, 1, 1, 2, 3]
# --- Striker: Overdrive
OVERDRIVE_SECS = (6.0, 8.0, 10.0, 10.0, 12.0, 14.0, 16.0)
OVERDRIVE_CD = (30.0, 30.0, 24.0, 24.0, 20.0, 18.0, 15.0)
OVERDRIVE_CAP = 20.0       # poziom 3: każde zabójstwo wydłuża Overdrive, ale do tylu sekund
COMBO_MAX = (0, 4, 8, 12, 20)   # Kill Combo (Striker): maks. liczba stosów, każdy +5% szybkostrzelności
COMBO_STEP = 0.05
COMBO_FRAMES = 150              # ile klatek bez zabójstwa gasi combo
# --- rakiety (Bruiser i Striker): więcej rakiet, a na 6. poziomie bomby kasetowe
MISSILE_N = (1, 2, 3, 4, 5, 5)
CLUSTER_LEVEL = 6
CLUSTER_BOMBLETS = 9
# --- Bruiser: Reactive Armor
REACTIVE_R = (240, 320, 400, 480, 560, 640)
REACTIVE_DMG = (6, 10, 14, 20, 28, 40)   # poziom 4+: odrzut asteroid, poziom 5: 30% szansy na zwrot ładunku tarczy
# --- Surveyor: Deep Scan
SCAN_SECS = (20.0, 30.0, 30.0, 30.0, 40.0, 40.0, 60.0)
SCAN_CD = (45.0, 35.0, 35.0, 30.0, 25.0, 20.0, 15.0)
SCAN_MULTS = (2.0, 2.0, 2.0, 3.0, 3.0, 4.0, 4.0)   # poziom 4: etykiety z ilością surowca, 5: +2 ore/trafienie podczas skanu, 6: 3x łupy
OPTICS_BONUS = 0.25        # Long Optics (Surveyor): dodatek do zasięgu pocisków na poziom
# --- Harvester: traktor-beamy
BEAM_N = (1, 1, 2, 3, 3, 4, 5, 6)
BEAM_POWER = (1.0, 1.6, 1.6, 2.0, 2.4, 2.4, 2.8, 3.2)
BEAM_RANGE_MULT = (1.0, 1.3, 1.3, 1.5, 1.7, 1.7, 2.0, 2.3)
BEAM_YIELD = (1.0, 1.25, 1.25, 1.5, 1.75, 1.75, 2.0, 2.5)
SILO_BONUS = 0.20          # Cargo Silo (Harvester): dodatek do ładowni na poziom
REFINE_CHANCE = (0.0, 0.25, 0.5, 0.75, 1.0)   # Ore Refiner: część iron z beamów zamienia się w titanium
COILS_BONUS = 0.35         # Magnet Coils (Hauler): dodatek do zasięgu magnesu na poziom
# --- Hauler: Gravity Well
WELL_R = (1600, 1900, 2200, 2500, 3000, 3400, 3800, 4200, 4800)
WELL_SECS = (2.5, 3.0, 3.5, 4.0, 5.0, 5.5, 6.0, 6.5, 7.5)
WELL_CD = (10.0, 9.0, 8.0, 7.0, 6.0, 5.5, 5.0, 4.5, 4.0)
WELL_CRUSH = (5, 8, 12, 16, 24, 32, 44, 60, 90)
WELL_KNOCK = 14.0          # prędkość odrzutu asteroid, gdy studnia się kończy
MEGAHOLD_BONUS = 0.20      # Mega Hold (Hauler): dodatek do pojemności ładowni na poziom

# automatyczne działko (tylko Bruiser)
TURRET_COOLDOWN = (0.55, 0.38, 0.24, 0.24, 0.20, 0.16)   # poziom 5: dwie lufy, poziom 6: rakiety kasetowe
TURRET_RANGE = (520, 580, 640, 700, 760, 820)
TURRET_MISSILE_CD = 2.4    # poziom 4: działko dodatkowo wystrzeliwuje salwy rakiet samonaprowadzających

# rozbudowa bazy: koszt w SUROWCACH, wpłacany z ładunku przy lądowaniu i z dostaw dronów
BASE_MODULES = [
    dict(key="drill", name="DRILL RIGS", costs=scaled_build([
        {"iron": 20}, {"iron": 35}, {"iron": 55}, {"iron": 80, "crystal": 5}, {"iron": 110, "crystal": 10},
        {"iron": 150, "crystal": 20}, {"iron": 200, "crystal": 30}, {"iron": 260, "crystal": 45}])),
    dict(key="refinery", name="REFINERY", costs=scaled_build([
        {"crystal": 10}, {"crystal": 18}, {"crystal": 30}, {"crystal": 45, "gold": 4}, {"crystal": 70, "gold": 8}])),
    dict(key="vault", name="VAULT", costs=scaled_build([
        {"gold": 6}, {"gold": 10}, {"gold": 16}, {"gold": 24}, {"gold": 36}, {"gold": 50}])),
]


def raw_build(costs):
    """Koszty w surowcach bez mnożnika BUILD_MULT (zera są pomijane)."""
    return [{k: n for k, n in c.items() if n > 0} for c in costs]


# ulepszenia planety-bazy: płacisz kredytami (przy starcie projektu) i surowcami (z ładunku i dostaw dronów)
BASE_MODULES += [
    dict(key="scanner", name="SCANNER ARRAY", costs=raw_build([
        {"titanium": 300}, {"titanium": 600}, {"titanium": 1100}, {"titanium": 1800}, {"titanium": 3000}]),
         credits=[15000, 40000, 100000, 250000, 600000]),
    dict(key="trade", name="TRADE HUB", costs=raw_build([
        {"emerald": 120}, {"emerald": 250}, {"emerald": 500}, {"emerald": 900}, {"emerald": 1500}]),
         credits=[30000, 80000, 200000, 500000, 1200000]),
    dict(key="shield", name="SHIELD GRID", costs=raw_build([
        {"plasma": 60}, {"plasma": 160}, {"plasma": 400}]),
         credits=[80000, 300000, 900000]),
    dict(key="warp", name="WARP BEACON", costs=raw_build([
        {"voidium": 30, "plasma": 40}, {"voidium": 80, "plasma": 100}, {"voidium": 200, "plasma": 250}]),
         credits=[150000, 500000, 1500000]),
    dict(key="engine", name="ENGINE LAB", costs=raw_build([
        {"titanium": 500}, {"titanium": 1000, "plasma": 40}, {"titanium": 2000, "plasma": 100},
        {"titanium": 3500, "plasma": 220}]),
         credits=[60000, 160000, 420000, 1000000]),
    dict(key="ring", name="ORBITAL RING", costs=raw_build([
        {"voidium": 150, "plasma": 200, "emerald": 300}, {"voidium": 400, "plasma": 500, "emerald": 800},
        {"voidium": 1000, "plasma": 1200, "emerald": 2000}]),
         credits=[1000000, 3500000, 10000000]),
]
TRADE_BONUS = 0.10         # Trade Hub: dodatek do ceny sprzedaży na poziom
SCANNER_BONUS = 0.20       # Scanner Array: dodatek do zasięgu minimapy na poziom
ENGINE_BONUS = 0.08        # Engine Lab: dodatek do mocy i prędkości silników na poziom
RING_MULT = (1, 2, 4, 8)   # Orbital Ring: mnożnik pasywnego dochodu
DRILL_INCOME = (0, 15, 30, 50, 80, 120, 170, 230, 300)   # kredytów na minutę (poziom 0..8)
REFINERY_BONUS = (0.0, 0.12, 0.24, 0.36, 0.50, 0.65)     # dodatek do ceny sprzedaży surowców
VAULT_MINUTES = (10, 20, 30, 45, 60, 90, 120)            # ile minut dochodu mieści skarbiec

# drony górnicze: kupowane za kredyty, latają same i dostarczają surowce do bazy
DRONE_COSTS = tuple(scaled([1500, 2500, 4000, 6500, 10000, 15000, 22000, 32000, 46000, 65000], DRONE_COST_MULT))
DRONE_TECH_COSTS = tuple(scaled([1200, 2500, 5000, 9000, 16000, 28000], DRONE_COST_MULT))
DRONE_TECH = (  # (sztuk surowca na wyprawę, sekund wyprawy, skład ładunku)
    (72, 60, {"iron": 1.0}),
    (90, 55, {"iron": 1.0}),
    (108, 50, {"iron": 0.7, "crystal": 0.3}),
    (132, 45, {"iron": 0.5, "crystal": 0.4, "gold": 0.1}),
    (156, 40, {"iron": 0.3, "crystal": 0.45, "gold": 0.25}),
    (180, 36, {"crystal": 0.2, "gold": 0.3, "titanium": 0.3, "emerald": 0.2}),
    (210, 32, {"gold": 0.2, "titanium": 0.2, "emerald": 0.35, "plasma": 0.25}),
)


def module_by_key(key):
    return next(m for m in BASE_MODULES if m["key"] == key)


META_MULT = {"income": 1.0}   # mnożnik dochodu pasywnego (odświeżany przez refresh_meta w progression.py)


def income_rate(base):
    """Pasywny dochód (kredytów/min): Drill Rigs razy mnożnik Orbital Ring."""
    return int(round(DRILL_INCOME[base["drill"]] * RING_MULT[base["ring"]] * META_MULT["income"]))


def vault_cap(base):
    return income_rate(base) * VAULT_MINUTES[base["vault"]]


def sale_mult(base):
    return 1.0 + REFINERY_BONUS[base["refinery"]] + TRADE_BONUS * base["trade"]


def short_cr(n):
    return f"{n / 1_000_000:.1f}M".replace(".0M", "M") if n >= 1_000_000 else (f"{n // 1000}K" if n >= 1000 else str(n))


def cost_text(cost):
    return " ".join(f"{ORE[k]['name']} {n}" for k, n in cost.items())


def module_info(key, lvl):
    m = module_by_key(key)
    nxt = ""
    if lvl < len(m["costs"]):
        cr = m.get("credits")
        ore = " ".join(f"{n}{ORE[k]['name'][:3]}" for k, n in m["costs"][lvl].items())
        nxt = "  NEXT: " + (f"{short_cr(cr[lvl])} CR, " if cr else "") + ore
    if key == "drill":
        eff = f"{DRILL_INCOME[lvl]} CR/MIN"
    elif key == "refinery":
        eff = f"ORE PRICE +{int(REFINERY_BONUS[lvl] * 100)}%"
    elif key == "vault":
        eff = f"HOLDS {VAULT_MINUTES[lvl]} MIN OF INCOME"
    elif key == "scanner":
        eff = f"MAP RANGE +{int(SCANNER_BONUS * 100 * lvl)}%"
    elif key == "trade":
        eff = f"ORE PRICE +{int(TRADE_BONUS * 100 * lvl)}% MORE"
    elif key == "shield":
        eff = f"+{lvl} SHIELD FOR ALL SHIPS"
    elif key == "warp":
        eff = "LOCKED" if lvl == 0 else f"[H] {lvl} WARP{'S' if lvl > 1 else ''} PER TRIP"
    elif key == "engine":
        eff = f"ENGINES +{int(ENGINE_BONUS * 100 * lvl)}%"
    else:
        eff = f"INCOME X{RING_MULT[lvl]}"
    return eff + nxt


def mix_text(mix):
    return "+".join(ORE[k]["name"] for k in ORE_KINDS if mix.get(k, 0) > 0)


def fire_rate_of(level):
    return max(MIN_FIRE_RATE, round(0.4 - FIRE_STEP * level, 2))


def engine_of(level):
    return 2.0 + 0.5 * level


def missile_of(level):
    """(liczba rakiet w salwie, czas przeładowania w s) dla poziomu 1..6."""
    level = max(1, min(len(MISSILE_N), level))
    return MISSILE_N[level - 1], max(1.6, 4.0 - 0.4 * level)


def upgrade_info(key, lvl, owned=()):
    """Opis ulepszeń wspólnych dla wszystkich statków."""
    if key == "cargo":
        nxt = CARGO_CAP[min(lvl + 1, len(CARGO_CAP) - 1)]
        return f"HOLDS {CARGO_CAP[lvl]} UNITS" + (f" (NEXT {nxt})" if lvl < len(CARGO_CAP) - 1 else "")
    if key == "fire":
        return f"{fire_rate_of(lvl):.2f}S BETWEEN SHOTS"
    if key == "engine":
        return f"THRUST {engine_of(lvl):.1f}"
    if key == "double":
        return "TWIN CANNONS: ACTIVE" if lvl else "FIRE TWO BULLETS AT ONCE"
    if key == "shield":
        n = max(lvl, 1)
        return f"{n} HIT{'S' if n > 1 else ''} ABSORBED PER TRIP" + ("" if lvl else "  (NEXT)")
    return ""


def special_value(key, lvl):
    """Krótki opis skutków ulepszenia na danym poziomie (do wyświetlenia 'teraz > następny')."""
    if key == "repair":
        return f"+{REPAIR_N[lvl]} SHIELD /{REPAIR_CD[lvl]:.0f}S" + (" +SAFE" if lvl >= 5 else "")
    if key == "salvage":
        return f"+{int(SALVAGE_BONUS * 100 * lvl)}% ROCK LOOT"
    if key == "autorepair":
        return "OFF" if lvl == 0 else f"1 SHIELD EVERY {AUTOREPAIR_SECS[lvl]:.0f}S"
    if key == "dash":
        return (f"CD {DASH_CD[lvl]:.1f}S" + (" RAM" if lvl >= 2 else "") + (" TRAIL" if lvl >= 4 else "")
                + (" X2" if lvl >= 5 else "") + (" STRIKE" if lvl >= 6 else ""))
    if key == "wave":
        if lvl == 0:
            return "LOCKED"
        i = lvl - 1
        return f"{WAVE_PULSES[i]}X R{WAVE_RADIUS[i]} DMG{WAVE_DAMAGE[i]} /{WAVE_COOLDOWN[i]:.0f}S"
    if key == "guns":
        return f"FIRE DELAY X{1.25 - GUNS_BONUS * lvl:.2f}"
    if key == "overdrive":
        return (f"{OVERDRIVE_SECS[lvl]:.0f}S /{OVERDRIVE_CD[lvl]:.0f}S CD" + (" KILLS" if lvl >= 3 else "")
                + (" MSL" if lvl >= 4 else "") + (" SAFE" if lvl >= 5 else "") + (" X3" if lvl >= 6 else ""))
    if key == "combo":
        return "OFF" if lvl == 0 else f"MAX {COMBO_MAX[lvl]} STACKS, +5% EACH"
    if key == "missile":
        if lvl == 0:
            return "LOCKED"
        n, cd = missile_of(lvl)
        return f"{n} MISSILE{'S' if n > 1 else ''} /{cd:.1f}S" + (" CLUSTER" if lvl >= CLUSTER_LEVEL else "")
    if key == "turret":
        if lvl == 0:
            return "LOCKED"
        i = lvl - 1
        return (f"{1 / TURRET_COOLDOWN[i]:.1f}/S R{TURRET_RANGE[i]}" + (" +MSL" if lvl >= 4 else "")
                + (" TWIN" if lvl >= 5 else "") + (" CLUSTER" if lvl >= 6 else ""))
    if key == "reactive":
        return f"BLAST R{REACTIVE_R[lvl]} DMG{REACTIVE_DMG[lvl]}" + (" PUSH" if lvl >= 4 else "") + (" REFUND" if lvl >= 5 else "")
    if key == "scan":
        drops = " 3X DROPS" if lvl >= 6 else (" 2X DROPS" if lvl >= 2 else "")
        return (f"{SCAN_SECS[lvl]:.0f}S X{SCAN_MULTS[lvl]:.0f} /{SCAN_CD[lvl]:.0f}S" + drops
                + (" LABELS" if lvl >= 4 else "") + (" MINE+" if lvl >= 5 else ""))
    if key == "prospect":
        return f"+{1 + lvl} ORE PER HIT"
    if key == "optics":
        return f"BULLET RANGE +{int(OPTICS_BONUS * 100 * lvl)}%"
    if key == "beam":
        return f"{BEAM_N[lvl]} BEAM{'S' if BEAM_N[lvl] > 1 else ''} POWER X{BEAM_POWER[lvl]:.1f} R+{int((BEAM_RANGE_MULT[lvl] - 1) * 100)}%"
    if key == "silo":
        return f"CARGO +{int(SILO_BONUS * 100 * lvl)}%"
    if key == "refine":
        return "OFF" if lvl == 0 else f"{int(REFINE_CHANCE[lvl] * 100)}% IRON BECOMES TITANIUM"
    if key == "pulse":
        return f"R{WELL_R[lvl]} {WELL_SECS[lvl]:.1f}S CRUSH{WELL_CRUSH[lvl]} /{WELL_CD[lvl]:.0f}S"
    if key == "megahold":
        return f"CARGO +{int(MEGAHOLD_BONUS * 100 * lvl)}%"
    if key == "coils":
        return f"MAGNET +{int(COILS_BONUS * 100 * lvl)}%"
    return ""


def special_info(key, lvl):
    total = len(SPECIAL_ROWS[key]["costs"])
    cur = special_value(key, lvl)
    if lvl >= total:
        return cur + " (MAX)"
    nxt = special_value(key, lvl + 1)
    txt = f"{cur} > {nxt}"
    return txt if len(txt) <= 46 else f"NEXT: {nxt}"
