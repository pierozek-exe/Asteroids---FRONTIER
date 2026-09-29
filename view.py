"""Stan widoku, który zmienia się w trakcie gry (rozmiar płótna, DT_SCALE, kamera) i przeliczanie świat -> ekran.

Inne moduły czytają te wartości jako view.CW / view.VW / view.VH / view.DT_SCALE, żeby zawsze widzieć aktualne.
"""
from config import CH, K, ZOOM


CW = 480                   # szerokość warstwy HUD/menu; dopasowywana do proporcji okna (set_view)
VW, VH = CW * ZOOM, CH * ZOOM   # rozmiar płótna ze światem
DT_SCALE = 1.0              # aktualny_dt * FPS; przy 60 FPS = 1.0 (dokładnie jak dawniej), przy 120 = 0.5 itd.


def set_view(aspect):
    """Dopasowuje szerokość widoku do proporcji okna, żeby nie było czarnych pasów po bokach."""
    global CW, VW, VH
    CW = max(426, min(768, int(round(CH * aspect / 2.0)) * 2))
    VW, VH = CW * ZOOM, CH * ZOOM

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
