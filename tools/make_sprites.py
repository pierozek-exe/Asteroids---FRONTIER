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


BUILDINGS = {"drill": b_drill, "refinery": b_refinery, "vault": b_vault, "hq": b_hq, "scanner": b_scanner,
             "trade": b_trade, "shield": b_shield, "warp": b_warp, "engine": b_engine}


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
