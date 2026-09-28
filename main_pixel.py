"""Asteroids - wersja pixel art (pygame).

Rozbudowana wersja z main.py: pixel art, ogień ciągły, ulepszenia do 0.05 s, skalowanie okna
oraz nowości: Hangar z 4 statkami (każdy z unikalną zdolnością), rakiety samonaprowadzające,
fala uderzeniowa, tarcza, rosnące HP asteroid i złote asteroidy.
Postęp (punkty, ulepszenia, statki) zapisuje się w progress.json obok tego pliku.

Uruchomienie:
    pip install pygame
    python main_pixel.py
    python main_pixel.py --points 40     # (opcjonalnie) dodaje 40 punktów ulepszeń na start

Sterowanie: A/D obrót, W przyspieszenie, SPACJA strzał (przytrzymaj = ogień ciągły),
Q rakiety samonaprowadzające, E fala uderzeniowa, SHIFT zdolność statku (dash Interceptora),
ESC powrót do menu, F11 pełny ekran. Traktor-beam Harvestera działa automatycznie.
"""
import json
import math
import os
import random
import sys
from pathlib import Path

if sys.platform == "win32":
    try:
        import ctypes
        ctypes.windll.user32.SetProcessDPIAware()
    except Exception:
        pass
os.environ.setdefault("SDL_VIDEO_CENTERED", "1")

import pygame

# --------------------
# Stałe
# --------------------
W, H = 1200, 800           # współrzędne logiki gry (jak w main.py)
CW, CH = 480, 320          # rozdzielczość płótna pixel art
K = CW / W                 # 0.4: logika -> piksele płótna
FPS = 60
DEGTORAD = 0.017453
MIN_FIRE_RATE = 0.05
FIRE_STEP = 0.05
ROT_STEP = 5               # obrót sprite'ów co 5 stopni (bardziej "pikselowy" ruch)

HP_START = 60.0            # od której sekundy asteroidy zaczynają "twardnieć" (HP 2)
HP_STEP = 30.0             # ...i co ile sekund dochodzi kolejny +1 HP
HP_MAX = 25
GOLD_CHANCE = 0.09         # szansa, że nowa asteroida jest złota
BEAM_RANGE = 420           # zasięg traktor-beamu (współrzędne logiki)
DASH_FRAMES = 8            # dash Interceptora: długość sprintu w klatkach
DASH_SPEED = 30            # ...i prędkość (px logiki / klatkę)
DASH_COOLDOWN = 3.5
PHASE_FRAMES = 22          # odporność na kolizje w trakcie i tuż po dashu

BASE_DIR = Path(__file__).resolve().parent
ASSETS = BASE_DIR / "assets"
PIXEL = BASE_DIR / "assets_pixel"
SCORE_FILE = BASE_DIR / "scores.txt"
PROGRESS_FILE = BASE_DIR / "progress.json"

# Paleta Sweetie 16 (GrafxKid)
NAVY = (26, 28, 44)
PLUM = (93, 39, 93)
RED = (177, 62, 83)
ORANGE = (239, 125, 87)
YELLOW = (255, 205, 117)
LIME = (167, 240, 112)
CYAN = (115, 239, 247)
WHITE = (244, 244, 244)
GREY = (148, 176, 194)
DARK = (51, 60, 87)
BLUE_D = (59, 93, 201)


# --------------------
# Wyniki
# --------------------
def read_scores(path):
    """Zwraca (lista top 10, highscore, last_score, last_destroyed)."""
    scores, highscore, last_score, last_destroyed = [], 0, 0, 0
    try:
        lines = path.read_text(encoding="utf-8").splitlines()
    except OSError:
        return scores, highscore, last_score, last_destroyed

    def parse(line, prefix):
        if line.startswith(prefix):
            try:
                return int(line[len(prefix):])
            except ValueError:
                pass
        return 0

    if len(lines) > 0:
        highscore = parse(lines[0], "Highscore:")
    if len(lines) > 1:
        last_score = parse(lines[1], "LastScore:")
    if len(lines) > 2:
        last_destroyed = parse(lines[2], "LastDestroyed:")
    for line in lines[3:]:
        if len(scores) >= 10:
            break
        try:
            scores.append(int(line))
        except ValueError:
            pass
    return scores, highscore, last_score, last_destroyed


def save_scores(path, highscore, scores, last_score, last_destroyed):
    try:
        with path.open("w", encoding="utf-8") as f:
            f.write(f"Highscore: {highscore}\n")
            f.write(f"LastScore: {last_score}\n")
            f.write(f"LastDestroyed: {last_destroyed}\n")
            for s in scores:
                f.write(f"{s}\n")
    except OSError:
        print("Nie można zapisać wyników do pliku:", path)


def update_scores(scores, new_score, highscore):
    scores.append(new_score)
    scores.sort(reverse=True)
    del scores[10:]
    return max(highscore, new_score)


# --------------------
# Okno: skalowanie do rozdzielczości ekranu
# --------------------
def default_window_size():
    """Największe okno 3:2, które mieści się na pulpicie (z zapasem na pasek zadań)."""
    dw, dh = pygame.display.get_desktop_sizes()[0]
    s = min(dw * 0.9 / CW, dh * 0.85 / CH)
    return int(CW * s), int(CH * s)


def open_window(fullscreen, size):
    if fullscreen:
        return pygame.display.set_mode((0, 0), pygame.FULLSCREEN)
    return pygame.display.set_mode(size, pygame.RESIZABLE)


def present(canvas):
    """Powiększa płótno 480x320 do okna z zachowaniem ostrych pikseli.
    Przy niewielkim powiększeniu: najpierw całkowita krotność bez wygładzania, potem delikatne
    dociągnięcie do rozmiaru okna. Przy dużym (>= 4x) wystarczy skalowanie wprost."""
    win = pygame.display.get_surface()
    ww, wh = win.get_size()
    s = min(ww / CW, wh / CH)
    tw, th = int(CW * s), int(CH * s)
    if tw < 1 or th < 1:  # okno zminimalizowane
        pygame.display.flip()
        return
    if (tw, th) != (ww, wh):
        win.fill((0, 0, 0))  # czarne pasy, gdy proporcje okna są inne niż 3:2
    rect = ((ww - tw) // 2, (wh - th) // 2, tw, th)
    try:
        dest = win.subsurface(rect)
        k = int(s)
        if s >= 4 or k * CW == tw:
            pygame.transform.scale(canvas, (tw, th), dest)
        else:
            step = pygame.transform.scale(canvas, (CW * k, CH * k))
            pygame.transform.smoothscale(step, (tw, th), dest)
    except (ValueError, pygame.error):
        win.blit(pygame.transform.scale(canvas, (tw, th)), rect[:2])
    pygame.display.flip()


# --------------------
# Animation
# --------------------
class Animation:
    """Lista klatek (już w rozmiarze pixel art). Klatki są współdzielone,
    a licznik klatki (frame) ma każda kopia osobno."""

    def __init__(self, frames, speed):
        self.frame = 0.0
        self.speed = speed
        self.frames = frames

    def copy(self):
        return Animation(self.frames, self.speed)

    def update(self):
        self.frame += self.speed
        n = len(self.frames)
        if self.frame >= n:
            self.frame -= n

    def is_end(self):
        return self.frame + self.speed >= len(self.frames)

    @property
    def image(self):
        return self.frames[int(self.frame)]


_rot_cache = {}


def rotated(img, deg):
    """Obrót sprite'a (zgodnie z ruchem wskazówek zegara) z cache i krokiem ROT_STEP."""
    step = int(round(deg / ROT_STEP)) % (360 // ROT_STEP)
    if step == 0:
        return img
    key = (id(img), step)
    r = _rot_cache.get(key)
    if r is None:
        r = _rot_cache[key] = pygame.transform.rotate(img, -step * ROT_STEP)
    return r


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

    def settings(self, anim, x, y, angle=0.0, radius=1):
        self.anim = anim.copy()
        self.x, self.y = x, y
        self.angle = angle
        self.R = radius

    def update(self):
        pass

    def draw(self, canvas):
        img = rotated(self.anim.image, self.angle + 90)
        canvas.blit(img, img.get_rect(center=(round(self.x * K), round(self.y * K))))


class Player(Entity):
    def __init__(self):
        super().__init__("player")
        self.thrust = False
        self.speed = 4.0
        self.turn = 3.0
        self.max_speed = 15
        self.dash_t = 0
        self.dash_angle = 0.0

    def update(self):
        if self.dash_t > 0:  # sprint: stała prędkość w jednym kierunku
            self.dash_t -= 1
            rad = self.dash_angle * DEGTORAD
            self.dx = math.cos(rad) * DASH_SPEED
            self.dy = math.sin(rad) * DASH_SPEED
            if self.dash_t == 0:  # po sprincie wracamy do normalnej prędkości maksymalnej
                k = self.max_speed / DASH_SPEED
                self.dx *= k
                self.dy *= k
        else:
            if self.thrust:
                self.dx += math.cos(self.angle * DEGTORAD) * self.speed * 0.05
                self.dy += math.sin(self.angle * DEGTORAD) * self.speed * 0.05
            else:
                self.dx *= 0.99
                self.dy *= 0.99

            v = math.hypot(self.dx, self.dy)
            if v > self.max_speed:
                self.dx *= self.max_speed / v
                self.dy *= self.max_speed / v

        self.x += self.dx
        self.y += self.dy
        wrap(self)


class Asteroid(Entity):
    def __init__(self):
        super().__init__("asteroid")
        self.dx = random.randint(-4, 3)
        self.dy = random.randint(-4, 3)
        self.hp = self.max_hp = 1
        self.base = 1            # poziom HP skał w chwili spawnu (dziedziczą go odłamki)
        self.gold = False
        self.value = 50          # punkty za zniszczenie
        self.flash = 0           # klatki białego błysku po trafieniu
        self.beam = False        # czy jest celem traktor-beamu
        self.pull_t = 0
        self.phase = random.randrange(70)  # przesunięcie połysku złotych asteroid

    def update(self):
        self.x += self.dx
        self.y += self.dy
        wrap(self)
        if self.flash > 0:
            self.flash -= 1

    def draw(self, canvas):
        img = rotated(self.anim.image, self.angle + 90)
        if self.flash > 0:
            img = silhouette(img, WHITE)
        elif self.gold and (pygame.time.get_ticks() // 33 + self.phase) % 70 < 3:
            img = silhouette(img, (255, 244, 200))  # krótki połysk
        cx, cy = round(self.x * K), round(self.y * K)
        canvas.blit(img, img.get_rect(center=(cx, cy)))
        if self.hp < self.max_hp:  # pasek HP pokazuje się dopiero po uszkodzeniu
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

    def update(self):
        self.dx = math.cos(self.angle * DEGTORAD) * 6
        self.dy = math.sin(self.angle * DEGTORAD) * 6
        self.x += self.dx
        self.y += self.dy
        if self.x > W or self.x < 0 or self.y > H or self.y < 0:
            self.life = False


class Missile(Entity):
    """Rakieta samonaprowadzająca: krótki lot prosto, potem skręca w stronę celu."""
    TURN = 5.5

    def __init__(self, world, target):
        super().__init__("missile")
        self.world = world
        self.target = target
        self.age = 0
        self.spd = 3.0

    def update(self):
        self.age += 1
        t = self.target
        if t is None or not t.life:
            t = self.target = nearest_asteroid(self.world, self.x, self.y)
        if t is not None and self.age > 6:
            want = math.degrees(math.atan2(t.y - self.y, t.x - self.x))
            diff = (want - self.angle + 180) % 360 - 180
            self.angle += max(-self.TURN, min(self.TURN, diff))
        self.spd = min(9.0, self.spd + 0.25)
        self.dx = math.cos(self.angle * DEGTORAD) * self.spd
        self.dy = math.sin(self.angle * DEGTORAD) * self.spd
        self.x += self.dx
        self.y += self.dy
        if self.age > 240 or self.x > W or self.x < 0 or self.y > H or self.y < 0:
            self.life = False


class Shockwave:
    """Pierścień rozchodzący się od statku; każdej asteroidzie, którą minie, zadaje obrażenia."""
    GROW = 26
    FADE = 8

    def __init__(self, owner, max_r, damage=8, colors=(CYAN, WHITE)):
        self.owner = owner
        self.max_r = max_r
        self.damage = damage     # obrażenia zadawane każdej asteroidzie (raz na falę)
        self.colors = colors
        self.t = 0
        self.hit = set()
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
        self.t += 1
        if self.t > self.GROW + self.FADE:
            self.life = False

    def draw(self, canvas):
        r = int(self.r * K)
        if r < 2 or (not self.active and (self.t // 2) % 2):
            return
        c = (round(self.x * K), round(self.y * K))
        pygame.draw.circle(canvas, self.colors[0], c, r, 2)
        if r > 6:
            pygame.draw.circle(canvas, self.colors[1], c, r - 3, 1)


class Particle:
    __slots__ = ("x", "y", "dx", "dy", "life", "max", "colors")

    def __init__(self, x, y, dx, dy, life, colors):
        self.x, self.y, self.dx, self.dy = x, y, dx, dy
        self.life = self.max = life
        self.colors = colors

    def update(self):
        self.x += self.dx
        self.y += self.dy
        self.dx *= 0.95
        self.dy *= 0.95
        self.life -= 1

    def draw(self, canvas):
        frac = 1 - self.life / self.max
        c = self.colors[min(len(self.colors) - 1, int(frac * len(self.colors)))]
        s = 2 if frac < 0.4 else 1
        canvas.fill(c, (round(self.x * K), round(self.y * K), s, s))


class Sparkle:
    """Błysk w kształcie "+" na złotych asteroidach."""

    def __init__(self, x, y):
        self.x, self.y = x, y
        self.life = self.max = 12

    def update(self):
        self.life -= 1

    def draw(self, canvas):
        frac = self.life / self.max
        arm = 1 + int(2 * (1 - abs(2 * frac - 1)))  # rośnie do 3 px i znów maleje
        cx, cy = round(self.x * K), round(self.y * K)
        canvas.fill(WHITE, (cx, cy, 1, 1))
        for d in range(1, arm + 1):
            c = WHITE if d == 1 else YELLOW
            for ox, oy in ((d, 0), (-d, 0), (0, d), (0, -d)):
                canvas.fill(c, (cx + ox, cy + oy, 1, 1))


class Ghost:
    """Powidok statku podczas dashu (jednokolorowa sylwetka)."""

    def __init__(self, x, y, img):
        self.x, self.y, self.img = x, y, img
        self.life = 8

    def update(self):
        self.life -= 1

    def draw(self, canvas):
        s = silhouette(self.img, CYAN if self.life > 4 else BLUE_D)
        canvas.blit(s, s.get_rect(center=(round(self.x * K), round(self.y * K))))


_sil_cache = {}


def silhouette(img, color):
    """Jednokolorowa sylwetka sprite'a (do błysków i powidoków), z cache."""
    key = (id(img), color)
    s = _sil_cache.get(key)
    if s is None:
        s = pygame.mask.from_surface(img).to_surface(setcolor=tuple(color) + (255,), unsetcolor=(0, 0, 0, 0))
        _sil_cache[key] = s
    return s


def rock_hp(t):
    """Bazowe HP asteroid po t sekundach gry: 1 do HP_START, potem 2 i +1 co HP_STEP."""
    if t < HP_START:
        return 1
    return min(HP_MAX, 2 + int((t - HP_START) // HP_STEP))


def nearest_asteroid(world, x, y):
    best, best_d = None, 1e18
    for e in world:
        if e.name == "asteroid" and e.life:
            d = (e.x - x) ** 2 + (e.y - y) ** 2
            if d < best_d:
                best, best_d = e, d
    return best


# --------------------
# Dane: statki i ulepszenia
# --------------------
SHIPS = [
    dict(id="scout", name="SCOUT", cost=0, radius=20, speed=1.0, turn=3.0, fire=1.0, shields=0, dmg=1,
         dash=False, reactive=False, beam=False, sheet="ship.png", stats=(3, 3, 3, 3),
         perk=("BALANCED ALL-ROUNDER", "", "")),
    dict(id="interceptor", name="INTERCEPTOR", cost=5, radius=14, speed=1.35, turn=4.5, fire=1.25, shields=0,
         dmg=1, dash=True, reactive=False, beam=False, sheet="ship_interceptor.png", stats=(5, 5, 2, 2),
         perk=("SHIFT: PHASE DASH", "IMMUNE WHILE DASHING", "TINY HITBOX, GUNS -25%")),
    dict(id="heavy", name="BRUISER", cost=8, radius=26, speed=0.8, turn=2.0, fire=0.8, shields=1,
         dmg=2, dash=False, reactive=True, beam=False, sheet="ship_heavy.png", stats=(2, 1, 4, 5),
         perk=("BULLETS DEAL 2 DAMAGE", "SHIELD HIT = BLAST", "+1 FREE SHIELD")),
    dict(id="harvester", name="HARVESTER", cost=10, radius=22, speed=0.9, turn=2.6, fire=1.6, shields=0,
         dmg=1, dash=False, reactive=False, beam=True, sheet="ship_harvester.png", stats=(3, 3, 1, 2),
         perk=("AUTO TRACTOR BEAM:", "ROCKS PULLED IN = 3X PTS", "GOLD = 4X, WEAK GUNS")),
]
STAT_NAMES = ("SPEED", "TURN", "FIRE", "ARMOR")

UPGRADES = [
    dict(key="fire", name="FIRE RATE", costs=[1] * 7),
    dict(key="engine", name="ENGINE", costs=[1] * 8),
    dict(key="double", name="DOUBLE SHOT", costs=[5]),
    dict(key="missile", name="HOMING MISSILES", costs=[3, 4, 5]),
    dict(key="wave", name="SHOCKWAVE", costs=[3, 4, 5]),
    dict(key="shield", name="SHIELD", costs=[2, 3, 4]),
]
WAVE_RADIUS = [320, 400, 480]
WAVE_COOLDOWN = [18.0, 14.0, 10.0]
WAVE_DAMAGE = [8, 12, 16]


def fire_rate_of(level):
    return max(MIN_FIRE_RATE, round(0.4 - FIRE_STEP * level, 2))


def engine_of(level):
    return 2.0 + 0.5 * level


def missile_of(level):
    return level, 4.0 - 0.5 * level  # (rakiet w salwie, czas przeładowania w s)


def upgrade_info(key, lvl):
    if key == "fire":
        return f"{fire_rate_of(lvl):.2f}S BETWEEN SHOTS"
    if key == "engine":
        return f"THRUST {engine_of(lvl):.1f}"
    if key == "double":
        return "TWIN CANNONS: ACTIVE" if lvl else "FIRE TWO BULLETS AT ONCE"
    if key == "missile":
        n, cd = missile_of(max(lvl, 1))
        return f"[Q] {n} MISSILE{'S' if n > 1 else ''} / {cd:.1f}S RELOAD" + ("" if lvl else "  (NEXT)")
    if key == "wave":
        i = max(lvl, 1) - 1
        return f"[E] R{WAVE_RADIUS[i]} DMG {WAVE_DAMAGE[i]} / {WAVE_COOLDOWN[i]:.0f}S COOLDOWN" + ("" if lvl else "  (NEXT)")
    if key == "shield":
        n = max(lvl, 1)
        return f"{n} HIT{'S' if n > 1 else ''} ABSORBED PER RUN" + ("" if lvl else "  (NEXT)")
    return ""


# --------------------
# Postęp gracza (progress.json)
# --------------------
def default_progress():
    return {"points": 0, "levels": {u["key"]: 0 for u in UPGRADES}, "owned": ["scout"], "ship": "scout"}


def load_progress(path):
    prog = default_progress()
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
        prog["points"] = max(0, int(data.get("points", 0)))
        for u in UPGRADES:
            prog["levels"][u["key"]] = max(0, min(len(u["costs"]), int(data.get("levels", {}).get(u["key"], 0))))
        ids = {s["id"] for s in SHIPS}
        prog["owned"] = sorted({o for o in data.get("owned", []) if o in ids} | {"scout"})
        prog["ship"] = data.get("ship") if data.get("ship") in prog["owned"] else "scout"
    except (OSError, ValueError, TypeError, AttributeError):
        pass
    return prog


def save_progress(path, prog):
    try:
        path.write_text(json.dumps(prog, indent=2), encoding="utf-8")
    except OSError:
        print("Nie można zapisać postępu:", path)


def wrap(e):
    if e.x > W:
        e.x = 0
    if e.x < 0:
        e.x = W
    if e.y > H:
        e.y = 0
    if e.y < 0:
        e.y = H


def is_collide(a, b):
    return (b.x - a.x) ** 2 + (b.y - a.y) ** 2 < (a.R + b.R) ** 2


# --------------------
# Gra
# --------------------
MISSILE_TRAIL = (YELLOW, ORANGE, RED, PLUM, DARK)


def main():
    pygame.init()
    pygame.display.set_caption("Asteroids! (pixel)")
    windowed_size = default_window_size()
    fullscreen = False
    open_window(fullscreen, windowed_size)
    screen = pygame.Surface((CW, CH)).convert()  # płótno pixel art
    clock = pygame.time.Clock()

    # --- Postęp (punkty, ulepszenia, statki) i wyniki ---
    prog = load_progress(PROGRESS_FILE)
    if "--points" in sys.argv:
        try:
            prog["points"] += int(sys.argv[sys.argv.index("--points") + 1])
            save_progress(PROGRESS_FILE, prog)
        except (ValueError, IndexError):
            pass
    scores, highscore, last_score, last_destroyed = read_scores(SCORE_FILE)

    # --- Zasoby ---
    def load(name):
        return pygame.image.load(str(PIXEL / name)).convert_alpha()

    def strip(name, count, speed):
        sheet = load(name)
        fw = sheet.get_width() // count
        frames = [sheet.subsurface((i * fw, 0, fw, sheet.get_height())).copy() for i in range(count)]
        return Animation(frames, speed)

    background = pygame.image.load(str(PIXEL / "bg.png")).convert()
    s_explosion = strip("explosion.png", 48, 0.5)
    s_rock = strip("rock.png", 16, 0.2)
    s_rock_small = strip("rock_small.png", 16, 0.2)
    s_rock_gold = strip("rock_gold.png", 16, 0.2)
    s_rock_small_gold = strip("rock_small_gold.png", 16, 0.2)
    s_bullet = strip("bullet.png", 16, 0.8)
    s_missile = strip("missile.png", 3, 0.3)
    ship_frames, ship_anims = {}, {}
    for sh in SHIPS:
        two = strip(sh["sheet"], 2, 0)
        ship_frames[sh["id"]] = two.frames
        ship_anims[sh["id"]] = (Animation([two.frames[0]], 0), Animation([two.frames[1]], 0))

    font_path = str(ASSETS / "PressStart2P-Regular.ttf")
    fonts = {}

    def text(msg, size, color, pos, center=False, right=False, mid=False, shadow=NAVY):
        if size not in fonts:
            fonts[size] = pygame.font.Font(font_path, size)
        f = fonts[size]
        surf = f.render(msg, False, color)  # False = bez antyaliasingu, ostre piksele
        x, y = pos
        if center:
            x = (CW - surf.get_width()) // 2
        elif right:
            x = x - surf.get_width()
        elif mid:
            x = x - surf.get_width() // 2
        if shadow:
            off = 1 if size <= 16 else 2
            screen.blit(f.render(msg, False, shadow), (x + off, y + off))
        screen.blit(surf, (x, y))

    # --- Stan gry ---
    entities, particles, waves, pending = [], [], [], []
    player = None
    ship = SHIPS[0]
    safe_time = 5.0
    start_ticks = 0
    destroyed = 0
    kill_points = 0              # punkty za zniszczone/przetworzone asteroidy
    fire_cooldown = missile_cd = wave_cd = dash_cd = 0.0
    shield_charges = max_shields = 0
    invuln = shake = phase_t = 0
    beam_target = None
    last_hp = 1
    floats, ghosts = [], []      # unoszące się napisy z punktami, powidoki dashu
    toast = ["", WHITE, 0]       # komunikat na środku ekranu w trakcie gry
    state = "menu"  # menu / game / hangar / upgrades / scores
    selected = hangar_sel = up_sel = 0
    menu_items = ["START GAME", "HANGAR", "UPGRADES", "VIEW SCORES", "EXIT"]
    notice = ["", WHITE, 0]  # komunikat w hangarze / ulepszeniach: tekst, kolor, licznik klatek
    banner = ""

    def set_notice(msg, color):
        notice[0], notice[1], notice[2] = msg, color, 90

    def ship_by_id(sid):
        return next(s for s in SHIPS if s["id"] == sid)

    def elapsed():
        return (pygame.time.get_ticks() - start_ticks) / 1000.0

    def burst(x, y, n, colors, speed=4.0, life=22):
        for _ in range(n):
            ang = random.random() * math.tau
            sp = random.uniform(0.5, 1.0) * speed
            particles.append(Particle(x, y, math.cos(ang) * sp, math.sin(ang) * sp,
                                      random.randint(life - 8, life), colors))
        if len(particles) > 500:
            del particles[:100]

    def new_rock(x, y, angle, small, gold, base):
        """Asteroida o HP i wartości zależnych od `base` (aktualny poziom HP skał)."""
        a = Asteroid()
        if small:
            anim = s_rock_small_gold if gold else s_rock_small
            hp = max(2, base + 1) if gold else max(1, (base + 1) // 2)
            mult = 2 if gold else 1
        else:
            anim = s_rock_gold if gold else s_rock
            hp = base * 2 + 1 if gold else base
            mult = 6 if gold else 1
        a.settings(anim, x, y, angle, 15 if small else 25)
        a.hp = a.max_hp = hp
        a.base, a.gold = base, gold
        a.value = (50 + 10 * (base - 1)) * mult
        return a

    def kill_asteroid(a, split=True):
        """Zniszczenie asteroidy: punkty, wybuch, odłamki i (dla dużych) rozpad na dwie małe."""
        nonlocal destroyed, kill_points
        a.life = False
        destroyed += 1
        kill_points += a.value
        ex = Entity("explosion")
        ex.settings(s_explosion, a.x, a.y)
        pending.append(ex)
        if a.gold:
            burst(a.x, a.y, 16, (WHITE, YELLOW, ORANGE), speed=5.0, life=26)
            floats.append([a.x, a.y, f"+{a.value}", YELLOW, 50])
        else:
            burst(a.x, a.y, 8, (WHITE, GREY, DARK))
        if split and a.R != 15:
            for _ in range(2):
                pending.append(new_rock(a.x, a.y, random.randrange(360), True, a.gold, a.base))

    def damage_asteroid(a, dmg, split=True):
        """Zadaje obrażenia; asteroida ginie dopiero, gdy jej HP spadnie do zera."""
        if not a.life:
            return
        a.hp -= dmg
        if a.hp <= 0:
            kill_asteroid(a, split)
        else:
            a.flash = 3
            burst(a.x, a.y, 3, (WHITE, YELLOW if a.gold else GREY), speed=2.5, life=10)

    def convert_asteroid(a):
        """Traktor-beam: asteroida dociągnięta do statku zamienia się w punkty (3x, złota 4x)."""
        nonlocal destroyed, kill_points
        a.life = False
        destroyed += 1
        pts = a.value * (4 if a.gold else 3)
        kill_points += pts
        floats.append([player.x, player.y - 24, f"+{pts}", YELLOW if a.gold else WHITE, 55])
        burst(player.x, player.y, 12, (YELLOW, WHITE, ORANGE), speed=3.5, life=20)

    def start_game():
        nonlocal player, ship, destroyed, fire_cooldown, missile_cd, wave_cd, shield_charges, max_shields
        nonlocal invuln, shake, start_ticks, state, banner, kill_points, dash_cd, phase_t, beam_target, last_hp
        lv = prog["levels"]
        ship = ship_by_id(prog["ship"])
        for group in (entities, particles, waves, pending, floats, ghosts):
            group.clear()
        toast[2] = 0
        player = Player()
        player.settings(ship_anims[ship["id"]][0], W // 2, H // 2, 0, ship["radius"])
        player.speed = engine_of(lv["engine"]) * ship["speed"]
        player.max_speed = 15 * ship["speed"]
        player.turn = ship["turn"]
        entities.append(player)
        destroyed = kill_points = 0
        fire_cooldown = missile_cd = wave_cd = dash_cd = 0.0
        max_shields = shield_charges = lv["shield"] + ship["shields"]
        invuln = shake = phase_t = 0
        beam_target = None
        last_hp = 1
        start_ticks = pygame.time.get_ticks()
        banner = ""
        state = "game"

    def shoot():
        nonlocal fire_cooldown
        lv = prog["levels"]
        if lv["double"]:
            offset = max(12.0, ship["radius"] * 0.75)
            rad = player.angle * math.pi / 180.0
            dx = math.cos(rad + math.pi / 2) * offset
            dy = math.sin(rad + math.pi / 2) * offset
            for sign in (1, -1):
                b = Bullet()
                b.settings(s_bullet, player.x + sign * dx, player.y + sign * dy, player.angle, 10)
                b.dmg = ship["dmg"]
                entities.append(b)
        else:
            b = Bullet()
            b.settings(s_bullet, player.x, player.y, player.angle, 10)
            b.dmg = ship["dmg"]
            entities.append(b)
        fire_cooldown = fire_rate_of(lv["fire"]) * ship["fire"]

    def fire_missiles():
        """Salwa rakiet; każda dostaje inny cel (najbliższe asteroidy)."""
        nonlocal missile_cd
        n, cd = missile_of(prog["levels"]["missile"])
        rocks = sorted((e for e in entities if e.name == "asteroid" and e.life),
                       key=lambda a: (a.x - player.x) ** 2 + (a.y - player.y) ** 2)
        for i, spread in enumerate({1: (0,), 2: (-28, 28), 3: (-45, 0, 45)}[n]):
            m = Missile(entities, rocks[i % len(rocks)] if rocks else None)
            m.settings(s_missile, player.x, player.y, player.angle + spread, 10)
            entities.append(m)
        missile_cd = cd

    def cast_wave():
        nonlocal wave_cd, shake
        i = prog["levels"]["wave"] - 1
        waves.append(Shockwave(player, WAVE_RADIUS[i], WAVE_DAMAGE[i]))
        wave_cd = WAVE_COOLDOWN[i]
        shake = 14

    def start_dash():
        """Phase Dash Interceptora: krótki sprint w kierunku dziobu, w trakcie którego statek jest nietykalny."""
        nonlocal dash_cd, phase_t
        player.dash_t = DASH_FRAMES
        player.dash_angle = player.angle
        dash_cd = DASH_COOLDOWN
        phase_t = PHASE_FRAMES
        burst(player.x, player.y, 10, (CYAN, WHITE, BLUE_D), speed=4.0, life=14)

    def buy_upgrade(i):
        u = UPGRADES[i]
        lvl = prog["levels"][u["key"]]
        if lvl >= len(u["costs"]):
            set_notice("ALREADY AT MAX", ORANGE)
            return
        cost = u["costs"][lvl]
        if prog["points"] < cost:
            set_notice(f"NEED {cost} POINTS", RED)
            return
        prog["points"] -= cost
        prog["levels"][u["key"]] = lvl + 1
        save_progress(PROGRESS_FILE, prog)
        set_notice("UPGRADED!", LIME)

    def select_ship(i):
        sh = SHIPS[i]
        if sh["id"] in prog["owned"]:
            prog["ship"] = sh["id"]
            set_notice("EQUIPPED", LIME)
        elif prog["points"] >= sh["cost"]:
            prog["points"] -= sh["cost"]
            prog["owned"].append(sh["id"])
            prog["ship"] = sh["id"]
            set_notice("UNLOCKED AND EQUIPPED!", LIME)
        else:
            set_notice(f"NEED {sh['cost']} POINTS", RED)
            return
        save_progress(PROGRESS_FILE, prog)

    def pips(x, y, filled, total, on, off, w=5, gap=2, h=5):
        for j in range(total):
            pygame.draw.rect(screen, on if j < filled else off, (x + j * (w + gap), y, w, h))

    def panel(rect):
        pygame.draw.rect(screen, NAVY, rect)
        pygame.draw.rect(screen, DARK, rect, 1)

    running = True
    while running:
        # ---------- zdarzenia ----------
        for event in pygame.event.get():
            if event.type == pygame.QUIT:
                running = False
            elif event.type == pygame.VIDEORESIZE:
                if not fullscreen:
                    windowed_size = (event.w, event.h)
            elif event.type == pygame.KEYDOWN:
                key = event.key
                if key == pygame.K_F11:
                    fullscreen = not fullscreen
                    open_window(fullscreen, windowed_size)
                elif state == "menu":
                    if key == pygame.K_UP:
                        selected = (selected - 1) % len(menu_items)
                    elif key == pygame.K_DOWN:
                        selected = (selected + 1) % len(menu_items)
                    elif key in (pygame.K_RETURN, pygame.K_KP_ENTER):
                        if selected == 0:
                            start_game()
                        elif selected == 1:
                            hangar_sel = next(i for i, s in enumerate(SHIPS) if s["id"] == prog["ship"])
                            notice[2] = 0
                            banner = ""
                            state = "hangar"
                        elif selected == 2:
                            notice[2] = 0
                            banner = ""
                            state = "upgrades"
                        elif selected == 3:
                            banner = ""
                            state = "scores"
                        else:
                            running = False
                elif state == "game":
                    if key == pygame.K_SPACE and fire_cooldown <= 1e-6:
                        shoot()
                    elif key == pygame.K_e and prog["levels"]["wave"] and wave_cd <= 1e-6:
                        cast_wave()
                    elif key in (pygame.K_LSHIFT, pygame.K_RSHIFT) and ship["dash"] and dash_cd <= 1e-6:
                        start_dash()
                    elif key == pygame.K_ESCAPE:
                        state = "menu"
                elif state == "scores":
                    if key == pygame.K_ESCAPE:
                        state = "menu"
                elif state == "hangar":
                    if key == pygame.K_LEFT:
                        hangar_sel = (hangar_sel - 1) % len(SHIPS)
                    elif key == pygame.K_RIGHT:
                        hangar_sel = (hangar_sel + 1) % len(SHIPS)
                    elif key in (pygame.K_RETURN, pygame.K_KP_ENTER):
                        select_ship(hangar_sel)
                    elif key == pygame.K_ESCAPE:
                        state = "menu"
                elif state == "upgrades":
                    if key == pygame.K_UP:
                        up_sel = (up_sel - 1) % len(UPGRADES)
                    elif key == pygame.K_DOWN:
                        up_sel = (up_sel + 1) % len(UPGRADES)
                    elif key in (pygame.K_RETURN, pygame.K_KP_ENTER):
                        buy_upgrade(up_sel)
                    elif key == pygame.K_ESCAPE:
                        state = "menu"

        # ---------- logika + rysowanie ----------
        if state == "menu":
            screen.blit(background, (0, 0))
            text("ASTEROIDS", 32, YELLOW, (0, 40), center=True, shadow=RED)
            blink = (pygame.time.get_ticks() // 400) % 2 == 0
            for i, label in enumerate(menu_items):
                if i == selected:
                    label = f"> {label} <" if blink else f"  {label}  "
                text(label, 16, YELLOW if i == selected else WHITE, (0, 112 + i * 26), center=True)
            if banner:
                text(banner, 8, ORANGE, (0, 250), center=True)
            text(f"POINTS {prog['points']}", 8, CYAN, (CW - 6, 6), right=True)
            text("UP/DOWN + ENTER", 8, GREY, (0, CH - 26), center=True)
            text("F11 - FULLSCREEN", 8, GREY, (0, CH - 14), center=True)

        elif state == "hangar":
            screen.blit(background, (0, 0))
            text("HANGAR", 24, YELLOW, (0, 14), center=True, shadow=RED)
            text(f"POINTS: {prog['points']}", 8, CYAN, (CW - 6, 6), right=True)
            sh = SHIPS[hangar_sel]
            owned = sh["id"] in prog["owned"]
            equipped = prog["ship"] == sh["id"]

            panel((24, 60, 190, 190))
            t = pygame.time.get_ticks()
            img = ship_frames[sh["id"]][(t // 250) % 2 if owned else 0]
            img = rotated(img, t // 30)
            img = pygame.transform.scale(img, (img.get_width() * 4, img.get_height() * 4))
            if not owned:
                img = img.copy()
                img.fill((90, 90, 110), special_flags=pygame.BLEND_RGB_MULT)
            screen.blit(img, img.get_rect(center=(119, 155)))
            if not owned:
                text("LOCKED", 8, ORANGE, (119 - 24, 232))
            for j in range(len(SHIPS)):  # kropki: który statek z kolei
                pygame.draw.rect(screen, YELLOW if j == hangar_sel else DARK, (119 - len(SHIPS) * 6 + j * 12, 68, 8, 4))
            if (t // 400) % 2 == 0:
                text("<", 16, WHITE, (6, 146))
                text(">", 16, WHITE, (216, 146))

            panel((232, 60, 224, 190))
            text(sh["name"], 16, YELLOW, (244, 72))
            for i, (label, val) in enumerate(zip(STAT_NAMES, sh["stats"])):
                y = 108 + i * 18
                text(label, 8, GREY, (244, y))
                pips(316, y, val, 5, LIME, DARK, w=12, gap=3, h=7)
            for i, line in enumerate(sh["perk"]):
                if line:
                    text(line, 8, WHITE, (244, 182 + i * 12))
            if equipped:
                text("EQUIPPED", 8, LIME, (244, 224))
            elif owned:
                text("OWNED - ENTER TO EQUIP", 8, CYAN, (244, 224))
            else:
                text(f"ENTER TO BUY: {sh['cost']} PTS", 8, YELLOW if prog["points"] >= sh["cost"] else RED, (244, 224))
            if notice[2] > 0:
                text(notice[0], 8, notice[1], (0, 258), center=True)
                notice[2] -= 1
            text("LEFT/RIGHT CHOOSE  ENTER SELECT  ESC BACK", 8, GREY, (0, CH - 16), center=True)

        elif state == "upgrades":
            screen.blit(background, (0, 0))
            text("UPGRADES", 24, YELLOW, (0, 12), center=True, shadow=RED)
            text(f"POINTS: {prog['points']}", 16, CYAN, (0, 40), center=True)
            panel((16, 62, CW - 32, len(UPGRADES) * 30 + 6))
            for i, u in enumerate(UPGRADES):
                y = 66 + i * 30
                lvl = prog["levels"][u["key"]]
                total = len(u["costs"])
                maxed = lvl >= total
                sel = i == up_sel
                if sel:
                    pygame.draw.rect(screen, DARK, (20, y, CW - 40, 28))
                    pygame.draw.rect(screen, YELLOW, (20, y, CW - 40, 28), 1)
                text(u["name"], 8, YELLOW if sel else WHITE, (28, y + 4), shadow=None)
                pips(176, y + 4, lvl, total, LIME if maxed else YELLOW, NAVY if sel else DARK)
                if maxed:
                    text("MAX", 8, LIME, (CW - 28, y + 4), right=True, shadow=None)
                else:
                    cost = u["costs"][lvl]
                    text(f"COST {cost}", 8, YELLOW if prog["points"] >= cost else RED, (CW - 28, y + 4),
                         right=True, shadow=None)
                text(upgrade_info(u["key"], lvl), 8, GREY, (28, y + 16), shadow=None)
            if notice[2] > 0:
                text(notice[0], 8, notice[1], (0, 258), center=True)
                notice[2] -= 1
            text("UP/DOWN SELECT  ENTER BUY  ESC BACK", 8, GREY, (0, CH - 16), center=True)

        elif state == "scores":
            screen.blit(background, (0, 0))
            text("SCORES", 24, YELLOW, (0, 22), center=True, shadow=RED)
            text(f"BEST {highscore}", 16, CYAN, (0, 62), center=True)
            text(f"LAST GAME  {last_score}", 8, WHITE, (0, 92), center=True)
            text(f"DESTROYED  {last_destroyed}", 8, WHITE, (0, 106), center=True)
            for i, s in enumerate(scores, 1):
                text(f"{i:>2}. {s}", 8, WHITE if i > 1 else YELLOW, (CW // 2 - 48, 130 + (i - 1) * 13))
            text("ESC - BACK", 8, GREY, (0, CH - 16), center=True)

        elif state == "game":
            lv = prog["levels"]
            dt = 1.0 / FPS
            fire_cooldown = max(0.0, fire_cooldown - dt) if fire_cooldown > 0 else 0.0
            missile_cd = max(0.0, missile_cd - dt)
            wave_cd = max(0.0, wave_cd - dt)
            dash_cd = max(0.0, dash_cd - dt)
            if invuln > 0:
                invuln -= 1
            if phase_t > 0:
                phase_t -= 1

            keys = pygame.key.get_pressed()
            if keys[pygame.K_d]:
                player.angle += player.turn
            if keys[pygame.K_a]:
                player.angle -= player.turn
            player.thrust = bool(keys[pygame.K_w])
            if keys[pygame.K_SPACE] and fire_cooldown <= 1e-6:  # przytrzymana spacja = ogień ciągły
                shoot()
            if lv["missile"] and keys[pygame.K_q] and missile_cd <= 1e-6:
                fire_missiles()

            # rosnące HP asteroid: komunikat przy każdym skoku
            base_hp = rock_hp(elapsed())
            if base_hp > last_hp:
                last_hp = base_hp
                toast[0], toast[1], toast[2] = f"ROCKS GROW TOUGHER! HP {base_hp}", ORANGE, 150

            # asteroidy po czasie ochronnym (część z nich jest złota)
            if elapsed() > safe_time and random.randrange(150) == 0:
                gold = random.random() < GOLD_CHANCE
                entities.append(new_rock(0, random.randrange(H), random.randrange(360), False, gold, base_hp))

            # --- kolizje ---
            game_over = False
            splashes = []
            for a in entities:
                if a.name != "asteroid" or not a.life:
                    continue
                for b in entities:
                    if b.name in ("bullet", "missile") and b.life and is_collide(a, b):
                        b.life = False
                        damage_asteroid(a, 4 if b.name == "missile" else b.dmg)
                        if b.name == "missile":
                            splashes.append((b.x, b.y, a))
                        break
                if a.life and is_collide(player, a):
                    if a.beam or invuln > 0 or phase_t > 0:  # cel beamu / tarcza / dash: bez obrażeń
                        continue
                    if shield_charges > 0:  # tarcza pochłania uderzenie i niszczy skałę
                        shield_charges -= 1
                        invuln = 90
                        shake = 10
                        kill_asteroid(a, split=False)
                        burst(player.x, player.y, 14, (WHITE, CYAN, BLUE_D), speed=5.0)
                        if ship["reactive"]:  # Bruiser: trafienie w tarczę wywołuje wybuch dookoła
                            waves.append(Shockwave(player, 240, 6, (ORANGE, YELLOW)))
                    else:
                        a.life = False
                        game_over = True
                        break

            # wybuch rakiety rani też asteroidy w pobliżu
            for sx, sy, src in splashes:
                burst(sx, sy, 14, (YELLOW, ORANGE, RED, PLUM))
                for a in entities:
                    if (a.name == "asteroid" and a.life and a is not src
                            and (a.x - sx) ** 2 + (a.y - sy) ** 2 <= (90 + a.R) ** 2):
                        damage_asteroid(a, 2)

            # fala uderzeniowa rani każdą asteroidę, którą minie (raz na falę)
            for w in waves:
                if w.active:
                    r = w.r
                    for a in entities:
                        if (a.name == "asteroid" and a.life and a not in w.hit
                                and math.hypot(a.x - w.x, a.y - w.y) <= r + a.R):
                            w.hit.add(a)
                            damage_asteroid(a, w.damage, split=False)

            # traktor-beam Harvestera: namierza, przyciąga i zamienia asteroidę w punkty
            if ship["beam"] and not game_over:
                if beam_target is not None and (
                        not beam_target.life
                        or math.hypot(beam_target.x - player.x, beam_target.y - player.y) > BEAM_RANGE * 1.3):
                    beam_target.beam = False
                    beam_target = None
                if beam_target is None:  # najpierw złote, potem najbliższe
                    best, best_key = None, None
                    for a in entities:
                        if a.name == "asteroid" and a.life:
                            d = math.hypot(a.x - player.x, a.y - player.y)
                            if d <= BEAM_RANGE and (best_key is None or (not a.gold, d) < best_key):
                                best, best_key = a, (not a.gold, d)
                    if best is not None:
                        beam_target, best.beam, best.pull_t = best, True, 0
                if beam_target is not None:
                    a = beam_target
                    dxp, dyp = player.x - a.x, player.y - a.y
                    d = math.hypot(dxp, dyp) or 1.0
                    if d <= player.R + a.R + 10:
                        convert_asteroid(a)
                        beam_target = None
                    else:
                        a.pull_t += 1
                        spd = min(9.0, 2.5 + a.pull_t * 0.12) * (0.75 if a.gold else 1.0)
                        a.dx += (dxp / d * spd - a.dx) * 0.2
                        a.dy += (dyp / d * spd - a.dy) * 0.2

            entities.extend(pending)
            pending.clear()

            if game_over:
                score = int(elapsed()) * 100 + kill_points
                highscore = update_scores(scores, score, highscore)
                save_scores(SCORE_FILE, highscore, scores, score, destroyed)
                last_score, last_destroyed = score, destroyed
                gain = score // 2000  # 1 punkt ulepszeń za każde 2000
                prog["points"] += gain
                save_progress(PROGRESS_FILE, prog)
                banner = f"RUN OVER  SCORE {score}  +{gain} PTS"
                state = "menu"
            else:
                player.anim = ship_anims[ship["id"]][1 if player.thrust else 0]

                for e in entities:
                    if e.name == "explosion" and e.anim.is_end():
                        e.life = False

                for e in entities:
                    e.update()
                    e.anim.update()
                    if e.name == "asteroid" and e.gold and random.random() < 0.12:  # błyski na złocie
                        particles.append(Sparkle(e.x + random.uniform(-e.R, e.R), e.y + random.uniform(-e.R, e.R)))
                    if e.name == "missile":  # smuga za rakietą
                        rad = e.angle * DEGTORAD
                        particles.append(Particle(e.x - math.cos(rad) * 14 + random.uniform(-3, 3),
                                                  e.y - math.sin(rad) * 14 + random.uniform(-3, 3),
                                                  random.uniform(-0.4, 0.4), random.uniform(-0.4, 0.4),
                                                  16, MISSILE_TRAIL))
                if player.dash_t > 0:  # powidoki dashu
                    ghosts.append(Ghost(player.x, player.y, rotated(player.anim.image, player.angle + 90)))
                for p in particles:
                    p.update()
                for g_ in ghosts:
                    g_.update()
                for w in waves:
                    w.update()
                for f in floats:
                    f[1] -= 1.6
                    f[4] -= 1
                entities[:] = [e for e in entities if e.life]
                particles[:] = [p for p in particles if p.life > 0]
                ghosts[:] = [g_ for g_ in ghosts if g_.life > 0]
                waves[:] = [w for w in waves if w.life]
                floats[:] = [f for f in floats if f[4] > 0]

                # --- rysowanie ---
                screen.blit(background, (0, 0))
                for w in waves:
                    w.draw(screen)
                if beam_target is not None and beam_target.life:  # wiązka i celownik na asteroidzie
                    x0, y0 = round(player.x * K), round(player.y * K)
                    x1, y1 = round(beam_target.x * K), round(beam_target.y * K)
                    n = max(1, int(math.hypot(x1 - x0, y1 - y0)))
                    ph = pygame.time.get_ticks() // 50
                    pulse = (YELLOW, YELLOW, WHITE, ORANGE)
                    for i in range(n + 1):
                        f = i / n
                        c = pulse[(i + ph) % 4]
                        size = 2 if c == WHITE else 1  # jaśniejsze "paczki energii" płyną wzdłuż wiązki
                        screen.fill(c, (round(x0 + (x1 - x0) * f), round(y0 + (y1 - y0) * f), size, size))
                    rr = int(beam_target.R * K) + 3
                    for sx in (-1, 1):
                        for sy in (-1, 1):
                            cx, cy = x1 + sx * rr, y1 + sy * rr
                            screen.fill(YELLOW, (cx if sx < 0 else cx - 2, cy, 3, 1))
                            screen.fill(YELLOW, (cx, cy if sy < 0 else cy - 2, 1, 3))
                for g_ in ghosts:
                    g_.draw(screen)
                ship_blink = invuln > 0 and (invuln // 3) % 2 == 0
                for e in entities:
                    if e is player and ship_blink:
                        continue
                    e.draw(screen)
                for p in particles:
                    p.draw(screen)
                for f in floats:
                    text(f[2], 8, f[3], (round(f[0] * K), round(f[1] * K)), mid=True)
                if shield_charges > 0 or invuln > 0:
                    c = (round(player.x * K), round(player.y * K))
                    ring = WHITE if invuln > 0 else CYAN
                    pygame.draw.circle(screen, ring, c, int((player.R + 7) * K), 1)

                t = int(elapsed())
                text(f"HIGHSCORE {highscore}", 8, WHITE, (6, 6))
                text(f"TIME {t // 60}:{t % 60:02d}", 8, WHITE, (6, 18))
                text(f"SCORE {t * 100 + kill_points}", 8, WHITE, (6, 30))
                text(f"DESTROYED {destroyed}", 8, WHITE, (6, 42))
                text(f"ROCK HP {base_hp}", 8, ORANGE if base_hp > 1 else GREY, (6, 54))
                if max_shields:
                    text("SHIELD", 8, CYAN, (6, 66))
                    pips(62, 66, shield_charges, max_shields, CYAN, DARK, w=6, gap=2, h=7)
                if toast[2] > 0:
                    if toast[2] > 30 or (toast[2] // 3) % 2 == 0:
                        text(toast[0], 8, toast[1], (0, 84), center=True)
                    toast[2] -= 1
                text("ESC - MENU", 8, GREY, (CW - 6, CH - 14), right=True)

                def cooldown_bar(y, label, remaining, total):
                    frac = 1.0 - remaining / total
                    ready = remaining <= 1e-6
                    text(label, 8, LIME if ready else GREY, (6, y))
                    x0 = 6 + len(label) * 8 + 6
                    pygame.draw.rect(screen, DARK, (x0, y, 40, 7))
                    pygame.draw.rect(screen, LIME if ready else ORANGE, (x0, y, int(40 * frac), 7))
                    pygame.draw.rect(screen, NAVY, (x0, y, 40, 7), 1)

                bars = []
                if lv["wave"]:
                    bars.append(("E SHOCKWAVE", wave_cd, WAVE_COOLDOWN[lv["wave"] - 1]))
                if lv["missile"]:
                    bars.append(("Q MISSILES", missile_cd, missile_of(lv["missile"])[1]))
                if ship["dash"]:
                    bars.append(("SHIFT DASH", dash_cd, DASH_COOLDOWN))
                for i, (label, remaining, total) in enumerate(bars):
                    cooldown_bar(CH - 14 - i * 12, label, remaining, total)
                if ship["beam"]:
                    locked = beam_target is not None
                    text("TRACTOR BEAM", 8, GREY, (6, CH - 14 - len(bars) * 12))
                    text("LOCKED" if locked else "SCANNING", 8, YELLOW if locked else GREY,
                         (6 + 13 * 8, CH - 14 - len(bars) * 12))

                if shake > 0:  # drżenie ekranu po fali / trafieniu w tarczę
                    screen.scroll(random.randint(-2, 2), random.randint(-2, 2))
                    shake -= 1

        present(screen)
        clock.tick(FPS)

    pygame.quit()
    sys.exit()


if __name__ == "__main__":
    main()
