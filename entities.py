"""Obiekty w świecie: animacje i obroty sprite'ów, statek, asteroidy, pociski, rakiety, bryłki surowca."""
import math
import random

import pygame

import view
from config import *
from view import sp


# --------------------
# Animacje, obroty, sylwetki
# --------------------
class Animation:
    def __init__(self, frames, speed):
        self.frame = 0.0
        self.speed = speed
        self.frames = frames

    def copy(self):
        return Animation(self.frames, self.speed)

    def update(self):
        self.frame += self.speed * view.DT_SCALE   # tempo animacji niezależne od limitu FPS
        n = len(self.frames)
        if self.frame >= n:
            self.frame %= n

    def is_end(self):
        return self.frame + self.speed * view.DT_SCALE >= len(self.frames)

    @property
    def image(self):
        return self.frames[int(self.frame)]


_rot_cache = {}


def rotated(img, deg):
    step = int(round(deg / ROT_STEP)) % (360 // ROT_STEP)
    if step == 0:
        return img
    key = (id(img), step)
    r = _rot_cache.get(key)
    if r is None:
        r = _rot_cache[key] = pygame.transform.rotate(img, -step * ROT_STEP)
    return r


_sil_cache = {}


def silhouette(img, color):
    key = (id(img), color)
    s = _sil_cache.get(key)
    if s is None:
        s = pygame.mask.from_surface(img).to_surface(setcolor=tuple(color) + (255,), unsetcolor=(0, 0, 0, 0))
        _sil_cache[key] = s
    return s


# --------------------
# Encje
# --------------------
class Entity:
    def __init__(self, name="entity"):
        self.x = self.y = self.dx = self.dy = 0.0
        self.R = 1
        self.angle = 0.0
        self.life = True
        self.name = name
        self.anim = None
        self.scale = 1.0

    def settings(self, anim, x, y, angle=0.0, radius=1):
        self.anim = anim.copy()
        self.x, self.y = x, y
        self.angle = angle
        self.R = radius

    def update(self):
        pass

    def draw(self, canvas):
        img = rotated(self.anim.image, self.angle + 90)
        if self.scale != 1.0:  # animacja lądowania/startu: statek "oddala się" od kamery
            img = pygame.transform.scale(img, (max(1, round(img.get_width() * self.scale)),
                                               max(1, round(img.get_height() * self.scale))))
        canvas.blit(img, img.get_rect(center=sp(self.x, self.y)))


class Player(Entity):
    def __init__(self):
        super().__init__("player")
        self.thrust = False
        self.speed = 4.0
        self.turn = 3.0
        self.max_speed = 15
        self.dash_t = 0
        self.dash_angle = 0.0
        self.dash_speed = DASH_SPEED
        self.boost = 1.0         # mnożnik silnika (Overdrive Strikera)
        self.reverse = False     # klawisz S: małe dopalacze hamujące / cofające

    def update(self):
        if self.dash_t > 0:
            self.dash_t -= view.DT_SCALE
            if self.dash_t <= 0:
                self.dash_t = 0
            rad = self.dash_angle * DEGTORAD
            self.dx = math.cos(rad) * self.dash_speed
            self.dy = math.sin(rad) * self.dash_speed
            if self.dash_t == 0:
                k = self.max_speed / self.dash_speed
                self.dx *= k
                self.dy *= k
        else:
            if self.thrust:
                self.dx += math.cos(self.angle * DEGTORAD) * self.speed * self.boost * 0.05 * view.DT_SCALE
                self.dy += math.sin(self.angle * DEGTORAD) * self.speed * self.boost * 0.05 * view.DT_SCALE
            elif self.reverse:  # dopalacze wsteczne: słabsze niż silnik główny
                self.dx -= math.cos(self.angle * DEGTORAD) * self.speed * self.boost * 0.05 * 0.6 * view.DT_SCALE
                self.dy -= math.sin(self.angle * DEGTORAD) * self.speed * self.boost * 0.05 * 0.6 * view.DT_SCALE
                self.dx *= 0.985 ** view.DT_SCALE
                self.dy *= 0.985 ** view.DT_SCALE
            else:
                self.dx *= 0.99 ** view.DT_SCALE
                self.dy *= 0.99 ** view.DT_SCALE
            v = math.hypot(self.dx, self.dy)
            cap = self.max_speed * self.boost
            if v > cap:
                self.dx *= cap / v
                self.dy *= cap / v
        self.x += self.dx * view.DT_SCALE
        self.y += self.dy * view.DT_SCALE


class Asteroid(Entity):
    def __init__(self):
        super().__init__("asteroid")
        self.dx = random.randint(-4, 3)
        self.dy = random.randint(-4, 3)
        self.hp = self.max_hp = 1
        self.tier = "large"      # "small", "large" albo "colossus"
        self.ore = "iron"        # jaki surowiec zostawia (iron, titanium albo gold)
        self.field = None        # planeta, wokół której asteroida krąży w skupisku
        self.base = 1            # poziom HP w miejscu spawnu (dziedziczą go odłamki)
        self.gold = False
        self.flash = 0
        self.beam = False
        self.pull_t = 0
        self.crush_cd = 0        # przerwa między zgnieceniami przez Gravity Well
        self.knock = 0           # klatki po odrzucie: skupisko nie hamuje asteroidy
        self.phase = random.randrange(70)

    def update(self):
        self.x += self.dx * view.DT_SCALE
        self.y += self.dy * view.DT_SCALE
        if self.flash > 0:
            self.flash -= view.DT_SCALE
        if self.crush_cd > 0:
            self.crush_cd -= view.DT_SCALE
        if self.knock > 0:
            self.knock -= view.DT_SCALE

    def draw(self, canvas):
        img = rotated(self.anim.image, self.angle + 90)
        if self.flash > 0:
            img = silhouette(img, WHITE)
        elif self.gold and (pygame.time.get_ticks() // 33 + self.phase) % 70 < 3:
            img = silhouette(img, (255, 244, 200))
        cx, cy = sp(self.x, self.y)
        canvas.blit(img, img.get_rect(center=(cx, cy)))
        if self.hp < self.max_hp:
            w = max(6, int(self.R * 2 * K))
            x0, y0 = cx - w // 2, cy - int(self.R * K) - 5
            frac = self.hp / self.max_hp
            canvas.fill(NAVY, (x0 - 1, y0 - 1, w + 2, 4))
            canvas.fill(LIME if frac > 0.5 else (ORANGE if frac > 0.25 else RED),
                        (x0, y0, max(1, int(w * frac)), 2))


class Bullet(Entity):
    def __init__(self):
        super().__init__("bullet")
        self.dmg = 1
        self.age = 0
        self.maxage = BULLET_LIFE   # Long Optics wydłuża zasięg
        self.spark = False          # bomblety kasetowe zostawiają iskry
        self.ivx = self.ivy = 0.0   # prędkość statku w chwili strzału (żeby pocisk jej nie tracił)

    def update(self):
        self.age += view.DT_SCALE
        self.dx = math.cos(self.angle * DEGTORAD) * BULLET_SPEED + self.ivx
        self.dy = math.sin(self.angle * DEGTORAD) * BULLET_SPEED + self.ivy
        self.x += self.dx * view.DT_SCALE
        self.y += self.dy * view.DT_SCALE
        if self.age > self.maxage:
            self.life = False


class Missile(Entity):
    TURN = 7.5

    def __init__(self, world, target):
        super().__init__("missile")
        self.world = world
        self.target = target
        self.age = 0
        self.spd = 3.0
        self.dmg = 4             # obrażenia bezpośrednie
        self.cluster = False     # najwyższy poziom: po trafieniu rozpada się na bomblety

    def update(self):
        self.age += view.DT_SCALE
        t = self.target
        if t is None or not t.life:
            t = self.target = nearest_asteroid(self.world, self.x, self.y)
        if t is not None and self.age > 6:
            want = math.degrees(math.atan2(t.y - self.y, t.x - self.x))
            diff = (want - self.angle + 180) % 360 - 180
            turn = self.TURN * view.DT_SCALE
            self.angle += max(-turn, min(turn, diff))
        self.spd = min(MISSILE_SPEED, self.spd + 0.35 * view.DT_SCALE)
        self.dx = math.cos(self.angle * DEGTORAD) * self.spd
        self.dy = math.sin(self.angle * DEGTORAD) * self.spd
        self.x += self.dx * view.DT_SCALE
        self.y += self.dy * view.DT_SCALE
        if self.age > 240:
            self.life = False


class Ore:
    """Bryłka surowca: dryfuje, a gdy jesteś blisko i masz miejsce w ładowni, leci do statku."""
    MAGNET = 520

    def __init__(self, x, y, kind, dx, dy, amount=1):
        self.x, self.y, self.dx, self.dy = x, y, dx, dy
        self.kind = kind
        self.amount = amount     # ile jednostek surowca niesie ta bryłka
        self.life = 1500
        self.age = 0
        self.pull = 0            # klatki, przez które bryłka jest przyciągana bez względu na odległość (Ore Pulse)

    def update(self, player, can_pick, magnet=None):
        """Zwraca True, gdy bryłka została zebrana."""
        self.age += view.DT_SCALE
        self.life -= view.DT_SCALE
        mg = magnet or self.MAGNET
        px, py = player.x - self.x, player.y - self.y
        d = math.hypot(px, py) or 1.0
        if self.pull > 0:
            self.pull -= view.DT_SCALE
        if can_pick and (d < mg or self.pull > 0):
            spd = 22.0 if self.pull > 0 else min(22.0, 7.0 + (mg - d) * 0.09)
            lerp = min(1.0, 0.3 * view.DT_SCALE)
            self.dx += (px / d * spd - self.dx) * lerp
            self.dy += (py / d * spd - self.dy) * lerp
        else:
            self.dx *= 0.99 ** view.DT_SCALE
            self.dy *= 0.99 ** view.DT_SCALE
        self.x += self.dx * view.DT_SCALE
        self.y += self.dy * view.DT_SCALE
        return can_pick and d < player.R + 16

    def draw(self, canvas):
        x, y = sp(self.x, self.y)
        c = ORE[self.kind]["color"]
        if self.life < 240 and (int(self.life) // 6) % 2:  # migocze tuż przed zniknięciem
            return
        if self.amount >= 20:    # duże bryłki są większe i błyszczą
            canvas.fill(NAVY, (x - 3, y - 3, 7, 7))
            canvas.fill(c, (x - 2, y - 2, 5, 5))
            canvas.fill(WHITE, (x - 1, y - 1, 2, 2) if (int(self.age) // 5) % 2 else (x, y, 1, 1))
        elif self.amount >= 5:
            canvas.fill(NAVY, (x - 2, y - 2, 5, 5))
            canvas.fill(c, (x - 1, y - 1, 3, 3))
            if (int(self.age) // 6) % 2 == 0:
                canvas.fill(WHITE, (x, y, 1, 1))
        else:
            canvas.fill(NAVY, (x, y + 1, 3, 1))
            canvas.fill(c, (x - 1, y, 3, 1))
            canvas.fill(c, (x, y - 1, 1, 3))
            if (int(self.age) // 6) % 2 == 0:
                canvas.fill(WHITE, (x, y, 1, 1))


def nearest_asteroid(world, x, y):
    best, best_d = None, 1e18
    for e in world:
        if e.name == "asteroid" and e.life:
            d = (e.x - x) ** 2 + (e.y - y) ** 2
            if d < best_d:
                best, best_d = e, d
    return best


def is_collide(a, b):
    return (b.x - a.x) ** 2 + (b.y - a.y) ** 2 < (a.R + b.R) ** 2
