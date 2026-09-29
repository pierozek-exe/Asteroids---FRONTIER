"""Generator sprite'ów statków, drona i budynków bazy (pixel-art z cieniowaniem "3D").

Każdy sprite to siatka ASCII: litera = materiał. Symetryczne statki rysujemy tylko w lewej połowie
(kolumna środkowa na końcu wiersza), reszta jest odbijana. Cieniowanie jest liczone automatycznie:
światło z lewej-góry, więc lewa część każdego elementu jest jaśniejsza, prawa ciemniejsza,
górne krawędzie dostają odblask, a dolne cień. Na końcu obrys i (dla budynków) cień rzucony na grunt.

Uruchomienie (nadpisuje pliki w assets_pixel/):
    python tools/make_sprites.py
    python tools/make_sprites.py --preview out.png     # tylko podgląd, powiększony 4x
"""
import math
import random
import sys
from pathlib import Path

import pygame

OUT = Path(__file__).resolve().parent.parent / "assets_pixel"
OUTLINE = (20, 20, 34, 255)
SHADOW = (10, 10, 24, 110)

# rampy kolorów: od najciemniejszego do najjaśniejszego (4 tony)
R = dict(
    steel=[(51, 60, 87), (94, 110, 140), (148, 176, 194), (214, 226, 236)],
    white=[(94, 110, 140), (160, 180, 200), (214, 226, 236), (250, 250, 252)],
    dark=[(26, 28, 44), (41, 46, 70), (58, 68, 96), (82, 94, 124)],
    panel=[(51, 60, 87), (74, 90, 122), (112, 132, 162), (160, 182, 204)],
    glass=[(26, 50, 110), (59, 93, 201), (65, 166, 246), (160, 245, 250)],
    engine=[(26, 28, 44), (51, 60, 87), (94, 110, 140), (148, 176, 194)],
    red=[(93, 39, 93), (137, 44, 70), (177, 62, 83), (226, 98, 104)],
    wine=[(52, 22, 48), (93, 39, 93), (128, 44, 70), (170, 60, 84)],
    orange=[(137, 44, 70), (198, 84, 64), (239, 125, 87), (255, 170, 120)],
    yellow=[(190, 100, 60), (230, 150, 80), (255, 205, 117), (255, 236, 170)],
    blue=[(29, 43, 83), (41, 72, 160), (59, 93, 201), (95, 150, 240)],
    navyblue=[(26, 28, 60), (36, 52, 110), (50, 76, 160), (70, 110, 210)],
    cyan=[(36, 110, 150), (56, 170, 200), (115, 239, 247), (200, 252, 255)],
    green=[(24, 70, 60), (37, 113, 121), (56, 183, 100), (167, 240, 112)],
    purple=[(50, 30, 90), (90, 60, 160), (150, 100, 255), (210, 184, 255)],
    gold=[(130, 70, 40), (200, 130, 50), (255, 205, 117), (255, 245, 200)],
    ground=[(26, 28, 44), (41, 46, 70), (51, 60, 87), (70, 80, 108)],
    concrete=[(58, 68, 96), (100, 116, 146), (140, 160, 182), (186, 202, 216)],
)
FIXED = {"g": None, "r": (239, 70, 80), "y": (255, 225, 120), "l": (180, 255, 250), "o": (255, 150, 60),
         "m": (230, 140, 255)}


def expand(rows, mode):
    """Lewa połowa -> pełny wiersz. mode: 'odd' (kolumna środkowa wspólna), 'even' albo 'full'."""
    if mode == "full":
        return list(rows)
    out = []
    for r in rows:
        out.append(r + (r[:-1][::-1] if mode == "odd" else r[::-1]))
    return out


def render(rows, mats, glow=(115, 239, 247), mode="odd", shadow=False, pad=1):
    """Siatka ASCII -> Surface z cieniowaniem, obrysem i (opcjonalnie) cieniem rzuconym."""
    rows = expand(rows, mode)
    h, w = len(rows), max(len(r) for r in rows)
    rows = [r.ljust(w, ".") for r in rows]
    if shadow:   # budynki: przycinamy puste kolumny/wiersze, żeby grafika była wyśrodkowana na slocie
        cols = [x for x in range(w) if any(r[x] != "." for r in rows)]
        rows = [r[cols[0]:cols[-1] + 1] for r in rows if r.strip(".")]
        h, w = len(rows), len(rows[0])
    sh = 2 if shadow else 0
    surf = pygame.Surface((w + 2 * pad + sh, h + 2 * pad + sh), pygame.SRCALPHA)

    def at(x, y):
        return rows[y][x] if 0 <= x < w and 0 <= y < h else "."

    for y in range(h):
        for x in range(w):
            m = rows[y][x]
            if m == ".":
                continue
            if m == "g":
                col = glow
            elif m in FIXED:
                col = FIXED[m]
            elif m == "s":   # panel słoneczny: siatka ramek i ogniw
                ramp = R["navyblue"]
                col = R["dark"][2] if (x % 3 == 0 or y % 3 == 0) else ramp[2 if (x + y) % 5 else 3]
            else:
                ramp = R[mats[m]]
                # objętość: pozycja w ciągłym odcinku tego samego materiału w wierszu
                L = x
                while at(L - 1, y) == m:
                    L -= 1
                Rr = x
                while at(Rr + 1, y) == m:
                    Rr += 1
                t = 2
                if Rr > L:
                    u = (x - L) / (Rr - L)
                    t += 1 if u < 0.3 else (-1 if u > 0.7 else 0)
                if at(x, y - 1) != m:
                    t += 1
                if at(x, y + 1) == ".":
                    t -= 1
                col = ramp[max(0, min(3, t))]
            surf.set_at((x + pad, y + pad), (*col, 255))

    filled = {(x, y) for y in range(h) for x in range(w) if rows[y][x] != "."}
    for y in range(-1, h + 1):
        for x in range(-1, w + 1):
            if (x, y) in filled:
                continue
            if any((x + dx, y + dy) in filled for dx, dy in ((1, 0), (-1, 0), (0, 1), (0, -1))):
                surf.set_at((x + pad, y + pad), OUTLINE)
    if shadow:   # cień rzucony w prawo-dół (budynki "stoją" na planecie)
        base = surf.copy()
        mask = pygame.mask.from_surface(base)
        for y in range(surf.get_height()):
            for x in range(surf.get_width()):
                if base.get_at((x, y)).a == 0 and 0 <= x - sh < surf.get_width() and 0 <= y - sh < surf.get_height() \
                        and mask.get_at((x - sh, y - sh)):
                    surf.set_at((x, y), SHADOW)
    return surf


# --------------------
# Statki (lewa połowa, ostatnia kolumna = środek)
# --------------------
# ramka: (szerokość, wysokość, x, y) obszaru statku w klatce; wymiary zgodne z SHIP_FX w grze (dysze, płomienie)
SHIPS = {
    "fr_ship.png": dict(frame=(23, 39), at=(0, 6), mats=dict(h="steel", a="red", b="wine", c="glass", d="dark",
                                                               e="engine", p="panel"), glow=(115, 239, 247),
                        bw=21, nozzles=(8, 12), art="""
..........h
..........h
.........hh
.........hc
........hhc
........hcc
........hcc
........hcc
.......hhdc
.......hhhh
.......phhd
......aphhd
.....aaphhh
....aaaphhh
...aaaaphhh
..aaaaaphhh
.aaaaaaphhd
aaaaaaaphhd
abbbrhhhhhh
b....dhhhhd
.....dhhhhd
......dhhhd
......ddddd
.......eee.
.......eee.
"""),
    "fr_ship_interceptor.png": dict(frame=(19, 43), at=(0, 6), mats=dict(h="white", a="blue", b="cyan", c="glass",
                                                                          d="dark", e="engine", p="panel"),
                                    glow=(115, 239, 247), bw=17, nozzles=(7, 9), art="""
........h
........h
........h
.......hh
.......hh
.......hc
.......hc
.......cc
......hcc
......hcc
......hhd
......hhh
.....ahhh
.....ahhd
....aahhd
....abhhh
...aabhhh
...aabhhh
..aaabhhd
..aaabhhd
.aaaaabhh
.aaaabbhh
aaaa.bbhh
aab..bdhh
ab...ddhd
a....ddhd
.....dddd
......eee
......eee
"""),
    "fr_ship_striker.png": dict(frame=(25, 41), at=(0, 6), mats=dict(h="steel", a="red", b="wine", c="glass",
                                                                      d="dark", e="engine", p="panel"),
                                glow=(255, 150, 60), bw=23, nozzles=(9, 13), art="""
...........h
...........h
..........hh
..........ha
..........ha
.........hhc
.........hcc
a........hcc
a........hcc
aa.......hhd
aa.......hhd
aad.....hhhh
aad....ahhhh
aaa...aahhha
aaaa.aaahhha
aaaaaaaahhha
abaaaaaahhhh
abbaaaaahhhd
abbbaaaphhhd
.bbbbaaphhhd
..bbbbbphhhd
...bbbddhhhh
....b..dhhhd
.......ddhhd
.......ddddd
........eee.
........eee.
"""),
    "fr_ship_heavy.png": dict(frame=(35, 42), at=(1, 6), mats=dict(h="steel", a="green", b="green", c="glass",
                                                                    d="dark", e="engine", p="panel"),
                              glow=(167, 240, 112), bw=33, nozzles=(11, 16, 21), art="""
..............hh
.............hhh
..d.........hhcc
..d.........hccc
..d........hhccc
..d........hhddd
.dhd......phhhhh
dhhhd....pphhhhh
dhahd...ppphhhhh
dhhhd..pppphdddd
dhhhhdppppphhhhh
dhhhhhhhhhhhhhhh
dbbbbbbbbbbbbbbb
dhhhhhhhhhhhhhhh
dhhhhpppphhhdddd
dhhhhpppphhhhhhh
dhhhhpppphhhhhhh
dhhhhpppphhhdddd
dhhhhhhhhhhhhhhh
dbbbbbbbbbbbbbbb
dhhhhhdddhhhhhhh
.dhhd...dhhhhhhh
.dhhd...dddddddd
..dd.....eee.eee
.........eee.eee
.........eee.eee
"""),
    "fr_ship_surveyor.png": dict(frame=(23, 41), at=(0, 6), mats=dict(h="white", a="blue", b="cyan", c="glass",
                                                                       d="dark", e="engine", p="panel"),
                                 glow=(167, 240, 112), bw=21, nozzles=(10,), art="""
.......d..g
........d.g
.........dh
........hhh
.......hhhc
.......hhcc
.......hhcc
.......hhcc
.......hhhc
.......phhh
.......phhh
sssss..bhhh
sssss..bhhh
sssssddphhh
sssss..phhh
sssssddbhhh
sssss..bhhh
sssssddphhh
sssss..phhh
sssss..bhhh
.......phhh
.......phhh
........hhh
........ddd
.........dd
.........ee
.........ee
"""),
    "fr_ship_harvester.png": dict(frame=(31, 41), at=(1, 6), mats=dict(h="yellow", a="red", b="dark", c="glass",
                                                                        d="dark", e="engine", p="steel"),
                                  glow=(255, 205, 117), bw=29, nozzles=(10, 14, 18), art="""
..dd..........
..dg..........
..dd........hh
..pp.......hcc
..pp......hccc
..pp......hccc
.dppd.....hhdd
.dpppphhhhhhhh
.dpppphaaaaaaa
dppppphhhhhhhh
dpbbbphhhhhhhh
dppppphaaaaaaa
dpbbbphhhhhhhh
dppppphhhhdddh
dpbbbphaaaaaaa
dppppphhhhhhhh
dpbbbphhhhhhhh
dppppphaaaaaaa
dppppphhhhhhhh
.dppppphhhhhhh
.dhhhhhhhhhhhh
..dddddddddddd
........eee.ee
........eee.ee
........eee.ee
"""),
    "fr_ship_hauler.png": dict(frame=(37, 44), at=(1, 6), mats=dict(h="steel", a="orange", b="yellow", c="glass",
                                                                     d="dark", e="engine", p="panel", x="red",
                                                                     z="green", q="blue"),
                               glow=(255, 205, 117), bw=35, nozzles=(13, 17, 21), art="""
................h
...............hh
..............hhh
.............hhcc
............hhhcc
............hhccc
............hhhdd
...........ahhhhh
.ddddddddd.ahhhhh
.dxxxdbbbd.phhhhh
.dxxxdbbbd.phhhhh
.dxxxdbbbd.phhhhh
.dddddddddddhhhhh
.dzzzdxxxd.phhhhh
.dzzzdxxxd.phhhhh
.dzzzdxxxd.phhhhh
.dddddddddddhhhhh
.dbbbdqqqd.phhhhh
.dbbbdqqqd.phhhhh
.dbbbdqqqd.phhhhh
.dddddddddddhhhhh
.dqqqdzzzd.phhhhh
.dqqqdzzzd.phhhhh
.dqqqdzzzd.phhhhh
.dddddddddddhhhhh
..........dhhhhhh
..........ddddddd
...........eee.ee
...........eee.ee
"""),
}

DRONE = dict(mats=dict(h="yellow", a="orange", c="glass", d="dark", e="engine"), art="""
.....h
....hc
....hc
...ahh
d.aahh
daahhh
dahhhd
daahhh
d..ahd
....dd
....ee
....ee
""")


def ship_frames(spec):
    """Dwie klatki: 0 = statek, 1 = statek z małymi płomieniami (animacja w hangarze)."""
    fw, fh = spec["frame"]
    body = render(spec["art"].strip("\n").split("\n"), spec["mats"], spec["glow"])
    sheet = pygame.Surface((fw * 2, fh), pygame.SRCALPHA)
    ox = (fw - body.get_width()) // 2
    oy = spec["at"][1]
    for i in range(2):
        sheet.blit(body, (i * fw + ox, oy))
    bottom = oy + body.get_height()
    # płomienie w klatce 1: pod każdą dyszą; n i szerokość kadłuba jak w SHIP_FX (środek kadłuba = środek klatki)
    for n in spec["nozzles"]:
        x = fw + round((fw - 1) / 2 + n - (spec["bw"] - 1) / 2)
        for dy, cols in enumerate(((255, 245, 200), (255, 205, 117), (239, 125, 87), (177, 62, 83))):
            w_ = 1 if dy >= 2 else 3
            for dx in range(-(w_ // 2), w_ // 2 + 1):
                sheet.set_at((x + dx, bottom - 1 + dy), (*cols, 255))
    return sheet


# --------------------
# Budynki bazy: rysowane proceduralnie z brył (skrzynie, walce, kule, czasze) z oświetleniem Lamberta.
# Widok 3/4 z góry: skrzynia ma jasny dach i ciemniejszą ścianę frontową. Każda bryła dostaje
# własny obrys, więc elementy czytelnie się rozdzielają; na końcu cały budynek rzuca cień w prawo-dół.
# --------------------
_L = (-0.5, -0.62, 0.6)
_ln = math.sqrt(sum(c * c for c in _L))
LIGHT = tuple(c / _ln for c in _L)
EDGE = OUTLINE[:3]
RED_LAMP = (239, 70, 80)
CYAN_LAMP = (180, 255, 250)


def tone_of(n, bias=0.0):
    d = n[0] * LIGHT[0] + n[1] * LIGHT[1] + n[2] * LIGHT[2] + bias
    return 0 if d < 0.12 else (1 if d < 0.45 else (2 if d < 0.78 else 3))


class Painter:
    def __init__(self):
        self.px = {}
        self.anchors = {}   # nazwane punkty (lampki, komin...) -> przesunięcie od środka obrazka w grze

    def put(self, pts, outline=True):
        """pts: {(x, y): kolor}. Obrys (4-sąsiedztwo) jest rysowany pod kształtem."""
        if outline:
            for (x, y) in pts:
                for dx, dy in ((1, 0), (-1, 0), (0, 1), (0, -1)):
                    q = (x + dx, y + dy)
                    if q not in pts:
                        self.px[q] = EDGE
        self.px.update(pts)

    def rect(self, x, y, w, h, col):
        self.px.update({(i, j): col for i in range(x, x + w) for j in range(y, y + h)})

    def dot(self, x, y, col):
        self.px[(x, y)] = col

    def line(self, x0, y0, x1, y1, col, outline=False):
        n = max(abs(x1 - x0), abs(y1 - y0), 1)
        pts = {(round(x0 + (x1 - x0) * t / n), round(y0 + (y1 - y0) * t / n)): col for t in range(n + 1)}
        self.put(pts, outline)

    def box(self, x, y, w, h, d, front, top=None, outline=True):
        """Skrzynia: dach (w x d) na górze, ściana frontowa (w x h) pod nim."""
        tp, fr = R[top or front], R[front]
        pts = {}
        for j in range(d):
            for i in range(w):
                t = 3 if (j == 0 or i == 0) else 2
                if i == w - 1:
                    t = 2 if j == 0 else 1
                pts[(x + i, y + j)] = tp[t]
        for j in range(h):
            for i in range(w):
                t = 2 if i == 0 else (0 if i == w - 1 or j == h - 1 else 1)
                if j == 0 and i < w - 1:
                    t = 2
                pts[(x + i, y + d + j)] = fr[t]
        self.put(pts, outline)

    def cyl(self, cx, y, r, h, ramp, cap=None, outline=True, bands=None):
        """Pionowy walec: pokrywa-elipsa u góry (środek cx, y), korpus wysokości h; bands = {wiersz: rampa}."""
        rp, cp = R[ramp], R[cap or ramp]
        ry = max(1.0, r * 0.45)
        pts = {}
        for j in range(h):
            for i in range(-r, r + 1):
                nx = (i + 0.5) / (r + 1)
                t = tone_of((nx, 0.0, math.sqrt(max(0.0, 1 - nx * nx))), 0.1)
                if j == h - 1:
                    t = max(0, t - 1)
                pts[(cx + i, y + j)] = R[bands[j]][t] if bands and j in bands else rp[t]
        for j in range(-int(ry) - 1, int(ry) + 2):
            for i in range(-r, r + 1):
                if (i / (r + 0.5)) ** 2 + (j / (ry + 0.5)) ** 2 <= 1.0:
                    edge = (i / (r + 0.5)) ** 2 + ((j + 1) / (ry + 0.5)) ** 2 > 1.0
                    pts[(cx + i, y + j)] = cp[2 if edge else 3]
        self.put(pts, outline)

    def sphere(self, cx, cy, r, ramp, squash=1.0, half=False, outline=True, spec=True):
        rp = R[ramp]
        pts = {}
        rs = r + 0.5
        for j in range(-r, r + 1):
            if half and j > 0:
                continue
            for i in range(-r, r + 1):
                u, v = i / rs, j / rs
                if u * u + v * v > 1.0:
                    continue
                n = (u, v, math.sqrt(max(0.0, 1 - u * u - v * v)))
                d = n[0] * LIGHT[0] + n[1] * LIGHT[1] + n[2] * LIGHT[2]
                col = (255, 255, 255) if spec and d > 0.97 else rp[tone_of(n)]
                pts[(cx + i, cy + round(j * squash))] = col
        self.put(pts, outline)

    def dish(self, cx, cy, rx, ry, ramp, outline=True):
        """Czasza wklęsła: światło pada na jej dolną-prawą wewnętrzną część."""
        rp = R[ramp]
        pts = {}
        for j in range(-ry, ry + 1):
            for i in range(-rx, rx + 1):
                u, v = i / (rx + 0.5), j / (ry + 0.5)
                q = u * u + v * v
                if q > 1.0:
                    continue
                t = tone_of((-u, -v, math.sqrt(max(0.0, 1 - q))), 0.15)
                if q > 0.72:   # obręcz
                    t = 3 if (u < 0 and v < 0.3) else 1
                pts[(cx + i, cy + j)] = rp[t]
        self.put(pts, outline)

    def ring(self, cx, cy, rx, ry, col, front=True):
        """Pierścień (elipsa 1 px); front=True: dolna (przednia) połowa, False: tylna."""
        for k in range(360):
            a = math.radians(k)
            if (math.sin(a) >= 0) == front:
                self.px[(cx + round(math.cos(a) * rx), cy + round(math.sin(a) * ry))] = col

    def surface(self, shadow=True):
        xs = [p[0] for p in self.px]
        ys = [p[1] for p in self.px]
        x0, y0 = min(xs), min(ys)
        sh = 2 if shadow else 0
        surf = pygame.Surface((max(xs) - x0 + 1 + sh, max(ys) - y0 + 1 + sh), pygame.SRCALPHA)
        cx, cy = surf.get_width() // 2, surf.get_height() // 2
        self.offsets = {k: (x - x0 - cx, y - y0 - cy) for k, (x, y) in self.anchors.items()}
        for (x, y), col in self.px.items():
            surf.set_at((x - x0, y - y0), (*col[:3], 255))
        if shadow:
            base = surf.copy()
            for (x, y) in self.px:
                q = (x - x0 + sh, y - y0 + sh)
                if base.get_at(q).a == 0:
                    surf.set_at(q, SHADOW)
        return surf


WIN = (255, 205, 117)
WIN_OFF = (41, 46, 70)


def windows(p, x, y, cols, rows, gx=3, gy=3, lit=0.7, seed=1):
    rng = random.Random(seed)
    for j in range(rows):
        for i in range(cols):
            p.rect(x + i * gx, y + j * gy, 2, 2 if gy > 2 else 1, WIN if rng.random() < lit else WIN_OFF)


def b_drill():
    p = Painter()
    p.box(2, 30, 24, 5, 4, "panel", "concrete")
    p.line(21, 32, 15, 5, R["steel"][0])      # tylna noga
    for yy in range(9, 31, 5):                 # poprzeczki kratownicy
        a = (yy - 5) / 27
        xl, xr = round(12 - 6 * a), round(15 + 6 * a)
        p.line(xl, yy, xr, yy, R["steel"][1])
        p.line(xl, yy, round(15 + 6 * min(1.0, a + 5 / 27)), min(32, yy + 5), R["dark"][3])
    p.line(6, 32, 12, 5, R["steel"][2])       # przednia noga
    p.line(13, 6, 13, 34, R["dark"][2])       # przewód wiertniczy
    p.line(14, 6, 14, 34, R["dark"][1])
    p.box(10, 1, 8, 3, 2, "orange", "yellow")  # kabina na szczycie
    p.dot(13, 0, RED_LAMP)                     # lampka (miga w grze)
    p.anchors["lamp"] = (13, 0)
    p.box(17, 24, 8, 6, 3, "orange", "yellow")  # pompa
    p.rect(19, 29, 2, 2, WIN)
    p.box(3, 26, 6, 4, 2, "steel", "concrete")
    for i in range(3, 25):                     # pasy ostrzegawcze
        p.dot(i, 35, R["yellow"][2] if (i // 2) % 2 else R["dark"][0])
    return p


def b_refinery():
    p = Painter()
    p.cyl(33, 3, 2, 26, "steel", "dark", bands={3: "red", 4: "red", 7: "red", 8: "red"})   # komin
    p.anchors["smoke"] = (33, 1)
    p.box(1, 27, 38, 5, 3, "panel", "concrete")
    p.cyl(10, 11, 7, 17, "steel", "white", bands={4: "cyan", 5: "cyan", 11: "cyan", 12: "cyan"})
    p.cyl(23, 15, 5, 13, "steel", "white", bands={4: "orange", 5: "orange"})
    p.rect(17, 21, 2, 2, R["dark"][2])   # rura między zbiornikami
    p.rect(16, 18, 4, 1, R["dark"][1])
    p.box(28, 19, 9, 8, 3, "panel", "concrete")
    windows(p, 30, 24, 3, 1, gx=2)
    p.rect(8, 7, 5, 1, R["red"][2])      # zawór na zbiorniku
    return p


def b_vault():
    p = Painter()
    p.box(1, 9, 30, 12, 5, "steel", "concrete")
    p.sphere(16, 13, 8, "steel", squash=0.55, half=True)
    for i in range(3, 29, 4):            # nity pancerza
        p.dot(i, 16, R["steel"][3])
    p.sphere(16, 21, 5, "gold")          # okrągłe drzwi skarbca
    p.rect(13, 21, 7, 1, R["gold"][0])
    p.rect(16, 18, 1, 7, R["gold"][0])
    p.sphere(16, 21, 1, "dark", spec=False, outline=False)
    for i in range(2, 30):               # pasy ostrzegawcze na dole
        p.dot(i, 26, R["yellow"][2] if (i // 2) % 2 else R["dark"][0])
    p.dot(5, 17, RED_LAMP)
    p.dot(27, 17, RED_LAMP)
    return p


def b_hq():
    p = Painter()
    p.line(12, 4, 12, 22, R["dark"][3], outline=True)   # maszt z lampką
    p.dot(12, 3, RED_LAMP)
    p.anchors["lamp"] = (12, 3)
    p.box(2, 38, 70, 9, 5, "panel", "concrete")         # platforma
    p.box(5, 20, 17, 18, 4, "steel", "concrete")        # lewe skrzydło
    windows(p, 7, 27, 5, 3, seed=3)
    p.line(60, 23, 60, 15, R["dark"][3], outline=True)  # maszt radaru
    p.box(52, 23, 17, 15, 4, "steel", "concrete")       # prawe skrzydło
    windows(p, 54, 30, 5, 2, seed=4)
    p.dish(60, 12, 6, 3, "white")
    p.dot(60, 12, (115, 239, 247))                      # czasza radaru (miga w grze)
    p.anchors["radar"] = (60, 12)
    p.sphere(37, 37, 18, "glass", half=True)            # kopuła centralna
    for a in (-0.6, 0.0, 0.6):                          # żebra kopuły
        for j in range(1, 18):
            x = 37 + round(math.sin(a) * math.sqrt(max(0, 18 * 18 - j * j)))
            p.dot(x, 37 - j, R["glass"][0])
    p.rect(20, 37, 35, 1, R["steel"][3])
    p.rect(33, 42, 8, 5, R["dark"][0])                  # brama
    p.rect(34, 43, 6, 4, (59, 93, 201))
    p.rect(36, 43, 1, 4, R["glass"][3])
    for i in range(4, 71, 4):                           # światła krawędzi platformy
        p.dot(i, 51, (115, 239, 247) if i % 8 else WIN)
    return p


def b_scanner():
    p = Painter()
    p.box(9, 30, 20, 5, 3, "panel", "concrete")
    p.cyl(19, 17, 2, 14, "steel")
    p.box(15, 25, 8, 5, 2, "steel", "concrete")
    p.dish(18, 13, 14, 9, "white")
    p.line(11, 6, 18, 13, R["dark"][2])
    p.line(18, 13, 25, 3, R["dark"][3], outline=True)   # ramię odbiornika
    p.dot(25, 2, CYAN_LAMP)                             # końcówka (miga w grze)
    p.anchors["tip"] = (25, 2)
    p.dot(18, 13, R["dark"][0])
    return p


def b_trade():
    p = Painter()
    p.box(1, 28, 40, 5, 3, "panel", "concrete")
    p.box(4, 10, 34, 18, 4, "steel", "concrete")
    p.box(15, 2, 12, 6, 2, "yellow", "gold")            # szyld z symbolem kredytów
    for x, y in ((20, 4), (21, 4), (22, 4), (20, 5), (21, 6), (22, 7), (20, 8), (21, 8), (22, 8), (21, 3), (21, 9)):
        p.dot(x, y, R["red"][1])
    for j in range(5):                                  # markiza w pasy
        for i in range(3 + (j > 1), 39 - (j > 1)):
            red = ((i - j // 2) // 3) % 2 == 0
            t = 3 if j == 0 else (2 if j < 3 else 1)
            p.dot(i, 14 + j, R["red"][t] if red else R["white"][t])
    for x in (7, 14, 31):                               # witryny
        p.rect(x, 21, 6, 6, R["glass"][1])
        p.rect(x, 21, 2, 3, R["glass"][3])
        p.rect(x + 3, 21, 1, 6, R["glass"][0])
    p.rect(23, 21, 5, 7, R["dark"][0])                  # drzwi
    p.rect(24, 22, 3, 6, R["navyblue"][2])
    p.dot(26, 25, WIN)
    return p


def b_shield():
    p = Painter()
    p.box(5, 31, 22, 5, 3, "panel", "concrete")
    p.cyl(16, 19, 3, 13, "steel", bands={4: "cyan", 8: "cyan"})
    for sx in (-1, 1):   # ramiona emitera
        p.line(16 + 4 * sx, 22, 16 + 10 * sx, 12, R["steel"][2 if sx < 0 else 0], outline=True)
        p.dot(16 + 10 * sx, 11, CYAN_LAMP)
    p.sphere(16, 10, 8, "cyan")                         # rdzeń tarczy
    p.anchors["orb"] = (16, 10)
    return p


def b_warp():
    p = Painter()
    rings = (15, 26, 37)
    for cy in rings:
        p.ring(13, cy, 9, 3, R["purple"][1], front=False)
    p.box(3, 46, 20, 5, 3, "panel", "concrete")
    p.cyl(13, 35, 4, 12, "steel", "concrete")
    p.cyl(13, 8, 2, 28, "steel", "white")
    for cy in rings:
        p.ring(13, cy + 1, 9, 3, R["purple"][2], front=True)
        p.ring(13, cy, 9, 3, R["purple"][3], front=True)
    p.sphere(13, 5, 3, "purple")                         # kryształ na szczycie (błyska w grze)
    p.anchors["tip"] = (13, 5)
    p.rect(8, 50, 3, 1, (230, 140, 255))
    p.rect(16, 50, 3, 1, (230, 140, 255))
    return p


def b_engine():
    p = Painter()
    p.box(1, 25, 40, 5, 3, "panel", "concrete")
    p.line(6, 3, 6, 10, R["dark"][3], outline=True)
    p.dot(6, 2, RED_LAMP)
    p.box(3, 10, 11, 15, 3, "steel", "concrete")        # sterownia
    windows(p, 5, 16, 3, 2, seed=9)
    for x in (20, 30):                                  # wsporniki
        p.line(x, 20, x - 2, 26, R["dark"][2], outline=True)
    pts = {}                                            # silnik: poziomy walec
    for i in range(18, 34):
        for j in range(-5, 6):
            v = (j + 0.5) / 6
            ramp = R["orange"] if 24 <= i <= 26 else R["steel"]
            pts[(i, 16 + j)] = ramp[tone_of((0.0, v, math.sqrt(max(0.0, 1 - v * v))), 0.1)]
    for i in range(34, 38):                             # dysza rozszerzająca się
        r_ = 4 + (i - 34) // 2
        for j in range(-r_, r_ + 1):
            v = (j + 0.5) / (r_ + 1)
            pts[(i, 16 + j)] = R["dark"][tone_of((0.0, v, math.sqrt(max(0.0, 1 - v * v))), 0.2)]
    p.put(pts)
    p.rect(37, 14, 1, 5, (255, 150, 60))
    p.anchors["nozzle"] = (38, 16)
    return p


def hazard(p, x0, x1, y):
    for i in range(x0, x1):
        p.dot(i, y, R["yellow"][2] if (i // 2) % 2 else R["dark"][0])


# --- miejsca na stacji (podjeżdżasz łazikiem i wciskasz ENTER) ---
def b_hangar():
    p = Painter()
    p.box(0, 34, 58, 5, 3, "panel", "concrete")          # płyta
    p.box(3, 8, 52, 24, 6, "steel", "white")             # hala
    for x in range(8, 52, 7):                            # żebra dachu
        p.line(x, 8, x, 13, R["steel"][1])
    p.rect(12, 19, 34, 19, R["dark"][0])                 # wielka brama
    for j in range(20, 38, 3):
        p.rect(13, j, 32, 1, R["dark"][2])
    p.rect(11, 18, 36, 1, R["steel"][3])
    hazard(p, 12, 46, 37)
    p.box(22, 14, 14, 2, 1, "yellow", "gold", outline=False)   # szyld nad bramą
    p.dot(6, 8, RED_LAMP)
    p.dot(51, 8, RED_LAMP)
    p.anchors["lamp"] = (6, 8)
    return p


def b_garage():
    p = Painter()
    p.box(0, 27, 42, 4, 3, "panel", "concrete")
    p.box(3, 8, 36, 18, 5, "steel", "concrete")
    p.box(27, 3, 9, 3, 3, "dark", "panel")               # wentylator na dachu
    p.rect(3, 14, 36, 1, R["orange"][2])                 # pas na elewacji
    for dx in (6, 22):                                   # dwie bramy rolowane
        for j in range(17, 31):
            p.rect(dx, j, 14, 1, R["steel"][1] if j % 2 else R["steel"][0])
    hazard(p, 5, 37, 31)
    p.dot(20, 10, WIN)
    return p


def b_workshop():
    p = Painter()
    p.box(0, 32, 50, 5, 3, "panel", "concrete")
    p.box(2, 13, 32, 19, 5, "steel", "concrete")
    windows(p, 5, 21, 3, 2, seed=11)
    p.rect(19, 23, 12, 12, R["dark"][0])                 # brama warsztatu
    for j in range(24, 35, 2):
        p.rect(20, j, 10, 1, R["dark"][2])
    p.sphere(26, 18, 3, "orange")                        # godło (zębatka)
    p.dot(26, 18, R["dark"][0])
    p.line(40, 5, 40, 34, R["steel"][2], outline=True)   # dźwig
    p.line(26, 5, 48, 5, R["yellow"][2], outline=True)
    p.box(37, 3, 6, 2, 2, "yellow", "gold")
    p.line(46, 6, 46, 15, R["dark"][2])
    p.dot(46, 16, R["steel"][3])
    p.box(42, 27, 7, 5, 3, "orange", "yellow")           # skrzynia z częściami
    p.anchors["weld"] = (31, 30)
    return p


def b_lab():
    p = Painter()
    p.box(0, 34, 46, 5, 3, "panel", "concrete")
    p.box(4, 20, 38, 14, 4, "white", "white")
    windows(p, 7, 27, 7, 1, gx=4, seed=5)
    p.sphere(14, 20, 8, "glass", half=True)              # kopuły laboratoriów
    p.sphere(31, 21, 6, "cyan", half=True)
    p.line(40, 6, 40, 20, R["dark"][3], outline=True)    # antena
    p.dot(40, 5, CYAN_LAMP)
    p.anchors["tip"] = (40, 5)
    return p


def b_mission():
    p = Painter()
    p.box(0, 42, 42, 5, 3, "panel", "concrete")
    p.box(6, 30, 30, 12, 4, "steel", "concrete")
    windows(p, 9, 37, 6, 1, gx=4, seed=7)
    p.cyl(21, 14, 5, 22, "white", bands={3: "cyan", 4: "cyan", 12: "cyan"})   # wieża kontroli
    p.box(12, 7, 19, 5, 3, "steel", "white")             # kabina z oknami dookoła
    for i in range(14, 30, 3):
        p.rect(i, 11, 2, 2, R["glass"][2])
    p.line(21, 1, 21, 7, R["dark"][3], outline=True)
    p.dot(21, 0, RED_LAMP)
    p.anchors["lamp"] = (21, 0)
    p.dish(36, 24, 6, 4, "white")                        # antena talerzowa
    return p


def b_gate():
    p = Painter()
    p.box(2, 46, 44, 5, 3, "panel", "concrete")
    p.box(4, 32, 7, 14, 3, "steel", "concrete")          # pylony
    p.box(37, 32, 7, 14, 3, "steel", "concrete")
    cx, cy, rx, ry = 24, 25, 17, 21
    inner = {}
    for j in range(-ry + 4, ry - 3):                     # wir w środku bramy
        for i in range(-rx + 4, rx - 3):
            u, v = i / (rx - 3.5), j / (ry - 3.5)
            q = u * u + v * v
            if q <= 1.0:
                sw = (math.atan2(v, u) * 3 + q * 9) % math.tau
                inner[(cx + i, cy + j)] = R["purple"][1 + int(sw / math.tau * 3) % 3] if q > 0.15 else FIXED["m"]
    p.put(inner, outline=False)
    ring = {}
    for k in range(720):
        a = k * math.tau / 720
        for t in range(4):
            x, y = cx + round(math.cos(a) * (rx - t)), cy + round(math.sin(a) * (ry - t))
            d = -(math.cos(a) * LIGHT[0] + math.sin(a) * LIGHT[1])
            tone = 3 if (t == 0 and d < -0.3) else (2 if d < 0.2 else 1) if t < 3 else 0
            ring[(x, y)] = R["steel"][tone] if k % 60 < 50 else R["purple"][3]
    p.put(ring)
    p.anchors["core"] = (cx, cy)
    return p


def rover_sheet():
    """Mały łazik gąsienicowy (dziób w górę, jak statki): 3 klatki = przesunięcie ogniw gąsienic."""
    frames = []
    for f in range(3):
        pts = {}
        for y in range(2, 21):                          # gąsienice (4 px szerokości) z ogniwami
            for x in (0, 1, 2, 3, 14, 15, 16, 17):
                if y in (2, 20) and x in (0, 3, 14, 17):
                    continue                            # zaokrąglone końce (koła napędowe)
                seg = (y + f) % 3 == 0
                inner = x in (3, 14)
                col = R["steel"][2 if x in (1, 15) else 1] if seg else R["dark"][1]
                if x in (0, 17):
                    col = R["dark"][2] if seg else R["dark"][0]
                if inner:
                    col = R["steel"][0]
                pts[(x, y)] = col
            if y in (3, 19):                            # piasty kół na końcach gąsienic
                pts[(1, y)] = pts[(15, y)] = R["steel"][3]
                pts[(2, y)] = pts[(16, y)] = R["steel"][2]
        for y in range(3, 20):                          # kadłub
            for x in range(4, 14):
                t = 3 if (x == 4 or y == 3) else (2 if x < 8 else (1 if x < 12 else 0))
                pts[(x, y)] = R["orange"][t]
        for x in range(5, 13):                          # zderzak z przodu
            pts[(x, 2)] = R["steel"][3 if x < 9 else 2]
        for y in range(5, 10):                          # kabina z szybą
            for x in range(5, 13):
                edge = y == 5 or x in (5, 12)
                pts[(x, y)] = R["steel"][2] if edge else R["glass"][3 if (x < 8 and y == 6) else (2 if x < 10 else 1)]
        for x in range(5, 13):                          # pas ostrzegawczy
            pts[(x, 11)] = R["yellow"][2] if (x // 2) % 2 else R["dark"][0]
        for y in range(13, 19):                         # skrzynia ładunkowa
            for x in range(6, 12):
                pts[(x, y)] = R["dark"][1] if (x in (6, 11) or y in (13, 18)) else R["dark"][2 if (x + y) % 2 else 3]
        pts[(5, 1)] = pts[(12, 1)] = FIXED["y"]         # reflektory
        pts[(12, 17)] = RED_LAMP                        # lampka
        p = Painter()
        p.put(pts)
        frames.append(p.surface(shadow=False))
    fw, fh = frames[0].get_size()
    sheet = pygame.Surface((fw * 3, fh), pygame.SRCALPHA)
    for i, fr in enumerate(frames):
        sheet.blit(fr, (i * fw, 0))
    return sheet


BUILDINGS = {"drill": b_drill, "refinery": b_refinery, "vault": b_vault, "hq": b_hq, "scanner": b_scanner,
             "trade": b_trade, "shield": b_shield, "warp": b_warp, "engine": b_engine,
             "hangar": b_hangar, "garage": b_garage, "workshop": b_workshop, "lab": b_lab, "mission": b_mission,
             "gate": b_gate}


# --------------------
# Stacja kosmiczna (baza gracza): widok z góry, ten sam rozmiar co dawna planeta-baza (1068 px, promień 528),
# więc lądowiska, kolizje i sloty budynków w grze pasują bez zmian.
# Strefy od zewnątrz: pierścień dokujący (rura z paneli) -> szczelina z kratownicą -> pokład główny
# (sektory płyt, korytarze-szprychy) -> hub pod centrum dowodzenia. Całość lekko wypukła: światło z lewej-góry,
# przejścia między tonami ditherowane macierzą Bayera (jak na planetach).
# --------------------
BAYER = ((0, 8, 2, 10), (12, 4, 14, 6), (3, 11, 1, 9), (15, 7, 13, 5))
ST_R = 500            # promień okrągłego centrum stacji (station_layout.CORE_R)
RING_IN, RING_OUT = 472, 496   # obręcz-chodnik wokół pokładu z modułami
DECK_R = 470          # krawędź pokładu głównego
HUB_R = 118
DECK_BANDS = (HUB_R, 185, 255, 325, 395, DECK_R)   # granice pierścieni płyt
DECK_SEGS = (18, 26, 34, 42, 50)                    # płyty w każdym pierścieniu
SPOKES = 8
PLATE_KINDS = ("panel", "panel", "panel", "panel", "steel", "steel", "concrete", "solar", "vent", "dark", "dark")


def _lit(nx, ny, nz):
    return nx * LIGHT[0] + ny * LIGHT[1] + nz * LIGHT[2]


def _dither_tone(v, x, y):
    """Ciągła jasność (0..3) -> ton rampy z ditheringiem Bayera na przejściach."""
    base = int(v)
    frac = v - base
    return max(0, min(3, base + (1 if frac * 16 > BAYER[y % 4][x % 4] + 0.5 else 0)))


def station_core():
    """Okrągłe centrum stacji: pokład z płytami i szprychami pod moduły bazy, hub pod centrum dowodzenia, obręcz."""
    size = 2 * 504
    c = size // 2
    rng = random.Random(1320)
    kinds = [[rng.choice(PLATE_KINDS) for _ in range(n)] for n in DECK_SEGS]
    shade = [[rng.uniform(-0.35, 0.35) for _ in range(n)] for n in DECK_SEGS]   # każda płyta trochę inna
    surf = pygame.Surface((size, size), pygame.SRCALPHA)
    ring_mid, ring_half = (RING_IN + RING_OUT) / 2, (RING_OUT - RING_IN) / 2
    spoke_w = 11.0
    lx, ly = LIGHT[0], LIGHT[1]
    for y in range(size):
        dy = y - c + 0.5
        for x in range(size):
            dx = x - c + 0.5
            r = math.hypot(dx, dy)
            if r > ST_R:
                continue
            a = math.atan2(dy, dx) % math.tau
            ux, uy = dx / r if r else 0.0, dy / r if r else 0.0
            s_ = 0.85 * r / ST_R   # wypukłość całej stacji: światło z lewej-góry, cień z prawej-dołu
            nl = math.sqrt(1 + s_ * s_)
            d_ = _lit(ux * s_ / nl, uy * s_ / nl, 1 / nl)
            dome = max(0.0, min(1.0, (d_ - 0.3) / 0.62))   # 0 = najciemniej, 1 = najjaśniej
            col = None
            if r > RING_OUT:                                        # obręcz zewnętrzna
                col = OUTLINE[:3] if r > ST_R - 2 else R["steel"][3 if (ux * LIGHT[0] + uy * LIGHT[1]) > 0.25 else 0]
            elif r > RING_IN:                                       # pierścień dokujący: rura
                s = (r - ring_mid) / ring_half
                d = _lit(ux * s, uy * s, math.sqrt(max(0.0, 1 - s * s)))
                seg = (a / math.tau * 64) % 1.0
                if seg < 0.045 or abs(r - RING_IN) < 1.2 or abs(r - RING_OUT) < 1.2:
                    col = R["dark"][1]
                elif abs(r - ring_mid) < 1.6 and int(a / math.tau * 128) % 2 == 0:
                    col = (255, 205, 117) if int(a / math.tau * 256) % 5 else (180, 255, 250)   # rząd świateł
                else:
                    col = R["steel"][_dither_tone(0.4 + 3.2 * max(0.0, d), x, y)]
            elif r > DECK_R:                                        # szczelina z kratownicą
                strut = (a / math.tau * 96) % 1.0 < 0.18 or (a / math.tau * 16) % 1.0 < 0.06
                col = R["steel"][1] if strut else (R["dark"][1] if (x + y) % 3 == 0 else R["dark"][0])
            else:
                # korytarze-szprychy
                k = round(a / math.tau * SPOKES - 0.5) + 0.5
                sa = k * math.tau / SPOKES
                off = abs(-math.sin(sa) * dx + math.cos(sa) * dy)
                along = math.cos(sa) * dx + math.sin(sa) * dy
                if r > HUB_R and along > 0 and off < spoke_w:
                    if off > spoke_w - 1.5:
                        col = R["dark"][1]
                    elif off < 1.0 and int(r) % 14 < 2:
                        col = (180, 255, 250)                       # lampki na osi korytarza
                    else:
                        col = R["concrete"][_dither_tone(0.7 + 2.1 * dome, x, y)]
                elif r <= HUB_R:                                    # hub pod centrum dowodzenia
                    if abs(r - 100) < 1.5 and int(a / math.tau * 48) % 2 == 0:
                        col = (115, 239, 247)
                    elif abs(r - HUB_R) < 1.5 or abs(r - 92) < 1:
                        col = R["dark"][1]
                    else:
                        col = R["panel"][_dither_tone(0.8 + 2.2 * dome, x, y)]
                else:                                               # pokład: sektory płyt
                    band = next(i for i in range(len(DECK_SEGS)) if r <= DECK_BANDS[i + 1])
                    r0, r1 = DECK_BANDS[band], DECK_BANDS[band + 1]
                    n = DECK_SEGS[band]
                    fa = a / math.tau * n
                    seg = int(fa) % n
                    kind = kinds[band][seg]
                    arc = math.tau * r / n
                    e_start, e_end = fa % 1.0 * arc, (1 - fa % 1.0) * arc   # px od szwów kątowych
                    e_in, e_out = r - r0, r1 - r                            # px od szwów promieniowych
                    edge = min(e_start, e_end, e_in, e_out)
                    # normalna najbliższej krawędzi (na zewnątrz płyty) -> fazka jasna od światła, ciemna od cienia
                    tx, ty = -uy, ux
                    nx, ny = ((-tx, -ty) if edge == e_start else (tx, ty) if edge == e_end
                              else (-ux, -uy) if edge == e_in else (ux, uy))
                    facing = nx * lx + ny * ly > 0
                    base_v = 0.4 + 2.2 * dome + shade[band][seg]
                    if edge < 1.2:
                        col = R["dark"][0]                          # szew między płytami
                    elif edge < 3.0 and kind not in ("vent", "solar"):
                        col = R[kind if kind != "dark" else "panel"][_dither_tone(base_v + (1.1 if facing else -1.0), x, y)]
                    elif kind == "solar":
                        gx, gy = int(min(e_start, e_end)) % 6, int(min(e_in, e_out)) % 6
                        col = R["dark"][1] if (gx == 0 or gy == 0) else R["navyblue"][_dither_tone(0.8 + 1.8 * dome, x, y)]
                    elif kind == "vent":
                        col = R["dark"][0] if int(e_in) % 4 < 2 else R["dark"][_dither_tone(1.0 + 1.6 * dome, x, y)]
                    elif kind == "dark":
                        col = R["dark"][_dither_tone(0.9 + 1.8 * dome + shade[band][seg], x, y)]
                    else:
                        col = R[kind][_dither_tone(base_v - 0.3, x, y)]
                    if col is None:
                        col = R["panel"][1]
            surf.set_at((x, y), (*col[:3], 255))
    # drobne detale: włazy i światła pozycyjne na pierścieniu (czerwone po jednej stronie, zielone po drugiej)
    for i in range(24):
        a = i * math.tau / 24 + 0.13
        px_, py_ = c + math.cos(a) * (RING_OUT - 4), c + math.sin(a) * (RING_OUT - 4)
        lamp = (239, 70, 80) if math.cos(a) < 0 else (120, 255, 140)
        pygame.draw.rect(surf, (*lamp, 255), (round(px_) - 1, round(py_) - 1, 2, 2))
    for _ in range(60):
        a = rng.uniform(0, math.tau)
        rr = rng.uniform(HUB_R + 12, DECK_R - 12)
        px_, py_ = round(c + math.cos(a) * rr), round(c + math.sin(a) * rr)
        pygame.draw.rect(surf, (*R["dark"][0], 255), (px_ - 3, py_ - 2, 6, 4))
        pygame.draw.rect(surf, (*R["steel"][2], 255), (px_ - 2, py_ - 1, 4, 2))
    return surf


# --------------------
# Dekoracje dzielnic (wypiekane w obraz stacji) i duża brama skoku
# --------------------
def d_gantry():
    p = Painter()
    p.box(0, 60, 28, 4, 3, "panel", "concrete")
    p.line(5, 10, 5, 60, R["steel"][2], outline=True)       # nogi wieży
    p.line(21, 10, 21, 60, R["steel"][0], outline=True)
    for y in range(12, 58, 8):                              # kratownica
        p.line(5, y, 21, y + 8, R["dark"][3])
        p.line(21, y, 5, y + 8, R["dark"][2])
    p.line(21, 26, 44, 26, R["steel"][2], outline=True)     # ramię do rakiety
    p.box(1, 4, 25, 6, 3, "orange", "yellow")
    p.dot(13, 2, RED_LAMP)
    return p


def d_tank():
    p = Painter()
    p.box(0, 32, 22, 4, 2, "panel", "concrete")
    p.cyl(11, 8, 9, 26, "white", bands={5: "orange", 6: "orange", 19: "orange"})
    return p


def d_booth():
    p = Painter()
    p.box(0, 10, 38, 14, 4, "steel", "concrete")
    windows(p, 3, 17, 7, 1, gx=5, seed=21)
    p.line(32, 2, 32, 10, R["dark"][3], outline=True)
    p.dot(32, 1, RED_LAMP)
    return p


def d_post():
    p = Painter()
    p.line(2, 1, 2, 15, R["steel"][2], outline=True)
    p.dot(2, 0, WIN)
    p.rect(0, 15, 5, 2, R["dark"][2])
    return p


def d_charger():
    p = Painter()
    p.box(0, 4, 9, 12, 3, "steel", "concrete")
    p.rect(2, 9, 5, 3, (115, 239, 247))
    p.line(8, 12, 12, 16, R["dark"][1])
    return p


def d_crates():
    p = Painter()
    p.box(0, 12, 14, 8, 4, "orange", "yellow")
    p.box(13, 14, 12, 7, 3, "steel", "concrete")
    p.box(4, 2, 12, 8, 4, "yellow", "gold")
    for x in (3, 10):
        p.line(x, 16, x, 22, R["orange"][0])
    return p


def d_engine():
    p = Painter()
    p.box(4, 20, 30, 4, 3, "panel", "concrete")
    pts = {}
    for i in range(2, 30):
        for j in range(-6, 7):
            v = (j + 0.5) / 7
            ramp = R["orange"] if 12 <= i <= 14 else R["steel"]
            pts[(i, 13 + j)] = ramp[tone_of((0.0, v, math.sqrt(max(0.0, 1 - v * v))), 0.1)]
    for i in range(30, 35):
        r_ = 5 + (i - 30) // 2
        for j in range(-r_, r_ + 1):
            v = (j + 0.5) / (r_ + 1)
            pts[(i, 13 + j)] = R["dark"][tone_of((0.0, v, math.sqrt(max(0.0, 1 - v * v))), 0.2)]
    p.put(pts)
    return p


def d_arm():
    p = Painter()
    p.cyl(8, 20, 6, 6, "steel", "dark")
    p.line(8, 19, 16, 6, R["yellow"][2], outline=True)
    p.line(16, 6, 28, 12, R["yellow"][1], outline=True)
    p.sphere(16, 6, 2, "orange")
    p.line(28, 12, 30, 16, R["steel"][2])
    p.line(28, 12, 26, 16, R["steel"][2])
    return p


def d_cradle():
    """Kadłub statku w doku remontowym: rusztowanie, brakujące płyty, żółte ramiona podpór."""
    p = Painter()
    p.box(0, 34, 84, 5, 3, "panel", "concrete")
    for x in (6, 78):
        p.line(x, 4, x, 34, R["steel"][1], outline=True)
        for y in range(8, 34, 6):
            p.line(x - 3, y, x + 3, y, R["dark"][3])
    p.box(12, 10, 60, 18, 6, "steel", "white")
    for x0 in (22, 40, 54):                                 # zdjęte płyty poszycia
        p.rect(x0, 20, 8, 6, R["dark"][0])
        p.rect(x0 + 1, 21, 6, 1, R["orange"][1])
    p.sphere(70, 22, 6, "glass", half=True)
    for x in (20, 60):
        p.line(x, 34, x + 4, 28, R["yellow"][2], outline=True)
    p.dot(42, 8, (255, 245, 200))                           # iskry spawania
    p.dot(43, 7, (255, 205, 117))
    return p


def d_plates():
    p = Painter()
    for i in range(4):
        p.box(0 + i, 14 - i * 3, 40, 2, 3, "steel", "concrete")
    return p


def d_container():
    p = Painter()
    p.box(0, 6, 52, 14, 6, "blue", "navyblue")
    for x in range(3, 50, 5):
        p.line(x, 12, x, 25, R["blue"][0])
    p.rect(44, 13, 5, 10, R["dark"][1])
    return p


def d_dish():
    p = Painter()
    p.box(2, 26, 18, 4, 2, "panel", "concrete")
    p.cyl(11, 16, 2, 11, "steel")
    p.dish(10, 11, 10, 7, "white")
    p.line(10, 11, 16, 3, R["dark"][3], outline=True)
    p.dot(16, 2, CYAN_LAMP)
    return p


def d_biggate():
    """Brama skoku w pełnej skali: pierścień z panelami, pylony, wir w środku."""
    p = Painter()
    cx, cy, rx, ry = 60, 62, 46, 56
    p.box(4, 112, 112, 8, 4, "panel", "concrete")
    p.box(6, 70, 16, 42, 5, "steel", "concrete")
    p.box(98, 70, 16, 42, 5, "steel", "concrete")
    inner = {}
    for j in range(-ry + 8, ry - 7):
        for i in range(-rx + 8, rx - 7):
            u, v = i / (rx - 7.5), j / (ry - 7.5)
            q = u * u + v * v
            if q <= 1.0:
                sw = (math.atan2(v, u) * 3 + q * 11) % math.tau
                inner[(cx + i, cy + j)] = R["purple"][1 + int(sw / math.tau * 3) % 3] if q > 0.08 else FIXED["m"]
    p.put(inner, outline=False)
    ring = {}
    for k in range(1600):
        a = k * math.tau / 1600
        for t in range(8):
            x, y = cx + round(math.cos(a) * (rx - t)), cy + round(math.sin(a) * (ry - t))
            d = -(math.cos(a) * LIGHT[0] + math.sin(a) * LIGHT[1])
            if k % 100 < 8:
                col = R["purple"][3]                            # świecące węzły
            elif t in (0, 7):
                col = R["dark"][1]
            else:
                col = R["steel"][3 if d < -0.35 else (2 if d < 0.25 else 1)]
            ring[(x, y)] = col
    p.put(ring)
    return p


DECOR = {"gantry": d_gantry, "tank": d_tank, "booth": d_booth, "post": d_post, "charger": d_charger,
         "crates": d_crates, "engine": d_engine, "arm": d_arm, "cradle": d_cradle, "plates": d_plates,
         "container": d_container, "dish": d_dish, "biggate": d_biggate}


# --------------------
# Stacja w dzielnicach: centrum + mosty + platformy (układ z station_layout.py)
# --------------------
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
import station_layout as SL   # noqa: E402

ZONE_TEXT = {"launch": "L-1 LAUNCH", "garage": "V-YARD", "hangar": "HANGAR BAY", "workshop": "WORKSHOP",
             "lab": "R&D", "mission": "MISSION CTRL", "gate": "JUMP GATE"}


def _floor(style, lx, ly, w, h, lv, x, y, z):
    """Kolor podłogi dzielnicy w punkcie (lx, ly) od lewego-górnego rogu platformy; lv = oświetlenie 0..1."""
    if style == "launch":
        for px_, py_ in SL.PAD_SPOTS:                       # wymalowane lądowiska
            dx, dy = lx - (w / 2 + px_), ly - (h / 2 + py_)
            d = math.hypot(dx, dy)
            if d < SL.PAD_RADIUS:
                if d > SL.PAD_RADIUS - 5:
                    return R["yellow"][2] if (math.atan2(dy, dx) * 8 / math.pi) % 2 < 1.4 else R["dark"][0]
                if d > SL.PAD_RADIUS - 8:
                    return R["dark"][0]
                if abs(d - 40) < 1.2 and (math.atan2(dy, dx) * 12 / math.pi) % 2 < 1:
                    return R["white"][2]
                if (16 <= abs(dx) <= 23 and abs(dy) <= 27) or (abs(dy) <= 3 and abs(dx) <= 23):
                    return R["yellow"][2]                   # litera H
                return R["dark"][_dither_tone(1.2 + 1.2 * lv, x, y)]
        if lx % 40 < 1 or ly % 40 < 1:
            return R["concrete"][0]
        return R["concrete"][_dither_tone(0.6 + 1.6 * lv, x, y)]
    if style == "garage":
        for sx_, sy_ in SL.VEHICLE_SPOTS:                   # zatoki parkingowe
            dx, dy = abs(lx - (w / 2 + sx_)), abs(ly - (h / 2 + sy_))
            if dx < 32 and dy < 44 and (dx > 29 or dy > 41) and not (dy > 41 and ly > h / 2 + sy_):
                return R["concrete"][3]
        if abs(ly - (h / 2 - 5)) < 1 and (lx // 12) % 2 == 0:
            return R["yellow"][2]                           # pas ruchu
        return R["dark"][_dither_tone(1.0 + 1.4 * lv + (0.3 if (x * 7 + y * 13) % 11 == 0 else 0), x, y)]
    if style == "hangar":
        for sx_, sy_ in SL.SHIP_SPOTS:                      # stanowiska statków
            d = math.hypot(lx - (w / 2 + sx_), ly - (h / 2 + sy_))
            if abs(d - 34) < 1.0:
                return R["yellow"][1]
        if abs(ly - (h / 2 + 65)) < 1 and (lx // 10) % 2 == 0:
            return R["yellow"][2]
        if lx % 32 < 1 or ly % 32 < 1:
            return R["dark"][1]
        return R["panel"][_dither_tone(0.7 + 1.6 * lv, x, y)]
    if style == "workshop":
        e = min(lx, ly, w - lx, h - ly)
        if 10 < e < 20:                                     # pas ostrzegawczy
            return R["yellow"][2] if ((lx + ly) // 8) % 2 else R["dark"][0]
        if (lx + ly) % 4 == 0 and (lx // 4 + ly // 4) % 2 == 0:
            return R["steel"][3]                            # blacha ryflowana
        return R["steel"][_dither_tone(0.4 + 1.5 * lv, x, y)]
    if style == "lab":
        if lx % 22 < 1 or ly % 22 < 1:
            return R["panel"][1]
        if ly % 66 < 1:
            return (56, 170, 200)
        return R["concrete"][_dither_tone(0.8 + 1.4 * lv, x, y)]
    if style == "mission":
        if lx % 72 < 1 or ly % 72 < 1:
            return (37, 113, 121)
        if lx % 24 < 1 or ly % 24 < 1:
            return R["dark"][0]
        return R["dark"][_dither_tone(1.3 + 1.4 * lv, x, y)] if (lx // 24 + ly // 24) % 2 else \
            R["navyblue"][_dither_tone(0.4 + 1.1 * lv, x, y)]
    # gate: ciemna podłoga z fioletowymi okręgami wokół bramy
    d = math.hypot(lx - w / 2, ly - (h / 2 - 20))
    if abs(d % 34 - 17) < 0.9:
        return R["purple"][2 if d < 110 else 1]
    return R["dark"][_dither_tone(0.9 + 1.4 * lv + (0.5 if d < 90 else 0.0), x, y)]


def zone_platform(surf, z, c, font):
    x0, y0 = c + z["cx"] - z["w"] // 2, c + z["cy"] - z["h"] // 2
    w, h = z["w"], z["h"]
    for ly in range(h):
        for lx in range(w):
            wx, wy = x0 + lx - c, y0 + ly - c
            if not SL._in_round_rect(wx, wy, z):
                continue
            # odległość do krawędzi (z zaokrąglonymi narożnikami)
            ex, ey = min(lx, w - 1 - lx), min(ly, h - 1 - ly)
            k = SL.CORNER
            e = (k - math.hypot(k - ex, k - ey)) if (ex < k and ey < k) else min(ex, ey)
            lv = 1 - 0.5 * (lx / w + ly / h)                # platforma jaśniejsza z lewej-góry
            x, y = x0 + lx, y0 + ly
            if e < 1.5:
                col = OUTLINE[:3]
            elif e < 6:
                lit_side = (ex < ey and lx < w / 2) or (ey <= ex and ly < h / 2)
                col = R["steel"][3 if lit_side else 1]      # obrzeże platformy
                if e > 3.5 and (lx + ly) % 18 == 0:
                    col = (115, 239, 247)                   # lampki na obrzeżu
            elif e < 7.5:
                col = R["dark"][0]
            else:
                col = _floor(z["style"], lx, ly, w, h, lv, x, y, z)
            surf.set_at((x, y), (*col[:3], 255))
    label = font.render(ZONE_TEXT[z["key"]], False, R["dark"][0])   # napis wymalowany na podłodze
    label.set_alpha(150)
    surf.blit(label, (x0 + w - label.get_width() - 26, y0 + h - 44))


def bridge(surf, x0, y0, x1, y1):
    dx, dy = x1 - x0, y1 - y0
    L_ = math.hypot(dx, dy)
    ux, uy = dx / L_, dy / L_
    qx, qy = -uy, ux
    hw = SL.BRIDGE_W / 2

    def quad(o0, o1):
        return [(x0 + qx * o0, y0 + qy * o0), (x1 + qx * o0, y1 + qy * o0),
                (x1 + qx * o1, y1 + qy * o1), (x0 + qx * o1, y0 + qy * o1)]

    pygame.draw.polygon(surf, (*OUTLINE[:3], 255), quad(-hw - 2, hw + 2))
    pygame.draw.polygon(surf, (*R["panel"][1], 255), quad(-hw + 4, hw - 4))
    lit = qx * LIGHT[0] + qy * LIGHT[1] < 0                 # która krawędź jest od strony światła
    pygame.draw.polygon(surf, (*R["steel"][3 if lit else 1], 255), quad(-hw, -hw + 4))
    pygame.draw.polygon(surf, (*R["steel"][1 if lit else 3], 255), quad(hw - 4, hw))
    for t in range(0, int(L_), 22):                         # szwy płyt w poprzek mostu
        a = (x0 + ux * t + qx * (-hw + 4), y0 + uy * t + qy * (-hw + 4))
        b = (x0 + ux * t + qx * (hw - 4), y0 + uy * t + qy * (hw - 4))
        pygame.draw.line(surf, (*R["dark"][1], 255), a, b)
        for s in (-hw + 2, hw - 2):
            if t % 44 == 0:
                pygame.draw.rect(surf, (115, 239, 247, 255), (round(x0 + ux * t + qx * s) - 1, round(y0 + uy * t + qy * s) - 1, 2, 2))
    for s in (-12, 12):                                     # linie pasów ruchu
        for t in range(0, int(L_) - 10, 16):
            a = (x0 + ux * t + qx * s, y0 + uy * t + qy * s)
            b = (x0 + ux * (t + 8) + qx * s, y0 + uy * (t + 8) + qy * s)
            pygame.draw.line(surf, (*R["panel"][3], 255), a, b)


def station():
    ext = int(SL.extent()) + 16
    size, c = 2 * ext, ext
    surf = pygame.Surface((size, size), pygame.SRCALPHA)
    font = pygame.font.Font(str(OUT.parent / "assets" / "PressStart2P-Regular.ttf"), 16)
    for x0, y0, x1, y1 in SL.bridges():
        bridge(surf, c + x0, c + y0, c + x1, c + y1)
    for z in SL.ZONES.values():
        zone_platform(surf, z, c, font)
    core = station_core()
    surf.blit(core, core.get_rect(center=(c, c)))
    items = []
    for zone, name, dx, dy, _, _ in SL.ITEMS:
        spr = (DECOR[name] if name in DECOR else BUILDINGS[name])().surface()
        x, y = SL.zone_point(zone, dx, dy)
        items.append((y, spr, c + x, c + y))
    for _, spr, x, y in sorted(items, key=lambda t: t[0]):   # od góry do dołu: bliższe przykrywają dalsze
        surf.blit(spr, spr.get_rect(center=(round(x), round(y))))
    return surf


# --------------------
# Pojazdy naziemne (dziób w górę, 3 klatki animacji kół / gąsienic)
# --------------------
def buggy_sheet():
    frames = []
    for f in range(3):
        pts = {}
        for wy in (4, 12, 20):                              # 6 kół z bieżnikiem
            for x0 in (0, 16):
                for y in range(wy, wy + 5):
                    for x in range(x0, x0 + 4):
                        tread = (y + f) % 2 == 0
                        pts[(x, y)] = R["dark"][2 if tread else 0] if x in (x0 + 1, x0 + 2) else R["dark"][1]
                pts[(x0 + 1 + (x0 > 0), wy + 2)] = R["steel"][2]   # piasta
        for y in range(2, 25):                              # kadłub
            for x in range(4, 16):
                if y < 5 and (x < 6 or x > 13):
                    continue
                t = 3 if (x == 4 or y == 2) else (2 if x < 9 else (1 if x < 14 else 0))
                pts[(x, y)] = R["blue"][t]
        for x in range(6, 14):                              # rama bezpieczeństwa
            pts[(x, 13)] = R["steel"][3 if x < 10 else 2]
        for y in range(7, 12):                              # kabina
            for x in range(6, 14):
                pts[(x, y)] = R["glass"][3 if (x < 9 and y == 8) else (2 if x < 11 else 1)]
        for x in range(3, 17):                              # spojler
            pts[(x, 24)] = R["red"][2 if x < 10 else 1]
        pts[(6, 1)] = pts[(13, 1)] = FIXED["y"]
        pts[(9, 18)] = pts[(10, 18)] = R["cyan"][2]
        p = Painter()
        p.put(pts)
        frames.append(p.surface(shadow=False))
    return _sheet(frames)


def crawler_sheet():
    frames = []
    for f in range(3):
        pts = {}
        for y in range(4, 33):                              # szerokie gąsienice
            for x in list(range(0, 6)) + list(range(22, 28)):
                if y in (4, 32) and x in (0, 5, 22, 27):
                    continue
                seg = (y + f) % 3 == 0
                col = R["steel"][2] if seg else R["dark"][1]
                if x in (0, 27):
                    col = R["dark"][2] if seg else R["dark"][0]
                if x in (5, 22):
                    col = R["steel"][0]
                pts[(x, y)] = col
        for y in range(6, 32):                              # kadłub
            for x in range(6, 22):
                t = 3 if (x == 6 or y == 6) else (2 if x < 12 else (1 if x < 19 else 0))
                pts[(x, y)] = R["yellow"][t]
        for y in range(0, 7):                               # wiertło z przodu
            half = 1 + y // 2
            for x in range(14 - half, 14 + half):
                pts[(x, y)] = R["steel"][3 if (x + y + f) % 3 == 0 else 1]
        for y in range(8, 14):                              # kabina
            for x in range(8, 14):
                pts[(x, y)] = R["glass"][3 if (x < 10 and y == 9) else 2]
        for y in range(18, 30):                             # zbiornik na rudę
            for x in range(9, 19):
                pts[(x, y)] = R["dark"][1] if (x in (9, 18) or y in (18, 29)) else R["orange"][2 if (x + y) % 4 else 3]
        for x in (16, 18):                                  # rury wydechowe
            pts[(x, 9)] = pts[(x, 10)] = R["dark"][0]
        pts[(8, 5)] = pts[(19, 5)] = FIXED["y"]
        pts[(20, 30)] = RED_LAMP
        p = Painter()
        p.put(pts)
        frames.append(p.surface(shadow=False))
    return _sheet(frames)


def _sheet(frames):
    fw = max(f.get_width() for f in frames)
    fh = max(f.get_height() for f in frames)
    sheet = pygame.Surface((fw * len(frames), fh), pygame.SRCALPHA)
    for i, fr in enumerate(frames):
        sheet.blit(fr, (i * fw + (fw - fr.get_width()) // 2, (fh - fr.get_height()) // 2))
    return sheet


def build_all():
    out = {}
    for name, spec in SHIPS.items():
        out[name] = ship_frames(spec)
    d = render(DRONE["art"].strip("\n").split("\n"), DRONE["mats"])
    fw, fh = 13, 18
    sheet = pygame.Surface((fw * 2, fh), pygame.SRCALPHA)
    for i in range(2):
        sheet.blit(d, (i * fw + (fw - d.get_width()) // 2, 3))
    bx = fw + (fw - d.get_width()) // 2 + 1 + 5   # środek dyszy drona w klatce 1
    for dy, col in enumerate(((255, 205, 117), (239, 125, 87))):
        sheet.set_at((bx, 3 + d.get_height() - 1 + dy), (*col, 255))
    out["drone.png"] = sheet
    for key, fn in BUILDINGS.items():
        p = fn()
        out[f"bld_{key}.png"] = p.surface()
        if p.offsets:
            print(f"  {key}: {p.offsets}")
    out["rover.png"] = rover_sheet()
    out["buggy.png"] = buggy_sheet()
    out["crawler.png"] = crawler_sheet()
    if "--no-station" not in sys.argv:   # największa grafika, liczy się kilka sekund
        out["base_station.png"] = station()
    return out


def main():
    pygame.init()
    sprites = build_all()
    if "--preview" in sys.argv:
        path = sys.argv[sys.argv.index("--preview") + 1]
        old = {}
        for name in sprites:
            try:
                old[name] = pygame.image.load(str(OUT / name))
            except (FileNotFoundError, pygame.error):
                pass
        sc = 4
        sheet = pygame.Surface((1500, 1000))
        sheet.fill((40, 42, 62))
        x = y = 10
        row_h = 0
        for name, img in sprites.items():
            pair = [img] + ([old[name]] if name in old and "--no-old" not in sys.argv else [])
            for im in pair:
                im = pygame.transform.scale_by(im, sc)
                if x + im.get_width() > 1490:
                    x, y = 10, y + row_h + 12
                    row_h = 0
                sheet.blit(im, (x, y))
                x += im.get_width() + 6
                row_h = max(row_h, im.get_height())
            x += 20
        pygame.image.save(sheet, path)
        return
    for name, img in sprites.items():
        pygame.image.save(img, str(OUT / name))
        print("zapisano", name, img.get_size())


if __name__ == "__main__":
    main()
