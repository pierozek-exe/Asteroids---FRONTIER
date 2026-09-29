"""Nieskończony świat: grafika planet, planety z surowcami generowane z seeda, strefy trudności, lądowiska."""
import math
import random

import pygame

from balance import MINE_YIELD
from config import *


# --------------------
# Planety: nieregularny brzeg i wystające kryształy / bryły rudy (dorysowywane do arkusza przy starcie)
# --------------------
PLANET_PAD = 32            # o tyle powiększamy obrazek planety z każdej strony, żeby zmieściły się wystające kryształy
OUTCROP = {  # rampa (ciemny -> jasny), styl: prism = kryształy, shard = cienkie odłamki, chunk = kanciaste bryły
    "iron": ([(93, 39, 60), (160, 70, 50), (239, 125, 87), (255, 190, 140)], "chunk", False),
    "crystal": ([(30, 80, 120), (56, 170, 200), (115, 239, 247), (230, 255, 255)], "prism", False),
    "gold": ([(130, 70, 40), (210, 140, 50), (255, 205, 117), (255, 250, 210)], "chunk", False),
    "titanium": ([(70, 80, 105), (140, 155, 180), (200, 215, 235), (250, 252, 255)], "shard", False),
    "emerald": ([(20, 70, 50), (37, 130, 80), (56, 200, 110), (180, 255, 170)], "prism", False),
    "plasma": ([(90, 30, 90), (170, 60, 160), (230, 100, 210), (255, 200, 250)], "prism", True),
    "voidium": ([(40, 20, 80), (90, 50, 170), (150, 100, 255), (225, 205, 255)], "prism", True),
}
DEAD_RAMP = [(26, 28, 44), (51, 60, 87), (86, 100, 124), (130, 146, 166)]
LIGHT2 = (-0.6, -0.8)      # kierunek światła na arkuszu planet (z lewej-góry)


def _shade(c, f):
    return tuple(max(0, min(255, int(v * f))) for v in c[:3])


def rugged_planet(img, kind, variant, depleted):
    """Zwraca większy obrazek planety: garby i wyszczerbienia na brzegu + klastry kryształów / rudy.
    Kryształy na nocnej stronie planety są przyciemnione (świecące rodzaje świecą zawsze)."""
    rng = random.Random(ORE_KINDS.index(kind) * 31 + variant * 7 + 5)   # deterministycznie: stały wygląd planet
    S = img.get_width() + 2 * PLANET_PAD
    out = pygame.Surface((S, S), pygame.SRCALPHA)
    out.blit(img, (PLANET_PAD, PLANET_PAD))
    c = S / 2
    R = img.get_bounding_rect().width / 2
    ramp, style, glows = OUTCROP[kind]
    if depleted:
        ramp, glows = DEAD_RAMP, False

    def lit(a):
        """Oświetlenie planety w kierunku a: 1 = strona dzienna, 0 = noc."""
        return max(0.0, min(1.0, 0.55 + 0.9 * (math.cos(a) * LIGHT2[0] + math.sin(a) * LIGHT2[1])))

    def sample(a, r):
        x, y = int(c + math.cos(a) * r), int(c + math.sin(a) * r)
        return out.get_at((x, y))

    # 1) nierówny brzeg: promień zmienia się z kątem (suma kilku sinusów), teren "wylewa się" lub zapada
    ph = [rng.uniform(0, math.tau) for _ in range(3)]
    amp = (2.6, 1.8, 1.1)

    def edge(a):
        return R - 1 + amp[0] * math.sin(3 * a + ph[0]) + amp[1] * math.sin(7 * a + ph[1]) + amp[2] * math.sin(15 * a + ph[2])

    src = out.copy()
    n_ang = 1600
    for i in range(n_ang):
        a = i * math.tau / n_ang
        ca, sa = math.cos(a), math.sin(a)
        e = edge(a)
        fill = src.get_at((int(c + ca * (R - 9)), int(c + sa * (R - 9))))
        for r in range(int(R - 7), int(R + 7)):
            p = (int(c + ca * r), int(c + sa * r))
            if r > e:
                out.set_at(p, (0, 0, 0, 0))
            elif src.get_at(p).a == 0 or r > R - 3:
                out.set_at(p, fill)
    for i in range(n_ang):   # obrys nowego brzegu
        a = i * math.tau / n_ang
        r = int(edge(a))
        p = (int(c + math.cos(a) * r), int(c + math.sin(a) * r))
        out.set_at(p, (20, 20, 34, 255))

    def prism(bx, by, a, length, width, shade):
        """Graniastosłup: dwie ściany (oświetlona i w cieniu), grzbiet i jasny czubek."""
        dx, dy = math.cos(a), math.sin(a)
        nx, ny = -dy, dx
        tip = (bx + dx * length, by + dy * length)
        sL = (bx + dx * length * 0.72 + nx * width * 0.5, by + dy * length * 0.72 + ny * width * 0.5)
        sR = (bx + dx * length * 0.72 - nx * width * 0.5, by + dy * length * 0.72 - ny * width * 0.5)
        bL = (bx + nx * width * 0.5, by + ny * width * 0.5)
        bR = (bx - nx * width * 0.5, by - ny * width * 0.5)
        mid = (bx + dx * length * 0.72, by + dy * length * 0.72)
        left_lit = nx * LIGHT2[0] + ny * LIGHT2[1] > 0
        t = lambda i: (*_shade(ramp[max(0, min(3, i))], shade), 255)
        pygame.draw.polygon(out, (20, 20, 34), [bL, sL, tip, sR, bR], 0)
        pygame.draw.polygon(out, (20, 20, 34), [bL, sL, tip, sR, bR], 2)
        pygame.draw.polygon(out, t(2 if left_lit else 1), [bL, sL, tip, mid, (bx, by)])
        pygame.draw.polygon(out, t(1 if left_lit else 2), [(bx, by), mid, tip, sR, bR])
        pygame.draw.line(out, t(3), (bx, by), tip)
        pygame.draw.line(out, t(3), mid, tip, 2 if width > 6 else 1)
        return tip

    def chunk(bx, by, a, size, shade):
        """Kanciasta bryła rudy: nieregularny wielokąt z jasną górną-lewą krawędzią."""
        pts = []
        n = rng.randint(5, 7)
        for i in range(n):
            ang = a + i * math.tau / n + rng.uniform(-0.3, 0.3)
            rr = size * rng.uniform(0.6, 1.0)
            pts.append((bx + math.cos(ang) * rr, by + math.sin(ang) * rr * 0.85))
        t = lambda i: (*_shade(ramp[max(0, min(3, i))], shade), 255)
        pygame.draw.polygon(out, (20, 20, 34), pts, 0)
        pygame.draw.polygon(out, (20, 20, 34), pts, 2)
        inner = [(bx + (x - bx) * 0.85, by + (y - by) * 0.85) for x, y in pts]
        pygame.draw.polygon(out, t(1), inner)
        lit_pts = [(bx + (x - bx) * 0.7 + LIGHT2[0] * size * 0.18, by + (y - by) * 0.7 + LIGHT2[1] * size * 0.18)
                   for x, y in pts]
        pygame.draw.polygon(out, t(2), lit_pts)
        hx, hy = bx + LIGHT2[0] * size * 0.4, by + LIGHT2[1] * size * 0.4
        pygame.draw.circle(out, t(3), (hx, hy), max(1, size * 0.18))
        return hx, hy

    glow_layer = pygame.Surface((S, S), pygame.SRCALPHA) if glows else None
    tips = []
    # 3) klastry na brzegu: sterczą na zewnątrz i łamią okrągły kształt
    n_rim = rng.randint(4, 6)
    base_a = rng.uniform(0, math.tau)
    for i in range(n_rim):
        a = base_a + i * math.tau / n_rim + rng.uniform(-0.35, 0.35)
        shade = 0.4 + 0.6 * lit(a)
        bx, by = c + math.cos(a) * (R - 8), c + math.sin(a) * (R - 8)
        for j in range(rng.randint(3, 4)):
            aa = a + rng.uniform(-0.5, 0.5) * (0.4 if j == 0 else 1.0)
            ox, oy = rng.uniform(-5, 5), rng.uniform(-5, 5)
            if style == "chunk":
                size = rng.uniform(8, 14) * (0.55 if depleted else 1.0)
                tips.append(chunk(bx + ox + math.cos(aa) * size * 0.6, by + oy + math.sin(aa) * size * 0.6, aa, size, shade))
            else:
                length = (rng.uniform(26, 38) if j == 0 else rng.uniform(14, 26)) * (1.0 if style == "prism" else 0.8)
                width = rng.uniform(8, 12) if style == "prism" else rng.uniform(4, 6)
                if depleted:
                    length *= 0.35
                tips.append(prism(bx + ox, by + oy, aa, length, width, shade))
    # 4) mniejsze wychodnie na oświetlonej powierzchni (patrzymy z góry, więc są krótsze)
    for _ in range(rng.randint(2, 3)):
        a = rng.uniform(math.radians(160), math.radians(290))
        r = rng.uniform(0.25, 0.7) * R
        bx, by = c + math.cos(a) * r, c + math.sin(a) * r
        for j in range(rng.randint(2, 3)):
            aa = a + rng.uniform(-0.8, 0.8)
            if style == "chunk":
                tips.append(chunk(bx + rng.uniform(-4, 4), by + rng.uniform(-4, 4), aa, rng.uniform(6, 9), 1.0))
            else:
                tips.append(prism(bx + rng.uniform(-3, 3), by + rng.uniform(-3, 3), aa,
                                  rng.uniform(12, 18) * (0.4 if depleted else 1.0), rng.uniform(6, 8), 1.0))
    if glow_layer is not None:   # poświata świecących kryształów (widoczna także na nocnej stronie)
        col = ramp[2]
        for x, y in tips:
            for rr, al in ((10, 26), (6, 40), (3, 70)):
                pygame.draw.circle(glow_layer, (*col, al), (x, y), rr)
        glow_layer.blit(out, (0, 0))
        out = glow_layer
    return out


class Planet:
    """Mini-planeta z surowcem. Kolejne trafienia wykuwają bryłki, aż zasób się wyczerpie."""

    def __init__(self, x, y, kind, variant, ore, field_r=0.0):
        self.x, self.y = x, y
        self.kind, self.variant = kind, variant
        self.R = RES_R
        self.max_ore = self.ore_left = ore
        self.flash = 0
        self.field_r = field_r   # > 0: wokół planety jest skupisko asteroid o tym promieniu

    @property
    def depleted(self):
        return self.ore_left <= 0

    def hit(self, dmg):
        """Zwraca liczbę wykutych jednostek surowca (trafienie daje MINE_YIELD razy obrażenia)."""
        if self.depleted:
            return 0
        n = min(dmg * MINE_YIELD, self.ore_left)
        self.ore_left -= n
        self.flash = 3
        return n


def planet_kind_for(d, r):
    """Im dalej od bazy, tym cenniejsze surowce: iron -> titanium/crystal -> gold -> emerald -> plasma -> voidium."""
    if d < 8500:
        return "iron"
    if d < 13000:
        return "iron" if r < 0.5 else ("titanium" if r < 0.75 else "crystal")
    if d < 20000:
        return "iron" if r < 0.15 else ("titanium" if r < 0.4 else ("crystal" if r < 0.7 else "gold"))
    if d < 30000:
        return "crystal" if r < 0.25 else ("gold" if r < 0.6 else "emerald")
    if d < 45000:
        return "gold" if r < 0.25 else ("emerald" if r < 0.7 else "plasma")
    return "emerald" if r < 0.25 else ("plasma" if r < 0.65 else "voidium")


class World:
    """Nieskończony świat: mini-planety generowane deterministycznie z 'kafelków' (chunków)."""

    def __init__(self, seed):
        self.seed = seed
        self.cache = {}
        self._near = {}

    def chunk_planet(self, cx, cy):
        key = (cx, cy)
        if key in self.cache:
            return self.cache[key]
        rng = random.Random(((cx * 73856093) ^ (cy * 19349663) ^ (self.seed * 83492791)) & 0xFFFFFFFF)
        px = (cx + 0.15 + 0.7 * rng.random()) * CHUNK   # margines: planety z sąsiednich kafelków się nie stykają
        py = (cy + 0.15 + 0.7 * rng.random()) * CHUNK
        roll, kind_roll = rng.random(), rng.random()
        variant = rng.randrange(2)
        jitter = rng.uniform(0.85, 1.15)
        field_roll, field_size = rng.random(), rng.uniform(1500, 2400)   # losowane na końcu: pozycje planet się nie zmieniają
        d = math.hypot(px, py)
        planet = None
        if d >= PLANET_MIN_D and roll < (0.75 if d < 16000 else 0.5):   # bliżej bazy planet jest więcej
            kind = planet_kind_for(d, kind_roll)
            ore = {"iron": 420, "crystal": 320, "gold": 220, "titanium": 380, "emerald": 200, "plasma": 150,
                   "voidium": 100}[kind] * 6 * jitter * (1 + d / 15000)  # dalej = bogatsze
            planet = Planet(px, py, kind, variant, max(300, int(ore)),
                            field_size if (field_roll < 0.4 and d > SAFE_R + 1200) else 0.0)  # skupisko ma ok. 40% planet
        self.cache[key] = planet
        return planet

    def reset(self):
        self.cache.clear()
        self._near = {}

    def near(self, x, y, span=4):
        cx, cy = int(x // CHUNK), int(y // CHUNK)
        ent = self._near.get(span)
        if ent is None or ent[0] != (cx, cy):
            out = []
            for i in range(cx - span, cx + span + 1):
                for j in range(cy - span, cy + span + 1):
                    p = self.chunk_planet(i, j)
                    if p is not None:
                        out.append(p)
            ent = self._near[span] = ((cx, cy), out)
        return ent[1]


WORLD = World(WORLD_SEED)


def zone_tier(d):
    """-1 = strefa bezpieczna; 0, 1, 2... = kolejne pierścienie coraz twardszych asteroid."""
    if d < SAFE_R:
        return -1
    return int((d - SAFE_R) // TIER_STEP)


def pad_angle(k):
    return PAD_OFFSET + k * (math.tau / N_PADS)


def pad_pos(k):
    a = pad_angle(k)
    return math.cos(a) * PAD_R, math.sin(a) * PAD_R
