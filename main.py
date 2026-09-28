"""Asteroids - port gry z C++/SFML (Projekt_Wrzesiem/Wersja_5) na Python + pygame.

Uruchomienie:
    pip install pygame
    python main.py

Sterowanie: A/D obrót, W przyspieszenie, SPACJA strzał (przytrzymaj = ogień ciągły),
ESC powrót do menu, F11 pełny ekran. Okno można dowolnie rozciągać.
"""
import math
import os
import random
import sys
from pathlib import Path

# Windows: bez tego system "rozciąga" okno przy skalowaniu ekranu 125%/150% i robi się rozmyte
if sys.platform == "win32":
    try:
        import ctypes
        ctypes.windll.user32.SetProcessDPIAware()
    except Exception:
        pass
os.environ.setdefault("SDL_VIDEO_CENTERED", "1")

import pygame

# --------------------
# Stałe (Constants.h)
# --------------------
W, H = 1200, 800
FPS = 60
DEGTORAD = 0.017453
MIN_FIRE_RATE = 0.05   # najszybszy możliwy strzał (s)
FIRE_STEP = 0.05       # o ile jedno ulepszenie skraca czas między strzałami

BASE_DIR = Path(__file__).resolve().parent
ASSETS = BASE_DIR / "assets"
SCORE_FILE = BASE_DIR / "scores.txt"

WHITE = (255, 255, 255)
YELLOW = (255, 255, 0)


# --------------------
# Wyniki (readScores / saveScores / updateScores)
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
    s = min(dw * 0.9 / W, dh * 0.85 / H)
    return int(W * s), int(H * s)


def open_window(fullscreen, size):
    if fullscreen:
        return pygame.display.set_mode((0, 0), pygame.FULLSCREEN)
    return pygame.display.set_mode(size, pygame.RESIZABLE)


def present(canvas):
    """Skaluje obraz gry (W x H) do aktualnego okna, zachowując proporcje."""
    win = pygame.display.get_surface()
    ww, wh = win.get_size()
    s = min(ww / W, wh / H)
    tw, th = int(W * s), int(H * s)
    if tw < 1 or th < 1:  # okno zminimalizowane
        pygame.display.flip()
        return
    if (tw, th) != (ww, wh):
        win.fill((0, 0, 0))  # czarne pasy, gdy proporcje okna są inne niż 3:2
    rect = ((ww - tw) // 2, (wh - th) // 2, tw, th)
    try:
        pygame.transform.smoothscale(canvas, (tw, th), win.subsurface(rect))
    except (ValueError, pygame.error):
        win.blit(pygame.transform.smoothscale(canvas, (tw, th)), rect[:2])
    pygame.display.flip()


# --------------------
# Animation
# --------------------
class Animation:
    """Pasek klatek z jednego arkusza. Lista klatek jest współdzielona,
    a licznik klatki (frame) ma każda kopia osobno - tak jak w C++."""

    def __init__(self, sheet, x, y, w, h, count, speed, frames=None):
        self.frame = 0.0
        self.speed = speed
        if frames is None:
            frames = [
                sheet.subsurface(pygame.Rect(x + i * w, y, w, h)).copy()
                for i in range(count)
            ]
        self.frames = frames

    def copy(self):
        return Animation(None, 0, 0, 0, 0, 0, self.speed, frames=self.frames)

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


# --------------------
# Encje (Entity, player, asteroid, bullet)
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

    def draw(self, screen):
        # SFML obraca zgodnie z ruchem wskazówek zegara, pygame przeciwnie
        img = pygame.transform.rotate(self.anim.image, -(self.angle + 90))
        screen.blit(img, img.get_rect(center=(self.x, self.y)))


class Player(Entity):
    def __init__(self):
        super().__init__("player")
        self.thrust = False
        self.speed = 4.0

    def update(self):
        if self.thrust:
            self.dx += math.cos(self.angle * DEGTORAD) * self.speed * 0.05
            self.dy += math.sin(self.angle * DEGTORAD) * self.speed * 0.05
        else:
            self.dx *= 0.99
            self.dy *= 0.99

        max_speed = 15
        v = math.hypot(self.dx, self.dy)
        if v > max_speed:
            self.dx *= max_speed / v
            self.dy *= max_speed / v

        self.x += self.dx
        self.y += self.dy
        wrap(self)


class Asteroid(Entity):
    def __init__(self):
        super().__init__("asteroid")
        self.dx = random.randint(-4, 3)
        self.dy = random.randint(-4, 3)

    def update(self):
        self.x += self.dx
        self.y += self.dy
        wrap(self)


class Bullet(Entity):
    def __init__(self):
        super().__init__("bullet")

    def update(self):
        self.dx = math.cos(self.angle * DEGTORAD) * 6
        self.dy = math.sin(self.angle * DEGTORAD) * 6
        self.x += self.dx
        self.y += self.dy
        if self.x > W or self.x < 0 or self.y > H or self.y < 0:
            self.life = False


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
def main():
    pygame.init()
    pygame.display.set_caption("Asteroids!")
    windowed_size = default_window_size()
    fullscreen = False
    open_window(fullscreen, windowed_size)
    screen = pygame.Surface((W, H)).convert()  # tu rysuje cała gra, present() skaluje to do okna
    clock = pygame.time.Clock()

    # --- Ulepszenia ---
    player_fire_rate = 0.4   # czas między strzałami (mniej = szybciej)
    player_speed = 2.0
    max_player_speed = 6.0
    fire_cooldown = 0.0
    upgrade_points = 0
    double_shot = False

    # --- Wyniki ---
    scores, highscore, last_score, last_destroyed = read_scores(SCORE_FILE)

    # --- Zasoby ---
    def img(name):
        return pygame.image.load(str(ASSETS / name)).convert_alpha()

    background = pygame.image.load(str(ASSETS / "background.jpg")).convert()
    t_ship, t_expl, t_rock = img("spaceship.png"), img("type_C.png"), img("rock.png")
    t_fire, t_rock_small, t_expl_ship = img("fire_red.png"), img("rock_small.png"), img("type_B.png")

    s_explosion = Animation(t_expl, 0, 0, 256, 256, 48, 0.5)
    s_rock = Animation(t_rock, 0, 0, 64, 64, 16, 0.2)
    s_rock_small = Animation(t_rock_small, 0, 0, 64, 64, 16, 0.2)
    s_bullet = Animation(t_fire, 0, 0, 32, 64, 16, 0.8)
    s_player = Animation(t_ship, 40, 0, 40, 40, 1, 0)
    s_player_go = Animation(t_ship, 40, 40, 40, 40, 1, 0)
    s_explosion_ship = Animation(t_expl_ship, 0, 0, 192, 192, 64, 0.5)

    font_path = str(ASSETS / "Orbitron-Regular.ttf")
    fonts = {}

    def font(size, bold=False):
        key = (size, bold)
        if key not in fonts:
            f = pygame.font.Font(font_path, size)
            f.set_bold(bold)
            fonts[key] = f
        return fonts[key]

    def text(msg, size, color, pos, bold=False, center_x=False):
        surf = font(size, bold).render(msg, True, color)
        rect = surf.get_rect(topleft=pos)
        if center_x:
            rect.centerx = W // 2
        screen.blit(surf, rect)

    # --- Stan gry ---
    entities = []
    player = None
    safe_time = 5.0
    start_ticks = 0
    destroyed = 0
    state = "menu"  # menu / game / upgrades / scores
    selected = 0
    menu_items = ["Start Game", "Upgrades", "View Scores", "Exit"]
    menu_pos = [(W / 2 - 75, H / 2.5), (W / 2 - 75, H / 2.1),
                (W / 2 - 75, H / 1.8), (W / 2 - 75, H / 1.5)]

    def elapsed():
        return (pygame.time.get_ticks() - start_ticks) / 1000.0

    def start_game():
        nonlocal player, destroyed, fire_cooldown, start_ticks, state
        entities.clear()
        player = Player()
        player.settings(s_player, W // 2, H // 2, 0, 20)
        player.speed = player_speed
        entities.append(player)
        destroyed = 0
        fire_cooldown = 0.0
        start_ticks = pygame.time.get_ticks()
        state = "game"

    def shoot():
        nonlocal fire_cooldown
        if double_shot:
            offset = 15.0
            rad = player.angle * math.pi / 180.0
            dx = math.cos(rad + math.pi / 2) * offset
            dy = math.sin(rad + math.pi / 2) * offset
            for sign in (1, -1):
                b = Bullet()
                b.settings(s_bullet, player.x + sign * dx, player.y + sign * dy, player.angle, 10)
                entities.append(b)
        else:
            b = Bullet()
            b.settings(s_bullet, player.x, player.y, player.angle, 10)
            entities.append(b)
        fire_cooldown = player_fire_rate

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
                        selected = (selected - 1) % 4
                    elif key == pygame.K_DOWN:
                        selected = (selected + 1) % 4
                    elif key in (pygame.K_RETURN, pygame.K_KP_ENTER):
                        if selected == 0:
                            start_game()
                        elif selected == 1:
                            state = "upgrades"
                        elif selected == 2:
                            state = "scores"
                        else:
                            running = False
                elif state == "game":
                    if key == pygame.K_SPACE and fire_cooldown <= 1e-6:
                        shoot()
                    elif key == pygame.K_ESCAPE:
                        state = "menu"
                elif state == "scores":
                    if key == pygame.K_ESCAPE:
                        state = "menu"
                elif state == "upgrades":
                    if key == pygame.K_q and upgrade_points > 0 and player_fire_rate > MIN_FIRE_RATE + 1e-6:
                        player_fire_rate = max(MIN_FIRE_RATE, round(player_fire_rate - FIRE_STEP, 2))
                        upgrade_points -= 1
                    elif key == pygame.K_e and upgrade_points > 0 and player_speed < max_player_speed:
                        player_speed = min(max_player_speed, player_speed + 0.5)
                        upgrade_points -= 1
                    elif key == pygame.K_r and upgrade_points >= 5 and not double_shot:
                        double_shot = True
                        upgrade_points -= 5
                    elif key == pygame.K_ESCAPE:
                        state = "menu"

        # ---------- logika + rysowanie ----------
        if state == "menu":
            screen.blit(background, (0, 0))
            text("ASTEROIDS", 100, WHITE, (0, H / 6), bold=True, center_x=True)
            for i, label in enumerate(menu_items):
                text(label, 30, YELLOW if i == selected else WHITE, menu_pos[i])

        elif state == "upgrades":
            screen.blit(background, (0, 0))
            text("UPGRADES", 40, YELLOW, (W / 2 - 100, H / 6))
            text(f"Upgrade Points: {upgrade_points}", 28, WHITE, (W / 2 - 120, H / 3.5))
            maxed = " (MAX)" if player_fire_rate <= MIN_FIRE_RATE + 1e-6 else ""
            text(f"Fire Rate (Q): {player_fire_rate:.2f}s{maxed}", 24, WHITE, (W / 2 - 120, H / 2.5))
            text(f"Speed (E): {player_speed:.1f}", 24, WHITE, (W / 2 - 120, H / 2.1))
            text(f"Double Shot (R): {'ON' if double_shot else 'OFF'} (koszt: 5)", 24, WHITE,
                 (W / 2 - 120, H / 1.8))
            text("Q - Fire Rate | E - Speed | R - Double Shot | ESC - Powrót", 20, WHITE,
                 (W / 2 - 220, H - 80))

        elif state == "scores":
            screen.blit(background, (0, 0))
            text(f"Highscore: {highscore}", 30, WHITE, (W / 2 - 75, H / 4))
            text(f"Previous score: {last_score}", 24, WHITE, (W / 2 - 75, H / 3.2))
            text(f"Last destroyed: {last_destroyed}", 24, WHITE, (W / 2 - 75, H / 2.8))
            y = H / 2.3
            for i, s in enumerate(scores, 1):
                text(f"{i}. {s}", 24, WHITE, (W / 2 - 75, y))
                y += font(24).get_linesize()
            text("Press Escape to Return", 20, WHITE, (W / 2 - 75, H - 40))

        elif state == "game":
            if fire_cooldown > 0.0:
                fire_cooldown -= 1.0 / FPS

            keys = pygame.key.get_pressed()
            if keys[pygame.K_d]:
                player.angle += 3
            if keys[pygame.K_a]:
                player.angle -= 3
            player.thrust = bool(keys[pygame.K_w])
            if keys[pygame.K_SPACE] and fire_cooldown <= 1e-6:  # przytrzymana spacja = ogień ciągły
                shoot()

            # asteroidy po czasie ochronnym
            if elapsed() > safe_time and random.randrange(150) == 0:
                a = Asteroid()
                a.settings(s_rock, 0, random.randrange(H), random.randrange(360), 25)
                entities.append(a)

            # kolizje
            new_entities = []
            game_over = False
            for a in entities:
                if a.name == "asteroid" and a.life:
                    for b in entities:
                        if b.name == "bullet" and b.life and is_collide(a, b):
                            a.life = False
                            b.life = False
                            destroyed += 1
                            ex = Entity("explosion")
                            ex.settings(s_explosion, a.x, a.y)
                            new_entities.append(ex)
                            if a.R != 15:  # duża asteroida rozpada się na dwie małe
                                for _ in range(2):
                                    small = Asteroid()
                                    small.settings(s_rock_small, a.x, a.y, random.randrange(360), 15)
                                    new_entities.append(small)
                            break
                    if a.life and is_collide(player, a):
                        a.life = False
                        game_over = True
                        break
            entities.extend(new_entities)

            if game_over:
                score = int(elapsed()) * 100 + destroyed * 50
                highscore = update_scores(scores, score, highscore)
                save_scores(SCORE_FILE, highscore, scores, score, destroyed)
                last_score, last_destroyed = score, destroyed
                upgrade_points += score // 2000  # 1 punkt za każde 2000
                state = "menu"
            else:
                # animacja statku: z ogniem / bez ognia
                player.anim = s_player_go if player.thrust else s_player

                for e in entities:
                    if e.name == "explosion" and e.anim.is_end():
                        e.life = False

                for e in entities:
                    e.update()
                    e.anim.update()
                entities[:] = [e for e in entities if e.life]

                screen.blit(background, (0, 0))
                for e in entities:
                    e.draw(screen)

                t = int(elapsed())
                text(f"Highscore: {highscore}", 24, WHITE, (10, 40))
                text(f"Time: {t // 60}:{t % 60:02d}", 24, WHITE, (10, 70))
                text(f"Score: {t * 100 + destroyed * 50}", 24, WHITE, (10, 100))
                text(f"Asteroids destroyed: {destroyed}", 24, WHITE, (10, 130))
                text("Press ESC to quit", 20, WHITE, (W - 200, H - 30))

        present(screen)
        clock.tick(FPS)

    pygame.quit()
    sys.exit()


if __name__ == "__main__":
    main()
