"""Dungeon Warden - pygame front end.

Main menu -> game screen (map + reasoning panel) with pause, help and game-over overlays.

  Menu    Up/Down choose a setting, Left/Right change it, Enter start, H help, Esc quit
  Game    WASD / arrows move, Space wait, B belief overlay, V reveal sensors, H help,
          Tab human/bot, P pause bot, +/- bot speed, R restart, Esc pause menu
"""
from __future__ import annotations

import argparse
import csv
import math
import sys
from datetime import datetime
from pathlib import Path

import pygame

from bots import BOTS
from engine import Match
from kb import RULES as FOL_RULES
from settings import DIFFICULTIES, SIZES, game_settings, load_balance, map_key, map_paths
from warden import WARDENS
from world import RULESETS, DungeonMap, action_str, sight_cells

W, H = 1280, 800
TOP = 60                    # top bar height
MARGIN = 24
BOARD = H - TOP - MARGIN - 40   # square area for the map (40 px legend below)
PANEL_X = MARGIN * 2 + BOARD
PANEL_W = W - PANEL_X - MARGIN
LOG_FILE = Path(__file__).parent / "logs" / "games.csv"   # proposal 2.1 output: CSV log of metrics
MOVE_MS = 110               # player slide time per cell
WALL_MS = 320               # wall rise animation

COL = {
    "bg": (14, 12, 19), "bar": (22, 19, 29), "panel": (24, 21, 31), "card": (32, 28, 41),
    "line": (52, 47, 66), "line_hi": (78, 70, 98),
    "floor": (92, 84, 100), "floor_dark": (83, 76, 91), "crack": (70, 64, 78),
    "wall": (34, 30, 43), "wall_top": (62, 57, 76), "wall_shadow": (20, 17, 26), "placed": (156, 66, 52), "placed_top": (198, 98, 74),
    "door": (139, 96, 52), "door_hi": (178, 128, 74), "locked": (232, 72, 72),
    "treasure": (246, 204, 64), "treasure_hi": (255, 240, 170), "player": (84, 170, 255),
    "player_hi": (200, 230, 255), "belief": (255, 64, 96), "assumed": (255, 206, 60),
    "sight": (110, 190, 255), "plate": (190, 180, 110), "eye": (176, 126, 255),
    "text": (230, 228, 240), "dim": (146, 141, 165), "faint": (98, 94, 116), "accent": (255, 186, 90),
    "good": (120, 222, 140), "bad": (255, 108, 108),
}

KEYMOVES = {
    pygame.K_w: "up", pygame.K_UP: "up", pygame.K_s: "down", pygame.K_DOWN: "down",
    pygame.K_a: "left", pygame.K_LEFT: "left", pygame.K_d: "right", pygame.K_RIGHT: "right",
    pygame.K_SPACE: "wait",
}
CONTROLLERS = {"human": "You (WASD)", "rusher": "Rusher bot", "cautious": "Cautious bot"}
WARDEN_INFO = {
    "W0": "Places a random valid block each turn (baseline).",
    "W1": "Predicts your route with A* and blocks it greedily, no lookahead (baseline).",
    "W2": "Belief set + A* + planning + Minimax with alpha-beta: the full AI.",
    "W3": "Like W2 but it can see you. An upper bound, not fair play.",
}
RULE_INFO = {
    "proposal": "Proposal rules: the Warden wins after T turns; locks stay until unlocked.",
    "variant": "Variant: no turn limit, doors reopen, walls have a cooldown. Score = turns used.",
}


def font(size: int, bold: bool = False, mono: bool = True) -> pygame.font.Font:
    names = "menlo,dejavusansmono,consolas,couriernew" if mono else "avenirnext,futura,helveticaneue,arial"
    return pygame.font.SysFont(names, size, bold=bold)


def wrap(text: str, f: pygame.font.Font, width: int) -> list[str]:
    lines, cur = [], ""
    for word in text.split(" "):
        trial = f"{cur} {word}".strip()
        if f.size(trial)[0] <= width or not cur:
            cur = trial
        else:
            lines.append(cur)
            cur = word
    return lines + [cur] if cur else lines


def blit_text(surf, f, text, color, pos, anchor="topleft") -> pygame.Rect:
    t = f.render(text, True, COL[color] if isinstance(color, str) else color)
    r = t.get_rect(**{anchor: pos})
    surf.blit(t, r)
    return r


def log_game(row: dict):
    """Append one finished game to logs/games.csv. A failed write must never crash the game."""
    try:
        LOG_FILE.parent.mkdir(exist_ok=True)
        new = not LOG_FILE.exists()
        with LOG_FILE.open("a", newline="") as f:
            w = csv.DictWriter(f, fieldnames=list(row))
            if new:
                w.writeheader()
            w.writerow(row)
    except OSError as e:
        print(f"could not write {LOG_FILE}: {e}", file=sys.stderr)


def ease_out(k: float) -> float:
    return 1 - (1 - min(1.0, max(0.0, k))) ** 3


class Button:
    def __init__(self, label: str, action: str, rect: pygame.Rect, primary=False):
        self.label, self.action, self.rect, self.primary = label, action, rect, primary

    def draw(self, surf, f, mouse):
        hover = self.rect.collidepoint(mouse)
        base = COL["accent"] if self.primary else COL["card"]
        fill = tuple(min(255, c + 22) for c in base) if hover else base
        pygame.draw.rect(surf, fill, self.rect, border_radius=10)
        pygame.draw.rect(surf, COL["treasure_hi"] if self.primary else COL["line_hi"], self.rect, 2, border_radius=10)
        blit_text(surf, f, self.label, COL["bg"] if self.primary else COL["text"], self.rect.center, "center")


# =============================================================== menu

class Menu:
    """Settings screen. Every row cycles through its values with Left/Right or a click."""

    def __init__(self, app):
        self.app = app
        self.sel = 0
        self.buttons = [Button("Start game", "start", pygame.Rect(0, 0, 240, 54), primary=True),
                        Button("How to play", "help", pygame.Rect(0, 0, 190, 54)),
                        Button("Quit", "quit", pygame.Rect(0, 0, 130, 54))]
        self.rows: list[pygame.Rect] = []

    @property
    def options(self):
        maps = [p.stem for p in map_paths(self.app.cfg["size"])]
        return [
            ("Map size", "size", list(SIZES), lambda v: v),
            ("Map", "map", maps, lambda v: v.title()),
            ("Difficulty", "difficulty", list(DIFFICULTIES), lambda v: DIFFICULTIES[v].label),
            ("Warden AI", "warden", sorted(WARDENS), lambda v: f"{v}  {WARDENS[v].label}"),
            ("Rules", "rules", list(RULESETS), lambda v: v.title()),
            ("Player", "ctrl", list(CONTROLLERS), lambda v: CONTROLLERS[v]),
        ]

    def change(self, i: int, step: int):
        _, key, values, _ = self.options[i]
        cfg = self.app.cfg
        cur = values.index(cfg[key]) if cfg[key] in values else 0
        cfg[key] = values[(cur + step) % len(values)]
        if key == "size":           # keep the map valid for the new size
            cfg["map"] = map_paths(cfg["size"])[0].stem

    def key(self, k):
        n = len(self.options)
        if k in (pygame.K_UP, pygame.K_w):
            self.sel = (self.sel - 1) % n
        elif k in (pygame.K_DOWN, pygame.K_s):
            self.sel = (self.sel + 1) % n
        elif k in (pygame.K_LEFT, pygame.K_a):
            self.change(self.sel, -1)
        elif k in (pygame.K_RIGHT, pygame.K_d):
            self.change(self.sel, 1)
        elif k in (pygame.K_RETURN, pygame.K_KP_ENTER, pygame.K_SPACE):
            self.app.start_game()
        elif k == pygame.K_h:
            self.app.overlay = "help"
        elif k == pygame.K_ESCAPE:
            self.app.quit()

    def click(self, pos):
        for b in self.buttons:
            if b.rect.collidepoint(pos):
                return self.app.do(b.action)
        for i, r in enumerate(self.rows):
            if r.collidepoint(pos):
                self.sel = i
                self.change(i, -1 if pos[0] < r.centerx + 60 else 1)

    def describe(self) -> str:
        cfg, app = self.app.cfg, self.app
        key = self.options[self.sel][1]
        if key == "difficulty":
            if not RULESETS[cfg["rules"]].turn_limit:
                e, c = DIFFICULTIES[cfg["difficulty"]].variant_energy
                return f"Variant rules have no turn limit: the Warden starts with {e} energy (cap {c})."
            s = app.preview_settings()
            win = load_balance().get(map_key(app.map_path()), {}).get(f"{cfg['difficulty']}_win")
            extra = f" In calibration the bots beat W2 in ~{win}% of games." if win is not None else ""
            return f"You get T = {s['T']} turns to reach the treasure.{extra}"
        if key == "warden":
            return WARDEN_INFO[cfg["warden"]]
        if key == "rules":
            return RULE_INFO[cfg["rules"]] + "  " + RULESETS[cfg["rules"]].describe()
        if key in ("map", "size"):
            m = app.preview_map()
            return f"{m.w}x{m.h}, shortest path {app.preview_shortest()} steps, {len(m.doors)} doors."
        if cfg["ctrl"] != "human":
            return "The bot plays by itself; press Tab in game to take over."
        return "Move with WASD or the arrow keys, Space to wait."

    def draw(self, surf, t):
        surf.fill(COL["bg"])
        glow = 0.5 + 0.5 * math.sin(t / 380) * math.sin(t / 970 + 1)     # torch flicker
        hero = self.app.f_hero
        g = hero.render("DUNGEON WARDEN", True, COL["accent"])
        for r, a in ((10, 30), (5, 55)):
            g.set_alpha(int(a * (0.6 + 0.4 * glow)))
            for dx, dy in ((-r, 0), (r, 0), (0, -r), (0, r)):
                surf.blit(g, g.get_rect(midtop=(W // 2 + dx, 44 + dy)))
        blit_text(surf, hero, "DUNGEON WARDEN", "accent", (W // 2, 44), "midtop")
        blit_text(surf, self.app.f, "Reach the treasure. The Warden can't see you - it reasons about where you might be.",
                  "dim", (W // 2, 126), "midtop")

        x0, y0, row_h, label_w, val_w = 110, 190, 58, 200, 380
        self.rows = []
        for i, (label, key, values, show) in enumerate(self.options):
            r = pygame.Rect(x0, y0 + i * row_h, label_w + val_w + 80, row_h - 10)
            self.rows.append(r)
            active = i == self.sel
            pygame.draw.rect(surf, COL["card"] if active else COL["bar"], r, border_radius=10)
            if active:
                pygame.draw.rect(surf, COL["accent"], r, 2, border_radius=10)
            blit_text(surf, self.app.f_b, label, "accent" if active else "dim", (r.x + 20, r.centery), "midleft")
            vx = r.x + label_w
            blit_text(surf, self.app.f_b, "<", "text" if active else "faint", (vx + 10, r.centery), "midleft")
            blit_text(surf, self.app.f_b, show(self.app.cfg[key]), "text", (vx + 40 + val_w // 2, r.centery), "center")
            blit_text(surf, self.app.f_b, ">", "text" if active else "faint", (vx + val_w + 70, r.centery), "midright")

        dy = y0 + len(self.options) * row_h + 4
        for i, line in enumerate(wrap(self.describe(), self.app.f, label_w + val_w + 70)[:3]):
            blit_text(surf, self.app.f, line, "text", (x0 + 4, dy + i * 22))

        self.draw_preview(surf, pygame.Rect(850, 190, 310, 310))

        bx = x0
        for b in self.buttons:
            b.rect.topleft = (bx, 650)
            bx += b.rect.w + 20
            b.draw(surf, self.app.f_b, pygame.mouse.get_pos())
        blit_text(surf, self.app.f_s, "Up/Down choose  -  Left/Right or click to change  -  Enter start  -  H help  -  Esc quit",
                  "faint", (W // 2, H - 26), "midbottom")

    def draw_preview(self, surf, box):
        m = self.app.preview_map()
        cell = box.w // max(m.w, m.h)
        ox = box.x + (box.w - cell * m.w) // 2
        oy = box.y + (box.h - cell * m.h) // 2
        pygame.draw.rect(surf, COL["bar"], box.inflate(28, 28), border_radius=14)
        for (x, y) in m.cells:
            c = (x, y)
            color = COL["wall"] if c in m.walls else COL["door"] if c in m.doors else COL["floor"]
            pygame.draw.rect(surf, color, (ox + x * cell, oy + y * cell, cell, cell))
        for c, color in ((m.start, "player"), (m.treasure, "treasure")):
            pygame.draw.circle(surf, COL[color], (ox + c[0] * cell + cell // 2, oy + c[1] * cell + cell // 2), max(3, cell // 2))
        blit_text(surf, self.app.f_b, m.name.title(), "text", (box.centerx, box.bottom + 26), "midtop")
        blit_text(surf, self.app.f_s, "blue = start   gold = treasure   brown = door", "faint",
                  (box.centerx, box.bottom + 50), "midtop")


# =============================================================== game screen

class GameScreen:
    def __init__(self, app):
        self.app = app
        cfg = app.cfg
        self.path = app.map_path()
        self.dmap = DungeonMap.load(self.path)
        self.rules = RULESETS[cfg["rules"]]
        self.settings = game_settings(self.path, Match(self.dmap).original_len, cfg["difficulty"], self.rules)
        if app.args.T and self.rules.turn_limit:
            self.settings["T"] = app.args.T
        for key in ("energy", "cap"):
            if getattr(app.args, key) is not None:
                self.settings[key] = getattr(app.args, key)
        self.match = Match(self.dmap, cfg["warden"], seed=app.seed, rules=self.rules, **self.settings)
        app.seed += 1
        self.bot = BOTS[cfg["ctrl"]](app.seed) if cfg["ctrl"] != "human" else None
        self.show_belief, self.reveal, self.paused_bot = True, False, False
        self.cell = max(16, min(64, BOARD // max(self.dmap.w, self.dmap.h)))
        gw, gh = self.cell * self.dmap.w, self.cell * self.dmap.h
        self.grid = pygame.Rect(MARGIN + (BOARD - gw) // 2, TOP + 12 + (BOARD - gh) // 2, gw, gh)
        self.base = self.bake()
        self.light = self.bake_light()
        self.player_px = pygame.Vector2(self.center(self.match.player))
        self.move_from, self.move_at = self.player_px.copy(), -MOVE_MS
        self.anims: dict = {}           # cell -> (kind, start ms)
        self.route: list = []
        self.log: list[tuple[str, str]] = [("dim", f"{self.dmap.name.title()}: reach the gold before the Warden stops you.")]
        self.last_bot = 0
        self.was_seen = False
        self.message = ("", 0)
        self.over_buttons = [Button("Play again", "restart", pygame.Rect(0, 0, 170, 46), primary=True),
                             Button("Next map", "next", pygame.Rect(0, 0, 150, 46)),
                             Button("Menu", "menu", pygame.Rect(0, 0, 110, 46))]

    # ---- geometry and baking

    def rect(self, c, inset=0) -> pygame.Rect:
        s = self.cell
        return pygame.Rect(self.grid.x + c[0] * s + inset, self.grid.y + c[1] * s + inset, s - 2 * inset, s - 2 * inset)

    def center(self, c):
        return self.rect(c).center

    def bake(self) -> pygame.Surface:
        """Static floor and map walls with shading, drawn once per game."""
        m, s = self.dmap, self.cell
        surf = pygame.Surface(self.grid.size)
        for (x, y) in m.cells:
            r = pygame.Rect(x * s, y * s, s, s)
            noise = ((x * 73856093) ^ (y * 19349663)) % 13 - 6     # stable per-tile variation
            if (x, y) in m.walls:
                pygame.draw.rect(surf, tuple(max(0, c + noise) for c in COL["wall"]), r)
                pygame.draw.rect(surf, COL["wall_top"], (r.x, r.y, r.w, max(3, s // 7)))
                pygame.draw.line(surf, COL["wall_shadow"], (r.x, r.bottom - 1), (r.right, r.bottom - 1), 2)
            else:
                base = COL["floor"] if (x + y) % 2 else COL["floor_dark"]
                pygame.draw.rect(surf, tuple(max(0, c + noise) for c in base), r)
                if s >= 24 and noise > 3:      # a few cracks
                    pygame.draw.line(surf, COL["crack"], (r.x + s // 4, r.y + s // 3), (r.x + s // 2, r.y + s // 2), 1)
                if (x, y - 1) in m.walls:      # the wall above casts a shadow
                    shade = pygame.Surface((s, max(4, s // 5)), pygame.SRCALPHA)
                    shade.fill((0, 0, 0, 60))
                    surf.blit(shade, r.topleft)
        return surf

    def bake_light(self) -> pygame.Surface:
        """Torch light: a dark vignette with a soft hole, centred on the player each frame."""
        gw, gh = self.grid.size
        size = (gw * 2, gh * 2)
        surf = pygame.Surface(size, pygame.SRCALPHA)
        surf.fill((0, 0, 0, 110))
        radius = max(gw, gh) * 0.6
        for i in range(40, 0, -1):
            k = i / 40
            pygame.draw.circle(surf, (0, 0, 0, int(110 * k ** 1.6)), (size[0] // 2, size[1] // 2), int(radius * k))
        return surf

    # ---- playing

    def play(self, move: str):
        m = self.match
        before_walls, before_locked, prev = m.state.walls, m.state.locked, m.player
        if not m.step(move):
            if not m.winner:
                why = ("Proposal rules: you must move one cell every turn." if move == "wait"
                       else "Blocked - you can't walk there.")
                self.message = (why, pygame.time.get_ticks())
            return
        now = pygame.time.get_ticks()
        if m.player != prev:
            self.move_from, self.move_at = self.player_px.copy(), now
        turn = m.state.turn
        for c in sorted(m.state.walls - before_walls):
            self.anims[c] = ("wall", now)
            self.log.append(("bad", f"T{turn}: a wall rises at {c}"))
        for c in sorted(m.state.locked - before_locked):
            self.anims[c] = ("lock", now)
            self.log.append(("bad", f"T{turn}: the Warden locks the door at {c}"))
        for c in sorted(before_locked - m.state.locked):
            self.log.append(("good", f"T{turn}: the door at {c} opens"))
        seen = bool(m.percept and m.percept.seen)
        if seen and not self.was_seen and not m.winner:     # log only when you come into view
            self.log.append(("accent", f"T{turn}: an eye spotted you!"))
        self.was_seen = seen
        d = m.decision
        self.route = (m.warden.routes.path(d.assumed, m.state) or []) if d and d.assumed and not m.winner else []
        if m.winner:
            self.log.append(("good", "You reached the treasure!") if m.winner == "player"
                            else ("bad", "Time is up - the Warden wins."))
            log_game({"time": datetime.now().isoformat(timespec="seconds"), "player": self.app.cfg["ctrl"],
                      "difficulty": self.app.cfg["difficulty"], **m.summary()})
        self.log = self.log[-6:]

    def key(self, k):
        app = self.app
        if k == pygame.K_ESCAPE:
            app.overlay = "pause"
        elif k in KEYMOVES and self.bot is None and not self.match.winner:
            self.play(KEYMOVES[k])
        elif k == pygame.K_r:
            app.do("restart")
        elif k == pygame.K_n and self.match.winner:
            app.do("next")
        elif k == pygame.K_m and self.match.winner:
            app.do("menu")
        elif k == pygame.K_TAB:
            keys = list(CONTROLLERS)
            app.cfg["ctrl"] = keys[(keys.index(app.cfg["ctrl"]) + 1) % len(keys)]
            self.bot = BOTS[app.cfg["ctrl"]](app.seed) if app.cfg["ctrl"] != "human" else None
        elif k == pygame.K_b:
            self.show_belief = not self.show_belief
        elif k == pygame.K_v:
            self.reveal = not self.reveal
        elif k == pygame.K_h:
            app.overlay = "help"
        elif k == pygame.K_p:
            self.paused_bot = not self.paused_bot
        elif k in (pygame.K_PLUS, pygame.K_EQUALS, pygame.K_KP_PLUS):
            app.delay = max(40, int(app.delay * 0.7))
        elif k in (pygame.K_MINUS, pygame.K_KP_MINUS):
            app.delay = min(2000, int(app.delay / 0.7))

    def click(self, pos):
        if self.match.winner:
            for b in self.over_buttons:
                if b.rect.collidepoint(pos):
                    self.app.do(b.action)

    def update(self, now):
        if (self.bot and not self.match.winner and not self.paused_bot
                and now - self.last_bot >= self.app.delay):
            self.play(self.bot.move(self.match))
            self.last_bot = now
        k = ease_out((now - self.move_at) / MOVE_MS)
        self.player_px = self.move_from.lerp(pygame.Vector2(self.center(self.match.player)), k)

    # ---- drawing

    def draw(self, surf, now):
        surf.fill(COL["bg"])
        self.draw_top(surf)
        self.draw_board(surf, now)
        self.draw_panel(surf)
        self.draw_legend(surf, now)
        if self.match.winner and self.app.overlay is None:
            self.draw_game_over(surf)

    def draw_top(self, surf):
        app, cfg = self.app, self.app.cfg
        pygame.draw.rect(surf, COL["bar"], (0, 0, W, TOP))
        pygame.draw.line(surf, COL["line"], (0, TOP), (W, TOP), 2)
        blit_text(surf, app.f_title, "DUNGEON WARDEN", "accent", (MARGIN, TOP // 2), "midleft")
        x = MARGIN + 240
        diff_color = {"easy": "good", "normal": "accent", "hard": "bad"}[cfg["difficulty"]]
        for text, color in ((f"{self.dmap.name.title()} {self.dmap.w}x{self.dmap.h}", "text"),
                            (DIFFICULTIES[cfg["difficulty"]].label, diff_color),
                            (f"{self.rules.name.title()} rules", "dim"),
                            (f"{cfg['warden']} {WARDENS[cfg['warden']].label}", "dim")):
            t = app.f_s.render(text, True, COL[color])
            chip = pygame.Rect(x, TOP // 2 - 13, t.get_width() + 22, 26)
            pygame.draw.rect(surf, COL["card"], chip, border_radius=13)
            pygame.draw.rect(surf, COL["line_hi"], chip, 1, border_radius=13)
            surf.blit(t, t.get_rect(center=chip.center))
            x = chip.right + 8
        who = CONTROLLERS[cfg["ctrl"]]
        if self.bot:
            who += "  [paused]" if self.paused_bot else f"  {1000 / app.delay:.1f} moves/s"
        blit_text(surf, app.f_s, who + "    Esc menu   H help", "dim", (W - MARGIN, TOP // 2), "midright")

    def draw_board(self, surf, now):
        m, st, dm, s = self.match, self.match.state, self.dmap, self.cell
        pygame.draw.rect(surf, COL["line"], self.grid.inflate(10, 10), 5, border_radius=6)
        surf.blit(self.base, self.grid.topleft)

        if self.reveal:
            for c in sight_cells(dm, st.walls):
                self.tint(surf, c, COL["sight"], 38)
            for c in dm.plates:
                pygame.draw.rect(surf, COL["plate"], self.rect(c, s // 4), 2, border_radius=3)
            for c in dm.eyes:
                er = self.rect(c, s // 5)
                pygame.draw.ellipse(surf, COL["eye"], er.inflate(0, -er.h // 3), 2)
                pygame.draw.circle(surf, COL["eye"], er.center, max(2, s // 10))

        for c in dm.doors:
            self.draw_door(surf, c, st.lock_left(c), now)
        for c in st.walls - dm.walls:
            self.draw_placed_wall(surf, c, now)
        self.draw_treasure(surf, now)

        if self.show_belief and not m.winner:
            pulse = 52 + int(26 * (0.5 + 0.5 * math.sin(now / 260)))
            for c in m.kb.belief:
                self.tint(surf, c, COL["belief"], pulse)
            if len(self.route) > 1:
                pts = [self.center(c) for c in self.route]
                pygame.draw.lines(surf, COL["assumed"], False, pts, 2)
            d = m.decision
            if d and d.assumed:
                pygame.draw.rect(surf, COL["assumed"], self.rect(d.assumed, 2), 2, border_radius=5)

        px, py = int(self.player_px.x), int(self.player_px.y)
        glow = pygame.Surface((s * 2, s * 2), pygame.SRCALPHA)
        pygame.draw.circle(glow, (*COL["player"], 60), (s, s), int(s * 0.75))
        surf.blit(glow, (px - s, py - s))
        pygame.draw.circle(surf, COL["player"], (px, py), max(5, s // 3))
        pygame.draw.circle(surf, COL["player_hi"], (px, py), max(5, s // 3), 2)

        lw, lh = self.light.get_size()      # torch-light vignette, clipped to the board
        clip = surf.get_clip()
        surf.set_clip(self.grid)
        surf.blit(self.light, (px - lw // 2, py - lh // 2))
        surf.set_clip(clip)

    def tint(self, surf, c, color, alpha):
        t = pygame.Surface((self.cell, self.cell), pygame.SRCALPHA)
        t.fill((*color, alpha))
        surf.blit(t, self.rect(c).topleft)

    def draw_door(self, surf, c, lock_left, now):
        s = self.cell
        r = self.rect(c, max(2, s // 7))
        pygame.draw.rect(surf, COL["door"], r, border_radius=3)
        for i in (1, 2):
            x = r.x + r.w * i // 3
            pygame.draw.line(surf, COL["door_hi"], (x, r.y + 2), (x, r.bottom - 3), 1)
        if not lock_left:
            return
        anim = self.anims.get(c)
        k = ease_out((now - anim[1]) / 300) if anim and anim[0] == "lock" else 1
        pygame.draw.rect(surf, COL["locked"], r, 3, border_radius=3)
        body = pygame.Rect(0, 0, max(4, int(s / 3 * (0.6 + 0.4 * k))), max(3, int(s / 4 * (0.6 + 0.4 * k))))
        body.center = (r.centerx, r.centery + s // 12)
        pygame.draw.arc(surf, COL["locked"], body.move(0, -body.h // 2 - 2).inflate(-body.w // 4, 0), 0, 3.15, max(1, s // 20))
        pygame.draw.rect(surf, COL["locked"], body, border_radius=2)
        if lock_left != math.inf and s >= 24:
            blit_text(surf, self.app.f_s, str(int(lock_left)), "text", (r.right - 2, r.bottom), "bottomright")

    def draw_placed_wall(self, surf, c, now):
        s = self.cell
        r = self.rect(c)
        anim = self.anims.get(c)
        k = ease_out((now - anim[1]) / WALL_MS) if anim and anim[0] == "wall" else 1
        h = max(1, int(s * k))
        wr = pygame.Rect(r.x, r.bottom - h, s, h)
        pygame.draw.rect(surf, COL["placed"], wr)
        pygame.draw.rect(surf, COL["placed_top"], (wr.x, wr.y, wr.w, max(3, s // 7)))
        if k >= 1:      # brick seams
            pygame.draw.line(surf, COL["wall_shadow"], (r.x, r.centery), (r.right, r.centery), 2)
            pygame.draw.line(surf, COL["wall_shadow"], (r.centerx, r.y + s // 7), (r.centerx, r.centery), 2)
            pygame.draw.line(surf, COL["wall_shadow"], (r.x + s // 4, r.centery), (r.x + s // 4, r.bottom), 2)
        else:           # dust ring while it rises
            pygame.draw.circle(surf, COL["accent"], r.center, int(s * (0.4 + 0.5 * k)), 2)

    def draw_treasure(self, surf, now):
        s = self.cell
        r = self.rect(self.dmap.treasure, s // 6).move(0, int(math.sin(now / 300) * s * 0.06))
        halo = pygame.Surface((s * 2, s * 2), pygame.SRCALPHA)
        pygame.draw.circle(halo, (*COL["treasure"], 46 + int(20 * math.sin(now / 420))), (s, s), int(s * 0.8))
        surf.blit(halo, (r.centerx - s, r.centery - s))
        pts = [(r.centerx, r.y), (r.right, r.centery), (r.centerx, r.bottom), (r.x, r.centery)]
        pygame.draw.polygon(surf, COL["treasure"], pts)
        pygame.draw.polygon(surf, COL["treasure_hi"], pts, 2)

    def draw_legend(self, surf, now):
        y = self.grid.bottom + 16
        text, at = self.message
        if text and now - at < 1500:
            blit_text(surf, self.app.f, text, "bad", (self.grid.x, y))
            return
        items = [("player", "you"), ("treasure", "treasure"), ("placed", "Warden wall"), ("locked", "locked door")]
        if self.show_belief:
            items += [("belief", "belief B_t"), ("assumed", "assumed cell + route")]
        x = self.grid.x
        for key, label in items:
            if x + 18 + self.app.f_s.size(label)[0] > PANEL_X - 16:
                break
            pygame.draw.rect(surf, COL[key], (x, y + 3, 12, 12), border_radius=3)
            x = blit_text(surf, self.app.f_s, label, "dim", (x + 18, y + 1)).right + 16

    # ---- reasoning panel

    def draw_panel(self, surf):
        app, m, st = self.app, self.match, self.match.state
        x0, w = PANEL_X, PANEL_W
        y = TOP + 14

        def text(s, color="text", f=None, indent=0):
            nonlocal y
            f = f or app.f_s
            for line in wrap(s, f, w - indent):
                blit_text(surf, f, line, color, (x0 + indent, y))
                y += f.get_linesize()

        def heading(title):
            nonlocal y
            blit_text(surf, app.f_b, title, "accent", (x0, y))
            y += 24

        def bar(label, value, maximum, color, right=""):
            nonlocal y
            blit_text(surf, app.f_s, label, "text", (x0, y))
            bx, bw = x0 + 120, w - 120 - 60
            pygame.draw.rect(surf, COL["card"], (bx, y + 3, bw, 11), border_radius=6)
            if maximum:
                pygame.draw.rect(surf, COL[color], (bx, y + 3, int(bw * min(1, value / maximum)), 11), border_radius=6)
            blit_text(surf, app.f_s, right, "dim", (x0 + w, y), "topright")
            y += 20

        def divider():
            nonlocal y
            y += 6
            pygame.draw.line(surf, COL["line"], (x0, y), (x0 + w, y), 1)
            y += 8

        heading("STATUS")
        if m.T:
            bar("Turn", st.turn, m.T, "bad" if m.T - st.turn <= 5 else "sight", f"{st.turn}/{m.T}")
        else:
            text(f"Turn {st.turn}   (no turn limit - fewer turns is better)")
            y += 2
        bar("Warden energy", st.energy, m.cap, "accent", f"{st.energy}/{m.cap}")
        if self.rules.wall_cooldown:
            bar("Wall cooldown", self.rules.wall_cooldown - st.cooldown, self.rules.wall_cooldown,
                "bad" if st.cooldown else "good", f"{st.cooldown}" if st.cooldown else "ready")
        text(self.rules.describe(), "faint")

        divider()
        heading("PERCEPTS")
        p = m.percept
        if p is None:
            text("Waiting for your first move...", "dim")
        else:
            text(f"Plate: {'Stepped' + str(p.stepped) if p.stepped else 'nothing pressed'} · "
                 f"Door: {'noise at ' + str(p.noise) if p.noise else 'quiet'}")
            text(f"Eyes: {'PLAYER SEEN at ' + str(p.seen) if p.seen else 'player not in sight'}",
                 "bad" if p.seen else "text")

        divider()
        heading(f"KNOWLEDGE BASE   |B_t| = {len(m.kb.belief)}")
        if not m.kb.log:
            text("B_0 = {entrance}", "dim")
        for inf in m.kb.log:
            text(str(inf))

        divider()
        heading("DECISION")
        d = m.decision
        if d is None:
            text("-", "dim")
        else:
            if d.assumed:
                text(f"Worst case: player at {d.assumed}, needs {len(d.route) - 1 if d.route else '?'} steps")
            text(f"Action: {action_str(d.action)}", "bad" if d.note.startswith("INVALID") else "good", app.f_b)
            val = f"value {d.value:.2f}  " if d.value is not None else ""
            text(f"{val}nodes {d.nodes}  A* exp {d.expanded}  {d.ms:.1f} ms", "dim")
            if d.scored:
                y += 4
                vals = [v for _, v, _ in d.scored]
                lo, hi = min(vals), max(vals)
                for a, v, exact in sorted(d.scored, key=lambda t: -t[1])[:8]:
                    chosen = a == d.action
                    k = 1 if hi == lo else (v - lo) / (hi - lo)
                    bx, bw = x0 + 170, w - 170 - 64
                    pygame.draw.rect(surf, COL["card"], (bx, y + 3, bw, 10), border_radius=5)
                    pygame.draw.rect(surf, COL["accent" if chosen else "line_hi"],
                                     (bx, y + 3, max(4, int(bw * (0.15 + 0.85 * k))), 10), border_radius=5)
                    blit_text(surf, app.f_s, ("> " if chosen else "  ") + action_str(a), "accent" if chosen else "text", (x0, y))
                    blit_text(surf, app.f_s, f"{'' if exact else '<='}{v:.2f}", "dim", (x0 + w, y), "topright")
                    y += 17
                text("<= : branch pruned by alpha-beta (upper bound)", "faint")

        ly = H - MARGIN - 6 * 18        # event log pinned to the bottom of the panel
        pygame.draw.line(surf, COL["line"], (x0, ly - 10), (x0 + w, ly - 10), 1)
        for i, (color, msg) in enumerate(self.log[-6:]):
            blit_text(surf, app.f_s, msg[:64], color, (x0, ly + i * 18))

    def draw_game_over(self, surf):
        m = self.match
        veil = pygame.Surface(self.grid.size, pygame.SRCALPHA)
        veil.fill((10, 8, 14, 205))
        surf.blit(veil, self.grid.topleft)
        won = m.winner == "player"
        cx, cy = self.grid.centerx, self.grid.centery
        blit_text(surf, self.app.f_hero_s, "TREASURE FOUND!" if won else "THE WARDEN WINS",
                  "good" if won else "bad", (cx, cy - 90), "center")
        limit = f" of {m.T}" if m.T else ""
        lines = [f"Turns used: {m.state.turn}{limit}",
                 f"Forced detour: +{m.path_increase()} steps over the shortest path ({m.original_len})",
                 f"Walls placed: {len(m.state.walls - self.dmap.walls)}    Invalid Warden actions: {m.invalid}"]
        for i, line in enumerate(lines):
            blit_text(surf, self.app.f, line, "text", (cx, cy - 40 + i * 24), "center")
        total = sum(b.rect.w for b in self.over_buttons) + 16 * (len(self.over_buttons) - 1)
        bx = cx - total // 2
        for b in self.over_buttons:
            b.rect.topleft = (bx, cy + 50)
            bx += b.rect.w + 16
            b.draw(surf, self.app.f_b, pygame.mouse.get_pos())
        blit_text(surf, self.app.f_s, "R play again   N next map   M menu", "faint", (cx, cy + 114), "center")


# =============================================================== app

class App:
    def __init__(self, args):
        pygame.init()
        pygame.display.set_caption("Dungeon Warden")
        self.args = args
        self.screen = pygame.display.set_mode((W, H))
        self.clock = pygame.time.Clock()
        self.f_hero = font(64, True, mono=False)
        self.f_hero_s = font(38, True, mono=False)
        self.f_title = font(22, True, mono=False)
        self.f, self.f_b, self.f_s = font(16), font(16, True), font(13)
        self.seed = args.seed
        self.delay = args.delay
        self.overlay: str | None = None
        self.overlay_buttons: list[Button] = []
        size, name = "10x10", None
        if args.map:
            p = Path(args.map)
            size = p.parent.name if p.parent.name in SIZES else size
            name = p.stem
        self.cfg = {"size": size, "map": name or map_paths(size)[0].stem, "difficulty": args.difficulty,
                    "warden": args.warden, "rules": args.rules, "ctrl": args.bot or "human"}
        self.menu = Menu(self)
        self.game: GameScreen | None = None
        self._preview = None
        if args.skip_menu:
            self.start_game()

    # ---- settings helpers

    def map_path(self) -> Path:
        paths = {p.stem: p for p in map_paths(self.cfg["size"])}
        return paths.get(self.cfg["map"]) or next(iter(paths.values()))

    def preview_map(self) -> DungeonMap:
        path = self.map_path()
        if self._preview is None or self._preview[0] != path:
            m = DungeonMap.load(path)
            self._preview = (path, m, Match(m).original_len)
        return self._preview[1]

    def preview_shortest(self) -> int:
        self.preview_map()
        return self._preview[2]

    def preview_settings(self) -> dict:
        return game_settings(self.map_path(), self.preview_shortest(), self.cfg["difficulty"], RULESETS[self.cfg["rules"]])

    # ---- actions

    def start_game(self):
        self.overlay = None
        self.game = GameScreen(self)

    def do(self, action: str):
        if action in ("start", "restart"):
            self.start_game()
        elif action == "next":
            maps = [p.stem for p in map_paths(self.cfg["size"])]
            i = maps.index(self.cfg["map"]) if self.cfg["map"] in maps else -1
            self.cfg["map"] = maps[(i + 1) % len(maps)]
            self.start_game()
        elif action == "menu":
            self.game, self.overlay = None, None
        elif action == "resume":
            self.overlay = None
        elif action == "help":
            self.overlay = "help"
        elif action == "quit":
            self.quit()

    def quit(self):
        pygame.quit()
        sys.exit(0)

    # ---- overlays

    def overlay_key(self, k):
        if self.overlay == "help" and k in (pygame.K_h, pygame.K_ESCAPE, pygame.K_RETURN):
            self.overlay = None
        elif self.overlay == "pause":
            if k in (pygame.K_ESCAPE, pygame.K_RETURN):
                self.overlay = None
            elif k == pygame.K_r:
                self.do("restart")
            elif k == pygame.K_m:
                self.do("menu")
            elif k == pygame.K_q:
                self.quit()

    def draw_overlay(self, surf):
        veil = pygame.Surface((W, H), pygame.SRCALPHA)
        veil.fill((8, 6, 12, 190))
        surf.blit(veil, (0, 0))
        if self.overlay == "pause":
            box = pygame.Rect(0, 0, 360, 330)
            box.center = (W // 2, H // 2)
            pygame.draw.rect(surf, COL["panel"], box, border_radius=16)
            pygame.draw.rect(surf, COL["accent"], box, 2, border_radius=16)
            blit_text(surf, self.f_hero_s, "Paused", "accent", (box.centerx, box.y + 24), "midtop")
            self.overlay_buttons = []
            for i, (label, action) in enumerate((("Resume", "resume"), ("Restart", "restart"),
                                                 ("Main menu", "menu"), ("Quit", "quit"))):
                b = Button(label, action, pygame.Rect(box.x + 60, box.y + 96 + i * 56, 240, 44), primary=i == 0)
                b.draw(surf, self.f_b, pygame.mouse.get_pos())
                self.overlay_buttons.append(b)
        elif self.overlay == "help":
            box = pygame.Rect(60, 40, W - 120, H - 80)
            pygame.draw.rect(surf, COL["panel"], box, border_radius=16)
            pygame.draw.rect(surf, COL["accent"], box, 2, border_radius=16)
            blit_text(surf, self.f_hero_s, "How to play", "accent", (box.x + 36, box.y + 22))
            col_w = box.w // 2 - 60
            y = box.y + 86
            for para in (
                "Reach the gold treasure. Each turn you move one cell, then the Warden acts "
                "(waiting with Space is only allowed under the variant rules).",
                "The Warden can lock doors and raise walls, but it may never cut you off completely.",
                "It can't see you. Hidden pressure plates, creaking doors and eyes (2-cell sight) tell it roughly "
                "where you are; the red cells are every place it still thinks you could be.",
                "It plans against the cell closest to the treasure, looking 3 moves ahead with Minimax.",
                "Proposal rules: you lose when the turn limit runs out. Variant rules: no limit, fewer turns is better.",
            ):
                for line in wrap(para, self.f, col_w):
                    blit_text(surf, self.f, line, "text", (box.x + 36, y))
                    y += 22
                y += 8
            y += 6
            for k, v in (("WASD / arrows", "move"), ("Space", "wait (variant rules only)"), ("B", "belief overlay"),
                         ("V", "reveal hidden sensors"), ("Tab", "human / bot"), ("P, +/-", "pause bot, bot speed"),
                         ("R", "restart"), ("Esc", "pause menu")):
                blit_text(surf, self.f_b, k, "accent", (box.x + 36, y))
                blit_text(surf, self.f, v, "text", (box.x + 220, y))
                y += 22
            x2, y = box.x + box.w // 2 + 20, box.y + 86
            blit_text(surf, self.f_b, "The Warden's knowledge base (FOL)", "accent", (x2, y))
            y += 32
            for name, rule in FOL_RULES.items():
                blit_text(surf, self.f_b, name, "accent", (x2, y))
                for line in wrap(rule, self.f_s, col_w - 60):
                    blit_text(surf, self.f_s, line, "text", (x2 + 56, y + 2))
                    y += 18
                y += 10
            blit_text(surf, self.f_s, "H or Esc to close", "faint", (box.centerx, box.bottom - 22), "center")

    # ---- loop

    def frame(self, now: int):
        if self.game:
            if self.overlay is None:
                self.game.update(now)
            self.game.draw(self.screen, now)
        else:
            self.menu.draw(self.screen, now)
        if self.overlay:
            self.draw_overlay(self.screen)

    def handle(self, ev):
        if ev.type == pygame.QUIT:
            self.quit()
        if ev.type == pygame.KEYDOWN:
            if self.overlay:
                self.overlay_key(ev.key)
            elif self.game:
                self.game.key(ev.key)
            else:
                self.menu.key(ev.key)
        elif ev.type == pygame.MOUSEBUTTONDOWN and ev.button == 1:
            if self.overlay == "pause":
                for b in self.overlay_buttons:
                    if b.rect.collidepoint(ev.pos):
                        self.do(b.action)
            elif self.overlay == "help":
                self.overlay = None
            elif self.game:
                self.game.click(ev.pos)
            else:
                self.menu.click(ev.pos)

    def run(self):
        while True:
            for ev in pygame.event.get():
                self.handle(ev)
            self.frame(pygame.time.get_ticks())
            pygame.display.flip()
            self.clock.tick(60)


def main(argv=None):
    ap = argparse.ArgumentParser(description="Dungeon Warden")
    ap.add_argument("--map", help="map file, e.g. maps/20x20/fortress.txt")
    ap.add_argument("--warden", default="W2", choices=sorted(WARDENS))
    ap.add_argument("--difficulty", default="normal", choices=list(DIFFICULTIES))
    ap.add_argument("--rules", default="proposal", choices=list(RULESETS))
    ap.add_argument("--bot", choices=sorted(BOTS), help="let a bot play instead of you")
    ap.add_argument("--T", type=int, help="override the turn limit (proposal rules)")
    ap.add_argument("--energy", type=int, help="override the Warden's starting energy")
    ap.add_argument("--cap", type=int, help="override the Warden's energy cap")
    ap.add_argument("--seed", type=int, default=0)
    ap.add_argument("--delay", type=int, default=300, help="ms between bot moves")
    ap.add_argument("--skip-menu", action="store_true", help="start the game straight away")
    App(ap.parse_args(argv)).run()


if __name__ == "__main__":
    main()
