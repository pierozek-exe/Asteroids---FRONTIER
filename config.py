"""Stałe silnika, paleta kolorów, ścieżki i surowce (tylko dane, nic się tu nie zmienia w trakcie gry)."""
import math
from pathlib import Path


# --------------------
# Stałe
# --------------------
W, H = 1200, 800           # bazowy rozmiar widoku w jednostkach logiki (dla ZOOM = 1)
CH = 320                   # wysokość warstwy HUD/menu (szerokość CW jest w view.py)
K = 0.4                    # logika -> piksele płótna
ZOOM = 3                   # oddalenie kamery: widać ZOOM razy więcej świata w poziomie i pionie (obsługiwane 1-3; 2 = łagodniej)
KEY = (255, 0, 255)        # kolor przezroczysty warstwy HUD
ICE_C = (115, 239, 247)    # lodowy błękit (efekty)


FPS = 60                   # bazowa "jednostka" czasu gry: wszystkie tabele (sekundy->klatki) liczą względem 60/s.
RENDER_FPS_OPTIONS = (60, 90, 120, 144, 240)   # wybieralny limit odświeżania (ekran SETTINGS)
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
