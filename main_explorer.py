"""Asteroids: FRONTIER (pygame, pixel art).

Nowy tryb gry: nieskończony kosmos, własna planeta-baza, wyprawy po surowce i zakupy za kredyty.

  * Startujesz z bazy na planecie. Wokół niej jest strefa bezpieczna bez asteroid.
  * Dalej zaczynają się asteroidy (im dalej od bazy, tym twardsze i bogatsze) oraz rzadkie, wielkie planety.
  * Strzelaj w planety, żeby wykuwać surowce, i zbieraj je (ładownia ma ograniczoną pojemność).
  * Wokół ok. 40% planet krąży gęste skupisko asteroid (na minimapie widać je jako pierścień), a w nim
    kolosalne asteroidy: dużo HP, rozpadają się na duże skały i zostawiają mnóstwo surowca.
  * Z surowcami wracasz do bazy. Gdy podlecisz blisko, statek sam ustawia się i ląduje, a ładunek
    zamienia się na kredyty. Za kredyty kupujesz ulepszenia i statki.
  * Zniszczenie statku = utrata ładunku (kredyty i zakupy zostają).
  * Minimapa w rogu pokazuje bazę (strzałka na brzegu, gdy jest daleko) i strefę bezpieczną.
  * Ekran BASE: rozbudowa bazy surowcami (Drill Rigs = pasywny dochód, Refinery = lepsze ceny,
    Vault = pojemność dochodu) oraz zakup dronów, które same latają po surowce (drogie).
  * 7 surowców: iron, crystal, gold oraz titanium, emerald, plasma i voidium (coraz dalej od bazy).
  * Ekran BASE ma też ulepszenia planety za kredyty i surowce: Scanner Array, Trade Hub, Shield Grid,
    Warp Beacon (klawisz H = skok pod bazę), Engine Lab i Orbital Ring (widoczny pierścień, mnożnik dochodu).
  * AUTO TURRET: automatyczne działko, wyłącznie dla Bruisera (ulepszenie w SPECIALS).

Uruchomienie:
    pip install pygame
    python main_explorer.py
    python main_explorer.py --credits 500     # (opcjonalnie) dodaje kredyty na start

Sterowanie: A/D obrót, W przyspieszenie, S małe dopalacze wsteczne (hamowanie/cofanie), SPACJA strzał
(przytrzymaj = ogień ciągły), Q rakiety samonaprowadzające (tylko Bruiser i Striker), E fala uderzeniowa
(tylko Interceptor), ESC pauza, F11 pełny ekran (okno bez ramki na cały monitor).
SHIFT = zdolność aktywna statku: Scout (Field Repair), Interceptor (Phase Dash), Striker (Overdrive),
Surveyor (Deep Scan), Hauler (Gravity Well z odrzutem na koniec). Bruiser ma Auto Turret, Harvester traktor-beamy (działają same).
Menu bazy -> SPECIALS: każdy statek ma 3 własne linie ulepszeń (ok. 15 poziomów): rakiety kasetowe, podwójny dash,
Kill Combo, Nano Regen, do 6 beamów, Mega Hold itd. Zdolności mają rozbudowane animacje (aura, wir, sweep radaru, wiązki).
Widok dopasowuje się do proporcji okna (16:9, 21:9...), więc nie ma czarnych pasów.
Menu bazy -> SAVES: 3 sloty zapisu (nowa gra, wczytanie, kasowanie DEL). Zapisy: frontier.json (slot 1),
frontier_2.json, frontier_3.json.
Menu bazy -> SETTINGS: limit FPS (60/90/120/144/240). Symulacja gry zawsze działa w tym samym tempie
niezależnie od wybranego FPS-a - wyższy limit daje tylko płynniejszy obraz, nie przyspiesza gry.
"""
import json
import math
import os
import random
import sys
import time
from pathlib import Path
from types import SimpleNamespace

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
W, H = 1200, 800           # bazowy rozmiar widoku w jednostkach logiki (dla ZOOM = 1)
CW, CH = 480, 320          # warstwa HUD/menu; szerokość CW jest dopasowywana do proporcji okna (set_view)
K = 0.4                    # logika -> piksele płótna
ZOOM = 3                   # oddalenie kamery: widać ZOOM razy więcej świata w poziomie i pionie (obsługiwane 1-3; 2 = łagodniej)
VW, VH = CW * ZOOM, CH * ZOOM   # rozmiar płótna ze światem
KEY = (255, 0, 255)        # kolor przezroczysty warstwy HUD
ICE_C = (115, 239, 247)    # lodowy błękit (efekty)


def set_view(aspect):
    """Dopasowuje szerokość widoku do proporcji okna, żeby nie było czarnych pasów po bokach."""
    global CW, VW, VH
    CW = max(426, min(768, int(round(CH * aspect / 2.0)) * 2))
    VW, VH = CW * ZOOM, CH * ZOOM
FPS = 60                   # bazowa "jednostka" czasu gry: wszystkie tabele (sekundy->klatki) liczą względem 60/s.
RENDER_FPS_OPTIONS = (60, 90, 120, 144, 240)   # wybieralny limit odświeżania (ekran SETTINGS)
DT_SCALE = 1.0              # aktualny_dt * FPS; przy 60 FPS = 1.0 (dokładnie jak dawniej), przy 120 = 0.5 itd.
DT_SCALE_CAP = 3.0           # ochrona przed skokiem po zacięciu (np. przeciąganie okna)
DEGTORAD = 0.017453
MIN_FIRE_RATE = 0.05
FIRE_STEP = 0.05
ROT_STEP = 5
BULLET_SPEED = 13.0        # prędkość pocisków (px logiki / klatkę); było 6
BULLET_LIFE = 110          # klatek życia pocisku (zasięg = prędkość * życie)
MISSILE_SPEED = 14.0       # maksymalna prędkość rakiet
SHIP_SPEED_MULT = 1.0      # mnożnik prędkości wszystkich statków (2.0 = dwa razy szybsze)

# świat
WORLD_SEED = 20240921
BASE_R = 1320              # promień planety-bazy (logika)
BASE_ART_R = int(BASE_R * 0.4)   # ten sam promień w pikselach płótna
PAD_R = BASE_R - 60        # odległość lądowisk od środka planety
N_PADS = 16
PAD_OFFSET = math.pi / N_PADS
DOCK_R = BASE_R + 500      # w tej odległości od środka bazy zaczyna się automatyczne lądowanie
LAUNCH_DIST = DOCK_R - PAD_R + 60   # o ile statek odlatuje od lądowiska w animacji startu
SAFE_R = 5200              # strefa bez asteroid
PLANET_MIN_D = 6400        # najbliższa planeta z surowcami
TIER_STEP = 5000           # co tyle dalej od bazy asteroidy robią się twardsze
CHUNK = 6500               # rozmiar "kafelka" świata: w każdym jest najwyżej jedna planeta (rzadkie)
RES_R = 220                # promień planet z surowcami (jak dawna planeta-baza)
HP_MAX = 25
BEAM_RANGE = 420
DASH_FRAMES = 8
DASH_SPEED = 30
DASH_COOLDOWN = 3.5
PHASE_FRAMES = 22
LAND_FRAMES = 100
LAUNCH_FRAMES = 70
MAP_RANGE = 12000          # zasięg minimapy (logika)
SCAN_MULT = 2.0            # o ile Deep Scan Surveyora powiększa zasięg minimapy
MM_S = 70                  # średnica minimapy (px płótna)
CARGO_CAP = (30, 45, 65, 90, 125, 170, 250, 400, 650, 1000, 1600, 2500,          # poziomy 0-11
             3600, 5000, 7000, 10000, 14000, 19000, 26000, 35000, 48000, 65000, 90000)   # poziomy 12-22

BASE_DIR = Path(__file__).resolve().parent
ASSETS = BASE_DIR / "assets"
PIXEL = BASE_DIR / "assets_pixel"
SAVE_FILE = BASE_DIR / "frontier.json"

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

# surowce: kolor, cena w kredytach za sztukę
ORE = {
    "iron": dict(name="IRON", color=ORANGE, value=2),
    "crystal": dict(name="CRYSTAL", color=CYAN, value=6),
    "gold": dict(name="GOLD", color=YELLOW, value=15),
    "titanium": dict(name="TITANIUM", color=(200, 215, 235), value=4),
    "emerald": dict(name="EMERALD", color=(56, 183, 100), value=30),
    "plasma": dict(name="PLASMA", color=(220, 90, 200), value=60),
    "voidium": dict(name="VOIDIUM", color=(150, 100, 255), value=150),
}
ORE_KINDS = ("iron", "crystal", "gold", "titanium", "emerald", "plasma", "voidium")   # kolejność = wiersze arkusza planet


# --------------------
# Kamera i drobne narzędzia
# --------------------
CAM = [0.0, 0.0]


def sp(x, y):
    """Współrzędne świata -> piksele płótna (kamera wyśrodkowana na CAM)."""
    return round((x - CAM[0]) * K) + VW // 2, round((y - CAM[1]) * K) + VH // 2


def on_screen(x, y, margin=350):
    return abs(x - CAM[0]) < VW / K / 2 + margin and abs(y - CAM[1]) < VH / K / 2 + margin


def angle_diff(a, b):
    """Najkrótsza różnica kątów (stopnie) z a do b."""
    return (b - a + 180) % 360 - 180


def smoothstep(u):
    u = max(0.0, min(1.0, u))
    return u * u * (3 - 2 * u)


# --------------------
# Zapis postępu (kredyty, ulepszenia, statki)
# --------------------
SLOTS = 3


def slot_path(n):
    """Slot 1 to dawny frontier.json (stare zapisy działają dalej), pozostałe: frontier_2.json, frontier_3.json."""
    return SAVE_FILE if n == 1 else SAVE_FILE.with_name(f"frontier_{n}.json")


def settings_path():
    return SAVE_FILE.with_name("frontier_settings.json")


def read_settings():
    try:
        return json.loads(settings_path().read_text(encoding="utf-8"))
    except (OSError, ValueError, TypeError, AttributeError):
        return {}


def write_settings(patch):
    """Uaktualnia plik ustawień w miejscu (slot aktywny + limit FPS), nie nadpisując drugiego pola."""
    data = read_settings()
    data.update(patch)
    try:
        settings_path().write_text(json.dumps(data), encoding="utf-8")
    except OSError:
        pass


def read_active_slot():
    try:
        n = int(read_settings().get("slot", 1))
    except (ValueError, TypeError):
        n = 1
    return n if 1 <= n <= SLOTS else 1


def write_active_slot(n):
    write_settings({"slot": n})


def read_render_fps():
    try:
        n = int(read_settings().get("fps", 60))
    except (ValueError, TypeError):
        n = 60
    return n if n in RENDER_FPS_OPTIONS else 60


def write_render_fps(n):
    write_settings({"fps": n})


def default_save():
    return {"seed": WORLD_SEED, "credits": 0, "levels": {}, "owned": ["scout"], "ship": "scout",
            "base": {m["key"]: 0 for m in BASE_MODULES}, "project": None, "vault": 0.0,
            "drones": 0, "drone_tech": 0, "saved_at": 0.0}


def load_save(path, upgrade_keys, ship_ids):
    data = default_save()
    data["levels"] = {k: 0 for k in upgrade_keys}
    data["base"] = {m["key"]: 0 for m in BASE_MODULES}
    try:
        raw = json.loads(path.read_text(encoding="utf-8"))
        data["seed"] = int(raw.get("seed", WORLD_SEED))
        data["credits"] = max(0, int(raw.get("credits", 0)))
        for k, costs in upgrade_keys.items():
            data["levels"][k] = max(0, min(len(costs), int(raw.get("levels", {}).get(k, 0))))
        data["owned"] = sorted({o for o in raw.get("owned", []) if o in ship_ids} | {"scout"})
        data["ship"] = raw.get("ship") if raw.get("ship") in data["owned"] else "scout"
        for m in BASE_MODULES:  # poziomy modułów bazy
            data["base"][m["key"]] = max(0, min(len(m["costs"]), int(raw.get("base", {}).get(m["key"], 0))))
        data["vault"] = max(0.0, float(raw.get("vault", 0.0)))
        data["drones"] = max(0, min(len(DRONE_COSTS), int(raw.get("drones", 0))))
        data["drone_tech"] = max(0, min(len(DRONE_TECH_COSTS), int(raw.get("drone_tech", 0))))
        data["saved_at"] = float(raw.get("saved_at", 0.0))
        pr = raw.get("project")
        if isinstance(pr, dict) and pr.get("key") in {m["key"] for m in BASE_MODULES}:
            m = module_by_key(pr["key"])
            if data["base"][m["key"]] < len(m["costs"]):
                data["project"] = {"key": pr["key"], "paid": max(0, int(pr.get("paid", 0))),
                                   "progress": {k: max(0, int(pr.get("progress", {}).get(k, 0))) for k in ORE_KINDS}}
    except (OSError, ValueError, TypeError, AttributeError):
        pass
    return data


def write_save(path, data):
    data["saved_at"] = time.time()
    try:
        path.write_text(json.dumps(data, indent=2), encoding="utf-8")
    except OSError:
        print("Nie można zapisać postępu:", path)


# --------------------
# Okno: skalowanie do rozdzielczości ekranu
# --------------------
def default_window_size():
    dw, dh = pygame.display.get_desktop_sizes()[0]
    return int(dw * 0.9), int(dh * 0.85)


def open_window(fullscreen, size):
    if fullscreen:  # "pełny ekran" jako okno bez ramki na cały monitor: bez zmiany trybu wideo (płynny alt-tab)
        dw, dh = pygame.display.get_desktop_sizes()[0]
        return pygame.display.set_mode((dw, dh), pygame.NOFRAME)
    return pygame.display.set_mode(size, pygame.RESIZABLE)


def present(canvas):
    """Skaluje płótno (480x320 w menu, 1440x960 w locie) do okna z zachowaniem proporcji."""
    win = pygame.display.get_surface()
    ww, wh = win.get_size()
    cw, ch = canvas.get_size()
    s = min(ww / cw, wh / ch)
    tw, th = int(cw * s), int(ch * s)
    if tw < 1 or th < 1:
        pygame.display.flip()
        return
    if (tw, th) != (ww, wh):
        win.fill((0, 0, 0))
    rect = ((ww - tw) // 2, (wh - th) // 2, tw, th)
    try:
        dest = win.subsurface(rect)
        if s < 0.9:
            pygame.transform.smoothscale(canvas, (tw, th), dest)
        elif s >= 4 or abs(s - round(s)) < 0.04 or 0.9 <= s < 1.1:
            pygame.transform.scale(canvas, (tw, th), dest)
        else:
            k = int(s)
            step = pygame.transform.scale(canvas, (cw * k, ch * k))
            pygame.transform.smoothscale(step, (tw, th), dest)
    except (ValueError, pygame.error):
        win.blit(pygame.transform.scale(canvas, (tw, th)), rect[:2])
    pygame.display.flip()


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
        self.frame += self.speed * DT_SCALE   # tempo animacji niezależne od limitu FPS
        n = len(self.frames)
        if self.frame >= n:
            self.frame %= n

    def is_end(self):
        return self.frame + self.speed * DT_SCALE >= len(self.frames)

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
            self.dash_t -= DT_SCALE
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
                self.dx += math.cos(self.angle * DEGTORAD) * self.speed * self.boost * 0.05 * DT_SCALE
                self.dy += math.sin(self.angle * DEGTORAD) * self.speed * self.boost * 0.05 * DT_SCALE
            elif self.reverse:  # dopalacze wsteczne: słabsze niż silnik główny
                self.dx -= math.cos(self.angle * DEGTORAD) * self.speed * self.boost * 0.05 * 0.6 * DT_SCALE
                self.dy -= math.sin(self.angle * DEGTORAD) * self.speed * self.boost * 0.05 * 0.6 * DT_SCALE
                self.dx *= 0.985 ** DT_SCALE
                self.dy *= 0.985 ** DT_SCALE
            else:
                self.dx *= 0.99 ** DT_SCALE
                self.dy *= 0.99 ** DT_SCALE
            v = math.hypot(self.dx, self.dy)
            cap = self.max_speed * self.boost
            if v > cap:
                self.dx *= cap / v
                self.dy *= cap / v
        self.x += self.dx * DT_SCALE
        self.y += self.dy * DT_SCALE


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
        self.x += self.dx * DT_SCALE
        self.y += self.dy * DT_SCALE
        if self.flash > 0:
            self.flash -= DT_SCALE
        if self.crush_cd > 0:
            self.crush_cd -= DT_SCALE
        if self.knock > 0:
            self.knock -= DT_SCALE

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
        self.age += DT_SCALE
        self.dx = math.cos(self.angle * DEGTORAD) * BULLET_SPEED + self.ivx
        self.dy = math.sin(self.angle * DEGTORAD) * BULLET_SPEED + self.ivy
        self.x += self.dx * DT_SCALE
        self.y += self.dy * DT_SCALE
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
        self.age += DT_SCALE
        t = self.target
        if t is None or not t.life:
            t = self.target = nearest_asteroid(self.world, self.x, self.y)
        if t is not None and self.age > 6:
            want = math.degrees(math.atan2(t.y - self.y, t.x - self.x))
            diff = (want - self.angle + 180) % 360 - 180
            turn = self.TURN * DT_SCALE
            self.angle += max(-turn, min(turn, diff))
        self.spd = min(MISSILE_SPEED, self.spd + 0.35 * DT_SCALE)
        self.dx = math.cos(self.angle * DEGTORAD) * self.spd
        self.dy = math.sin(self.angle * DEGTORAD) * self.spd
        self.x += self.dx * DT_SCALE
        self.y += self.dy * DT_SCALE
        if self.age > 240:
            self.life = False


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
        self.t += DT_SCALE
        for b in self.bolts:
            b[2] -= DT_SCALE
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
            self.delay -= DT_SCALE
            return
        self.t += DT_SCALE
        self.life -= DT_SCALE

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
        self.x += self.dx * DT_SCALE
        self.y += self.dy * DT_SCALE
        self.dx *= 0.95 ** DT_SCALE
        self.dy *= 0.95 ** DT_SCALE
        self.life -= DT_SCALE

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
        self.life -= DT_SCALE

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
        self.life -= DT_SCALE

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
    x = n * DT_SCALE
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
            self.delay -= DT_SCALE
            return
        self.t += DT_SCALE
        self.life -= DT_SCALE

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
        self.x += self.dx * DT_SCALE
        self.y += self.dy * DT_SCALE
        k = self.drag ** DT_SCALE
        self.dx *= k
        self.dy *= k
        self.life -= DT_SCALE

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
        self.x += self.dx * DT_SCALE
        self.y += self.dy * DT_SCALE
        k = 0.965 ** DT_SCALE
        self.dx *= k
        self.dy *= k
        self.life -= DT_SCALE

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
        self.delay -= DT_SCALE
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
        self.age += DT_SCALE
        self.life -= DT_SCALE
        mg = magnet or self.MAGNET
        px, py = player.x - self.x, player.y - self.y
        d = math.hypot(px, py) or 1.0
        if self.pull > 0:
            self.pull -= DT_SCALE
        if can_pick and (d < mg or self.pull > 0):
            spd = 22.0 if self.pull > 0 else min(22.0, 7.0 + (mg - d) * 0.09)
            lerp = min(1.0, 0.3 * DT_SCALE)
            self.dx += (px / d * spd - self.dx) * lerp
            self.dy += (py / d * spd - self.dy) * lerp
        else:
            self.dx *= 0.99 ** DT_SCALE
            self.dy *= 0.99 ** DT_SCALE
        self.x += self.dx * DT_SCALE
        self.y += self.dy * DT_SCALE
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


def income_rate(base):
    """Pasywny dochód (kredytów/min): Drill Rigs razy mnożnik Orbital Ring."""
    return DRILL_INCOME[base["drill"]] * RING_MULT[base["ring"]]


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


# --------------------
# Gra
# --------------------
BASE_OBJ = SimpleNamespace(x=0.0, y=0.0, R=BASE_R)
MISSILE_TRAIL = (YELLOW, ORANGE, RED, PLUM, DARK)


def main():
    pygame.init()
    pygame.display.set_caption("Asteroids: Frontier")
    windowed_size = default_window_size()
    fullscreen = False
    render_fps = read_render_fps()
    open_window(fullscreen, windowed_size)
    screen = world = veil = None   # warstwa HUD/menu, płótno świata i zasłona pauzy (tworzone w apply_view)

    def apply_view():
        """Dopasowuje warstwy do proporcji okna: brak czarnych pasów na monitorach innych niż 3:2."""
        nonlocal screen, world, veil
        ww, wh = pygame.display.get_surface().get_size()
        set_view(ww / max(1, wh))
        if screen is None or screen.get_width() != CW:
            screen = pygame.Surface((CW, CH)).convert()
            world = pygame.Surface((VW, VH)).convert()
            veil = pygame.Surface((VW, VH))
            veil.fill(NAVY)
            veil.set_alpha(150)

    apply_view()
    clock = pygame.time.Clock()

    upgrade_keys = dict(ALL_UPGRADE_COSTS)
    ship_ids = [s_["id"] for s_ in SHIPS]
    active_slot = read_active_slot()
    save = load_save(slot_path(active_slot), upgrade_keys, ship_ids)
    WORLD.seed = save["seed"]  # każdy zapis ma własny świat
    WORLD.reset()
    if "--credits" in sys.argv:
        try:
            save["credits"] += int(sys.argv[sys.argv.index("--credits") + 1])
            write_save(slot_path(active_slot), save)
        except (ValueError, IndexError):
            pass

    # --- Zasoby ---
    def load(name):
        return pygame.image.load(str(PIXEL / name)).convert_alpha()

    def strip(name, count, speed):
        sheet = load(name)
        fw = sheet.get_width() // count
        frames = [sheet.subsurface((i * fw, 0, fw, sheet.get_height())).copy() for i in range(count)]
        return Animation(frames, speed)

    def planet_sheet(name):
        sheet = load(name)
        out = {}
        for row, kind in enumerate(ORE_KINDS):
            for v in range(2):
                out[(kind, v)] = sheet.subsurface((v * 192, row * 192, 192, 192)).copy()
        return out

    bg_src = pygame.image.load(str(PIXEL / "space_bg_big.png")).convert()
    bgw, bgh = bg_src.get_size()  # kafelek 1440x960; okres = szerokość widoku, więc wzór się nie powtarza w kadrze
    bg_big = pygame.Surface((bgw * 3, bgh * 2)).convert()
    for i_ in range(3):
        for j_ in range(2):
            bg_big.blit(bg_src, (i_ * bgw, j_ * bgh))

    def star_layer(name):
        src = load(name)
        w_, h_ = src.get_size()
        flat = pygame.Surface((w_, h_)).convert()
        flat.fill((0, 0, 0))
        flat.blit(src, (0, 0))
        big = pygame.Surface((w_ * 3, h_ * 2)).convert()
        big.fill((0, 0, 0))
        for i_ in range(3):
            for j_ in range(2):
                big.blit(flat, (i_ * w_, j_ * h_))
        big.set_colorkey((0, 0, 0))  # colorkey zamiast kanału alfa: dużo szybsze rysowanie
        return big

    stars_far_big, stars_near_big = star_layer("stars_far_big.png"), star_layer("stars_near_big.png")
    base_img = load("base_planet.png")
    bld_img = {k: load(f"bld_{k}.png") for k in ("drill", "refinery", "vault", "hq", "scanner", "trade", "shield",
                                                 "warp", "engine")}
    planet_img, dead_img = planet_sheet("planets.png"), planet_sheet("planets_depleted.png")
    s_explosion = strip("explosion.png", 48, 0.5)
    s_rock = strip("rock.png", 16, 0.2)
    s_rock_small = strip("rock_small.png", 16, 0.2)
    s_rock_gold = strip("rock_gold.png", 16, 0.2)
    s_rock_small_gold = strip("rock_small_gold.png", 16, 0.2)
    s_rock_colossus = strip("rock_colossus.png", 16, 0.25)
    s_rock_colossus_gold = strip("rock_colossus_gold.png", 16, 0.25)
    s_bullet = strip("bullet.png", 16, 0.8)
    s_missile = strip("missile.png", 3, 0.3)
    drone_frames = strip("drone.png", 2, 0).frames
    ship_frames, ship_anims = {}, {}
    for sh in SHIPS:
        two = strip(sh["sheet"], 2, 0)
        ship_frames[sh["id"]] = two.frames
        idle = Animation([two.frames[0]], 0)  # w grze płomienie są rysowane osobno (większe i animowane)
        ship_anims[sh["id"]] = (idle, idle.copy())

    font_path = str(ASSETS / "PressStart2P-Regular.ttf")
    fonts = {}

    def text(msg, size, color, pos, center=False, right=False, mid=False, shadow=NAVY):
        if size not in fonts:
            fonts[size] = pygame.font.Font(font_path, size)
        f = fonts[size]
        surf = f.render(msg, False, color)
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

    # --- Stan ---
    entities, ores, particles, waves, ghosts, floats, pending = [], [], [], [], [], [], []
    fx = []   # pierścienie i inne efekty w świecie (FxRing)
    flash_cache = {}
    S = SimpleNamespace(
        state="base", phase="fly", t=0, player=None, ship=SHIPS[0],
        cargo={k: 0 for k in ORE_KINDS}, cap=CARGO_CAP[0],
        fire_cd=0.0, missile_cd=0.0, wave_cd=0.0, dash_cd=0.0,
        shield=0, max_shield=0, invuln=0, phase_t=0, shake=0,
        beam_targets=[], undock_lock=False,
        pad=0, land_from=(0.0, 0.0), land_a0=0.0, unload_q=[], idle_t=0, sold=0, tally={k: 0 for k in ORE_KINDS},
        sel=0, hangar_sel=0, up_sel=0, build_sel=0, lines=[], pause_bg=None, dead_t=0,
        turret_cd=0.0, turret_msl_cd=0.0, turret_angle=0.0, turret_flash=0, frac=0.0, drones=[],
        slot=active_slot, slot_sel=active_slot - 1, slot_info=[], confirm=(-1, 0), ab_t=0, turn_dir=0,
        ab_total=1, well_t=0, well_total=1, wave_queue=[], spec_ship=0, spec_sel=0,
        unload_total=0, pick={k: 0 for k in ORE_KINDS}, pick_t=0, map_planets=[], warps=0, build_scroll=0,
        combo=0, combo_t=0, regen_t=0.0, dash_charges=1, dash_rt=0.0, dash_prev=0, turret_target=None,
        flash=0, flash_col=WHITE, react_fx=0, scan_ping_cd=0.0, well_ping_cd=0.0, dust_cd=0.0, unload_cd=0.0, vault_done=False,
        fps_sel=RENDER_FPS_OPTIONS.index(render_fps),
        div={k: 0 for k in ORE_KINDS}, div_t={k: 0 for k in ORE_KINDS}, sold_f=0.0, vault_got=0,
        notice=["", WHITE, 0], toast=["", WHITE, 0],
    )
    S.entities, S.ores = entities, ores  # dla testów i podglądu
    menu_items = ["LAUNCH", "UPGRADES", "SPECIALS", "HANGAR", "BASE", "SAVES", "SETTINGS", "EXIT GAME"]

    def ship_by_id(sid):
        return next(s for s in SHIPS if s["id"] == sid)

    def set_notice(msg, color):
        S.notice[0], S.notice[1], S.notice[2] = msg, color, 90

    def set_toast(msg, color, frames=150):
        S.toast[0], S.toast[1], S.toast[2] = msg, color, frames

    def cargo_total():
        return sum(S.cargo.values())

    def cargo_free():
        return S.cap - cargo_total()

    def add_cargo(kind, n):
        """Dodaje do ładowni (max do pojemności); zwraca ile faktycznie weszło."""
        n = max(0, min(n, cargo_free()))
        S.cargo[kind] += n
        if n and cargo_free() == 0:
            set_toast("CARGO FULL - RETURN TO BASE", ORANGE, 180)
        return n

    def persist():
        write_save(slot_path(S.slot), save)

    def scanning():
        return S.ship["ability"] == "scan" and S.ab_t > 0

    # ---------- ekonomia ----------
    def add_credits(x):
        """Dodaje (ułamkowe) kredyty; reszta ułamkowa czeka na kolejne wpłaty."""
        S.frac += x
        whole = int(S.frac)
        if whole:
            save["credits"] += whole
            S.frac -= whole

    def project_need(kind):
        pr = save["project"]
        if not pr:
            return 0
        cost = module_by_key(pr["key"])["costs"][save["base"][pr["key"]]]
        return max(0, cost.get(kind, 0) - pr["progress"].get(kind, 0))

    def process_unit(kind):
        """Jedna sztuka surowca: najpierw wpada do projektu bazy, reszta jest sprzedawana (z bonusem Refinery)."""
        if project_need(kind) > 0:
            save["project"]["progress"][kind] += 1
            return "proj", 0.0
        v = ORE[kind]["value"] * sale_mult(save["base"])
        add_credits(v)
        return "sold", v

    def check_project():
        """Gdy projekt ma komplet surowców, moduł awansuje. Zwraca komunikat albo None."""
        pr = save["project"]
        if not pr:
            return None
        m = module_by_key(pr["key"])
        lvl = save["base"][pr["key"]]
        if all(pr["progress"].get(k, 0) >= n for k, n in m["costs"][lvl].items()):
            save["base"][pr["key"]] = lvl + 1
            save["project"] = None
            return f"{m['name']} UPGRADED TO LV {lvl + 1}!"
        return None

    def sync_drones():
        while len(S.drones) < save["drones"]:
            secs = DRONE_TECH[save["drone_tech"]][1]
            S.drones.append(dict(total=secs, t=random.uniform(0.3, 1.0) * secs, kind="iron",
                                 ang=random.uniform(0, math.tau), dist=random.uniform(3000, 6500)))

    def economy_tick():
        """Co klatkę: dochód z Drill Rigs (w bazie wprost na konto, w locie do skarbca) i wyprawy dronów."""
        dt = real_dt   # rzeczywisty upływ czasu tej klatki (nie zakładane 1/60), więc tempo nie zależy od FPS
        rate = income_rate(save["base"]) / 60.0
        if rate > 0:
            if S.state in ("base", "specials", "saves", "upgrades", "hangar", "build"):
                add_credits(rate * dt)
            else:
                save["vault"] = min(float(vault_cap(save["base"])), save["vault"] + rate * dt)
        sync_drones()
        units, secs, mix = DRONE_TECH[save["drone_tech"]]
        for d in S.drones:
            d["t"] -= dt
            if d["t"] > 0:
                continue
            kinds = random.choices(ORE_KINDS, weights=[mix.get(k, 0) for k in ORE_KINDS], k=units)
            sold, proj = 0.0, 0
            for k in kinds:
                r, v = process_unit(k)
                if r == "proj":
                    proj += 1
                else:
                    sold += v
            msg = check_project()
            d["total"] = secs * random.uniform(0.9, 1.1)
            d["t"] = d["total"]
            d["ang"], d["dist"] = random.uniform(0, math.tau), random.uniform(3000, 6500)
            d["kind"] = random.choices(ORE_KINDS, weights=[mix.get(k, 0) for k in ORE_KINDS])[0]
            line = f"DRONES  +{int(sold)} CR" + (f"  {proj} ORE TO BASE" if proj else "")
            if S.state == "flight":
                set_toast(line, YELLOW, 150)
                if msg:
                    set_toast(msg, LIME, 220)
            else:
                S.lines.append((line, YELLOW))
                if msg:
                    S.lines.append((msg, LIME))
                del S.lines[:-4]
            persist()

    def burst(x, y, n, colors, speed=4.0, life=22):
        for _ in range(n):
            ang = random.random() * math.tau
            sp_ = random.uniform(0.5, 1.0) * speed
            particles.append(Particle(x, y, math.cos(ang) * sp_, math.sin(ang) * sp_,
                                      random.randint(life - 8, life), colors))
        if len(particles) > 700:
            del particles[:150]

    def streaks(x, y, n, colors, speed=8.0, life=16, drag=0.88):
        """Iskry-smugi rozlatujące się we wszystkie strony."""
        for _ in range(n):
            ang = random.random() * math.tau
            sp_ = random.uniform(0.4, 1.0) * speed
            particles.append(Streak(x, y, math.cos(ang) * sp_, math.sin(ang) * sp_,
                                    random.randint(max(4, life - 6), life), colors, drag))

    def debris(x, y, n, colors, speed=4.0, life=40, size=2, hot=True):
        for _ in range(n):
            ang = random.random() * math.tau
            sp_ = random.uniform(0.3, 1.0) * speed
            particles.append(Debris(x, y, math.cos(ang) * sp_, math.sin(ang) * sp_,
                                    random.randint(life // 2, life), random.choice(colors),
                                    random.choice((size, size, size + 1)), hot))

    def glow(x, y, r0, r1, life, color, power=1.0, delay=0, owner=None):
        fx.append(Glow(x, y, r0, r1, life, color, power, delay, owner))

    def kick(amount):
        """Drżenie ekranu: bierze mocniejsze z trwającego i nowego."""
        S.shake = max(S.shake, amount)

    def boom(x, y, size=1.0, gold=False, rock=True):
        """Wybuch: błysk światła, fala uderzeniowa, iskry-smugi i odłamki (size: 0.5 mała skała, 1 duża, 3 kolos)."""
        hot = (WHITE, YELLOW, ORANGE, RED)
        glow(x, y, 30 * size, 110 * size, 16 + 6 * size, (255, 170, 80), min(1.0, 0.55 + 0.2 * size))
        glow(x, y, 10 * size, 50 * size, 8 + 2 * size, (255, 255, 220), 0.9)
        fx.append(FxRing(x, y, 10 * size, 150 * size, int(12 + 5 * size), (ORANGE, YELLOW), 2 if size < 2 else 3))
        if size >= 1:
            fx.append(FxRing(x, y, 6 * size, 95 * size, int(10 + 4 * size), (WHITE, ORANGE), 1, delay=2))
        streaks(x, y, int(6 + 7 * size), hot, speed=6.0 + 3.0 * size, life=int(12 + 4 * size))
        if rock:
            cols = (YELLOW, ORANGE, (255, 244, 200), GREY) if gold else (GREY, (120, 132, 150), DARK, WHITE)
            debris(x, y, int(4 + 6 * size), cols, speed=2.5 + 1.5 * size, life=int(30 + 12 * size))
        if gold:
            for _ in range(int(4 + 4 * size)):
                a = random.random() * math.tau
                rr = random.uniform(10, 60 * size)
                particles.append(Sparkle(x + math.cos(a) * rr, y + math.sin(a) * rr))
            glow(x, y, 40 * size, 90 * size, 22, YELLOW, 0.6, delay=3)

    # ---------- efekty zdolności ----------
    def fx_dash_start(p):
        fx.append(FxRing(p.x, p.y, 8, 150, 14, (CYAN, WHITE), 3))
        fx.append(FxRing(p.x, p.y, 8, 90, 10, (WHITE, CYAN), 1, delay=3))
        glow(p.x, p.y, 40, 140, 14, CYAN, 0.9)
        rad = p.angle * DEGTORAD
        for _ in range(14):   # iskry wyrzucone do tyłu, jak przy przebiciu bariery dźwięku
            a = rad + math.pi + random.uniform(-0.7, 0.7)
            s_ = random.uniform(5, 12)
            particles.append(Streak(p.x, p.y, math.cos(a) * s_, math.sin(a) * s_, random.randint(8, 14),
                                    (WHITE, CYAN, BLUE_D), 0.86))
        floats.append([p.x, p.y - 75, "PHASE", CYAN, 36])

    def fx_dash_end(p, lvd):
        fx.append(FxRing(p.x, p.y, 20, 120, 12, (CYAN, WHITE), 2))
        glow(p.x, p.y, 30, 100, 12, CYAN, 0.7)
        burst(p.x, p.y, 12, (WHITE, CYAN, BLUE_D), speed=4.5, life=16)
        streaks(p.x, p.y, 10, (WHITE, CYAN, BLUE_D), speed=7.0, life=12)

    def fx_overdrive(p):
        fx.append(FxRing(p.x, p.y, 20, 340, 22, (ORANGE, YELLOW), 3))
        fx.append(FxRing(p.x, p.y, 20, 220, 18, (YELLOW, WHITE), 2, delay=5))
        fx.append(FxRing(p.x, p.y, 20, 130, 14, (RED, ORANGE), 2, delay=9))
        fx.append(FxRing(p.x, p.y, 380, 30, 16, (RED, ORANGE), 2, delay=2))    # zasysanie energii przed wybuchem mocy
        glow(p.x, p.y, 60, 420, 30, (255, 140, 60), 1.0)
        glow(p.x, p.y, 20, 120, 12, (255, 255, 210), 1.0)
        burst(p.x, p.y, 30, (WHITE, YELLOW, ORANGE, RED), speed=7.0, life=24)
        streaks(p.x, p.y, 28, (WHITE, YELLOW, ORANGE, RED), speed=13.0, life=18)
        S.flash, S.flash_col = 7, (255, 200, 120)
        kick(10)
        floats.append([p.x, p.y - 80, "OVERDRIVE", ORANGE, 60])

    def fx_repair(p, small=False):
        big = 60 if small else 120
        fx.append(FxRing(p.x, p.y, p.R, p.R + big, 26, (CYAN, WHITE), 2, "hex", spin=0.5))
        fx.append(FxRing(p.x, p.y, p.R, p.R + big * 0.7, 22, (LIME, WHITE), 2, "hex", delay=5, spin=-0.5))
        if not small:
            fx.append(FxRing(p.x, p.y, p.R + big * 1.4, p.R, 18, (WHITE, CYAN), 1, "hex", spin=0.3))
        glow(p.x, p.y, 30, 30 + big, 30, (120, 255, 220), 0.8 if small else 1.0, owner=p)
        for _ in range(6 if small else 16):
            a = random.random() * math.tau
            rr = random.uniform(p.R * 0.6, p.R + big)
            particles.append(Sparkle(p.x + math.cos(a) * rr, p.y + math.sin(a) * rr))
            particles.append(Particle(p.x + math.cos(a) * rr, p.y + math.sin(a) * rr, 0.0, -1.3, 30, (LIME, WHITE, CYAN, DARK)))
        floats.append([p.x, p.y - 78, "+SHIELD", CYAN, 48])

    def fx_scan_ping(p):
        fx.append(FxRing(p.x, p.y, 0, 2400, 80, (CYAN, WHITE), 2))
        fx.append(FxRing(p.x, p.y, 0, 1600, 60, (BLUE_D, CYAN), 1, delay=6))
        glow(p.x, p.y, 20, 180, 20, (90, 200, 255), 0.7, owner=p)

    def fx_well_start(p, radius):
        r0 = min(radius, 1400)
        fx.append(FxRing(p.x, p.y, r0, 40, 34, (LIME, WHITE), 2))
        fx.append(FxRing(p.x, p.y, r0 * 0.7, 30, 28, (WHITE, LIME), 1, delay=8))
        fx.append(FxRing(p.x, p.y, r0 * 1.2, 50, 40, ((56, 183, 100), LIME), 3, delay=4))
        glow(p.x, p.y, 300, 40, 30, (120, 255, 120), 0.9, owner=p)
        for k in range(40):  # cząstki wpadające do środka po spirali
            a = k * math.tau / 40
            rr = random.uniform(300, 620)
            particles.append(Streak(p.x + math.cos(a) * rr, p.y + math.sin(a) * rr,
                                    -math.cos(a + 0.5) * 9.0, -math.sin(a + 0.5) * 9.0, 30, (WHITE, LIME, (56, 183, 100)), 0.96))
        kick(8)
        floats.append([p.x, p.y - 80, "GRAVITY WELL", LIME, 60])

    def fx_well_end(p, radius):
        r1 = min(radius, 1500)
        fx.append(FxRing(p.x, p.y, 60, r1, 26, (LIME, WHITE), 3))
        fx.append(FxRing(p.x, p.y, 40, r1 * 0.7, 22, (WHITE, LIME), 2, delay=4))
        fx.append(FxRing(p.x, p.y, 30, r1 * 1.15, 32, ((56, 183, 100), LIME), 2, delay=8))
        glow(p.x, p.y, 80, 600, 26, (140, 255, 140), 1.0)
        glow(p.x, p.y, 20, 160, 10, (255, 255, 230), 1.0)
        burst(p.x, p.y, 44, (WHITE, LIME, CYAN), speed=10.0, life=26)
        streaks(p.x, p.y, 36, (WHITE, LIME, CYAN, (56, 183, 100)), speed=16.0, life=20, drag=0.9)
        debris(p.x, p.y, 16, (LIME, WHITE, GREY), speed=7.0, life=40, hot=False)
        S.flash, S.flash_col = 6, (200, 255, 200)

    def fx_warp(x0, y0, x1, y1):
        vio = (150, 100, 255)
        fx.append(FxRing(x0, y0, 320, 0, 22, (vio, WHITE), 3))       # zapadanie w miejscu wyjścia
        fx.append(FxRing(x0, y0, 0, 160, 14, (WHITE, (210, 184, 255)), 2, delay=10))
        fx.append(FxRing(x1, y1, 0, 420, 24, (vio, WHITE), 3))        # rozbłysk w miejscu przybycia
        fx.append(FxRing(x1, y1, 0, 260, 18, (WHITE, CYAN), 2, delay=4))
        fx.append(FxRing(x1, y1, 0, 620, 34, ((210, 184, 255), vio), 1, delay=8))
        glow(x0, y0, 250, 10, 22, vio, 1.0)
        glow(x1, y1, 30, 380, 30, (180, 140, 255), 1.0)
        glow(x1, y1, 10, 110, 12, (255, 255, 255), 1.0)
        for _ in range(26):   # iskry wciągane w miejsce wyjścia
            a = random.random() * math.tau
            rr = random.uniform(160, 330)
            particles.append(Streak(x0 + math.cos(a) * rr, y0 + math.sin(a) * rr, -math.cos(a) * 12, -math.sin(a) * 12,
                                    14, (WHITE, (210, 184, 255), vio), 0.93))
        streaks(x1, y1, 30, (WHITE, (210, 184, 255), vio, CYAN), speed=15.0, life=20)
        S.flash, S.flash_col = 14, (225, 210, 255)

    def fx_missile_launch(p):
        rad = p.angle * DEGTORAD
        nx, ny = p.x + math.cos(rad) * 18, p.y + math.sin(rad) * 18
        fx.append(FxRing(nx, ny, 4, 56, 10, (WHITE, YELLOW), 1))
        glow(nx, ny, 20, 70, 8, (255, 210, 120), 0.8)
        burst(nx, ny, 8, (WHITE, YELLOW, GREY), speed=3.5, life=14)
        for _ in range(8):   # dym z wyrzutni
            a = rad + math.pi + random.uniform(-0.9, 0.9)
            s_ = random.uniform(1.0, 3.0)
            particles.append(Particle(nx, ny, math.cos(a) * s_, math.sin(a) * s_, random.randint(18, 28), (WHITE, GREY, DARK)))

    def fx_cluster(x, y):
        fx.append(FxRing(x, y, 10, 220, 18, (ORANGE, YELLOW), 3))
        fx.append(FxRing(x, y, 10, 130, 12, (WHITE, YELLOW), 1, delay=2))
        glow(x, y, 40, 180, 18, (255, 160, 70), 1.0)
        burst(x, y, 18, (WHITE, YELLOW, ORANGE, RED), speed=6.0, life=20)
        streaks(x, y, 14, (WHITE, YELLOW, ORANGE, RED), speed=10.0, life=14)
        kick(5)

    def fx_turret_shot(p, rad):
        particles.append(Particle(p.x, p.y, -math.sin(rad) * 2.4 + random.uniform(-0.4, 0.4),
                                  math.cos(rad) * 2.4 + random.uniform(-0.4, 0.4), 16, (YELLOW, GREY, DARK)))
        mx, my = p.x + math.cos(rad) * 20, p.y + math.sin(rad) * 20
        glow(mx, my, 10, 36, 5, (255, 200, 110), 0.7)

    def fx_reactive(p, radius):
        fx.append(FxRing(p.x, p.y, 10, radius, 20, (ORANGE, YELLOW), 3))
        fx.append(FxRing(p.x, p.y, 10, radius * 0.7, 16, (WHITE, CYAN), 1, "hex", delay=2, spin=0.4))
        glow(p.x, p.y, 40, radius * 0.9, 20, (255, 170, 90), 1.0)
        burst(p.x, p.y, 16, (WHITE, CYAN, BLUE_D), speed=6.5, life=22)     # odłamki tarczy
        burst(p.x, p.y, 14, (YELLOW, ORANGE, RED), speed=5.0, life=20)
        streaks(p.x, p.y, 20, (WHITE, YELLOW, ORANGE), speed=12.0, life=16)
        S.flash, S.flash_col = 5, (255, 190, 120)

    def fx_muzzle(x, y, rad, big=False):
        """Błysk wylotowy przy strzale z działek statku."""
        glow(x, y, 8, 30 if big else 22, 5, (255, 210, 140), 0.6)
        for _ in range(2):
            a = rad + random.uniform(-0.45, 0.45)
            s_ = random.uniform(4, 8)
            particles.append(Streak(x, y, math.cos(a) * s_, math.sin(a) * s_, 5, (WHITE, YELLOW, ORANGE), 0.8))

    # ---------- asteroidy ----------
    def pick_ore(d0, gold):
        """Złote asteroidy dają gold, zwykłe iron, a dalej od bazy często też titanium."""
        if gold:
            return "gold"
        return "titanium" if (d0 > 12000 and random.random() < 0.4) else "iron"

    def new_rock(x, y, angle, tier, gold, base, ore=None):
        """tier: "small", "large" albo "colossus" (kolosalna: ogromna, dużo HP i łupów)."""
        a = Asteroid()
        if tier == "small":
            anim, radius = (s_rock_small_gold if gold else s_rock_small), 15
            hp = max(2, base + 1) if gold else max(1, (base + 1) // 2)
        elif tier == "colossus":
            anim, radius = (s_rock_colossus_gold if gold else s_rock_colossus), COLOSSUS_R
            hp = (16 + 12 * base) if gold else (8 + 6 * base)
        else:
            anim, radius = (s_rock_gold if gold else s_rock), 25
            hp = base * 2 + 1 if gold else base
        a.settings(anim, x, y, angle, radius)
        a.hp = a.max_hp = hp
        a.base, a.gold, a.tier = base, gold, tier
        a.ore = ore or ("gold" if gold else "iron")
        if tier == "colossus":  # kolosy dryfują powoli
            a.dx *= 0.35
            a.dy *= 0.35
        return a

    def spawn_ore(x, y, kind, units, vx=0.0, vy=0.0, spread=3.0, chunk=6):
        """Rozsypuje 'units' jednostek surowca w paczkach po 'chunk' sztuk (mniej obiektów, szybsze zbieranie)."""
        while units > 0:
            amt = min(chunk, units)
            units -= amt
            ang = random.random() * math.tau
            sp_ = random.uniform(0.5, 1.0) * spread
            ores.append(Ore(x + random.uniform(-6, 6), y + random.uniform(-6, 6), kind,
                            vx + math.cos(ang) * sp_, vy + math.sin(ang) * sp_, amt))
        if len(ores) > 600:
            del ores[:150]

    def kill_asteroid(a, split=True, drop=True):
        a.life = False
        colossus = a.tier == "colossus"
        ex = Entity("explosion")
        ex.settings(s_explosion, a.x, a.y)
        pending.append(ex)
        if a.gold:
            burst(a.x, a.y, 30 if colossus else 16, (WHITE, YELLOW, ORANGE), speed=5.0, life=26)
        else:
            burst(a.x, a.y, 24 if colossus else 8, (WHITE, GREY, DARK), speed=4.0)
        if colossus:  # kolos rozpada się w serii wybuchów, a na końcu pęka z wielkim błyskiem
            boom(a.x, a.y, 1.6, a.gold)
            for k in range(6):
                def blast(x=a.x + random.uniform(-110, 110), y=a.y + random.uniform(-110, 110), g=a.gold):
                    e2 = Entity("explosion")
                    e2.settings(s_explosion, x, y)
                    entities.append(e2)
                    boom(x, y, 1.0, g)
                    kick(8)
                fx.append(Timer(4 + k * 5, blast))

            def finale(x=a.x, y=a.y, g=a.gold):
                boom(x, y, 3.2, g)
                S.flash, S.flash_col = 6, ((255, 230, 150) if g else (255, 210, 170))
                kick(22)
            fx.append(Timer(34, finale))
            kick(14)
        else:
            boom(a.x, a.y, 1.0 if a.tier == "large" else 0.55, a.gold)
            if a.tier == "large":
                kick(3)
        if drop:  # asteroidy zostawiają surowiec (podczas Deep Scan poziomu 2+ dwa razy więcej)
            sl = save["levels"]["scan"]
            mult = (3 if sl >= 6 else 2) if (scanning() and sl >= 2) else 1
            if S.ship["id"] == "scout":  # Salvage Crew
                mult *= 1 + SALVAGE_BONUS * save["levels"]["salvage"]
            kind = a.ore
            spawn_ore(a.x, a.y, kind, max(1, int(math.ceil(ROCK_UNITS[kind][a.tier] * mult))),
                      spread=6.0 if colossus else 3.0, chunk=10 if colossus else 6)
        if S.ship["id"] == "striker" and save["levels"]["combo"] > 0:  # Kill Combo
            S.combo = min(COMBO_MAX[save["levels"]["combo"]], S.combo + 1)
            S.combo_t = COMBO_FRAMES
        if S.ab_t > 0 and S.ship["ability"] == "overdrive" and save["levels"]["overdrive"] >= 3:
            S.ab_t = min(S.ab_t + 30, int(OVERDRIVE_CAP * FPS))  # poziom 3: kolejne zabójstwa wydłużają Overdrive
            S.ab_total = max(S.ab_total, S.ab_t)
        if split and a.tier == "large":
            for _ in range(2):
                pending.append(new_rock(a.x, a.y, random.randrange(360), "small", a.gold, a.base, a.ore))
        elif split and colossus:
            for _ in range(3):
                pending.append(new_rock(a.x + random.uniform(-50, 50), a.y + random.uniform(-50, 50),
                                        random.randrange(360), "large", a.gold, a.base, a.ore))

    def damage_asteroid(a, dmg, split=True):
        if not a.life:
            return
        a.hp -= dmg
        if a.hp <= 0:
            kill_asteroid(a, split)
        else:
            a.flash = 3
            burst(a.x, a.y, 3, (WHITE, YELLOW if a.gold else GREY), speed=2.5, life=10)
            streaks(a.x, a.y, 3, (WHITE, YELLOW, ORANGE), speed=6.0, life=8)
            glow(a.x, a.y, 20, 45 + a.R * 0.6, 6, (255, 200, 140), 0.5)

    def convert_asteroid(a):
        """Traktor-beam Harvestera: asteroida wpada wprost do ładowni (2x więcej niż z odłamków)."""
        a.life = False
        kind = a.ore
        n = ROCK_UNITS[kind][a.tier] * 2
        n = max(1, int(round(n * BEAM_YIELD[save["levels"]["beam"]])))
        p = S.player
        ti = int(round(n * REFINE_CHANCE[save["levels"]["refine"]])) if kind == "iron" else 0  # Ore Refiner
        got = add_cargo(kind, n - ti)
        if ti:
            got_t = add_cargo("titanium", ti)
            if got_t:
                floats.append([p.x + 14, p.y - 34, f"+{got_t}", ORE["titanium"]["color"], 50])
        if got:
            floats.append([p.x, p.y - 24, f"+{got}", ORE[kind]["color"], 50])
        burst(p.x, p.y, 12, (YELLOW, WHITE, ORANGE), speed=3.5, life=20)

    def mine_planet(pl, b):
        """Pocisk uderza w planetę: wykuwa paczkę surowca (MINE_YIELD razy obrażenia), która leci do statku."""
        dmg = 6 if b.name == "missile" else b.dmg
        n = pl.hit(dmg)
        ux, uy = b.x - pl.x, b.y - pl.y
        d = math.hypot(ux, uy) or 1.0
        ux, uy = ux / d, uy / d
        col = ORE[pl.kind]["color"]
        if n:
            p = S.player
            tx, ty = p.x - pl.x, p.y - pl.y
            td = math.hypot(tx, ty) or 1.0
            vx, vy = (ux * 0.35 + tx / td * 0.65) * 9.0, (uy * 0.35 + ty / td * 0.65) * 9.0
            bonus = S.ship["mine_bonus"] + (save["levels"]["prospect"] if S.ship["id"] == "surveyor" else 0)
            if scanning() and save["levels"]["scan"] >= 5:
                bonus += 2   # Deep Scan poziomu 5: podczas skanu dodatkowe bryłki
            total = n + bonus * MINE_YIELD  # Surveyor dokłada darmowe jednostki (ulepszalne)
            spawn_ore(pl.x + ux * (pl.R + 8), pl.y + uy * (pl.R + 8), pl.kind, total, vx, vy, spread=1.0,
                      chunk=max(total, 1))
            burst(b.x, b.y, 4, (WHITE, col, col), speed=2.5, life=12)
            if pl.depleted:
                set_toast("PLANET DEPLETED", GREY, 120)
                burst(pl.x, pl.y, 24, (WHITE, col, DARK), speed=6.0, life=30)
        else:
            burst(b.x, b.y, 3, (GREY, DARK), speed=2.0, life=10)

    # ---------- statek ----------
    def fire_mult():
        """Mnożnik odstępu między strzałami: kara statku minus ulepszenia (Twin-Link Guns)."""
        if S.ship["id"] == "interceptor":
            return S.ship["fire"] - GUNS_BONUS * save["levels"]["guns"]
        return S.ship["fire"]

    def bullet_life():
        if S.ship["id"] == "surveyor":
            return int(BULLET_LIFE * (1 + OPTICS_BONUS * save["levels"]["optics"]))
        return BULLET_LIFE

    def shoot():
        lv = save["levels"]
        p, ship = S.player, S.ship
        od = ship["ability"] == "overdrive" and S.ab_t > 0   # Overdrive: 2x obrażeń (3x od poziomu 6) i ponad 2x szybciej
        odm = 3 if lv["overdrive"] >= 6 else 2
        if lv["double"]:
            offset = max(12.0, ship["radius"] * 0.75)
            rad = p.angle * math.pi / 180.0
            dx = math.cos(rad + math.pi / 2) * offset
            dy = math.sin(rad + math.pi / 2) * offset
            for sign in (1, -1):
                b = Bullet()
                b.settings(s_bullet, p.x + sign * dx, p.y + sign * dy, p.angle, 10)
                b.dmg = ship["dmg"] * (odm if od else 1)
                b.maxage = bullet_life()
                b.ivx, b.ivy = p.dx, p.dy
                entities.append(b)
        else:
            b = Bullet()
            b.settings(s_bullet, p.x, p.y, p.angle, 10)
            b.dmg = ship["dmg"] * (odm if od else 1)
            b.maxage = bullet_life()
            b.ivx, b.ivy = p.dx, p.dy
            entities.append(b)
        S.fire_cd = fire_rate_of(lv["fire"]) * fire_mult() * (0.4 if od else 1.0) / (1 + COMBO_STEP * S.combo)
        rad = p.angle * DEGTORAD
        fx_muzzle(p.x + math.cos(rad) * (ship["radius"] + 6), p.y + math.sin(rad) * (ship["radius"] + 6), rad, od)

    def fire_missiles():
        """Salwa rakiet samonaprowadzających (Bruiser, Striker); na 6. poziomie rakiety są kasetowe."""
        p = S.player
        lvl_m = save["levels"]["missile"]
        n, cd = missile_of(lvl_m)
        rocks = sorted((e for e in entities if e.name == "asteroid" and e.life),
                       key=lambda a: (a.x - p.x) ** 2 + (a.y - p.y) ** 2)
        step = 28 if n <= 3 else 22
        for i in range(n):
            m = Missile(entities, rocks[i % len(rocks)] if rocks else None)
            m.settings(s_missile, p.x, p.y, p.angle + (i - (n - 1) / 2) * step, 10)
            m.dmg = 4 + S.ship["missile_dmg"]
            m.cluster = lvl_m >= CLUSTER_LEVEL
            entities.append(m)
        S.missile_cd = cd * S.ship["missile_reload"]
        fx_missile_launch(p)

    def cluster_burst(x, y):
        """Bomba kasetowa: rakieta rozpada się na bomblety lecące we wszystkie strony."""
        for _ in range(CLUSTER_BOMBLETS):
            b = Bullet()
            b.settings(s_bullet, x, y, random.uniform(0, 360), 10)
            b.dmg = 3
            b.age = BULLET_LIFE - 10  # krótki lot: ok. 130 px
            b.spark = True
            pending.append(b)
        fx_cluster(x, y)

    def cast_wave():
        """Shockwave Interceptora; poziomy 4 i 5 uderzają kilka razy pod rząd."""
        i = save["levels"]["wave"] - 1
        waves.append(Shockwave(S.player, WAVE_RADIUS[i], WAVE_DAMAGE[i], (CYAN, WHITE), "electric"))
        for k in range(1, WAVE_PULSES[i]):
            S.wave_queue.append([28 * k, i])
        S.wave_cd = WAVE_COOLDOWN[i]
        S.shake = 14

    def do_warp():
        """Warp Beacon: natychmiastowy skok pod bazę; dalej lądowanie odbywa się automatycznie (ładunek zostaje)."""
        p = S.player
        burst(p.x, p.y, 30, (WHITE, CYAN, BLUE_D, (150, 100, 255)), speed=7.0, life=26)
        ox, oy = p.x, p.y
        ang = math.atan2(p.y, p.x)
        r_ = DOCK_R - 40
        p.x, p.y = math.cos(ang) * r_, math.sin(ang) * r_
        fx_warp(ox, oy, p.x, p.y)
        p.dx = p.dy = 0.0
        p.angle = math.degrees(ang) + 180
        CAM[0], CAM[1] = p.x, p.y
        S.warps -= 1
        S.undock_lock = False
        S.shake = 14
        burst(p.x, p.y, 30, (WHITE, CYAN, BLUE_D, (150, 100, 255)), speed=7.0, life=26)
        set_toast("WARP!", CYAN, 100)

    def knockback(x, y, radius, speed, dmg=0, min_gap=160):
        """Odrzuca asteroidy od punktu (x, y): wypycha te zbyt bliskie i nadaje prędkość na zewnątrz."""
        for a in entities:
            if a.name != "asteroid" or not a.life:
                continue
            dxp, dyp = a.x - x, a.y - y
            d = math.hypot(dxp, dyp) or 1.0
            if d < radius:
                ux, uy = dxp / d, dyp / d
                safe = S.player.R + a.R + min_gap
                if d < safe:
                    a.x, a.y = x + ux * safe, y + uy * safe
                a.dx, a.dy = ux * speed, uy * speed
                a.knock = 90
                if dmg:
                    damage_asteroid(a, dmg)

    def start_dash():
        p = S.player
        lvd = save["levels"]["dash"]
        p.dash_t = DASH_FRAMES
        p.dash_angle = p.angle
        p.dash_speed = DASH_SPEED * DASH_SPEED_MULT[lvd]
        if lvd >= 5:  # poziom 5: dwa ładunki dasha, każdy ładuje się osobno
            S.dash_charges -= 1
            if S.dash_rt <= 0:
                S.dash_rt = DASH_CD[lvd]
            S.dash_cd = 0.35 if S.dash_charges > 0 else S.dash_rt
        else:
            S.dash_cd = DASH_CD[lvd]
        S.phase_t = PHASE_FRAMES
        burst(p.x, p.y, 10, (CYAN, WHITE, BLUE_D), speed=4.0, life=14)
        fx_dash_start(p)

    def ability_cd(ab):
        L = save["levels"]
        return {"dash": DASH_CD[L["dash"]], "overdrive": OVERDRIVE_CD[L["overdrive"]], "scan": SCAN_CD[L["scan"]],
                "pulse": WELL_CD[L["pulse"]], "repair": REPAIR_CD[L["repair"]]}[ab]

    def scan_mult():
        return SCAN_MULTS[save["levels"]["scan"]]

    def map_range():
        """Zasięg minimapy (logika): bazowy x Scanner Array x Deep Scan."""
        return MAP_RANGE * (1 + SCANNER_BONUS * save["base"]["scanner"]) * (scan_mult() if scanning() else 1.0)

    def start_ability():
        """SHIFT: zdolność aktywna zależna od statku (poziomy z ekranu SPECIALS)."""
        p = S.player
        ab = S.ship["ability"]
        L = save["levels"]
        if ab == "dash":
            start_dash()
            return
        S.dash_cd = ability_cd(ab)
        if ab == "overdrive":
            S.ab_t = S.ab_total = int(OVERDRIVE_SECS[L["overdrive"]] * FPS)
            if L["overdrive"] >= 5:
                S.phase_t = max(S.phase_t, 180)   # poziom 5: 3 s nietykalności na start
            S.shake = 6
            fx_overdrive(p)
            set_toast("OVERDRIVE!", ORANGE, 90)
        elif ab == "scan":
            S.ab_t = S.ab_total = int(SCAN_SECS[L["scan"]] * FPS)
            waves.append(Shockwave(p, 900, 0, (CYAN, WHITE)))
            fx_scan_ping(p)
            set_toast("DEEP SCAN ACTIVE", CYAN, 120)
        elif ab == "pulse":  # Gravity Well: przyciąga bryłki i asteroidy, a asteroidy przy statku są miażdżone
            i = L["pulse"]
            S.well_t = S.well_total = int(WELL_SECS[i] * FPS)
            S.phase_t = max(S.phase_t, S.well_t + 8)  # w trakcie studni asteroidy nie ranią statku
            for o in ores:
                if math.hypot(p.x - o.x, p.y - o.y) < WELL_R[i]:
                    o.pull = S.well_t + 20
            waves.append(Shockwave(p, WELL_R[i], 0, (LIME, WHITE)))
            fx_well_start(p, WELL_R[i])
            S.shake = 5
            set_toast("GRAVITY WELL", LIME, 90)
        elif ab == "repair":  # Field Repair: odnawia ładunki tarczy (z ulepszeniami także ponad zwykły limit)
            n = REPAIR_N[L["repair"]]
            S.shield = min(S.shield + n, max(S.max_shield, 1) + L["repair"])
            S.max_shield = max(S.max_shield, S.shield)
            if L["repair"] >= 5:
                S.phase_t = max(S.phase_t, 90)   # poziom 5: chwila nietykalności
            fx_repair(p)
            set_toast(f"SHIELD +{n}", CYAN, 90)

    # ---------- start, lądowanie, utrata statku ----------
    def do_launch():
        lv = save["levels"]
        S.ship = ship_by_id(save["ship"])
        ship = S.ship
        for group in (entities, ores, particles, waves, ghosts, floats, pending, fx):
            group.clear()
        px, py = pad_pos(S.pad)
        p = Player()
        p.settings(ship_anims[ship["id"]][1], px, py, math.degrees(pad_angle(S.pad)), ship["radius"])
        eb = 1.0 + ENGINE_BONUS * save["base"]["engine"]   # Engine Lab
        p.speed = engine_of(lv["engine"]) * ship["speed"] * SHIP_SPEED_MULT * eb
        p.max_speed = 15 * ship["speed"] * SHIP_SPEED_MULT * eb
        p.turn = ship["turn"]
        p.scale = 0.55
        entities.append(p)
        S.player = p
        S.cargo = {k: 0 for k in ORE_KINDS}
        capm = ship["cargo_mult"]
        if ship["id"] == "hauler":
            capm *= 1 + MEGAHOLD_BONUS * lv["megahold"]
        elif ship["id"] == "harvester":
            capm *= 1 + SILO_BONUS * lv["silo"]
        S.cap = int(CARGO_CAP[lv["cargo"]] * capm)
        S.combo = S.combo_t = S.dash_prev = 0
        S.regen_t, S.dash_rt = 0.0, 0.0
        S.dash_charges = 2 if lv["dash"] >= 5 else 1
        S.fire_cd = S.missile_cd = S.wave_cd = S.dash_cd = 0.0
        S.ab_t = 0
        S.well_t = 0
        S.wave_queue = []
        S.turret_msl_cd = 0.0
        S.max_shield = S.shield = lv["shield"] + ship["shields"] + save["base"]["shield"]   # Shield Grid: +1 na poziom
        S.warps = save["base"]["warp"]
        S.invuln = S.shake = S.phase_t = 0
        S.beam_targets = []
        S.undock_lock = True
        S.lines = []
        S.turret_cd = 0.0
        S.toast[2] = 0
        S.phase, S.t = "launch", 0
        S.state = "flight"
        CAM[0], CAM[1] = px, py

    def start_landing():
        p = S.player
        ang = math.atan2(p.y, p.x)
        S.pad = min(range(N_PADS), key=lambda k: abs((ang - pad_angle(k) + math.pi) % math.tau - math.pi))
        S.phase, S.t = "landing", 0
        S.land_from = (p.x, p.y)
        S.land_a0 = p.angle
        S.beam_targets = []
        S.ab_t = 0
        S.well_t = 0
        S.wave_queue = []
        for e in entities:
            if e.name == "asteroid":
                e.beam = False
        p.dash_t = 0
        set_toast("AUTO-LANDING", CYAN, 100)

    def ship_lost(reason):
        p = S.player
        ex = Entity("explosion")
        ex.settings(s_explosion, p.x, p.y)
        pending.append(ex)
        burst(p.x, p.y, 24, (WHITE, ORANGE, RED, PLUM), speed=6.0, life=30)
        boom(p.x, p.y, 2.2, rock=False)
        debris(p.x, p.y, 26, (GREY, WHITE, CYAN, BLUE_D, DARK), speed=6.0, life=70, size=3)
        for k in range(4):
            def blast(x=p.x + random.uniform(-70, 70), y=p.y + random.uniform(-70, 70)):
                e2 = Entity("explosion")
                e2.settings(s_explosion, x, y)
                entities.append(e2)
                boom(x, y, 1.2, rock=False)
                kick(10)
            fx.append(Timer(6 + k * 7, blast))
        fx.append(FxRing(p.x, p.y, 20, 700, 40, (RED, ORANGE), 3, delay=4))
        S.flash, S.flash_col = 9, (255, 140, 110)
        p.life = False
        S.cargo = {k: 0 for k in ORE_KINDS}
        S.beam_targets = []
        S.phase, S.t = "dead", 0
        S.shake = 20
        S.lines = [(reason, RED)]
        set_toast("SHIP LOST!", RED, 100)

    # ---------- zakupy ----------
    def buy_level(key, costs):
        lvl = save["levels"][key]
        if lvl >= len(costs):
            set_notice("ALREADY AT MAX", ORANGE)
            return
        cost = costs[lvl]
        if save["credits"] < cost:
            set_notice(f"NEED {cost} CREDITS", RED)
            return
        save["credits"] -= cost
        save["levels"][key] = lvl + 1
        persist()
        set_notice("UPGRADED!", LIME)

    def buy_upgrade(i):
        u = UPGRADES[i]
        buy_level(u["key"], u["costs"])

    def buy_special():
        sh = SHIPS[S.spec_ship]
        key = SPECIALS[sh["id"]][S.spec_sel]
        if sh["id"] not in save["owned"]:
            set_notice(f"NEED THE {sh['name']} FIRST (HANGAR)", RED)
            return
        buy_level(key, SPECIAL_ROWS[key]["costs"])

    def build_rows():
        """Wiersze ekranu BASE: 3 moduły (za surowce) + drony i ich technologia (za kredyty)."""
        return [m["key"] for m in BASE_MODULES] + ["drones", "drone_tech"]

    def buy_base_row(i):
        key = build_rows()[i]
        if key in ("drones", "drone_tech"):
            costs = DRONE_COSTS if key == "drones" else DRONE_TECH_COSTS
            field = "drones" if key == "drones" else "drone_tech"
            n = save[field]
            if n >= len(costs):
                set_notice("ALREADY AT MAX", ORANGE)
                return
            if save["credits"] < costs[n]:
                set_notice(f"NEED {costs[n]} CREDITS", RED)
                return
            save["credits"] -= costs[n]
            save[field] = n + 1
            persist()
            set_notice("DRONE ADDED - DEPARTS SOON" if key == "drones" else "DRONE TECH UPGRADED!", LIME)
            return
        m = module_by_key(key)
        lvl = save["base"][key]
        if lvl >= len(m["costs"]):
            set_notice("ALREADY AT MAX", ORANGE)
            return
        pr = save["project"]
        if pr and pr["key"] == key:
            set_notice("ALREADY YOUR ACTIVE PROJECT", CYAN)
        elif pr and any(pr["progress"].values()):
            set_notice("FINISH THE CURRENT PROJECT FIRST", RED)
        else:
            cr = m["credits"][lvl] if m.get("credits") else 0
            refund = pr.get("paid", 0) if pr else 0  # zmiana projektu bez wpłat surowców zwraca kredyty
            if save["credits"] + refund < cr:
                set_notice(f"NEED {cr} CREDITS TO START", RED)
                return
            save["credits"] += refund - cr
            save["project"] = {"key": key, "paid": cr, "progress": {k: 0 for k in ORE_KINDS}}
            persist()
            set_notice(f"PROJECT STARTED (-{cr} CR): ORE GOES TO THE BASE" if cr else "PROJECT STARTED: ORE GOES TO THE BASE", LIME)

    def select_ship(i):
        sh = SHIPS[i]
        if sh["id"] in save["owned"]:
            save["ship"] = sh["id"]
            set_notice("EQUIPPED", LIME)
        elif save["credits"] >= sh["cost"]:
            save["credits"] -= sh["cost"]
            save["owned"].append(sh["id"])
            save["ship"] = sh["id"]
            set_notice("UNLOCKED AND EQUIPPED!", LIME)
        else:
            set_notice(f"NEED {sh['cost']} CREDITS", RED)
            return
        persist()

    def pips(x, y, filled, total, on, off, w=5, gap=2, h=5):
        for j in range(total):
            pygame.draw.rect(screen, on if j < filled else off, (x + j * (w + gap), y, w, h))

    def panel(rect):
        pygame.draw.rect(screen, NAVY, rect)
        pygame.draw.rect(screen, DARK, rect, 1)

    # ---------- sloty zapisu ----------
    def new_game_data():
        d = default_save()
        d["levels"] = {k: 0 for k in upgrade_keys}
        d["seed"] = random.randrange(1, 10 ** 9)  # nowa gra = nowy świat
        return d

    def apply_save(data):
        """Podmienia zawartość zapisu w miejscu (reszta kodu trzyma referencję do tego samego słownika)."""
        save.clear()
        save.update(data)
        WORLD.seed = save["seed"]
        WORLD.reset()
        S.drones.clear()
        S.cargo = {k: 0 for k in ORE_KINDS}
        S.frac = 0.0
        S.ab_t = 0
        S.well_t = 0
        S.warps = 0
        S.wave_queue = []
        S.beam_targets = []
        S.ship = ship_by_id(save["ship"])
        for grp in (entities, ores, particles, waves, ghosts, floats, pending, fx):
            grp.clear()

    def refresh_slots():
        S.slot_info = []
        for n in range(1, SLOTS + 1):
            if n == S.slot:
                S.slot_info.append(save)
            elif slot_path(n).exists():
                S.slot_info.append(load_save(slot_path(n), upgrade_keys, ship_ids))
            else:
                S.slot_info.append(None)

    def switch_slot(n):
        persist()
        S.slot = n
        fresh = not slot_path(n).exists()
        apply_save(new_game_data() if fresh else load_save(slot_path(n), upgrade_keys, ship_ids))
        write_active_slot(n)
        persist()
        S.lines = [("NEW GAME STARTED" if fresh else f"SLOT {n} LOADED", LIME)]
        refresh_slots()
        set_notice("NEW GAME!" if fresh else "SAVE LOADED", LIME)

    def delete_slot(n):
        try:
            slot_path(n).unlink()
        except OSError:
            pass
        if n == S.slot:  # skasowanie aktywnego zapisu = od razu świeża gra w tym slocie
            apply_save(new_game_data())
            persist()
            S.lines = [("SAVE ERASED - NEW GAME", ORANGE)]
        refresh_slots()
        set_notice(f"SLOT {n} ERASED", ORANGE)

    # ---------- rysowanie świata ----------
    def draw_space():
        for img, f in ((bg_big, 0.10), (stars_far_big, 0.22), (stars_near_big, 0.45)):
            iw, ih = img.get_width() // 3, img.get_height() // 2
            ox = int(-(CAM[0] * K * f) % iw)
            oy = int(-(CAM[1] * K * f) % ih)
            screen.blit(img, (ox - iw, oy - ih))

    # sloty budynków na planecie (px płótna względem środka): skarbce w środku, rafinerie dalej, wiertnie na obrzeżu
    def ring_slots(n, r, off):
        return [(round(math.cos(off + i * math.tau / n) * r), round(math.sin(off + i * math.tau / n) * r)) for i in range(n)]

    BUILD_LAYOUT = [  # (moduł, promień pierścienia w px płótna, liczba slotów, przesunięcie kąta)
        ("vault", 100, 6, 0.5), ("trade", 150, 5, 0.9), ("refinery", 210, 5, 0.3), ("scanner", 270, 5, 0.1),
        ("drill", 330, 8, 0.2), ("shield", 395, 3, 0.7), ("warp", 430, 3, 1.75), ("engine", 462, 4, 0.4)]
    slots = {k: ring_slots(n, r, off) for k, r, n, off in BUILD_LAYOUT}
    slot_r = {k: r for k, r, n, off in BUILD_LAYOUT}
    house_rng = random.Random(7)
    houses = []
    while len(houses) < 900:  # domki rozrzucone deterministycznie; ich liczba rośnie razem z bazą
        a_ = house_rng.uniform(0, math.tau)
        r_ = 64 + 400 * math.sqrt(house_rng.random())
        houses.append((round(math.cos(a_) * r_), round(math.sin(a_) * r_)))

    def visible(x, y, m=24):
        return -m < x < VW + m and -m < y < VH + m

    RING_PTS = [(math.cos(i * math.tau / 720), math.sin(i * math.tau / 720)) for i in range(720)]

    def draw_ring(cx, cy, lvl, t_ms):
        """Orbital Ring: pierścień stacji wokół planety; z poziomem grubszy, z większą liczbą modułów i świateł."""
        r = BASE_ART_R + 40
        thick = 2 + lvl
        for i, (ux, uy) in enumerate(RING_PTS):
            x_, y_ = cx + round(ux * r), cy + round(uy * r)
            if visible(x_, y_, 6):
                screen.fill(GREY if (i // 5) % 2 else BLUE_D, (x_ - thick // 2, y_ - thick // 2, thick, thick))
        n_mod = 8 + 4 * lvl
        for k in range(n_mod):  # moduły stacji
            ux, uy = RING_PTS[k * 720 // n_mod]
            x_, y_ = cx + round(ux * r), cy + round(uy * r)
            if visible(x_, y_, 8):
                screen.fill(NAVY, (x_ - 4, y_ - 4, 9, 9))
                screen.fill(GREY if k % 2 else WHITE, (x_ - 3, y_ - 3, 7, 7))
                screen.fill(CYAN if (k + t_ms // 400) % 3 else YELLOW, (x_ - 1, y_ - 1, 3, 3))
        for j in range(3):  # światła biegnące po pierścieniu
            idx = int(t_ms / 25 + j * 240) % 720
            ux, uy = RING_PTS[idx]
            x_, y_ = cx + round(ux * r), cy + round(uy * r)
            if visible(x_, y_, 6):
                screen.fill(WHITE, (x_ - 2, y_ - 2, 5, 5))
                screen.fill(CYAN, (x_ - 1, y_ - 1, 3, 3))

    base_layer = {"key": None, "surf": None}
    LAYER_R = 472   # promień warstwy (px płótna) mieszczący wszystkie drogi i domki

    def base_static_layer(n_house):
        """Drogi i domki bazy rysowane raz do osobnej warstwy (przebudowa tylko po zmianie bazy/dronów)."""
        b = save["base"]
        key = (tuple(sorted(b.items())), n_house)
        if base_layer["key"] != key:
            L = LAYER_R
            surf = pygame.Surface((2 * L + 1, 2 * L + 1)).convert()
            surf.fill(KEY)
            surf.set_colorkey(KEY)
            for k_, r, n_slots, off in BUILD_LAYOUT:   # drogi: pierścień + szprychy do centrum
                n = min(b[k_], n_slots)
                if not n:
                    continue
                for i in range(0, 360, 2):
                    a_ = i * math.tau / 360
                    surf.fill(DARK, (L + round(math.cos(a_) * r), L + round(math.sin(a_) * r), 1, 1))
                for dx, dy in slots[k_][:n]:
                    for t in range(2, 60, 2):
                        surf.fill(DARK, (L + round(dx * t / 60), L + round(dy * t / 60), 1, 1))
            for i, (hx, hy) in enumerate(houses[:n_house]):
                surf.fill(NAVY, (L + hx, L + hy + 1, 4, 3))
                surf.fill(GREY if i % 4 else WHITE, (L + hx, L + hy, 3, 2))
            base_layer["key"], base_layer["surf"] = key, surf
        return base_layer["surf"]

    def draw_buildings(cx, cy, t_ms):
        """Rozbudowa bazy widać na planecie: centrum dowodzenia, drogi, domki i budynki wszystkich modułów."""
        b = save["base"]
        blink = (t_ms // 500) % 2 == 0
        n_house = min(len(houses), 24 + 16 * sum(b.values()) + 8 * save["drones"])
        screen.blit(base_static_layer(n_house), (cx - LAYER_R, cy - LAYER_R))
        phase = t_ms // 700
        for i, (hx, hy) in enumerate(houses[:n_house]):
            if (i + phase) % 3:
                x, y = cx + hx, cy + hy
                if -4 < x < VW + 4 and -4 < y < VH + 4:
                    screen.fill(YELLOW, (x + 1, y + 1, 1, 1))  # światło w oknie
        for key, r, n_slots, off in BUILD_LAYOUT:
            img = bld_img[key]
            for idx, (dx, dy) in enumerate(slots[key][:min(b[key], n_slots)]):
                x, y = cx + dx, cy + dy
                if not visible(x, y, 40):
                    continue
                screen.blit(img, img.get_rect(center=(x, y)))
                if key == "drill":
                    screen.fill(WHITE if blink ^ (idx % 2 == 0) else RED, (x, y - 10, 1, 1))
                elif key == "refinery":  # dym z komina
                    for j in range(3):
                        tt = (t_ms // 130 + j * 4) % 12
                        screen.fill(GREY if tt < 6 else DARK, (x + 6 + (tt // 4) % 2, y - 10 - tt, 2 if tt < 6 else 1, 2 if tt < 6 else 1))
                elif key == "scanner":  # migająca końcówka czaszy
                    screen.fill(WHITE if blink ^ (idx % 2 == 0) else CYAN, (x, y - 11, 1, 1))
                elif key == "shield":  # pulsujące pole tarczy
                    rr = 9 + (t_ms // 120 + idx * 3) % 4
                    pygame.draw.circle(screen, (115, 239, 247), (x, y - 6), rr, 1)
                elif key == "warp":    # fioletowy błysk na szczycie iglicy
                    screen.fill(WHITE if (t_ms // 200 + idx) % 2 else (210, 184, 255), (x - 1, y - 14, 2, 2))
                elif key == "engine":  # płomień z dyszy stanowiska testowego
                    screen.fill(YELLOW if (t_ms // 90) % 2 else ORANGE, (x + 8, y + 5, 2, 2 + (t_ms // 90) % 3))
        hq = bld_img["hq"]
        screen.blit(hq, hq.get_rect(center=(cx, cy)))
        screen.fill(CYAN if blink else WHITE, (cx + 16, cy - 10, 1, 1))     # czasza radaru
        screen.fill(RED if blink else ORANGE, (cx - 17, cy - 15, 1, 1))    # lampka masztu

    def drone_pos(d):
        f = max(0.0, min(1.0, 1.0 - d["t"] / d["total"]))
        dist = BASE_R + 60 + d["dist"] * (1 - abs(2 * f - 1))  # w tę i z powrotem wzdłuż promienia
        return math.cos(d["ang"]) * dist, math.sin(d["ang"]) * dist, f

    def draw_drones():
        """Drony to małe statki: lecą dziobem w stronę celu, a w drodze powrotnej niosą kolorową bryłkę surowca."""
        for d in S.drones:
            x, y, f = drone_pos(d)
            if not on_screen(x, y, 60):
                continue
            heading = math.degrees(d["ang"]) + (0.0 if f < 0.5 else 180.0)
            frame = drone_frames[(pygame.time.get_ticks() // 110 + int(d["ang"] * 10)) % 2]
            img = rotated(frame, heading + 90)
            cx, cy = sp(x, y)
            screen.blit(img, img.get_rect(center=(cx, cy)))
            if f >= 0.5:  # ładunek
                col = ORE[d["kind"]]["color"]
                screen.fill(NAVY, (cx - 2, cy - 2, 5, 5))
                screen.fill(col, (cx - 1, cy - 1, 3, 3))

    def draw_pad(x, y, active, blink):
        """Lądowisko: płyta z oznaczeniem i migającymi światłami po rogach."""
        pygame.draw.rect(screen, NAVY, (x - 8, y - 8, 17, 17))
        pygame.draw.rect(screen, CYAN if active else DARK, (x - 8, y - 8, 17, 17), 1)
        pygame.draw.rect(screen, DARK, (x - 5, y - 5, 11, 11), 1)
        screen.fill(YELLOW if not active else CYAN, (x - 3, y, 7, 1))   # znak "H"
        screen.fill(YELLOW if not active else CYAN, (x - 3, y - 3, 1, 7))
        screen.fill(YELLOW if not active else CYAN, (x + 3, y - 3, 1, 7))
        col = (CYAN if blink else WHITE) if active else (LIME if blink else RED)
        for ox, oy in ((-7, -7), (7, -7), (-7, 7), (7, 7)):
            screen.fill(col, (x + ox, y + oy, 1, 1))

    def draw_base_planet(t_ms):
        cx, cy = sp(0, 0)
        lim = BASE_ART_R + 70
        if abs(cx - VW // 2) < VW // 2 + lim and abs(cy - VH // 2) < VH // 2 + lim:
            screen.blit(base_img, base_img.get_rect(center=(cx, cy)))
            if save["base"]["ring"]:
                draw_ring(cx, cy, save["base"]["ring"], t_ms)
            draw_buildings(cx, cy, t_ms)
            blink = (t_ms // 350) % 2 == 0
            for k in range(N_PADS):
                px, py = pad_pos(k)
                x, y = sp(px, py)
                active = S.state == "flight" and S.phase in ("landing", "unload", "launch") and k == S.pad
                draw_pad(x, y, active, blink)
            # okrąg zasięgu automatycznego lądowania
            if S.state == "flight" and S.phase == "fly" and not S.undock_lock:
                r = DOCK_R * K
                for i in range(0, 720):
                    a_ = i * math.tau / 720
                    x_, y_ = round(cx + math.cos(a_) * r), round(cy + math.sin(a_) * r)
                    if 0 <= x_ < VW and 0 <= y_ < VH:
                        screen.fill(BLUE_D, (x_, y_, 1, 1))

    def draw_planet(pl):
        x, y = sp(pl.x, pl.y)
        if not (abs(x - VW // 2) < VW // 2 + 100 and abs(y - VH // 2) < VH // 2 + 100):
            return
        img = (dead_img if pl.depleted else planet_img)[(pl.kind, pl.variant)]
        if pl.flash > 0:
            pl.flash -= DT_SCALE
            img = silhouette(img, WHITE)
        screen.blit(img, img.get_rect(center=(x, y)))

    corner_mask = pygame.Surface((MM_S, MM_S))
    corner_mask.fill((0, 0, 0))
    pygame.draw.circle(corner_mask, (255, 0, 255), (MM_S // 2, MM_S // 2), MM_S // 2)
    corner_mask.set_colorkey((255, 0, 255))
    mm = pygame.Surface((MM_S, MM_S)).convert()

    def draw_minimap(planets):
        p = S.player
        c = MM_S // 2
        s = (c - 2) / map_range()
        mm.fill(NAVY)
        bx, by = c + (0 - p.x) * s, c + (0 - p.y) * s
        pygame.draw.circle(mm, (37, 113, 121), (round(bx), round(by)), max(1, round(SAFE_R * s)), 1)  # strefa bezpieczna
        pygame.draw.circle(mm, DARK, (c, c), c - 2, 1)
        for pl in planets:
            x, y = c + (pl.x - p.x) * s, c + (pl.y - p.y) * s
            if (x - c) ** 2 + (y - c) ** 2 < (c - 2) ** 2:
                col = DARK if pl.depleted else ORE[pl.kind]["color"]
                if pl.field_r > 0:  # skupisko asteroid: cienki pierścień wokół planety
                    pygame.draw.circle(mm, (86, 108, 134), (round(x), round(y)), max(4, round(pl.field_r * s)), 1)
                pygame.draw.circle(mm, col, (round(x), round(y)), 3)
                pygame.draw.circle(mm, NAVY, (round(x), round(y)), 3, 1)
        for e in entities:
            if e.name == "asteroid":
                x, y = c + (e.x - p.x) * s, c + (e.y - p.y) * s
                if (x - c) ** 2 + (y - c) ** 2 < (c - 2) ** 2:
                    mm.fill(YELLOW if e.gold else GREY, (round(x), round(y), 1, 1))
        for d in S.drones:
            x, y, _ = drone_pos(d)
            mx, my = c + (x - p.x) * s, c + (y - p.y) * s
            if (mx - c) ** 2 + (my - c) ** 2 < (c - 2) ** 2:
                mm.fill(LIME, (round(mx) - 1, round(my) - 1, 2, 2))
        db = math.hypot(bx - c, by - c)
        if db <= c - 4:  # baza w zasięgu: niebieska kropka z obwódką
            pygame.draw.circle(mm, CYAN, (round(bx), round(by)), max(2, round(BASE_R * s)) + 1)
            pygame.draw.circle(mm, BLUE_D, (round(bx), round(by)), max(2, round(BASE_R * s)))
        else:  # baza poza zasięgiem: strzałka na brzegu
            ux, uy = (bx - c) / db, (by - c) / db
            tip = (c + ux * (c - 2), c + uy * (c - 2))
            back = (c + ux * (c - 9), c + uy * (c - 9))
            wx, wy = -uy * 3.5, ux * 3.5
            pygame.draw.polygon(mm, CYAN, [tip, (back[0] + wx, back[1] + wy), (back[0] - wx, back[1] - wy)])
        # statek: biały punkt + kreska kierunku
        rad = p.angle * DEGTORAD
        mm.fill(WHITE, (c - 1, c - 1, 2, 2))
        mm.fill(WHITE, (round(c + math.cos(rad) * 4), round(c + math.sin(rad) * 4), 1, 1))
        mm.blit(corner_mask, (0, 0))
        mm.set_colorkey((0, 0, 0))
        x0, y0 = CW - MM_S - 4, 4
        pygame.draw.circle(screen, NAVY, (x0 + c, y0 + c), c)
        screen.blit(mm, (x0, y0))
        pygame.draw.circle(screen, CYAN if scanning() else DARK, (x0 + c, y0 + c), c, 1)
        dist = math.hypot(p.x, p.y)
        label = "BASE" if dist < DOCK_R * 1.2 else f"BASE {int(dist // 100)}KM"
        text(label, 8, CYAN, (x0 + c, y0 + MM_S + 3), mid=True)

    def edge_arrow(dx, dy, col, m=14):
        """Strzałka na krawędzi warstwy HUD w kierunku (dx, dy) od środka ekranu. Zwraca jej pozycję i wersor."""
        d = math.hypot(dx, dy) or 1.0
        ux, uy = dx / d, dy / d
        t = min((CW / 2 - m) / max(abs(ux), 1e-6), (CH / 2 - m) / max(abs(uy), 1e-6))
        cx, cy = CW / 2 + ux * t, CH / 2 + uy * t
        wx, wy = -uy * 4, ux * 4
        pts = [(cx + ux * 5, cy + uy * 5), (cx - ux * 3 + wx, cy - uy * 3 + wy), (cx - ux * 3 - wx, cy - uy * 3 - wy)]
        pygame.draw.polygon(screen, NAVY, [(x + 1, y + 1) for x, y in pts])
        pygame.draw.polygon(screen, col, pts)
        return cx, cy, ux, uy

    def draw_base_arrow():
        """Strzałka przy krawędzi ekranu wskazująca bazę, gdy planeta-baza jest poza widokiem."""
        bx, by = sp(0, 0)
        dx, dy = bx - VW // 2, by - VH // 2
        if math.hypot(dx, dy) - BASE_ART_R < VH // 2:  # krawędź planety jest w kadrze
            return
        edge_arrow(dx, dy, CYAN)

    def draw_scan_arrows(planets):
        """Deep Scan: przy krawędzi ekranu strzałki do najbliższych planet (kolor = surowiec, liczba = km)."""
        p = S.player
        cand = sorted((q for q in planets if not q.depleted),
                      key=lambda q: (q.x - p.x) ** 2 + (q.y - p.y) ** 2)[:6]
        for pl in cand:
            x, y = sp(pl.x, pl.y)
            if abs(x - VW // 2) < VW // 2 + 100 and abs(y - VH // 2) < VH // 2 + 100:
                continue
            col = ORE[pl.kind]["color"]
            cx, cy, ux, uy = edge_arrow(x - VW // 2, y - VH // 2, col, m=20)
            km = int(math.hypot(pl.x - p.x, pl.y - p.y) // 100)
            text(str(km), 8, col, (round(cx - ux * 15), round(cy - uy * 9)), mid=True)

    def cooldown_bar(y, label, remaining, total, active=None):
        x0 = 6 + len(label) * 8 + 6
        pygame.draw.rect(screen, DARK, (x0, y, 40, 7))
        if active is not None:  # zdolność trwa: pasek pokazuje pozostały czas
            text(label, 8, CYAN, (6, y))
            pygame.draw.rect(screen, CYAN, (x0, y, max(1, int(40 * active)), 7))
        else:
            frac = 1.0 - remaining / total
            ready = remaining <= 1e-6
            text(label, 8, LIME if ready else GREY, (6, y))
            pygame.draw.rect(screen, LIME if ready else ORANGE, (x0, y, int(40 * frac), 7))
        pygame.draw.rect(screen, NAVY, (x0, y, 40, 7), 1)

    def draw_hud(tier):
        lv = save["levels"]
        p = S.player
        text(f"CREDITS {save['credits']}", 8, YELLOW, (6, 6))
        tot, cap = cargo_total(), S.cap
        full = tot >= cap
        text(f"CARGO {tot}/{cap}", 8, ORANGE if full and (pygame.time.get_ticks() // 300) % 2 else WHITE, (6, 18))
        x = 6
        for kind in ORE_KINDS:  # ile czego w ładowni (tylko to, co masz)
            if not S.cargo[kind]:
                continue
            screen.fill(ORE[kind]["color"], (x, 31, 5, 5))
            text(str(S.cargo[kind]), 8, WHITE, (x + 8, 30))
            x += 8 + 8 * len(str(S.cargo[kind])) + 8
        if x == 6:
            text("EMPTY", 8, GREY, (6, 30))
        if tier < 0:
            text("SAFE ZONE", 8, LIME, (6, 42))
        else:
            text(f"ROCK HP {min(HP_MAX, 1 + tier)}", 8, ORANGE, (6, 42))
        if S.max_shield:
            text("SHIELD", 8, CYAN, (6, 54))
            pips(62, 54, S.shield, S.max_shield, CYAN, DARK, w=6, gap=2, h=7)
        yy = 66
        if income_rate(save["base"]):
            text(f"VAULT {int(save['vault'])}/{vault_cap(save['base'])}", 8, YELLOW, (6, yy))
            yy += 12
        pr = save["project"]
        if pr:
            m = module_by_key(pr["key"])
            cost = m["costs"][save["base"][pr["key"]]]
            done = sum(min(pr["progress"][k], n) for k, n in cost.items())
            text(f"BUILD {m['name'].split()[0]} {done}/{sum(cost.values())}", 8, CYAN, (6, yy))
            yy += 12
        if save["drones"]:
            text(f"DRONES {save['drones']}", 8, LIME, (6, yy))
            yy += 12
        if S.combo > 1:
            text(f"COMBO X{S.combo}", 8, ORANGE, (6, yy))
        text("ESC - PAUSE", 8, GREY, (CW - 6, CH - 14), right=True)
        bars = []
        if lv["wave"] and S.ship["id"] == "interceptor":  # Shockwave jest wyłączny dla Interceptora
            bars.append(("E SHOCKWAVE", S.wave_cd, WAVE_COOLDOWN[lv["wave"] - 1], None))
        if lv["missile"] and S.ship["missiles"]:  # rakiety: tylko Bruiser i Striker
            bars.append(("Q MISSILES", S.missile_cd, missile_of(lv["missile"])[1] * S.ship["missile_reload"], None))
        ab = S.ship["ability"]
        if ab:
            act = None
            if ab in ("overdrive", "scan") and S.ab_t > 0:
                act = S.ab_t / max(1, S.ab_total)
            elif ab == "pulse" and S.well_t > 0:
                act = S.well_t / max(1, S.well_total)
            label = f"SHIFT {ABILITY_NAME[ab]}" + (f" X{S.dash_charges}" if ab == "dash" and lv["dash"] >= 5 else "")
            bars.append((label, S.dash_cd, ability_cd(ab), act))
        for i, (label, remaining, total, act) in enumerate(bars):
            cooldown_bar(CH - 14 - i * 12, label, remaining, total, act)
        if S.ship["beam"]:
            nb = len(S.beam_targets)
            text("TRACTOR BEAM", 8, GREY, (6, CH - 14 - len(bars) * 12))
            text(f"LOCKED {nb}/{BEAM_N[lv['beam']]}" if nb else "SCANNING", 8, YELLOW if nb else GREY,
                 (6 + 13 * 8, CH - 14 - len(bars) * 12))
        n_above = len(bars) + (1 if S.ship["beam"] else 0)
        if S.ship["id"] == "heavy" and lv["turret"]:
            text(f"AUTO TURRET LV {lv['turret']}", 8, ORANGE, (6, CH - 14 - n_above * 12))
            n_above += 1
        if save["base"]["warp"]:
            text(f"H WARP HOME x{S.warps}", 8, LIME if S.warps else GREY, (6, CH - 14 - n_above * 12))
        if S.toast[2] > 0:
            if S.toast[2] > 30 or (int(S.toast[2]) // 3) % 2 == 0:
                text(S.toast[0], 8, S.toast[1], (0, 104), center=True)
            S.toast[2] -= DT_SCALE

    # ---------- krok symulacji lotu ----------
    def flight_step():
        p = S.player
        lv = save["levels"]
        dt = real_dt   # rzeczywisty upływ czasu tej klatki (nie zakładane 1/60)
        S.fire_cd = max(0.0, S.fire_cd - dt)
        od_on = S.ship["ability"] == "overdrive" and S.ab_t > 0
        S.missile_cd = max(0.0, S.missile_cd - dt * (2.0 if (od_on and lv["overdrive"] >= 4) else 1.0))
        if S.combo_t > 0:  # Kill Combo gaśnie po kilku sekundach bez zabójstwa
            S.combo_t -= DT_SCALE
            if S.combo_t <= 0:
                S.combo_t, S.combo = 0, 0
        S.wave_cd = max(0.0, S.wave_cd - dt)
        S.dash_cd = max(0.0, S.dash_cd - dt)
        if S.ab_t > 0:
            S.ab_t -= DT_SCALE
            if S.ship["ability"] == "scan" and S.ab_t > 30:   # okresowe pingi skanera (co ~1.67s), dopóki > 0.5s zostało
                S.scan_ping_cd -= dt
                if S.scan_ping_cd <= 0:
                    S.scan_ping_cd = 100.0 / FPS
                    fx_scan_ping(p)
            if S.ship["ability"] == "overdrive" and S.phase == "fly":               # iskry i żar podczas Overdrive
                for _ in range(emit_count(2)):
                    a_ = random.random() * math.tau
                    particles.append(Particle(p.x + math.cos(a_) * 18, p.y + math.sin(a_) * 18,
                                              math.cos(a_) * 2.5, math.sin(a_) * 2.5, 14, (YELLOW, ORANGE, RED, PLUM)))
        if S.wave_queue:  # kolejne uderzenia Shockwave (poziomy 4-5)
            for q in S.wave_queue:
                q[0] -= DT_SCALE
                if q[0] <= 0 and S.phase == "fly":
                    waves.append(Shockwave(p, WAVE_RADIUS[q[1]], WAVE_DAMAGE[q[1]], (CYAN, WHITE), "electric"))
                    S.shake = max(S.shake, 8)
            S.wave_queue = [q for q in S.wave_queue if q[0] > 0]
        if S.well_t > 0 and S.phase == "fly":  # Gravity Well: ciągnie ładunek i asteroidy, miażdży te przy statku
            wi = save["levels"]["pulse"]
            R_, crush = WELL_R[wi], WELL_CRUSH[wi]
            S.well_t -= DT_SCALE
            S.phase_t = max(S.phase_t, 3)
            for a in entities:
                if a.name != "asteroid" or not a.life:
                    continue
                dxp, dyp = p.x - a.x, p.y - a.y
                d = math.hypot(dxp, dyp) or 1.0
                if d < R_:
                    spd = 3.0 + 9.0 * (1 - d / R_)
                    a.dx += (dxp / d * spd - a.dx) * min(1.0, 0.14 * DT_SCALE)
                    a.dy += (dyp / d * spd - a.dy) * min(1.0, 0.14 * DT_SCALE)
                    if d < p.R + a.R + 70 and a.crush_cd <= 0:
                        a.crush_cd = 12
                        damage_asteroid(a, crush)
            for o in ores:
                if math.hypot(p.x - o.x, p.y - o.y) < R_:
                    o.pull = max(o.pull, 4)
            for _ in range(emit_count(3)):   # materia wciągana spiralą do środka studni
                a_ = random.random() * math.tau
                rr = random.uniform(420, min(R_, 1300))
                sp_ = random.uniform(8, 14)
                particles.append(Streak(p.x + math.cos(a_) * rr, p.y + math.sin(a_) * rr,
                                        -math.cos(a_ + 0.6) * sp_, -math.sin(a_ + 0.6) * sp_, int(rr / sp_ * 0.9),
                                        ((56, 183, 100), LIME, WHITE), 1.0))
            if S.well_t > 0:
                S.well_ping_cd -= dt
                if S.well_ping_cd <= 0:
                    S.well_ping_cd = 45.0 / FPS
                    waves.append(Shockwave(p, R_, 0, (LIME, WHITE)))
            if S.well_t <= 0:  # koniec studni: odrzut, żeby zebrane asteroidy nie spadły na statek
                knockback(p.x, p.y, R_, WELL_KNOCK, crush)
                waves.append(Shockwave(p, R_, 0, (LIME, WHITE)))
                fx_well_end(p, R_)
                S.phase_t = max(S.phase_t, 90)   # chwila nietykalności po odrzucie
                S.shake = 18
                set_toast("KNOCKBACK!", LIME, 80)
        p.boost = 1.35 if (S.ship["ability"] == "overdrive" and S.ab_t > 0) else 1.0
        if S.invuln > 0:
            S.invuln -= DT_SCALE
        if S.phase_t > 0:
            S.phase_t -= DT_SCALE
        fly = S.phase == "fly"
        S.turn_dir = 0
        p.reverse = False

        if fly:
            keys = pygame.key.get_pressed()
            if keys[pygame.K_d]:
                p.angle += p.turn
            if keys[pygame.K_a]:
                p.angle -= p.turn
            p.thrust = bool(keys[pygame.K_w])
            p.reverse = bool(keys[pygame.K_s]) and not p.thrust
            S.turn_dir = (1 if keys[pygame.K_d] else 0) - (1 if keys[pygame.K_a] else 0)
            if keys[pygame.K_SPACE] and S.fire_cd <= 1e-6:
                shoot()
            if lv["missile"] and S.ship["missiles"] and keys[pygame.K_q] and S.missile_cd <= 1e-6:
                fire_missiles()
            p.anim = ship_anims[S.ship["id"]][1 if p.thrust else 0]

        # ---- Nano Regen (Scout): co pewien czas wraca ładunek tarczy ----
        if fly and S.ship["id"] == "scout" and lv["autorepair"] > 0:
            S.regen_t += dt
            if S.regen_t >= AUTOREPAIR_SECS[lv["autorepair"]]:
                S.regen_t = 0.0
                if S.shield < max(S.max_shield, 1):
                    S.shield += 1
                    S.max_shield = max(S.max_shield, S.shield)
                    fx_repair(p, small=True)

        # ---- automatyczne działko (tylko Bruiser) ----
        tl = lv["turret"] if S.ship["id"] == "heavy" else 0
        if fly and tl:
            S.turret_cd = max(0.0, S.turret_cd - dt)
            if S.turret_flash > 0:
                S.turret_flash -= DT_SCALE
            S.turret_msl_cd = max(0.0, S.turret_msl_cd - dt)
            best, bd = None, TURRET_RANGE[tl - 1] ** 2
            for a in entities:
                if a.name == "asteroid" and a.life:
                    d2 = (a.x - p.x) ** 2 + (a.y - p.y) ** 2
                    if d2 < bd:
                        best, bd = a, d2
            S.turret_target = best
            if best is None:
                S.turret_angle = p.angle
            else:
                t_hit = math.sqrt(bd) / BULLET_SPEED  # celuje z wyprzedzeniem
                ang = math.degrees(math.atan2(best.y + best.dy * t_hit - p.y, best.x + best.dx * t_hit - p.x))
                S.turret_angle = ang
                if S.turret_cd <= 1e-6:
                    rad = math.radians(ang)
                    for off in ((-6, 6) if tl >= 5 else (0,)):   # poziom 5: dwie lufy
                        b = Bullet()
                        b.settings(s_bullet, p.x + math.cos(rad) * 14 - math.sin(rad) * off,
                                   p.y + math.sin(rad) * 14 + math.cos(rad) * off, ang, 10)
                        b.dmg = 1 + (1 if tl >= 2 else 0)
                        b.ivx, b.ivy = p.dx, p.dy
                        entities.append(b)
                    S.turret_cd = TURRET_COOLDOWN[tl - 1]
                    S.turret_flash = 3
                    fx_turret_shot(p, rad)
                if tl >= 4 and S.turret_msl_cd <= 1e-6:  # poziom 4: rakiety samonaprowadzające, poziom 6: trzy kasetowe
                    for sgn in ((-1, 0, 1) if tl >= 6 else (-1, 1)):
                        m = Missile(entities, best)
                        m.settings(s_missile, p.x, p.y, ang + sgn * 25, 10)
                        m.cluster = tl >= 6
                        entities.append(m)
                    S.turret_msl_cd = TURRET_MISSILE_CD
                    S.turret_flash = 5
        else:
            S.turret_target = None

        # ---- skryptowane fazy: lądowanie, rozładunek, start, wrak ----
        if S.phase == "landing":
            u = S.t / LAND_FRAMES
            e = smoothstep(u)
            lfx, lfy = S.land_from
            tx, ty = pad_pos(S.pad)
            ox, oy = p.x, p.y
            p.x, p.y = lfx + (tx - lfx) * e, lfy + (ty - lfy) * e
            p.dx, p.dy = p.x - ox, p.y - oy
            target = math.degrees(pad_angle(S.pad))
            p.angle = S.land_a0 + angle_diff(S.land_a0, target) * min(1.0, u * 1.5)
            p.scale = 1.0 - 0.45 * e
            p.anim = ship_anims[S.ship["id"]][1]
            S.dust_cd -= dt
            if S.dust_cd <= 0:
                S.dust_cd = 3.0 / FPS
                rad = p.angle * DEGTORAD
                burst(p.x - math.cos(rad) * 12, p.y - math.sin(rad) * 12, 2, (WHITE, GREY, DARK), speed=1.5, life=16)
            S.t += DT_SCALE
            if S.t >= LAND_FRAMES:  # lądowanie: obłok pyłu i rozładunek
                burst(tx, ty, 26, (WHITE, GREY, DARK), speed=3.5, life=26)
                fx.append(FxRing(tx, ty, 20, 260, 20, (WHITE, GREY), 2))
                glow(tx, ty, 30, 150, 16, (170, 230, 255), 0.8)
                S.shake = 6
                p.dx = p.dy = 0.0
                p.anim = ship_anims[S.ship["id"]][0]
                S.unload_q = [[k, S.cargo[k]] for k in ORE_KINDS if S.cargo[k] > 0]   # partie: [surowiec, ile zostało]
                S.unload_total = sum(n for _, n in S.unload_q)
                S.cargo = {k: 0 for k in ORE_KINDS}
                S.phase, S.t, S.idle_t = "unload", 0, 0
                S.unload_cd = S.dust_cd = 0.0
                S.vault_done = False
                S.sold_f, S.vault_got = 0.0, 0
                S.div = {k: 0 for k in ORE_KINDS}
                S.div_t = {k: 0 for k in ORE_KINDS}
                S.tally = {k: 0.0 for k in ORE_KINDS}
        elif S.phase == "unload":
            tx, ty = pad_pos(S.pad)
            S.t += DT_SCALE
            S.unload_cd -= dt
            if S.unload_q and S.unload_cd <= 0:  # rozładunek zawsze trwa najwyżej ok. 1,5 s, nawet przy ładowni 2500
                S.unload_cd = 3.0 / FPS
                batch = max(1, -(-S.unload_total // 30))
                grp = S.unload_q[0]
                kind = grp[0]
                m = min(batch, grp[1])
                grp[1] -= m
                for _ in range(m):
                    r, v = process_unit(kind)  # najpierw projekt bazy, reszta na sprzedaż
                    if r == "proj":
                        S.div[kind] += 1
                        S.div_t[kind] += 1
                    else:
                        S.sold_f += v
                        S.tally[kind] += v
                burst(tx, ty - 8, 5, (YELLOW, WHITE, ORANGE), speed=2.5, life=18)
                if grp[1] <= 0:  # koniec partii jednego surowca: napisy z sumami
                    S.unload_q.pop(0)
                    fxx = tx + (ORE_KINDS.index(kind) - 1) * 30
                    if S.tally[kind] > 0:
                        floats.append([fxx, ty - 26, f"+{int(round(S.tally[kind]))}", ORE[kind]["color"], 60])
                    if S.div_t[kind] > 0:
                        floats.append([fxx, ty - 40, f"{S.div_t[kind]} TO BASE", LIME, 60])
                    S.tally[kind] = 0.0
                    S.div_t[kind] = 0
            if not S.unload_q:
                S.idle_t += DT_SCALE
                if not S.vault_done:  # skarbiec z pasywnym dochodem opróżnia się raz, przy lądowaniu
                    S.vault_done = True
                    got = int(save["vault"])
                    if got > 0:
                        add_credits(got)
                        save["vault"] -= got
                        S.vault_got = got
                        floats.append([tx, ty - 54, f"VAULT +{got}", YELLOW, 70])
                if S.idle_t > (28 if not (S.sold_f or S.vault_got or sum(S.div.values())) else 55):
                    msg = check_project()
                    lines = []
                    if S.sold_f:
                        lines.append((f"CARGO SOLD  +{int(S.sold_f)} CR", LIME))
                    if sum(S.div.values()):
                        lines.append((f"{sum(S.div.values())} ORE TO BASE PROJECT", CYAN))
                    if S.vault_got:
                        lines.append((f"VAULT  +{S.vault_got} CR", YELLOW))
                    if msg:
                        lines.append((msg, LIME))
                    S.lines = lines or [("LANDED - NOTHING TO SELL", GREY)]
                    persist()
                    S.state = "base"
                    S.sel = 0
        elif S.phase == "launch":
            u = S.t / LAUNCH_FRAMES
            e = smoothstep(u)
            sx, sy = pad_pos(S.pad)
            a = pad_angle(S.pad)
            ox, oy = p.x, p.y
            p.x, p.y = sx + math.cos(a) * LAUNCH_DIST * e, sy + math.sin(a) * LAUNCH_DIST * e
            p.dx, p.dy = p.x - ox, p.y - oy
            p.scale = 0.55 + 0.45 * e
            p.angle = math.degrees(a)
            p.anim = ship_anims[S.ship["id"]][1]
            S.dust_cd -= dt
            if S.dust_cd <= 0:
                S.dust_cd = 3.0 / FPS
                rad = p.angle * DEGTORAD
                burst(p.x - math.cos(rad) * 12, p.y - math.sin(rad) * 12, 2, (YELLOW, ORANGE, RED), speed=1.5, life=14)
            S.t += DT_SCALE
            if S.t >= LAUNCH_FRAMES:
                p.scale = 1.0
                p.dx, p.dy = math.cos(a) * 5, math.sin(a) * 5
                S.phase = "fly"
        elif S.phase == "dead":
            S.t += DT_SCALE
            if S.t > 100:
                S.state = "base"
                S.sel = 0

        alive = S.phase != "dead"

        # ---- asteroidy: pojawiają się dopiero poza strefą bezpieczną ----
        if fly:
            tier_p = zone_tier(math.hypot(p.x, p.y))
            if tier_p >= 0:
                n_rocks = sum(1 for e in entities if e.name == "asteroid")
                if n_rocks < min(90, 20 + 7 * tier_p) and random.random() < 0.25:
                    ang = random.uniform(0, math.tau)
                    vd = math.hypot(VW, VH) / K / 2   # połowa przekątnej widoku (logika)
                    dist = random.uniform(vd + 150, vd + 500)   # tuż za krawędzią widoku
                    x, y = p.x + math.cos(ang) * dist, p.y + math.sin(ang) * dist
                    tier_s = zone_tier(math.hypot(x, y))
                    if tier_s >= 0:
                        gold = random.random() < min(0.25, 0.08 + 0.02 * tier_s)
                        rt = "colossus" if random.random() < 0.02 else "large"   # rzadki wędrujący kolos
                        entities.append(new_rock(x, y, random.randrange(360), rt, gold, min(HP_MAX, 1 + tier_s),
                                                 pick_ore(math.hypot(x, y), gold)))
            # skupiska: wokół niektórych planet trzyma się gęsty pierścień asteroid (w tym kolosów)
            vdf = math.hypot(VW, VH) / K / 2
            for pl in WORLD.near(p.x, p.y):
                if pl.field_r <= 0:
                    continue
                if math.hypot(p.x - pl.x, p.y - pl.y) > pl.field_r + vdf + 300:
                    continue
                members = [e for e in entities if e.name == "asteroid" and e.field is pl]
                if len(members) < FIELD_TARGET and random.random() < 0.5:
                    for _try in range(4):
                        ang = random.uniform(0, math.tau)
                        r = pl.R + 260 + (random.random() ** 0.8) * (pl.field_r - pl.R - 260)
                        x, y = pl.x + math.cos(ang) * r, pl.y + math.sin(ang) * r
                        d0 = math.hypot(x, y)
                        if on_screen(x, y, -150) or d0 < SAFE_R + 300:   # nie pojawiają się w kadrze ani w strefie bazy
                            continue
                        tier_s = zone_tier(d0)
                        gold = random.random() < min(0.35, 0.16 + 0.02 * tier_s)
                        n_col = sum(1 for e in members if e.tier == "colossus")
                        rt = "colossus" if (n_col < 4 and random.random() < 0.12) else "large"
                        a = new_rock(x, y, random.randrange(360), rt, gold, min(HP_MAX, 1 + tier_s), pick_ore(d0, gold))
                        a.dx, a.dy = random.uniform(-1.4, 1.4) * (0.4 if rt == "colossus" else 1), random.uniform(-1.4, 1.4) * (0.4 if rt == "colossus" else 1)
                        a.field = pl
                        entities.append(a)
                        break
        for e in entities:  # sprzątanie i pole ochronne wokół bazy
            if e.name == "asteroid":
                dd = math.hypot(e.x - p.x, e.y - p.y)
                d0 = math.hypot(e.x, e.y) or 1.0
                vd = math.hypot(VW, VH) / K / 2
                if e.field is not None:  # asteroidy ze skupiska wolno krążą wokół swojej planety
                    fdx, fdy = e.field.x - e.x, e.field.y - e.y
                    fd = math.hypot(fdx, fdy) or 1.0
                    if fd > e.field.field_r:
                        e.dx += fdx / fd * 0.05 * DT_SCALE
                        e.dy += fdy / fd * 0.05 * DT_SCALE
                    elif fd < e.field.R + 200:
                        e.dx -= fdx / fd * 0.05 * DT_SCALE
                        e.dy -= fdy / fd * 0.05 * DT_SCALE
                    sp2 = math.hypot(e.dx, e.dy)
                    if sp2 > 2.2 and e.knock <= 0:
                        e.dx, e.dy = e.dx / sp2 * 2.2, e.dy / sp2 * 2.2
                if dd > vd + 1500:
                    e.life = False
                elif d0 < SAFE_R:
                    if dd > vd + 100:
                        e.life = False
                    else:
                        e.dx += e.x / d0 * 0.2 * DT_SCALE
                        e.dy += e.y / d0 * 0.2 * DT_SCALE

        # ---- kolizje ----
        planets = WORLD.near(p.x, p.y)   # fizyka i rysowanie: tylko okolica
        S.map_planets = WORLD.near(p.x, p.y, max(4, min(12, int(map_range() / CHUNK) + 2)))   # minimapa i strzałki: cały zasięg
        game_over = False
        splashes = []
        shots = [e for e in entities if e.name in ("bullet", "missile") and e.life]  # raz na klatkę, nie dla każdej asteroidy
        for a in entities:
            if a.name != "asteroid" or not a.life:
                continue
            ax, ay, ar = a.x, a.y, a.R
            for b in shots:
                if b.life and (b.x - ax) ** 2 + (b.y - ay) ** 2 < (ar + b.R) ** 2:   # bez wywołania funkcji na każdą parę
                    b.life = False
                    damage_asteroid(a, b.dmg)
                    if b.name == "missile":
                        splashes.append((b.x, b.y, a))
                        if b.cluster:
                            cluster_burst(b.x, b.y)
                    break
            if fly and alive and a.life and is_collide(p, a):
                if a.beam or S.invuln > 0 or S.phase_t > 0:
                    if p.dash_t > 0 and S.ship["ability"] == "dash" and save["levels"]["dash"] >= 2:
                        damage_asteroid(a, DASH_RAM_DMG)  # poziom 2 dasha: taranowanie
                    continue
                if S.shield > 0:
                    S.shield -= 1
                    S.invuln = 90
                    S.shake = 10
                    kill_asteroid(a, split=False)
                    burst(p.x, p.y, 14, (WHITE, CYAN, BLUE_D), speed=5.0)
                    if S.ship["reactive"]:
                        rl = save["levels"]["reactive"]
                        waves.append(Shockwave(p, REACTIVE_R[rl], REACTIVE_DMG[rl], (ORANGE, YELLOW), "fire"))
                        fx_reactive(p, REACTIVE_R[rl])
                        if rl >= 4:   # poziom 4: odrzut asteroid
                            knockback(p.x, p.y, REACTIVE_R[rl], 10.0)
                        if rl >= 5 and random.random() < 0.3:   # poziom 5: 30% szans na zwrot ładunku
                            S.shield += 1
                            set_toast("SHIELD REFUNDED", CYAN, 60)
                else:
                    a.life = False
                    game_over = True
                    break
        for b in shots:  # pociski kontra mini-planety
            if b.life:
                for pl in planets:
                    if (b.x - pl.x) ** 2 + (b.y - pl.y) ** 2 <= (pl.R + 6) ** 2:
                        b.life = False
                        mine_planet(pl, b)
                        if b.name == "missile":
                            splashes.append((b.x, b.y, None))
                        break
        if fly:  # planety są twarde: statek odbija się od nich
            for pl in planets + [BASE_OBJ]:
                dxp, dyp = p.x - pl.x, p.y - pl.y
                d = math.hypot(dxp, dyp) or 1.0
                lim = pl.R + p.R
                if d < lim:
                    nx, ny = dxp / d, dyp / d
                    p.x, p.y = pl.x + nx * lim, pl.y + ny * lim
                    vn = p.dx * nx + p.dy * ny
                    if vn < 0:
                        p.dx -= 1.5 * vn * nx
                        p.dy -= 1.5 * vn * ny
                    p.dash_t = 0
        for sx, sy, src in splashes:
            burst(sx, sy, 14, (YELLOW, ORANGE, RED, PLUM))
            fx.append(FxRing(sx, sy, 10, 110, 10, (ORANGE, YELLOW), 2))
            glow(sx, sy, 30, 110, 12, (255, 160, 80), 0.9)
            streaks(sx, sy, 6, (WHITE, YELLOW, ORANGE), speed=8.0, life=10)
            for a in entities:
                if (a.name == "asteroid" and a.life and a is not src
                        and (a.x - sx) ** 2 + (a.y - sy) ** 2 <= (90 + a.R) ** 2):
                    damage_asteroid(a, 2)
        for w in waves:
            if w.active and w.damage > 0:
                r = w.r
                for a in entities:
                    if (a.name == "asteroid" and a.life and a not in w.hit
                            and math.hypot(a.x - w.x, a.y - w.y) <= r + a.R):
                        w.hit.add(a)
                        if w.style == "electric":
                            w.add_bolt(a.x, a.y)
                        damage_asteroid(a, w.damage, split=False)

        # ---- traktor-beamy Harvestera (ulepszenia: moc, 2 i 3 wiązki) ----
        if S.ship["beam"] and fly and not game_over:
            bl = save["levels"]["beam"]
            rng_ = BEAM_RANGE * BEAM_RANGE_MULT[bl]
            keep = []
            for bt in S.beam_targets:
                if bt.life and math.hypot(bt.x - p.x, bt.y - p.y) <= rng_ * 1.3:
                    keep.append(bt)
                else:
                    bt.beam = False
            S.beam_targets = keep
            free_beams = BEAM_N[bl] - len(S.beam_targets)
            if free_beams > 0 and cargo_free() > 0:  # nowe cele: najpierw złote, potem najbliższe
                cands = sorted(((not a.gold, math.hypot(a.x - p.x, a.y - p.y), i, a) for i, a in enumerate(entities)
                                if a.name == "asteroid" and a.life and not a.beam
                                and math.hypot(a.x - p.x, a.y - p.y) <= rng_))
                for _, _, _, a in cands[:free_beams]:
                    a.beam, a.pull_t = True, 0
                    S.beam_targets.append(a)
            for bt in list(S.beam_targets):
                dxp, dyp = p.x - bt.x, p.y - bt.y
                d = math.hypot(dxp, dyp) or 1.0
                if d <= p.R + bt.R + 10:
                    convert_asteroid(bt)
                    S.beam_targets.remove(bt)
                else:
                    bt.pull_t += DT_SCALE
                    spd = min(9.0 * BEAM_POWER[bl], (2.5 + bt.pull_t * 0.12) * BEAM_POWER[bl]) * (0.75 if bt.gold else 1.0)
                    if bt.tier == "colossus":
                        spd *= 0.55
                    lerp = min(1.0, 0.2 * DT_SCALE)
                    bt.dx += (dxp / d * spd - bt.dx) * lerp
                    bt.dy += (dyp / d * spd - bt.dy) * lerp

        entities.extend(pending)
        pending.clear()

        if game_over:
            ship_lost("SHIP LOST - CARGO DESTROYED")
            alive = False

        # ---- aktualizacja obiektów ----
        for e in entities:
            if e is p and S.phase != "fly":
                e.anim.update()
                continue
            e.update()
            e.anim.update()
            if e.name == "asteroid" and e.gold and random.random() < 0.12 * DT_SCALE and on_screen(e.x, e.y, 50):
                particles.append(Sparkle(e.x + random.uniform(-e.R, e.R), e.y + random.uniform(-e.R, e.R)))
            if e.name == "bullet" and e.spark and random.random() < DT_SCALE:
                particles.append(Particle(e.x, e.y, random.uniform(-0.6, 0.6), random.uniform(-0.6, 0.6), 10, (YELLOW, ORANGE, RED)))
            if e.name == "missile" and random.random() < DT_SCALE:
                rad = e.angle * DEGTORAD
                particles.append(Particle(e.x - math.cos(rad) * 14 + random.uniform(-3, 3),
                                          e.y - math.sin(rad) * 14 + random.uniform(-3, 3),
                                          random.uniform(-0.4, 0.4), random.uniform(-0.4, 0.4), 16, MISSILE_TRAIL))
        if S.ship["ability"] == "dash" and alive:
            lvd = lv["dash"]
            if p.dash_t > 0 and lvd >= 4:   # poziom 4: smuga rani asteroidy na trasie
                for a in entities:
                    if (a.name == "asteroid" and a.life and a.crush_cd <= 0
                            and math.hypot(a.x - p.x, a.y - p.y) < p.R + a.R + 50):
                        a.crush_cd = 6
                        damage_asteroid(a, DASH_TRAIL_DMG)
            if S.dash_prev > 0 and p.dash_t == 0:
                fx_dash_end(p, lvd)
                if lvd >= 6 and S.phase == "fly":   # poziom 6: uderzenie fazowe na końcu dasha
                    waves.append(Shockwave(p, 340, 12, (CYAN, WHITE), "electric"))
            S.dash_prev = p.dash_t
            if lvd >= 5 and S.dash_charges < 2:
                S.dash_rt -= dt
                if S.dash_rt <= 0:
                    S.dash_charges += 1
                    S.dash_rt = DASH_CD[lvd] if S.dash_charges < 2 else 0.0
        for e in entities:
            if e.name == "explosion" and e.anim.is_end():
                e.life = False
        for o in ores:
            if o.update(p, fly and alive and cargo_free() > 0,
                        Ore.MAGNET * S.ship["magnet"] * (1 + COILS_BONUS * lv["coils"] if S.ship["id"] == "hauler" else 1)):
                got = add_cargo(o.kind, o.amount)
                if got:
                    S.pick[o.kind] += got
                    o.amount -= got
                    if o.amount <= 0:
                        o.life = 0
                    burst(p.x, p.y, 3, (WHITE, ORE[o.kind]["color"]), speed=2.0, life=10)
        S.pick_t += DT_SCALE
        if S.pick_t >= 20:  # zbiorcze napisy "+N" zamiast jednego na bryłkę
            for k in ORE_KINDS:
                if S.pick[k]:
                    floats.append([p.x + ORE_KINDS.index(k) * 14 - 14, p.y - 30, f"+{S.pick[k]}", ORE[k]["color"], 40])
                    S.pick[k] = 0
            S.pick_t = 0
        if alive:
            emit_exhaust(p)
        if p.dash_t > 0 and alive:
            ghosts.append(Ghost(p.x, p.y, rotated(p.anim.image, p.angle + 90)))
        if alive and S.ab_t > 0 and S.ship["ability"] == "overdrive" and random.random() < DT_SCALE:  # ognista smuga
            rad = p.angle * DEGTORAD
            particles.append(Particle(p.x - math.cos(rad) * 18 + random.uniform(-6, 6),
                                      p.y - math.sin(rad) * 18 + random.uniform(-6, 6),
                                      random.uniform(-0.6, 0.6), random.uniform(-0.6, 0.6), 18, (YELLOW, ORANGE, RED, PLUM)))
        for d in S.drones:
            x, y, f = drone_pos(d)
            if on_screen(x, y, 60) and random.random() < 0.35 * DT_SCALE:
                rad = d["ang"] + (0.0 if f < 0.5 else math.pi)
                particles.append(Particle(x - math.cos(rad) * 22, y - math.sin(rad) * 22,
                                          random.uniform(-0.3, 0.3), random.uniform(-0.3, 0.3), 14, (YELLOW, ORANGE, PLUM, DARK)))
        for grp in (particles, ghosts, waves, fx):
            for o in grp:
                o.update()
        for f in floats:
            f[1] -= 1.6 * DT_SCALE
            f[4] -= DT_SCALE
        for e in entities:
            if e.name == "bullet" and e.spark and not e.life:
                burst(e.x, e.y, 5, (WHITE, YELLOW, ORANGE), speed=2.5, life=12)   # bomblet gaśnie mini-wybuchem
        entities[:] = [e for e in entities if e.life]
        ores[:] = [o for o in ores if o.life > 0]
        particles[:] = [q for q in particles if q.life > 0]
        if len(particles) > 1400:   # bezpiecznik wydajności przy wielkich eksplozjach
            del particles[:len(particles) - 1400]
        ghosts[:] = [g_ for g_ in ghosts if g_.life > 0]
        waves[:] = [w for w in waves if w.life]
        fx[:] = [f for f in fx if f.life > 0]
        if S.flash > 0:
            S.flash -= DT_SCALE
        floats[:] = [f for f in floats if f[4] > 0]

        # ---- kamera: podąża za statkiem z lekkim wyprzedzeniem ----
        if S.phase == "fly" or S.phase == "launch":
            tx, ty = p.x + p.dx * 6, p.y + p.dy * 6
        else:
            tx, ty = p.x, p.y
        follow = 1 - 0.88 ** DT_SCALE   # to samo tempo kamery przy każdym limicie FPS
        CAM[0] += (tx - CAM[0]) * follow
        CAM[1] += (ty - CAM[1]) * follow

        # ---- undock: po starcie lądowanie włącza się dopiero po odlocie od bazy ----
        if fly:
            db = math.hypot(p.x, p.y)
            if S.undock_lock and db > DOCK_R + 100:
                S.undock_lock = False
            if not S.undock_lock and db < DOCK_R:
                start_landing()
        return planets

    # ---------- płomienie silników, dopalacze, RCS ----------
    FLAME_PAL = {"blue": (BLUE_D, CYAN, WHITE), "fire": (RED, ORANGE, YELLOW), "green": ((56, 183, 100), LIME, WHITE)}
    fx_pts = {}
    for sid, info in SHIP_FX.items():
        bw, bh = info["body"]
        cxb = (bw - 1) / 2
        fx_pts[sid] = dict(
            main=[(x - cxb, (bh + 1) / 2) for x in info["nozzles"]],
            aft=[(-(bw / 2 - 2.5), bh / 2 - 3), (bw / 2 - 2.5, bh / 2 - 3)],
            retro=[(-bw / 4, -bh / 4), (bw / 4, -bh / 4)],
            rcs_f=(bw / 2 - 1, -bh / 5), rcs_r=(bw / 2 - 1, bh / 3))

    def draw_flame(sx, sy, phi, sc, lx, ly, ex, ey, w, L, pal, layers=3):
        """Płomień w układzie statku (dziób w górę): nasada (lx, ly), kierunek wyrzutu (ex, ey), 3 warstwy kolorów."""
        if L < 1.5:
            return
        qx, qy = -ey, ex
        cp, sp_ = math.cos(phi), math.sin(phi)
        for wk, lk, col in ((1.0, 1.0, pal[0]), (0.66, 0.74, pal[1]), (0.34, 0.46, pal[2]))[:layers]:
            ww, ll = w * wk, L * lk
            local = [(lx + qx * ww / 2, ly + qy * ww / 2), (lx - qx * ww / 2, ly - qy * ww / 2),
                     (lx - qx * ww / 4 + ex * ll * 0.62, ly - qy * ww / 4 + ey * ll * 0.62),
                     (lx + ex * ll, ly + ey * ll),
                     (lx + qx * ww / 4 + ex * ll * 0.62, ly + qy * ww / 4 + ey * ll * 0.62)]
            pts = [(round(sx + (a * cp - b * sp_) * sc), round(sy + (a * sp_ + b * cp) * sc)) for a, b in local]
            pygame.draw.polygon(screen, col, pts)

    def ship_power(p):
        """Moc silników: 0 = luz, 1 = ciąg, >1 = dash / Overdrive."""
        if S.phase == "fly":
            power = 1.0 if p.thrust else 0.0
            if p.dash_t > 0:
                power = 1.9
            elif S.ab_t > 0 and S.ship["ability"] == "overdrive":
                power = max(power, 0.5) * 1.35
            return power
        if S.phase in ("landing", "launch"):
            return 0.85
        return 0.0

    def draw_ship_flames(p):
        sid = S.ship["id"]
        info, pts = SHIP_FX[sid], fx_pts[sid]
        power = ship_power(p)
        sx, sy = sp(p.x, p.y)
        phi = math.radians(p.angle + 90)
        sc = p.scale
        pal = FLAME_PAL[info["pal"]]
        t = pygame.time.get_ticks()
        pw = min(power, 1.0)
        if power > 0.25:   # poświata dysz
            back = math.radians(p.angle + 180)
            gx, gy = sx + math.cos(back) * 14 * sc, sy + math.sin(back) * 14 * sc
            draw_glow(screen, gx, gy, (16 + 10 * max(0.0, power - 1.0)) * sc, pal[1], 0.3 + 0.25 * min(power, 1.6))
        for i, (lx, ly) in enumerate(pts["main"]):  # silniki główne: dłuższe, migoczące
            flick = 0.82 + 0.28 * random.random() + 0.08 * math.sin(t / 55.0 + i * 2.1)
            L = info["L"] * (0.22 + 0.78 * pw + max(0.0, power - 1.0) * 0.8) * flick
            draw_flame(sx, sy, phi, sc, lx, ly, 0, 1, info["w"] * (0.6 + 0.4 * pw), L, pal)
        if power > 0.25:  # małe dopalacze z tyłu, na obrzeżach kadłuba
            for i, (lx, ly) in enumerate(pts["aft"]):
                flick = 0.7 + 0.5 * random.random()
                draw_flame(sx, sy, phi, sc, lx, ly, 0, 1, 2, info["L"] * 0.5 * min(power, 1.3) * flick, pal, layers=2)
        if p.reverse:  # dopalacze wsteczne: krótkie płomienie z dziobu
            for lx, ly in pts["retro"]:
                draw_flame(sx, sy, phi, sc, lx, ly, 0, -1, 2, 5 + 2 * random.random(), pal, layers=2)
        if S.turn_dir:  # RCS: maleńkie dysze boczne przy skręcie
            fxp, fyp = pts["rcs_f"]
            rxp, ryp = pts["rcs_r"]
            if S.turn_dir > 0:   # w prawo: dziób pchany w prawo (dysza z lewej), rufa w lewo (dysza z prawej)
                draw_flame(sx, sy, phi, sc, -fxp, fyp, -1, 0, 2, 4 + 2 * random.random(), pal, layers=2)
                draw_flame(sx, sy, phi, sc, rxp, ryp, 1, 0, 2, 4 + 2 * random.random(), pal, layers=2)
            else:
                draw_flame(sx, sy, phi, sc, fxp, fyp, 1, 0, 2, 4 + 2 * random.random(), pal, layers=2)
                draw_flame(sx, sy, phi, sc, -rxp, ryp, -1, 0, 2, 4 + 2 * random.random(), pal, layers=2)

    def emit_exhaust(p):
        """Smuga cząsteczek za silnikami: dłuższy, bardziej widoczny ogon ognia."""
        sid = S.ship["id"]
        pw = ship_power(p)
        if pw < 0.3:
            return
        pal = FLAME_PAL[SHIP_FX[sid]["pal"]]
        phi = math.radians(p.angle + 90)
        cp, sp_ = math.cos(phi), math.sin(phi)
        back = math.radians(p.angle + 180)
        for lx, ly in fx_pts[sid]["main"]:
            if random.random() < 0.55 * min(pw, 1.5) * DT_SCALE:
                ox = (lx * cp - (ly + SHIP_FX[sid]["L"] * 0.7) * sp_) * p.scale / K
                oy = (lx * sp_ + (ly + SHIP_FX[sid]["L"] * 0.7) * cp) * p.scale / K
                spd = random.uniform(1.5, 3.8) * (1 + max(0, pw - 1) * 0.6)
                particles.append(Particle(p.x + ox, p.y + oy,
                                          math.cos(back) * spd + random.uniform(-0.5, 0.5),
                                          math.sin(back) * spd + random.uniform(-0.5, 0.5),
                                          random.randint(14, 22), (pal[1], pal[0], DARK)))

    def draw_brackets(cx, cy, half, col):
        """Cztery narożniki celownika wokół punktu (cx, cy)."""
        for sx, sy in ((-1, -1), (1, -1), (-1, 1), (1, 1)):
            x, y = cx + sx * half, cy + sy * half
            screen.fill(col, (x if sx < 0 else x - 3, y, 4, 1))
            screen.fill(col, (x, y if sy < 0 else y - 3, 1, 4))

    BEAM_PALS = ((YELLOW, WHITE), (CYAN, WHITE), (ORANGE, YELLOW), (LIME, WHITE), (PLUM, WHITE), (RED, YELLOW))

    def draw_beams(p):
        """Traktor-beamy: rdzeń z pulsującą obwiednią, pakiety energii płynące do statku i obracający się celownik."""
        tick = pygame.time.get_ticks()
        x0, y0 = sp(p.x, p.y)
        rad = p.angle * DEGTORAD
        ex, ey = x0 + math.cos(rad) * 8, y0 + math.sin(rad) * 8   # emiter przy dziobie
        for bi, bt in enumerate(S.beam_targets):
            if not (bt.life and S.phase == "fly"):
                continue
            outer, core = BEAM_PALS[bi % len(BEAM_PALS)]
            x1, y1 = sp(bt.x, bt.y)
            dist = math.hypot(x1 - ex, y1 - ey)
            n = max(1, int(dist))
            ux, uy = (x1 - ex) / max(dist, 1), (y1 - ey) / max(dist, 1)
            qx, qy = -uy, ux
            wob = math.sin(tick / 90.0 + bi)
            for i in range(0, n + 1, 1):
                f = i / n
                bx, by = ex + (x1 - ex) * f, ey + (y1 - ey) * f
                w = 1.5 * math.sin(f * 9 - tick / 60.0) * (1 - abs(2 * f - 1) * 0.3)   # falowanie wiązki
                screen.fill(outer, (round(bx + qx * (w + wob)), round(by + qy * (w + wob)), 1, 1))
                if i % 2 == 0:
                    screen.fill(outer, (round(bx - qx * (w + wob)), round(by - qy * (w + wob)), 1, 1))
                screen.fill(core, (round(bx), round(by), 1, 1))
            for k in range(5):  # pakiety energii lecą od celu do statku
                f = 1 - ((tick / 700.0 + k / 5.0) % 1.0)
                bx, by = ex + (x1 - ex) * f, ey + (y1 - ey) * f
                screen.fill(outer, (round(bx) - 2, round(by) - 2, 5, 5))
                screen.fill(WHITE, (round(bx) - 1, round(by) - 1, 3, 3))
            pulse = (tick // 120) % 3
            screen.fill(WHITE, (ex - 1, ey - 1, 3, 3))                      # emiter
            screen.fill(outer, (ex - 2 + pulse % 2, ey - 2, 1, 1))
            draw_glow(screen, x1, y1, int(bt.R * K) + 14, outer, 0.45)
            draw_glow(screen, ex, ey, 12, outer, 0.5)
            draw_brackets(x1, y1, int(bt.R * K) + 3 + pulse, outer)         # celownik na asteroidzie
            for k in range(4):                                                # obracające się znaczniki
                a = k * math.tau / 4 + tick / 400.0
                rr = int(bt.R * K) + 6
                screen.fill(WHITE, (round(x1 + math.cos(a) * rr), round(y1 + math.sin(a) * rr), 2, 2))

    def draw_well_fx(p):
        """Gravity Well: wir z obracającymi się ramionami, zapadające się pierścienie i ciemny rdzeń."""
        if S.well_t <= 0 or S.phase != "fly":
            return
        cx, cy = sp(p.x, p.y)
        tick = S.well_total - S.well_t
        rart = min(WELL_R[save["levels"]["pulse"]] * K, 240)
        draw_glow(screen, cx, cy, rart * 0.9, (40, 150, 60), 0.5 + 0.1 * math.sin(tick * 0.3))
        draw_glow(screen, cx, cy, 34, (200, 255, 200), 0.9)
        for arm in range(5):
            for i in range(32):
                t_ = i / 31.0
                r = rart * (1 - t_) ** 1.25 + 7
                a = arm * math.tau / 5 - tick * 0.075 + t_ * 6.2
                col = WHITE if t_ > 0.86 else (LIME if t_ > 0.4 else (56, 183, 100))
                size = 2 if t_ > 0.55 else 1
                screen.fill(col, (round(cx + math.cos(a) * r), round(cy + math.sin(a) * r), size, size))
        for j in range(3):
            u = (tick * 0.03 + j / 3.0) % 1.0
            pygame.draw.circle(screen, LIME if u < 0.65 else DARK, (cx, cy), int(rart * (1 - u)) + 8, 1)
        pygame.draw.circle(screen, NAVY, (cx, cy), 6)
        pygame.draw.circle(screen, WHITE if (tick // 3) % 2 else LIME, (cx, cy), 6, 1)

    def draw_scan_fx(p, planets):
        """Deep Scan: obracający się promień radaru z zanikającym śladem i celowniki na planetach oraz cennych skałach."""
        if not scanning() or S.phase != "fly":
            return
        cx, cy = sp(p.x, p.y)
        tick = pygame.time.get_ticks()
        a0 = tick / 450.0
        for k, col in enumerate((WHITE, CYAN, CYAN, ICE_C, BLUE_D, BLUE_D, NAVY, NAVY)):
            a = a0 - k * 0.075
            pygame.draw.line(screen, col, (cx, cy), (cx + math.cos(a) * 430, cy + math.sin(a) * 430), 1)
        for pl in planets:
            x, y = sp(pl.x, pl.y)
            if visible(x, y, 100):
                draw_brackets(x, y, int(pl.R * K) + 8 + (tick // 200) % 3, ORE[pl.kind]["color"])
        for e in entities:
            if e.name == "asteroid" and e.life and (e.gold or e.tier == "colossus") and on_screen(e.x, e.y, 0):
                ex_, ey_ = sp(e.x, e.y)
                draw_brackets(ex_, ey_, int(e.R * K) + 3 + (tick // 250) % 2, YELLOW if e.gold else WHITE)

    def draw_ship_auras(p):
        """Efekty na statku: smugi i "glitch" fazowy podczas dasha, żarząca aura podczas Overdrive."""
        cx, cy = sp(p.x, p.y)
        tick = pygame.time.get_ticks()
        if p.dash_t > 0:
            ang = math.radians(p.dash_angle)
            ux, uy = math.cos(ang), math.sin(ang)
            for _ in range(9):   # linie prędkości
                off = random.uniform(-p.R * K, p.R * K)
                back = random.uniform(4, 12)
                sx, sy = cx - ux * back - uy * off, cy - uy * back + ux * off
                ln = random.uniform(16, 44)
                pygame.draw.line(screen, random.choice((WHITE, CYAN, CYAN, BLUE_D)), (sx, sy), (sx - ux * ln, sy - uy * ln), 1)
            img = rotated(p.anim.image, p.angle + 90)
            for col, o in (((255, 60, 120), 2), (CYAN, -2)):   # rozszczepienie kolorów (glitch)
                sil = silhouette(img, col)
                screen.blit(sil, sil.get_rect(center=(round(cx - uy * o), round(cy + ux * o))))
        if p.dash_t > 0:
            draw_glow(screen, cx, cy, 36, (80, 220, 255), 0.7)
        if S.ab_t > 0 and S.ship["ability"] == "overdrive":
            draw_glow(screen, cx, cy, 44 + 6 * math.sin(tick / 90.0), (255, 110, 40), 0.6)
            rr = int(p.R * K) + 6 + int(2 * math.sin(tick / 80.0))
            for k in range(16):
                a = k * math.tau / 16 + tick / 500.0
                l2 = rr + 3 + (k % 2) * 3
                pygame.draw.line(screen, ORANGE if k % 2 else YELLOW, (cx + math.cos(a) * rr, cy + math.sin(a) * rr),
                                 (cx + math.cos(a) * l2, cy + math.sin(a) * l2), 1)
            pygame.draw.circle(screen, RED, (cx, cy), rr, 1)
            for k in range(4):
                a = k * math.tau / 4 - tick / 300.0
                pygame.draw.line(screen, YELLOW, (cx + math.cos(a) * (rr + 3), cy + math.sin(a) * (rr + 3)),
                                 (cx + math.cos(a) * (rr + 12), cy + math.sin(a) * (rr + 12)), 1)

    def compose_hud():
        """Warstwa HUD (480x320) powiększona 3x nakładana na świat: HUD zostaje duży i "klockowy".
        Powiększa tylko kafelki, na których coś jest (reszta to przezroczysty KEY): kilka razy szybciej niż całość."""
        screen.set_colorkey(KEY)   # subsurface dziedziczy colorkey, więc get_bounding_rect pomija puste piksele
        T = 64
        for ty in range(0, CH, T):
            for tx in range(0, CW, T):
                br = screen.subsurface((tx, ty, min(T, CW - tx), min(T, CH - ty))).get_bounding_rect()
                if not br.w:
                    continue
                br.move_ip(tx, ty)
                part = pygame.transform.scale(screen.subsurface(br), (br.w * ZOOM, br.h * ZOOM))
                part.set_colorkey(KEY)
                world.blit(part, (br.x * ZOOM, br.y * ZOOM))
        screen.set_colorkey(None)

    def draw_flight(planets):
        nonlocal screen
        p = S.player
        hud_layer = screen
        screen = world  # w tej części rysujemy świat na dużym płótnie
        draw_space()
        draw_base_planet(pygame.time.get_ticks())
        for pl in planets:
            draw_planet(pl)
        draw_drones()
        for w in waves:
            w.draw(screen)
        for f in fx:
            f.draw(screen)
        draw_well_fx(p)
        draw_scan_fx(p, planets)
        draw_beams(p)
        for g_ in ghosts:
            g_.draw(screen)
        for o in ores:
            if on_screen(o.x, o.y, 60):
                o.draw(screen)
        blink = S.invuln > 0 and (int(S.invuln) // 3) % 2 == 0
        if p.life and S.phase != "dead" and not (blink and S.phase == "fly"):
            draw_ship_flames(p)
            if S.phase == "fly":
                draw_ship_auras(p)
        for e in entities:
            if e is p and blink:
                continue
            if on_screen(e.x, e.y, 350):
                e.draw(screen)
                if e.name == "bullet":      # pociski i rakiety świecą
                    bx_, by_ = sp(e.x, e.y)
                    draw_glow(screen, bx_, by_, 9, (150, 70, 40), 0.8)
                elif e.name == "missile":
                    bx_, by_ = sp(e.x, e.y)
                    draw_glow(screen, bx_, by_, 16, (255, 170, 80), 0.8)
        for q in particles:
            q.draw(screen)
        if S.phase == "fly" and p.life and S.ship["id"] == "heavy" and save["levels"]["turret"]:
            tl_ = save["levels"]["turret"]
            tcx, tcy = sp(p.x, p.y)
            ta = math.radians(S.turret_angle)
            ca, sa = math.cos(ta), math.sin(ta)
            pygame.draw.circle(screen, NAVY, (tcx, tcy), 3)
            pygame.draw.circle(screen, GREY, (tcx, tcy), 2)
            blen = 6 - (2 if S.turret_flash > 1 else 0)   # odrzut lufy po strzale
            for off in ((-2, 2) if tl_ >= 5 else (0,)):
                bx, by = tcx - sa * off, tcy + ca * off
                tip = (round(bx + ca * blen), round(by + sa * blen))
                pygame.draw.line(screen, ORANGE, (round(bx), round(by)), tip, 1)
                if S.turret_flash > 0:   # błysk wylotowy
                    screen.fill(WHITE, (tip[0] - 1, tip[1] - 1, 3, 3))
                    screen.fill(YELLOW, (tip[0] - 3, tip[1], 7, 1))
                    screen.fill(YELLOW, (tip[0], tip[1] - 3, 1, 7))
            tg = S.turret_target
            if tg is not None and tg.life:   # celownik na wybranym celu
                gx, gy = sp(tg.x, tg.y)
                draw_brackets(gx, gy, int(tg.R * K) + 3 + (pygame.time.get_ticks() // 150) % 2,
                              RED if (pygame.time.get_ticks() // 200) % 2 else ORANGE)
        if p.life and (S.shield > 0 or S.invuln > 0) and S.phase == "fly":
            ring = WHITE if S.invuln > 0 else CYAN
            pygame.draw.circle(screen, ring, sp(p.x, p.y), int((p.R + 7) * K), 1)
        if S.flash > 0:  # krótki rozbłysk (warp, Overdrive, koniec studni, wybuchy kolosów) w kolorze efektu
            key_ = (world.get_size(), S.flash_col)
            fs = flash_cache.get(key_)
            if fs is None:
                fs = pygame.Surface(world.get_size()).convert()
                fs.fill(S.flash_col)
                flash_cache[key_] = fs
            fs.set_alpha(min(200, int(28 * S.flash)))
            screen.blit(fs, (0, 0))
        if S.shake > 0:  # drżenie dotyczy świata, HUD stoi w miejscu; słabnie razem z S.shake
            amp = max(1, min(9, int(1 + S.shake * 0.45)))
            world.scroll(random.randint(-amp, amp), random.randint(-amp, amp))
            S.shake -= DT_SCALE
        screen = hud_layer  # dalej: warstwa HUD (przezroczysta)
        screen.fill(KEY)
        for f in floats:  # napisy z punktami/surowcami: pozycja ze świata przeliczona na HUD
            fx_, fy_ = sp(f[0], f[1])
            text(f[2], 8, f[3], (fx_ // ZOOM, fy_ // ZOOM), mid=True)
        if scanning() and save["levels"]["scan"] >= 4:   # Deep Scan poziomu 4: ile surowca zostało na planetach w kadrze
            for pl in planets:
                px_, py_ = sp(pl.x, pl.y)
                if visible(px_, py_, 0):
                    text(f"{ORE[pl.kind]['name']} {pl.ore_left}", 8, ORE[pl.kind]["color"],
                         (px_ // ZOOM, (py_ - int(pl.R * K) - 12) // ZOOM), mid=True)
        if S.phase in ("fly", "launch"):
            draw_base_arrow()
            if scanning():
                draw_scan_arrows(S.map_planets)
        draw_hud(zone_tier(math.hypot(p.x, p.y)))
        draw_minimap(S.map_planets)
        compose_hud()

    # ---------- ekrany bazy ----------
    def draw_base_backdrop(low=False):
        CAM[0] += 0.6
        draw_space()
        cy = CH + BASE_ART_R - (26 if low else 58)  # tylko wierzch planety wyłania się zza dołu ekranu
        screen.blit(base_img, base_img.get_rect(center=(CW // 2, cy)))

    # --- dochód z bazy nagromadzony pod nieobecność gracza (do pojemności skarbca) ---
    rate0 = income_rate(save["base"]) / 60.0
    if rate0 > 0 and save["saved_at"]:
        away = max(0.0, time.time() - save["saved_at"])
        save["vault"] = min(float(vault_cap(save["base"])),
                            save["vault"] + rate0 * min(away, VAULT_MINUTES[save["base"]["vault"]] * 60.0))
    got0 = int(save["vault"])
    if got0 > 0:
        add_credits(got0)
        save["vault"] -= got0
        S.lines.append((f"WELCOME BACK  VAULT +{got0} CR", YELLOW))

    running = True
    real_dt = 1.0 / FPS
    while running:
        global DT_SCALE
        raw_ms = clock.tick(render_fps)
        if raw_ms is None:   # niektóre nakładki testowe/mocki zwracają None zamiast ms
            raw_ms = 1000.0 / FPS
        real_dt = min(raw_ms / 1000.0, DT_SCALE_CAP / FPS)   # ochrona przed skokiem po zacięciu (np. przeciąganie okna)
        DT_SCALE = real_dt * FPS   # przy 60 FPS = 1.0 (identycznie jak dawniej); przy 120 = 0.5, przy 240 = 0.25
        for event in pygame.event.get():
            if event.type == pygame.QUIT:
                running = False
            elif event.type == pygame.VIDEORESIZE:
                if not fullscreen:
                    windowed_size = (event.w, event.h)
                apply_view()
            elif event.type == pygame.KEYDOWN:
                key = event.key
                if key == pygame.K_F11:
                    fullscreen = not fullscreen
                    open_window(fullscreen, windowed_size)
                    apply_view()
                elif S.state == "base":
                    if key == pygame.K_UP:
                        S.sel = (S.sel - 1) % len(menu_items)
                    elif key == pygame.K_DOWN:
                        S.sel = (S.sel + 1) % len(menu_items)
                    elif key in (pygame.K_RETURN, pygame.K_KP_ENTER):
                        choice = menu_items[S.sel]
                        if choice == "LAUNCH":
                            do_launch()
                        elif choice == "UPGRADES":
                            S.notice[2] = 0
                            S.state = "upgrades"
                        elif choice == "SPECIALS":
                            S.spec_ship = next(i for i, s_ in enumerate(SHIPS) if s_["id"] == save["ship"])
                            S.spec_sel = 0
                            S.notice[2] = 0
                            S.state = "specials"
                        elif choice == "HANGAR":
                            S.hangar_sel = next(i for i, s_ in enumerate(SHIPS) if s_["id"] == save["ship"])
                            S.notice[2] = 0
                            S.state = "hangar"
                        elif choice == "BASE":
                            S.notice[2] = 0
                            S.state = "build"
                        elif choice == "SETTINGS":
                            S.fps_sel = RENDER_FPS_OPTIONS.index(render_fps)
                            S.notice[2] = 0
                            S.state = "settings"
                        elif choice == "SAVES":
                            refresh_slots()
                            S.slot_sel = S.slot - 1
                            S.notice[2] = 0
                            S.confirm = (-1, 0)
                            S.state = "saves"
                        else:
                            running = False
                elif S.state == "flight":
                    if S.phase == "fly":
                        if key == pygame.K_SPACE and S.fire_cd <= 1e-6:
                            shoot()
                        elif (key == pygame.K_e and save["levels"]["wave"] and S.ship["id"] == "interceptor"
                              and S.wave_cd <= 1e-6):
                            cast_wave()
                        elif key in (pygame.K_LSHIFT, pygame.K_RSHIFT) and S.ship["ability"] and S.dash_cd <= 1e-6:
                            start_ability()
                        elif key == pygame.K_h and S.warps > 0 and math.hypot(S.player.x, S.player.y) > DOCK_R + 400:
                            do_warp()
                    if key == pygame.K_ESCAPE and S.phase in ("fly", "landing", "unload", "launch"):
                        S.pause_bg = world.copy()
                        S.state = "paused"
                elif S.state == "paused":
                    if key in (pygame.K_ESCAPE, pygame.K_RETURN, pygame.K_KP_ENTER):
                        S.state = "flight"
                    elif key == pygame.K_q:  # porzucenie wyprawy: wracasz do bazy bez ładunku
                        S.cargo = {k: 0 for k in ORE_KINDS}
                        S.lines = [("RUN ABANDONED - CARGO LOST", ORANGE)]
                        S.state = "base"
                        S.sel = 0
                elif S.state == "hangar":
                    if key == pygame.K_LEFT:
                        S.hangar_sel = (S.hangar_sel - 1) % len(SHIPS)
                    elif key == pygame.K_RIGHT:
                        S.hangar_sel = (S.hangar_sel + 1) % len(SHIPS)
                    elif key in (pygame.K_RETURN, pygame.K_KP_ENTER):
                        select_ship(S.hangar_sel)
                    elif key == pygame.K_ESCAPE:
                        S.state = "base"
                elif S.state == "build":
                    if key == pygame.K_UP:
                        S.build_sel = (S.build_sel - 1) % len(build_rows())
                    elif key == pygame.K_DOWN:
                        S.build_sel = (S.build_sel + 1) % len(build_rows())
                    elif key in (pygame.K_RETURN, pygame.K_KP_ENTER):
                        buy_base_row(S.build_sel)
                    elif key == pygame.K_ESCAPE:
                        S.state = "base"
                elif S.state == "saves":
                    if key == pygame.K_UP:
                        S.slot_sel = (S.slot_sel - 1) % SLOTS
                    elif key == pygame.K_DOWN:
                        S.slot_sel = (S.slot_sel + 1) % SLOTS
                    elif key in (pygame.K_RETURN, pygame.K_KP_ENTER):
                        if S.slot_sel + 1 == S.slot:
                            set_notice("THIS SAVE IS ALREADY ACTIVE", CYAN)
                        else:
                            switch_slot(S.slot_sel + 1)
                    elif key in (pygame.K_DELETE, pygame.K_BACKSPACE):
                        if S.confirm[0] == S.slot_sel and S.confirm[1] > 0:
                            delete_slot(S.slot_sel + 1)
                            S.confirm = (-1, 0)
                        elif S.slot_info[S.slot_sel] is None:
                            set_notice("SLOT IS ALREADY EMPTY", GREY)
                        else:
                            S.confirm = (S.slot_sel, 240)
                            set_notice("PRESS DEL AGAIN TO ERASE THIS SLOT", RED)
                    elif key == pygame.K_ESCAPE:
                        S.state = "base"
                elif S.state == "specials":
                    rows_n = len(SPECIALS[SHIPS[S.spec_ship]["id"]])
                    if key == pygame.K_LEFT:
                        S.spec_ship = (S.spec_ship - 1) % len(SHIPS)
                        S.spec_sel = 0
                    elif key == pygame.K_RIGHT:
                        S.spec_ship = (S.spec_ship + 1) % len(SHIPS)
                        S.spec_sel = 0
                    elif key == pygame.K_UP:
                        S.spec_sel = (S.spec_sel - 1) % rows_n
                    elif key == pygame.K_DOWN:
                        S.spec_sel = (S.spec_sel + 1) % rows_n
                    elif key in (pygame.K_RETURN, pygame.K_KP_ENTER):
                        buy_special()
                    elif key == pygame.K_ESCAPE:
                        S.state = "base"
                elif S.state == "settings":
                    if key in (pygame.K_LEFT, pygame.K_UP):
                        S.fps_sel = (S.fps_sel - 1) % len(RENDER_FPS_OPTIONS)
                    elif key in (pygame.K_RIGHT, pygame.K_DOWN):
                        S.fps_sel = (S.fps_sel + 1) % len(RENDER_FPS_OPTIONS)
                    elif key in (pygame.K_RETURN, pygame.K_KP_ENTER):
                        render_fps = RENDER_FPS_OPTIONS[S.fps_sel]
                        write_render_fps(render_fps)
                        set_notice(f"FPS CAP: {render_fps}", LIME)
                    elif key == pygame.K_ESCAPE:
                        S.state = "base"
                elif S.state == "upgrades":
                    if key == pygame.K_UP:
                        S.up_sel = (S.up_sel - 1) % len(UPGRADES)
                    elif key == pygame.K_DOWN:
                        S.up_sel = (S.up_sel + 1) % len(UPGRADES)
                    elif key in (pygame.K_RETURN, pygame.K_KP_ENTER):
                        buy_upgrade(S.up_sel)
                    elif key == pygame.K_ESCAPE:
                        S.state = "base"

        if S.state != "paused":
            economy_tick()

        if S.state == "base":
            draw_base_backdrop()
            text("HOME BASE", 24, YELLOW, (0, 8), center=True, shadow=RED)
            text(f"CREDITS {save['credits']}", 16, CYAN, (0, 36), center=True)
            info = []
            if income_rate(save["base"]):
                info.append(f"INCOME {income_rate(save['base'])}/MIN")
            if save["drones"]:
                info.append(f"DRONES {save['drones']}")
            if info:
                text("   ".join(info), 8, GREY, (0, 55), center=True)
            blink = (pygame.time.get_ticks() // 400) % 2 == 0
            item_y0, item_step = 66, 17   # więcej pozycji w menu (SPECIALS, SETTINGS) -> mniejszy odstęp, żeby zmieścić stopkę
            for i, label in enumerate(menu_items):
                if i == S.sel:
                    label = f"> {label} <" if blink else f"  {label}  "
                text(label, 16, YELLOW if i == S.sel else WHITE, (0, item_y0 + i * item_step), center=True)
            lines_y0 = item_y0 + len(menu_items) * item_step + 8
            for j, (line, col) in enumerate(S.lines[-3:]):
                text(line, 8, col, (0, lines_y0 + j * 9), center=True)
            footer_y = lines_y0 + 3 * 9 + 6
            text("UP/DOWN + ENTER", 8, GREY, (0, footer_y), center=True)
            text("F11 - FULLSCREEN", 8, GREY, (0, footer_y + 10), center=True)

        elif S.state == "hangar":
            draw_base_backdrop(low=True)
            mx = (CW - 480) // 2  # układ ekranu jest projektowany na 480 px, na szerszym ekranie wyśrodkowany
            text("HANGAR", 24, YELLOW, (0, 14), center=True, shadow=RED)
            text(f"CREDITS: {save['credits']}", 8, CYAN, (CW - 6, 6), right=True)
            sh = SHIPS[S.hangar_sel]
            owned = sh["id"] in save["owned"]
            equipped = save["ship"] == sh["id"]
            panel((mx + 24, 60, 190, 190))
            t = pygame.time.get_ticks()
            img = ship_frames[sh["id"]][(t // 250) % 2 if owned else 0]
            img = rotated(img, t // 30)
            img = pygame.transform.scale(img, (img.get_width() * 3, img.get_height() * 3))
            if not owned:
                img = img.copy()
                img.fill((90, 90, 110), special_flags=pygame.BLEND_RGB_MULT)
            screen.blit(img, img.get_rect(center=(mx + 119, 155)))
            if not owned:
                text("LOCKED", 8, ORANGE, (mx + 119 - 24, 232))
            for j in range(len(SHIPS)):
                pygame.draw.rect(screen, YELLOW if j == S.hangar_sel else DARK, (mx + 119 - len(SHIPS) * 6 + j * 12, 68, 8, 4))
            if (t // 400) % 2 == 0:
                text("<", 16, WHITE, (mx + 6, 146))
                text(">", 16, WHITE, (mx + 216, 146))
            panel((mx + 232, 60, 224, 190))
            text(sh["name"], 16, YELLOW, (mx + 244, 72))
            for i, (label, val) in enumerate(zip(STAT_NAMES, sh["stats"])):
                y = 108 + i * 18
                text(label, 8, GREY, (mx + 244, y))
                pips(mx + 316, y, val, 5, LIME, DARK, w=12, gap=3, h=7)
            for i, line in enumerate(sh["perk"]):
                if line:
                    text(line, 8, WHITE, (mx + 244, 182 + i * 12))
            if equipped:
                text("EQUIPPED", 8, LIME, (mx + 244, 224))
            elif owned:
                text("OWNED - ENTER TO EQUIP", 8, CYAN, (mx + 244, 224))
            else:
                text(f"ENTER TO BUY: {sh['cost']} CR", 8, YELLOW if save["credits"] >= sh["cost"] else RED, (mx + 244, 224))
            if S.notice[2] > 0:
                text(S.notice[0], 8, S.notice[1], (0, 258), center=True)
                S.notice[2] -= DT_SCALE
            text("LEFT/RIGHT CHOOSE  ENTER SELECT  ESC BACK", 8, GREY, (0, CH - 16), center=True)

        elif S.state == "specials":
            draw_base_backdrop(low=True)
            text("SPECIALS", 24, YELLOW, (0, 4), center=True, shadow=RED)
            text(f"CREDITS: {save['credits']}", 8, CYAN, (CW - 6, 6), right=True)
            sh = SHIPS[S.spec_ship]
            owned = sh["id"] in save["owned"]
            keys = SPECIALS[sh["id"]]
            panel((16, 34, CW - 32, 58))
            t = pygame.time.get_ticks()
            img = ship_frames[sh["id"]][0]
            img = pygame.transform.scale(img, (img.get_width() * 2, img.get_height() * 2))
            if not owned:
                img = img.copy()
                img.fill((90, 90, 110), special_flags=pygame.BLEND_RGB_MULT)
            screen.blit(img, img.get_rect(center=(52, 63)))
            tx_ = max(86, 52 + img.get_width() // 2 + 10)   # tekst obok sprite'a, także przy szerokich statkach
            text(sh["name"], 16, YELLOW, (tx_, 38))
            text("OWNED" if owned else "LOCKED - BUY IN THE HANGAR", 8, LIME if owned else ORANGE,
                 (tx_ + len(sh["name"]) * 16 + 10, 42), shadow=None)
            text(sh["perk"][0], 8, WHITE, (tx_, 60), shadow=None)
            text(sh["perk"][1], 8, GREY, (tx_, 72), shadow=None)
            for j in range(len(SHIPS)):
                pygame.draw.rect(screen, YELLOW if j == S.spec_ship else DARK, (CW - 24 - (len(SHIPS) - j) * 12, 42, 8, 4))
            if (t // 400) % 2 == 0:
                text("<", 16, WHITE, (4, 54))
                text(">", 16, WHITE, (CW - 20, 54))
            rows_n = len(keys)
            rh = 36
            panel((16, 98, CW - 32, rows_n * rh + 6))
            for i, key in enumerate(keys):
                r = SPECIAL_ROWS[key]
                y = 101 + i * rh
                lvl = save["levels"][key]
                total = len(r["costs"])
                maxed = lvl >= total
                sel = i == S.spec_sel
                if sel:
                    pygame.draw.rect(screen, DARK, (20, y, CW - 40, rh - 2))
                    pygame.draw.rect(screen, YELLOW, (20, y, CW - 40, rh - 2), 1)
                text(r["name"], 8, YELLOW if sel else WHITE, (28, y + 4), shadow=None)
                pips(176, y + 4, lvl, total, LIME if maxed else YELLOW, NAVY if sel else DARK)
                if maxed:
                    text("MAX", 8, LIME, (CW - 28, y + 4), right=True, shadow=None)
                else:
                    cost = r["costs"][lvl]
                    text(f"COST {cost}", 8, YELLOW if save["credits"] >= cost else RED, (CW - 28, y + 4),
                         right=True, shadow=None)
                text(special_info(key, lvl), 8, GREY, (28, y + 18), shadow=None)
            if S.notice[2] > 0:
                text(S.notice[0], 8, S.notice[1], (0, 98 + rows_n * rh + 12), center=True)
                S.notice[2] -= DT_SCALE
            text("LEFT/RIGHT SHIP  UP/DOWN SELECT  ENTER BUY", 8, GREY, (0, CH - 14), center=True)

        elif S.state == "upgrades":
            draw_base_backdrop(low=True)
            text("UPGRADES", 24, YELLOW, (0, 4), center=True, shadow=RED)
            text(f"CREDITS: {save['credits']}", 16, CYAN, (0, 30), center=True)
            rows = len(UPGRADES)
            rh = 34
            panel((16, 50, CW - 32, rows * rh + 6))
            for i, u in enumerate(UPGRADES):
                y = 53 + i * rh
                lvl = save["levels"][u["key"]]
                total = len(u["costs"])
                maxed = lvl >= total
                sel = i == S.up_sel
                if sel:
                    pygame.draw.rect(screen, DARK, (20, y, CW - 40, rh - 2))
                    pygame.draw.rect(screen, YELLOW, (20, y, CW - 40, rh - 2), 1)
                text(u["name"], 8, YELLOW if sel else WHITE, (28, y + 5), shadow=None)
                pips(176, y + 5, lvl, total, LIME if maxed else YELLOW, NAVY if sel else DARK)
                if maxed:
                    text("MAX", 8, LIME, (CW - 28, y + 5), right=True, shadow=None)
                else:
                    cost = u["costs"][lvl]
                    text(f"COST {cost}", 8, YELLOW if save["credits"] >= cost else RED, (CW - 28, y + 5),
                         right=True, shadow=None)
                text(upgrade_info(u["key"], lvl, save["owned"]), 8, GREY, (28, y + 19), shadow=None)
            if S.notice[2] > 0:
                text(S.notice[0], 8, S.notice[1], (0, 274), center=True)
                S.notice[2] -= DT_SCALE
            text("UP/DOWN SELECT  ENTER BUY  ESC BACK", 8, GREY, (0, CH - 14), center=True)

        elif S.state == "build":
            draw_base_backdrop(low=True)
            text("BASE", 24, YELLOW, (0, 4), center=True, shadow=RED)
            text(f"CREDITS: {save['credits']}", 16, CYAN, (0, 30), center=True)
            rate = income_rate(save["base"])
            text(f"INCOME {rate}/MIN   VAULT {int(save['vault'])}/{vault_cap(save['base'])}   ORE PRICE x{sale_mult(save['base']):.2f}",
                 8, GREY, (0, 50), center=True)
            rows = build_rows()
            rh, vis = 27, 6
            if S.build_sel < S.build_scroll:
                S.build_scroll = S.build_sel
            elif S.build_sel >= S.build_scroll + vis:
                S.build_scroll = S.build_sel - vis + 1
            S.build_scroll = max(0, min(S.build_scroll, len(rows) - vis))
            panel((16, 62, CW - 32, vis * rh + 6))
            pr = save["project"]
            for vi in range(vis):
                i = S.build_scroll + vi
                if i >= len(rows):
                    break
                key = rows[i]
                y = 65 + vi * rh
                sel = i == S.build_sel
                if sel:
                    pygame.draw.rect(screen, DARK, (20, y, CW - 40, rh - 2))
                    pygame.draw.rect(screen, YELLOW, (20, y, CW - 40, rh - 2), 1)
                if key in ("drones", "drone_tech"):
                    is_d = key == "drones"
                    costs = DRONE_COSTS if is_d else DRONE_TECH_COSTS
                    n = save["drones"] if is_d else save["drone_tech"]
                    name = "MINING DRONES" if is_d else "DRONE TECH"
                    units, secs, mix = DRONE_TECH[save["drone_tech"]]
                    if is_d:
                        info = f"{n} DRONES  {units} ORE / {secs}S EACH TRIP"
                    else:
                        nu, ns, nm = DRONE_TECH[min(n + 1, len(DRONE_TECH) - 1)]
                        newk = [k for k in ORE_KINDS if nm.get(k, 0) > 0 and mix.get(k, 0) == 0]
                        info = f"NOW {units} ORE/{secs}S" + (f"  NEXT {nu}/{ns}S" + (f" +{ORE[newk[0]]['name']}" if newk else "")
                                                             if n < len(costs) else "")
                    maxed = n >= len(costs)
                    right = ("MAX", LIME) if maxed else (f"COST {costs[n]}", YELLOW if save["credits"] >= costs[n] else RED)
                    total = len(costs)
                else:
                    m = module_by_key(key)
                    n = save["base"][key]
                    total = len(m["costs"])
                    name = m["name"]
                    maxed = n >= total
                    active = bool(pr and pr["key"] == key)
                    right = ("MAX", LIME) if maxed else (("ACTIVE", CYAN) if active else ("SELECT", YELLOW))
                    info = module_info(key, n)
                text(name, 8, YELLOW if sel else WHITE, (28, y + 3), shadow=None)
                pips(176, y + 3, n, total, LIME if maxed else YELLOW, NAVY if sel else DARK)
                text(right[0], 8, right[1], (CW - 28, y + 3), right=True, shadow=None)
                text(info, 8, GREY, (28, y + 14), shadow=None)
            if S.build_scroll > 0:
                text("^", 8, WHITE, (CW - 22, 64))
            if S.build_scroll + vis < len(rows):
                text("v", 8, WHITE, (CW - 22, 62 + vis * rh - 6))
            if pr:
                m = module_by_key(pr["key"])
                cost = m["costs"][save["base"][pr["key"]]]
                text(f"PROJECT: {m['name']} LV {save['base'][pr['key']] + 1}", 8, CYAN, (20, 236))
                x = 20
                for k, need in cost.items():
                    have = min(pr["progress"][k], need)
                    screen.fill(ORE[k]["color"], (x, 249, 5, 5))
                    txt = f"{have}/{need}"
                    text(txt, 8, LIME if have >= need else WHITE, (x + 8, 248))
                    x += 8 + 8 * len(txt) + 10
                paid = pr.get("paid", 0)
                text((f"{paid} CR PAID. " if paid else "") + "ORE FROM LANDINGS AND DRONES FILLS IT", 8, GREY, (20, 260))
            else:
                text("NO PROJECT: PRESS ENTER ON A MODULE", 8, GREY, (20, 236))
                text("CREDITS ARE PAID NOW, ORE COMES FROM YOUR TRIPS", 8, GREY, (20, 248))
            if S.notice[2] > 0:
                text(S.notice[0], 8, S.notice[1], (0, 278), center=True)
                S.notice[2] -= DT_SCALE
            text("UP/DOWN SELECT  ENTER BUY/START  ESC BACK", 8, GREY, (0, CH - 14), center=True)

        elif S.state == "settings":
            draw_base_backdrop(low=True)
            text("SETTINGS", 24, YELLOW, (0, 10), center=True, shadow=RED)
            text("DISPLAY FPS CAP", 8, GREY, (0, 46), center=True)
            n = len(RENDER_FPS_OPTIONS)
            cell = min(70, (CW - 40) // n)
            x0 = CW // 2 - cell * n // 2
            for i, opt in enumerate(RENDER_FPS_OPTIONS):
                x = x0 + i * cell
                sel = i == S.fps_sel
                active = opt == render_fps
                col = YELLOW if sel else (LIME if active else DARK)
                pygame.draw.rect(screen, NAVY, (x + 3, 68, cell - 6, 34))
                pygame.draw.rect(screen, col, (x + 3, 68, cell - 6, 34), 2 if sel else 1)
                text(str(opt), 16, LIME if active else (YELLOW if sel else WHITE), (x + cell // 2, 76), mid=True)
            text(f"ACTIVE: {render_fps} FPS", 8, LIME, (0, 112), center=True)
            text("SIMULATION ALWAYS RUNS AT THE SAME SPEED", 8, GREY, (0, 138), center=True)
            text("A HIGHER CAP ONLY MAKES MOTION SMOOTHER", 8, GREY, (0, 150), center=True)
            if S.notice[2] > 0:
                text(S.notice[0], 8, S.notice[1], (0, 178), center=True)
                S.notice[2] -= DT_SCALE
            text("LEFT/RIGHT SELECT  ENTER APPLY", 8, GREY, (0, 258), center=True)
            text("ESC - BACK", 8, GREY, (0, CH - 14), center=True)

        elif S.state == "saves":
            draw_base_backdrop(low=True)
            text("SAVES", 24, YELLOW, (0, 8), center=True, shadow=RED)
            text("EACH SLOT = SEPARATE GAME AND WORLD", 8, GREY, (0, 38), center=True)
            for i in range(SLOTS):
                y = 56 + i * 64
                info = S.slot_info[i] if i < len(S.slot_info) else None
                sel = i == S.slot_sel
                panel((28, y, CW - 56, 58))
                if sel:
                    pygame.draw.rect(screen, YELLOW, (28, y, CW - 56, 58), 1)
                active = i + 1 == S.slot
                text(f"SLOT {i + 1}", 8, YELLOW if sel else WHITE, (38, y + 6), shadow=None)
                if active:
                    text("ACTIVE", 8, LIME, (CW - 38, y + 6), right=True, shadow=None)
                if info is None:
                    text("EMPTY - ENTER STARTS A NEW GAME", 8, GREY, (38, y + 26), shadow=None)
                else:
                    ship_name = next(x["name"] for x in SHIPS if x["id"] == info["ship"])
                    text(f"CREDITS {info['credits']}   SHIP {ship_name}", 8, CYAN, (38, y + 20), shadow=None)
                    base_lv = sum(info["base"].values())
                    upg = sum(info["levels"].values())
                    text(f"BASE LV {base_lv}   DRONES {info['drones']}   UPGRADES {upg}", 8, GREY, (38, y + 32), shadow=None)
                    text(f"SHIPS {len(info['owned'])}/{len(SHIPS)}   WORLD {info['seed'] % 10000:04d}", 8, GREY, (38, y + 44), shadow=None)
            if S.confirm[1] > 0:
                S.confirm = (S.confirm[0], S.confirm[1] - DT_SCALE)
            if S.notice[2] > 0:
                text(S.notice[0], 8, S.notice[1], (0, 250), center=True)
                S.notice[2] -= DT_SCALE
            text("UP/DOWN SELECT  ENTER PLAY/NEW  DEL ERASE", 8, GREY, (0, 266), center=True)
            text("ESC - BACK", 8, GREY, (0, CH - 14), center=True)

        elif S.state == "flight":
            planets = flight_step()
            if S.state == "flight":
                draw_flight(planets)

        elif S.state == "paused":
            if S.pause_bg.get_size() == world.get_size():
                world.blit(S.pause_bg, (0, 0))
            world.blit(veil, (0, 0))
            screen.fill(KEY)
            text("PAUSED", 24, YELLOW, (0, 100), center=True, shadow=RED)
            text("ENTER / ESC - RESUME", 8, WHITE, (0, 150), center=True)
            text("Q - ABANDON RUN (CARGO LOST)", 8, GREY, (0, 166), center=True)
            compose_hud()

        present(world if S.state in ("flight", "paused") else screen)

    persist()
    pygame.quit()
    sys.exit()


if __name__ == "__main__":
    main()
