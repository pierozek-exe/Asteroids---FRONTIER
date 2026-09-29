"""Układ stacji: okrągłe centrum (moduły bazy) + dzielnice na platformach połączonych mostami.

Czyste dane i geometria (bez pygame), używane i przez generator grafiki (tools/make_sprites.py), i przez grę,
więc budynki narysowane na obrazku zawsze zgadzają się z kolizjami i miejscami do wciśnięcia ENTER.
Jednostki: piksele obrazka stacji, środek stacji = (0, 0), oś y w dół.
"""
import math

CORE_R = 500             # promień okrągłego centrum (pokład z modułami bazy + obręcz)
DECK_R = 470             # krawędź pokładu z płytami (dalej obręcz-chodnik)
BRIDGE_W = 70            # szerokość mostów
BRIDGE_LEN = 90          # długość mostu między centrum a dzielnicą
CORNER = 26              # zaokrąglenie narożników platform

# (klucz, nazwa, kąt mostu w stopniach (0 = w prawo, 90 = w dół), szerokość, wysokość, styl podłogi)
ZONE_DEFS = [
    ("launch", "LAUNCH COMPLEX", 0, 380, 290, "launch"),
    ("garage", "VEHICLE YARD", 52, 300, 236, "garage"),
    ("hangar", "HANGAR BAY", 104, 340, 256, "hangar"),
    ("workshop", "WORKSHOP SECTOR", 156, 330, 256, "workshop"),
    ("lab", "R&D DISTRICT", 208, 270, 220, "lab"),
    ("mission", "MISSION CONTROL", 260, 250, 230, "mission"),
    ("gate", "JUMP GATE", 312, 260, 260, "gate"),
]


def _edge(w, h, a):
    """Odległość od środka prostokąta do jego krawędzi w kierunku a."""
    c, s = abs(math.cos(a)), abs(math.sin(a))
    return min(w / 2 / c if c > 1e-6 else 1e9, h / 2 / s if s > 1e-6 else 1e9)


ZONES = {}
for key, name, deg, w, h, style in ZONE_DEFS:
    a = math.radians(deg)
    d = CORE_R + BRIDGE_LEN + _edge(w, h, a)
    ZONES[key] = dict(key=key, name=name, angle=a, w=w, h=h, style=style,
                      cx=round(math.cos(a) * d), cy=round(math.sin(a) * d))

# budynki i dekoracje w dzielnicach: (dzielnica, sprite, dx, dy, promień kolizji w px, klucz miejsca albo None)
# sprite = nazwa funkcji w tools/make_sprites.py (BUILDINGS / DECOR); dx, dy względem środka dzielnicy
ITEMS = [
    # start i lądowanie: lądowiska są rysowane w podłodze, tu wieża startowa, zbiorniki i dyspozytornia
    ("launch", "gantry", -158, 22, 22, None),
    ("launch", "tank", 118, -98, 16, None), ("launch", "tank", 150, -98, 16, None),
    ("launch", "booth", -10, -100, 22, None), ("launch", "crates", -130, -95, 16, None),
    ("launch", "post", -168, 125, 8, None), ("launch", "post", 168, 125, 8, None),
    # garaż i plac z pojazdami
    ("garage", "garage", -55, -68, 34, "garage"),
    ("garage", "charger", 72, -80, 10, None), ("garage", "charger", 96, -80, 10, None),
    ("garage", "charger", 120, -80, 10, None), ("garage", "crates", 110, -25, 16, None),
    # hangar i płyta z zaparkowanymi statkami
    ("hangar", "hangar", 0, -80, 42, "hangar"),
    ("hangar", "crates", -125, -85, 16, None), ("hangar", "tank", 128, -85, 14, None),
    # warsztat z placem części
    ("workshop", "workshop", -80, -68, 34, "workshop"),
    ("workshop", "crates", 35, -82, 16, None), ("workshop", "crates", 72, -86, 16, None),
    ("workshop", "engine", 105, -40, 20, None), ("workshop", "arm", 15, -15, 14, None),
    ("workshop", "arm", -40, 30, 14, None), ("workshop", "cradle", 80, 50, 38, None),
    ("workshop", "plates", -100, 20, 20, None), ("workshop", "container", -85, 80, 22, None),
    ("workshop", "tank", -10, 82, 14, None),
    # laboratorium
    ("lab", "lab", -25, -45, 34, "lab"),
    ("lab", "tank", 72, -55, 14, None), ("lab", "tank", 100, -55, 14, None),
    ("lab", "dish", 80, 35, 18, None), ("lab", "tank", -90, 50, 14, None), ("lab", "crates", -10, 55, 16, None),
    # kontrola misji
    ("mission", "mission", 0, -35, 30, "mission"),
    ("mission", "dish", -75, 45, 18, None), ("mission", "dish", 75, 45, 18, None),
    ("mission", "booth", 0, 70, 20, None),
    # brama skoku
    ("gate", "biggate", 0, -15, 62, "gate"),
    ("gate", "post", -100, 100, 8, None), ("gate", "post", 100, 100, 8, None),
]

# lądowiska w kompleksie startowym (px względem środka dzielnicy) i ich promień
PAD_SPOTS = [(-62, 40), (84, 40)]
PAD_RADIUS = 62
# miejsca na zaparkowane statki (hangar) i pojazdy (plac przy garażu)
SHIP_SPOTS = [(-105, 18), (0, 18), (105, 18), (-105, 84), (0, 84), (105, 84)]
VEHICLE_SPOTS = [(-102, 48), (-34, 48), (34, 48), (102, 48)]


def zone_point(zone, dx, dy):
    z = ZONES[zone]
    return z["cx"] + dx, z["cy"] + dy


def pads():
    return [zone_point("launch", dx, dy) for dx, dy in PAD_SPOTS]


def bridges():
    """Mosty: (x0, y0, x1, y1) od obręczy centrum do środka dzielnicy (dalej przykrywa je platforma)."""
    out = []
    for z in ZONES.values():
        a = z["angle"]
        out.append((math.cos(a) * (CORE_R - 20), math.sin(a) * (CORE_R - 20), z["cx"], z["cy"]))
    return out


def extent():
    """Najdalszy punkt stacji od środka (px) - do rozmiaru obrazka i zasięgu auto-lądowania."""
    far = CORE_R
    for z in ZONES.values():
        for sx in (-1, 1):
            for sy in (-1, 1):
                far = max(far, math.hypot(z["cx"] + sx * z["w"] / 2, z["cy"] + sy * z["h"] / 2))
    return far


def _in_round_rect(x, y, z, margin=0.0):
    hw, hh = z["w"] / 2 - margin, z["h"] / 2 - margin
    dx, dy = abs(x - z["cx"]), abs(y - z["cy"])
    if dx > hw or dy > hh:
        return False
    c = max(0.0, CORNER - margin)
    if dx > hw - c and dy > hh - c:
        return math.hypot(dx - (hw - c), dy - (hh - c)) <= c
    return True


def _near_segment(x, y, x0, y0, x1, y1, half):
    vx, vy = x1 - x0, y1 - y0
    L2 = vx * vx + vy * vy or 1.0
    t = max(0.0, min(1.0, ((x - x0) * vx + (y - y0) * vy) / L2))
    return math.hypot(x - (x0 + vx * t), y - (y0 + vy * t)) <= half


def on_station(x, y, margin=0.0):
    """Czy punkt (px) leży na stacji: centrum, most albo platforma dzielnicy (margin = zapas od krawędzi)."""
    if math.hypot(x, y) <= CORE_R - margin:
        return True
    for z in ZONES.values():
        if _in_round_rect(x, y, z, margin):
            return True
    for x0, y0, x1, y1 in bridges():
        if _near_segment(x, y, x0, y0, x1, y1, BRIDGE_W / 2 - margin):
            return True
    return False


def which_zone(x, y):
    for z in ZONES.values():
        if _in_round_rect(x, y, z):
            return z["key"]
    return None
