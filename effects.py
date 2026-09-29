"""Efekty specjalne: fale uderzeniowe, pierścienie, cząstki, poświata (glow), smugi, odłamki, błyskawice."""
import math
import random

import pygame

import view
from config import *
from entities import silhouette
from view import sp


class Shockwave:
    GROW = 26
    FADE = 8

    def __init__(self, owner, max_r, damage=8, colors=(CYAN, WHITE), style="plain"):
        self.owner = owner
        self.max_r = max_r
        self.damage = damage
        self.colors = colors
        self.style = style           # "plain", "electric" (błyskawice) albo "fire" (iskry)
        self.t = 0
        self.hit = set()
        self.bolts = []              # błyskawice do trafionych asteroid: [x, y, pozostałe klatki]
        self.life = True

    @property
    def x(self):
        return self.owner.x

    @property
    def y(self):
        return self.owner.y

    @property
    def r(self):
        return self.max_r * min(1.0, self.t / self.GROW) ** 0.7

    @property
    def active(self):
        return self.t <= self.GROW

    def update(self):
        self.t += view.DT_SCALE
        for b in self.bolts:
            b[2] -= view.DT_SCALE
        self.bolts = [b for b in self.bolts if b[2] > 0]
        if self.t > self.GROW + self.FADE and not self.bolts:
            self.life = False

    def add_bolt(self, x, y):
        if len(self.bolts) < 14:
            self.bolts.append([x, y, 9])

    def draw(self, canvas):
        r = int(self.r * K)
        cx, cy = sp(self.x, self.y)
        c0, c1 = self.colors
        for bx_, by_, ttl in self.bolts:   # łańcuch błyskawic do trafionych skał
            tx, ty = sp(bx_, by_)
            pts = bolt_points(cx, cy, tx, ty, 10 + ttl, 7)
            pygame.draw.lines(canvas, c0, False, pts, 3 if ttl > 5 else 2)
            pygame.draw.lines(canvas, WHITE, False, pts, 1)
            draw_glow(canvas, tx, ty, 22, c0, 0.5 * ttl / 9)
        if r < 2 or self.t > self.GROW + self.FADE or (not self.active and (self.t // 2) % 2):
            return
        if self.active and self.damage > 0:   # świecące czoło fali
            draw_glow(canvas, cx, cy, r * 1.1, c0, 0.45 * (1 - self.t / self.GROW))
        if self.style == "electric":  # postrzępiony, trzeszczący pierścień z błyskawicami do środka
            jit = 3 if self.active else 1
            outer, inner = [], []
            for deg in range(0, 361, 9):
                a = math.radians(deg)
                ro, ri = r + random.randint(-jit, jit), r - 3 + random.randint(-jit, jit)
                outer.append((cx + math.cos(a) * ro, cy + math.sin(a) * ro))
                inner.append((cx + math.cos(a) * ri, cy + math.sin(a) * ri))
            pygame.draw.lines(canvas, c0, False, outer, 2)
            pygame.draw.lines(canvas, c1, False, inner, 1)
            if self.active:
                for _ in range(7):
                    a = random.random() * math.tau
                    ln = random.randint(6, 16)
                    p1 = (cx + math.cos(a) * r, cy + math.sin(a) * r)
                    p2 = (cx + math.cos(a) * (r - ln) + random.randint(-3, 3), cy + math.sin(a) * (r - ln) + random.randint(-3, 3))
                    pygame.draw.line(canvas, WHITE, p1, p2, 1)
        else:
            pygame.draw.circle(canvas, c0, (cx, cy), r, 2)
            if r > 5:
                pygame.draw.circle(canvas, c1, (cx, cy), r - 3, 1)
            if r > 9 and self.active:
                pygame.draw.circle(canvas, DARK, (cx, cy), r - 6, 1)
        if self.active:  # iskry na obwodzie
            for _ in range(10 if self.style == "fire" else 6):
                a = random.random() * math.tau
                rr = r + random.randint(-2, 4)
                canvas.fill(random.choice((c1, WHITE, YELLOW) if self.style == "fire" else (c1, WHITE)),
                            (cx + math.cos(a) * rr, cy + math.sin(a) * rr, 2, 2))


class FxRing:
    """Pierścień efektu w stałym punkcie świata: rozszerza się albo zapada; kształt: koło lub sześciokąt."""

    def __init__(self, x, y, r0, r1, life, colors, width=2, shape="circle", delay=0, spin=0.0):
        self.x, self.y, self.r0, self.r1 = x, y, r0, r1
        self.max = self.life = life
        self.colors, self.width, self.shape, self.delay, self.spin = colors, width, shape, delay, spin
        self.t = 0

    def update(self):
        if self.delay > 0:
            self.delay -= view.DT_SCALE
            return
        self.t += view.DT_SCALE
        self.life -= view.DT_SCALE

    def draw(self, canvas):
        if self.delay > 0 or self.life <= 0:
            return
        u = self.t / self.max
        e = u if self.r1 < self.r0 else 1 - (1 - u) ** 2   # rozszerzanie: szybki start, zapadanie: przyspieszenie
        r = (self.r0 + (self.r1 - self.r0) * e) * K
        if r < 2 or (self.life < self.max * 0.25 and (self.t // 2) % 2):
            return
        cx, cy = sp(self.x, self.y)
        c0, c1 = self.colors
        if self.shape == "hex":
            def hexpts(rad):
                return [(cx + math.cos(self.spin * u * math.tau + k * math.pi / 3) * rad,
                         cy + math.sin(self.spin * u * math.tau + k * math.pi / 3) * rad) for k in range(6)]
            pygame.draw.polygon(canvas, c0, hexpts(r), self.width)
            pygame.draw.polygon(canvas, c1, hexpts(r * 0.8), 1)
            for px_, py_ in hexpts(r):
                canvas.fill(WHITE, (round(px_) - 1, round(py_) - 1, 2, 2))
        else:
            pygame.draw.circle(canvas, c0, (cx, cy), int(r), self.width)
            if r > 6:
                pygame.draw.circle(canvas, c1, (cx, cy), int(r) - self.width - 1, 1)


class Particle:
    __slots__ = ("x", "y", "dx", "dy", "life", "max", "colors")

    def __init__(self, x, y, dx, dy, life, colors):
        self.x, self.y, self.dx, self.dy = x, y, dx, dy
        self.life = self.max = life
        self.colors = colors

    def update(self):
        self.x += self.dx * view.DT_SCALE
        self.y += self.dy * view.DT_SCALE
        self.dx *= 0.95 ** view.DT_SCALE
        self.dy *= 0.95 ** view.DT_SCALE
        self.life -= view.DT_SCALE

    def draw(self, canvas):
        frac = 1 - self.life / self.max
        c = self.colors[min(len(self.colors) - 1, int(frac * len(self.colors)))]
        s = 2 if frac < 0.4 else 1
        x, y = sp(self.x, self.y)
        canvas.fill(c, (x, y, s, s))


class Sparkle:
    def __init__(self, x, y):
        self.x, self.y = x, y
        self.life = self.max = 12

    def update(self):
        self.life -= view.DT_SCALE

    def draw(self, canvas):
        frac = self.life / self.max
        arm = 1 + int(2 * (1 - abs(2 * frac - 1)))
        cx, cy = sp(self.x, self.y)
        canvas.fill(WHITE, (cx, cy, 1, 1))
        for d in range(1, arm + 1):
            c = WHITE if d == 1 else YELLOW
            for ox, oy in ((d, 0), (-d, 0), (0, d), (0, -d)):
                canvas.fill(c, (cx + ox, cy + oy, 1, 1))


class Ghost:
    def __init__(self, x, y, img):
        self.x, self.y, self.img = x, y, img
        self.life = 10

    def update(self):
        self.life -= view.DT_SCALE

    def draw(self, canvas):
        col = WHITE if self.life > 8 else (CYAN if self.life > 5 else (BLUE_D if self.life > 2 else NAVY))
        s_ = silhouette(self.img, col)
        canvas.blit(s_, s_.get_rect(center=sp(self.x, self.y)))


# --------------------
# Efekty specjalne: poświata (addytywna), smugi iskier, odłamki, efekty z opóźnieniem
# --------------------
_glow_base = {}
_glow_cache = {}


def glow_sprite(radius, color, lvl):
    """Okrągła poświata (czarne tło, jasny środek) do mieszania addytywnego; promień i jasność są kwantyzowane.
    Każdy kolor rysowany jest raz (64 px), kolejne rozmiary to tylko szybkie skalowanie + przyciemnienie."""
    step = max(2, int(radius) // 5)
    R = max(2, int(radius) // step * step)
    key = (R, color, lvl)
    s = _glow_cache.get(key)
    if s is None:
        base = _glow_base.get(color)
        if base is None:
            base = pygame.Surface((129, 129)).convert()
            base.fill((0, 0, 0))
            for r in range(64, 0, -1):
                f = (1 - r / 64) ** 1.7
                pygame.draw.circle(base, (int(color[0] * f), int(color[1] * f), int(color[2] * f)), (64, 64), r)
            _glow_base[color] = base
        s = pygame.transform.smoothscale(base, (2 * R + 1, 2 * R + 1))
        if lvl < 6:
            v = int(255 * lvl / 6)
            s.fill((v, v, v), special_flags=pygame.BLEND_RGB_MULT)
        if len(_glow_cache) > 1200:   # najstarsze wpisy wypadają pierwsze
            for k_ in list(_glow_cache)[:300]:
                del _glow_cache[k_]
        _glow_cache[key] = s
    return s


def draw_glow(canvas, cx, cy, radius, color, power=1.0):
    """Poświata w pikselach płótna: rozjaśnia to, co pod nią (BLEND_RGB_ADD), więc działa jak światło."""
    if power <= 0.04 or radius < 2:
        return
    s = glow_sprite(radius, color, min(6, max(1, round(power * 6))))
    R = s.get_width() // 2
    canvas.blit(s, (round(cx) - R, round(cy) - R), special_flags=pygame.BLEND_RGB_ADD)


def emit_count(n):
    """Ile cząstek wypuścić w tej klatce, żeby średnio było n na klatkę przy 60 FPS (niezależnie od limitu FPS)."""
    x = n * view.DT_SCALE
    k = int(x)
    return k + (1 if random.random() < x - k else 0)


class Glow:
    """Rozbłysk światła w punkcie świata (albo przyczepiony do obiektu): rośnie i gaśnie."""

    def __init__(self, x, y, r0, r1, life, color, power=1.0, delay=0, owner=None):
        self.x, self.y, self.r0, self.r1 = x, y, r0, r1
        self.max = self.life = life
        self.color, self.power, self.delay, self.owner = color, power, delay, owner
        self.t = 0

    def update(self):
        if self.delay > 0:
            self.delay -= view.DT_SCALE
            return
        self.t += view.DT_SCALE
        self.life -= view.DT_SCALE

    def draw(self, canvas):
        if self.delay > 0 or self.life <= 0:
            return
        u = min(1.0, self.t / self.max)
        r = (self.r0 + (self.r1 - self.r0) * (1 - (1 - u) ** 3)) * K
        x, y = (self.owner.x, self.owner.y) if self.owner is not None else (self.x, self.y)
        cx, cy = sp(x, y)
        draw_glow(canvas, cx, cy, r, self.color, self.power * (1 - u) ** 1.4)


class Streak:
    """Iskra-smuga: rysowana jako kreska wzdłuż prędkości, więc wybuchy wyglądają na szybkie i ostre."""
    __slots__ = ("x", "y", "dx", "dy", "life", "max", "colors", "drag")

    def __init__(self, x, y, dx, dy, life, colors, drag=0.9):
        self.x, self.y, self.dx, self.dy = x, y, dx, dy
        self.life = self.max = life
        self.colors, self.drag = colors, drag

    def update(self):
        self.x += self.dx * view.DT_SCALE
        self.y += self.dy * view.DT_SCALE
        k = self.drag ** view.DT_SCALE
        self.dx *= k
        self.dy *= k
        self.life -= view.DT_SCALE

    def draw(self, canvas):
        frac = 1 - self.life / self.max
        c = self.colors[min(len(self.colors) - 1, int(frac * len(self.colors)))]
        x, y = sp(self.x, self.y)
        ln = 1.6 * K
        x2, y2 = x - self.dx * ln, y - self.dy * ln
        if abs(x2 - x) + abs(y2 - y) < 1.5:
            canvas.fill(c, (x, y, 1, 1))
        else:
            pygame.draw.line(canvas, c, (x, y), (round(x2), round(y2)), 2 if frac < 0.3 else 1)


class Debris:
    """Odłamek skały/kadłuba: wiruje, zwalnia i zostawia żarzący się ślad."""
    __slots__ = ("x", "y", "dx", "dy", "life", "max", "color", "size", "hot")

    def __init__(self, x, y, dx, dy, life, color, size=2, hot=True):
        self.x, self.y, self.dx, self.dy = x, y, dx, dy
        self.life = self.max = life
        self.color, self.size, self.hot = color, size, hot

    def update(self):
        self.x += self.dx * view.DT_SCALE
        self.y += self.dy * view.DT_SCALE
        k = 0.965 ** view.DT_SCALE
        self.dx *= k
        self.dy *= k
        self.life -= view.DT_SCALE

    def draw(self, canvas):
        x, y = sp(self.x, self.y)
        frac = self.life / self.max
        if self.hot and frac > 0.35:   # rozżarzony ślad za odłamkiem
            canvas.fill(ORANGE if frac > 0.7 else RED, (round(x - self.dx * K * 2), round(y - self.dy * K * 2), 1, 1))
        s = self.size if frac > 0.3 else 1
        canvas.fill(NAVY, (x - s // 2 + 1, y - s // 2 + 1, s, s))
        canvas.fill(self.color if frac > 0.2 else DARK, (x - s // 2, y - s // 2, s, s))


class Timer:
    """Efekt z opóźnieniem (np. seria wybuchów kolosa): po 'delay' klatkach woła fn() i znika."""

    def __init__(self, delay, fn):
        self.delay, self.fn, self.life = delay, fn, 1

    def update(self):
        self.delay -= view.DT_SCALE
        if self.delay <= 0 and self.life > 0:
            self.life = 0
            self.fn()

    def draw(self, canvas):
        pass


def bolt_points(x1, y1, x2, y2, jit, n=6):
    """Postrzępiona błyskawica między dwoma punktami płótna."""
    pts = [(x1, y1)]
    dx, dy = x2 - x1, y2 - y1
    d = math.hypot(dx, dy) or 1.0
    qx, qy = -dy / d, dx / d
    for i in range(1, n):
        f = i / n
        o = random.uniform(-jit, jit) * (1 - abs(2 * f - 1) * 0.5)
        pts.append((x1 + dx * f + qx * o, y1 + dy * f + qy * o))
    pts.append((x2, y2))
    return pts
