"""GameSession class: coordinates an interactive match session between UI views and MatchEngine."""
from __future__ import annotations

from datetime import datetime
from typing import TYPE_CHECKING

import pygame

from DungeonWarden.core.dungeon_map import DungeonMap
from DungeonWarden.core.match_engine import MatchEngine
from DungeonWarden.core.settings import SettingsManager
from DungeonWarden.ui.board_view import BoardView
from DungeonWarden.ui.menu_view import format_map_name
from DungeonWarden.ui.panel_view import ReasoningPanelView
from DungeonWarden.ui.theme import COLORS, MOVE_ANIM_MS, Theme

if TYPE_CHECKING:
    from DungeonWarden.ui.app import DungeonWardenApp

KEYMOVES: dict[int, str] = {
    pygame.K_w: "up",
    pygame.K_UP: "up",
    pygame.K_s: "down",
    pygame.K_DOWN: "down",
    pygame.K_a: "left",
    pygame.K_LEFT: "left",
    pygame.K_d: "right",
    pygame.K_RIGHT: "right",
}


class GameSession:
    """Manages an active game session: input handling, animations, and view rendering."""

    def __init__(self, app: "DungeonWardenApp") -> None:
        self.app = app
        cfg = app.cfg
        self.path = app.map_path()
        self.dmap = DungeonMap.load(self.path)
        self.settings = SettingsManager.get_match_settings(
            self.path, MatchEngine(self.dmap).original_len, cfg["difficulty"]
        )
        if app.args.T:
            self.settings["T"] = app.args.T
        for key in ("energy", "cap", "lock_cost", "wall_cost"):
            if getattr(app.args, key) is not None:
                self.settings[key] = getattr(app.args, key)

        self.match = MatchEngine(self.dmap, seed=app.seed, **self.settings)
        app.seed += 1
        self.reveal_sensors = True
        self.show_belief = False

        self.board_view = BoardView(self.dmap, app.theme)
        self.panel_view = ReasoningPanelView(app.theme)
        self.player_px = pygame.Vector2(self.board_view.cell_center(self.match.player))
        self.move_from = self.player_px.copy()
        self.move_at = -MOVE_ANIM_MS
        self.event_log: list[tuple[str, str]] = [
            ("dim", f"Peta {format_map_name(self.dmap.name)}: capai Harta Karun sebelum langkah habis!")
        ]
        self.was_seen = False
        self.message: tuple[str, int] = ("", 0)

    def play_turn(self, move: str) -> None:
        """Advance the match by one player move and record visual animations and game logs."""
        m = self.match
        before_walls = m.state.walls
        before_locked = m.state.locked
        prev_cell = m.player

        if not m.step(move):
            if not m.winner:
                self.message = ("Jalan terhalang tembok atau pintu terkunci!", pygame.time.get_ticks())
            return

        now = pygame.time.get_ticks()
        if m.player != prev_cell:
            self.move_from = self.player_px.copy()
            self.move_at = now

        turn = m.state.turn
        for c in sorted(m.state.walls - before_walls):
            self.board_view.anims[c] = ("wall", now)
            self.event_log.append(("bad", f"Langkah {turn}: Tembok batu bangkit menghalangi lorong!"))
        for c in sorted(m.state.locked - before_locked):
            self.board_view.anims[c] = ("lock", now)
            self.event_log.append(("bad", f"Langkah {turn}: Warden mengunci sebuah pintu kayu!"))
        for c in sorted(before_locked - m.state.locked):
            self.event_log.append(("good", f"Langkah {turn}: Sebuah pintu kayu kembali terbuka."))

        seen = bool(m.percept and m.percept.seen)
        if seen and not self.was_seen and not m.winner:
            self.event_log.append(("accent", f"Langkah {turn}: Keberadaanmu terdeteksi oleh Warden!"))
        self.was_seen = seen

        self.app.tutorial_view.on_player_moved()

        if m.winner:
            self.app.tutorial_view.stop()
            self.event_log.append(
                ("good", "Selamat! Kamu berhasil mencapai Harta Karun!")
                if m.winner == "player"
                else ("bad", "Langkahmu habis — Warden berhasil menahanmu.")
            )
            self.app.log_finished_game(
                {
                    "time": datetime.now().isoformat(timespec="seconds"),
                    "player": "human",
                    "difficulty": self.app.cfg["difficulty"],
                    **m.summary(),
                }
            )
        self.event_log = self.event_log[-5:]

    def handle_key(self, key: int) -> None:
        """Process keyboard shortcuts during an active match."""
        app = self.app
        if key == pygame.K_ESCAPE:
            app.overlay = "pause"
        elif key in KEYMOVES and not self.match.winner:
            self.play_turn(KEYMOVES[key])
        elif key == pygame.K_b:
            self.show_belief = not self.show_belief
        elif key == pygame.K_v:
            self.reveal_sensors = not self.reveal_sensors
        elif key == pygame.K_r:
            app.execute_action("restart")
        elif key == pygame.K_n and self.match.winner:
            app.execute_action("next")
        elif key == pygame.K_m and self.match.winner:
            app.execute_action("menu")
        elif key == pygame.K_t:
            if app.tutorial_view.active:
                app.tutorial_view.stop()
            else:
                app.tutorial_view.start()
        elif key == pygame.K_h:
            app.overlay = "help"

    def handle_click(self, pos: tuple[int, int]) -> None:
        """Process mouse clicks on the game-over buttons."""
        if self.match.winner:
            for btn in self.app.overlay_view.over_buttons:
                if btn.rect.collidepoint(pos):
                    self.app.execute_action(btn.action)

    def update(self, now_ms: int) -> None:
        """Interpolate the player's on-screen position animation."""
        progress = Theme.ease_out((now_ms - self.move_at) / MOVE_ANIM_MS)
        target_px = pygame.Vector2(self.board_view.cell_center(self.match.player))
        self.player_px = self.move_from.lerp(target_px, progress)

    def draw(self, surf: pygame.Surface, now_ms: int) -> None:
        """Render the active game screen via BoardView, ReasoningPanelView, and TutorialView."""
        surf.fill(COLORS["bg"])
        self.panel_view.draw_top_bar(
            surf,
            self.match,
            self.app.cfg["difficulty"],
            show_belief=self.show_belief,
        )
        self.board_view.draw(
            surf,
            self.match,
            self.player_px,
            self.reveal_sensors,
            self.message,
            now_ms,
            show_belief=self.show_belief,
        )
        tut_active = self.app.tutorial_view.active and not self.match.winner and self.app.overlay is None
        self.panel_view.draw_panel(
            surf,
            self.match,
            self.event_log,
            tutorial_active=tut_active,
            show_belief=self.show_belief,
        )
        if tut_active:
            self.app.tutorial_view.draw(surf, now_ms)
        if self.match.winner and self.app.overlay is None:
            self.app.overlay_view.draw_game_over(surf, self.board_view.grid, self.match)
