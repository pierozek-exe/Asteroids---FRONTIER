"""Stacja jako miejsce do jeżdżenia: pojazd, budynki-miejsca w dzielnicach, przeszkody i kształt stacji.

Pozycje są w jednostkach logiki świata (środek stacji = 0, 0), tak samo jak statek w locie.
Układ dzielnic, budynków i lądowisk jest w station_layout.py (w pikselach obrazka; logika = px / K).
"""
import math

import station_layout as SL
import view
from config import K

USE_RANGE = 70           # o tyle od krawędzi budynku można już wcisnąć ENTER
HQ_R = 85                # centrum dowodzenia w środku stacji
MODULE_R = 32            # moduły bazy (wiertnie, rafinerie...)
PARKED_R = 40            # zaparkowane statki i pojazdy
SHIP_ON_PAD_R = 40       # statek na lądowisku

# miejsca do wciśnięcia ENTER: budynki z station_layout.ITEMS, które mają klucz miejsca
PLACES = {key: (SL.zone_point(zone, dx, dy), r / K) for zone, _, dx, dy, r, key in SL.ITEMS if key}
PLACE_NAMES = {"hangar": "HANGAR", "garage": "GARAGE", "workshop": "WORKSHOP", "lab": "R&D LAB",
               "mission": "MISSION CONTROL", "gate": "JUMP GATE", "hq": "COMMAND CENTER", "ship": "LAUNCH"}


def px(p):
    return p[0] / K, p[1] / K


PLACE_XY = {key: px(p) for key, (p, _) in PLACES.items()}
PLACE_R = {key: r for key, (_, r) in PLACES.items()}
# stałe przeszkody: wszystkie budynki i dekoracje dzielnic
ITEM_OBSTACLES = [(*px(SL.zone_point(zone, dx, dy)), r / K) for zone, _, dx, dy, r, _ in SL.ITEMS]
SHIP_SPOTS = [px(SL.zone_point("hangar", dx, dy)) for dx, dy in SL.SHIP_SPOTS]
VEHICLE_SPOTS = [px(SL.zone_point("garage", dx, dy)) for dx, dy in SL.VEHICLE_SPOTS]


def walkable(x, y, r):
    """Czy pojazd o promieniu r (logika) mieści się w tym miejscu na stacji (nie wystaje w kosmos)."""
    return SL.on_station(x * K, y * K, margin=r * K)


# --- kształt stacji dla statku w locie: koło centrum, prostokąty dzielnic, mosty jako kapsuły ---
_CORE = SL.CORE_R / K
_ZONES = [((z["cx"] - z["w"] / 2) / K, (z["cy"] - z["h"] / 2) / K, (z["cx"] + z["w"] / 2) / K,
           (z["cy"] + z["h"] / 2) / K) for z in SL.ZONES.values()]
_BRIDGES = [(x0 / K, y0 / K, x1 / K, y1 / K) for x0, y0, x1, y1 in SL.bridges()]
_BRIDGE_HALF = SL.BRIDGE_W / 2 / K


def hull_push(x, y, r):
    """Jeśli koło (x, y, r) wchodzi w stację, zwraca (nowe_x, nowe_y, nx, ny) - wypchnięte na zewnątrz; inaczej None."""
    hit = None
    d = math.hypot(x, y) or 1.0
    if d < _CORE + r:
        nx, ny = x / d, y / d
        x, y, hit = nx * (_CORE + r), ny * (_CORE + r), (nx, ny)
    for x0, y0, x1, y1 in _ZONES:
        cx, cy = min(max(x, x0), x1), min(max(y, y0), y1)
        dx, dy = x - cx, y - cy
        dd = math.hypot(dx, dy)
        if dd >= r:
            continue
        if dd > 1e-6:
            nx, ny = dx / dd, dy / dd
        else:   # środek w środku prostokąta: wypchnij najkrótszą drogą
            opts = [(x - x0, -1, 0), (x1 - x, 1, 0), (y - y0, 0, -1), (y1 - y, 0, 1)]
            _, nx, ny = min(opts)
            cx, cy = (x0 if nx < 0 else x1 if nx > 0 else x), (y0 if ny < 0 else y1 if ny > 0 else y)
        x, y, hit = cx + nx * r, cy + ny * r, (nx, ny)
    for x0, y0, x1, y1 in _BRIDGES:
        vx, vy = x1 - x0, y1 - y0
        t = max(0.0, min(1.0, ((x - x0) * vx + (y - y0) * vy) / (vx * vx + vy * vy)))
        qx, qy = x0 + vx * t, y0 + vy * t
        dx, dy = x - qx, y - qy
        dd = math.hypot(dx, dy) or 1e-6
        lim = _BRIDGE_HALF + r
        if dd < lim:
            nx, ny = dx / dd, dy / dd
            x, y, hit = qx + nx * lim, qy + ny * lim, (nx, ny)
    return None if hit is None else (x, y, hit[0], hit[1])


class Rover:
    """Pojazd naziemny: W/S gaz i wsteczny, A/D obrót (jak czołg), bez poślizgu bokiem. spec = wpis z VEHICLES."""

    def __init__(self, x, y, angle, spec):
        self.x, self.y, self.angle = x, y, angle
        self.spec = spec
        self.R = spec["radius"]
        self.v = 0.0              # prędkość wzdłuż kadłuba (ujemna = wstecz)
        self.tread = 0.0          # przesunięcie ogniw gąsienic / bieżnika kół (animacja)

    def update(self, fwd, back, turn, obstacles):
        dt = view.DT_SCALE
        s = self.spec
        if fwd:
            self.v = min(s["speed"], self.v + s["accel"] * dt)
        elif back:
            self.v = max(-s["reverse"], self.v - s["accel"] * dt)
        else:
            self.v *= 0.86 ** dt
            if abs(self.v) < 0.05:
                self.v = 0.0
        if turn:   # skręt; na wstecznym odwrotnie, jak w prawdziwym pojeździe
            self.angle += turn * s["turn"] * dt * (-1 if self.v < -0.3 else 1)
        rad = math.radians(self.angle)
        ox, oy = self.x, self.y
        self.x += math.cos(rad) * self.v * dt
        self.y += math.sin(rad) * self.v * dt
        self.tread += (abs(self.v) * 0.35 + (0.6 if turn else 0.0)) * dt
        self.collide(obstacles)
        if not walkable(self.x, self.y, self.R):   # krawędź platformy: ślizg wzdłuż niej zamiast wypadnięcia w kosmos
            if walkable(self.x, oy, self.R):
                self.y = oy
            elif walkable(ox, self.y, self.R):
                self.x = ox
            else:
                self.x, self.y = ox, oy
            self.v *= 0.4

    def collide(self, obstacles):
        for ox, oy, r in obstacles:
            dx, dy = self.x - ox, self.y - oy
            d = math.hypot(dx, dy) or 1.0
            lim = r + self.R
            if d < lim:
                self.x, self.y = ox + dx / d * lim, oy + dy / d * lim
                self.v *= 0.5
