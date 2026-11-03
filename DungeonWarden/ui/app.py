"""DungeonWardenApp class: manages Pygame lifecycle, screens, and CLI arguments."""
from __future__ import annotations

import argparse
import csv
from pathlib import Path
import sys

import pygame

from DungeonWarden.ai.player_bots import BOTS
from DungeonWarden.core.dungeon_map import DungeonMap
from DungeonWarden.core.match_engine import MatchEngine
from DungeonWarden.core.settings import DIFFICULTIES, LOGS_DIR, SettingsManager
from DungeonWarden.ui.game_session import GameSession
from DungeonWarden.ui.menu_view import MenuView
from DungeonWarden.ui.overlay_view import OverlayView
from DungeonWarden.ui.theme import SCREEN_H, SCREEN_W, Theme
from DungeonWarden.ui.tutorial_view import TutorialView

LOG_FILE = LOGS_DIR / "games.csv"


class DungeonWardenApp:
    """Top-level Pygame application coordinating MenuView, GameSession, and OverlayView."""

    def __init__(self, args: argparse.Namespace) -> None:
        pygame.init()
        pygame.display.set_caption("Dungeon Warden")
        self.args = args
        self.screen = pygame.display.set_mode((SCREEN_W, SCREEN_H))
        self.clock = pygame.time.Clock()
        self.theme = Theme()
        self.seed: int = args.seed
        self.delay: int = args.delay
        self.overlay: str | None = None

        map_name = Path(args.map).stem if args.map else None
        default_map = SettingsManager.map_paths()[0].stem
        self.cfg: dict[str, str] = {
            "map": map_name or default_map,
            "difficulty": args.difficulty,
            "ctrl": args.bot or "human",
        }

        self.menu_view = MenuView(self)
        self.overlay_view = OverlayView(self.theme)
        self.tutorial_view = TutorialView(self)
        self.session: GameSession | None = None
        self._preview_cache: tuple[Path, DungeonMap, int] | None = None

        if getattr(args, "tutorial", False):
            self.open_tutorial()
        elif args.skip_menu:
            self.start_game()

    def map_path(self) -> Path:
        """Resolve the currently selected 20x20 map file path."""
        if self.args.map and Path(self.args.map).exists():
            return Path(self.args.map)
        paths = {p.stem: p for p in SettingsManager.map_paths()}
        return paths.get(self.cfg["map"]) or next(iter(paths.values()))

    def preview_map(self) -> DungeonMap:
        """Return the cached DungeonMap for the menu preview."""
        path = self.map_path()
        if self._preview_cache is None or self._preview_cache[0] != path:
            dmap = DungeonMap.load(path)
            self._preview_cache = (path, dmap, MatchEngine(dmap).original_len)
        return self._preview_cache[1]

    def preview_shortest(self) -> int:
        """Return the shortest path length of the previewed map."""
        self.preview_map()
        assert self._preview_cache is not None
        return self._preview_cache[2]

    def preview_settings(self) -> dict[str, int]:
        """Return the calibrated settings for the previewed map and difficulty."""
        return SettingsManager.get_match_settings(
            self.map_path(), self.preview_shortest(), self.cfg["difficulty"]
        )

    def start_game(self, with_tutorial: bool = False) -> None:
        """Initialize a new GameSession; starts the hands-on tutorial only when requested."""
        self.overlay = None
        self.session = GameSession(self)
        if with_tutorial:
            self.tutorial_view.start()
        else:
            self.tutorial_view.stop()

    def open_tutorial(self) -> None:
        """Start or resume a live GameSession with the hands-on practice tutorial active."""
        self.overlay = None
        if self.session is None or self.session.match.winner:
            self.start_game(with_tutorial=True)
        else:
            self.tutorial_view.start()

    def execute_action(self, action: str) -> None:
        """Dispatch a high-level UI button or menu action."""
        if action in ("start", "restart"):
            self.start_game(with_tutorial=False)
        elif action == "tutorial":
            self.open_tutorial()
        elif action == "next":
            maps = [p.stem for p in SettingsManager.map_paths()]
            idx = maps.index(self.cfg["map"]) if self.cfg["map"] in maps else -1
            self.cfg["map"] = maps[(idx + 1) % len(maps)]
            self.start_game(with_tutorial=False)
        elif action == "menu":
            self.tutorial_view.stop()
            self.session = None
            self.overlay = None
        elif action == "resume":
            self.overlay = None
        elif action == "help":
            self.overlay = "help"
        elif action == "quit":
            self.quit()

    def quit(self) -> None:
        """Cleanly shut down Pygame and exit the process."""
        pygame.quit()
        sys.exit(0)

    @staticmethod
    def log_finished_game(row: dict[str, object]) -> None:
        """Append one finished game record to DungeonWarden/logs/games.csv."""
        try:
            LOG_FILE.parent.mkdir(parents=True, exist_ok=True)
            is_new = not LOG_FILE.exists()
            with LOG_FILE.open("a", newline="", encoding="utf-8") as f:
                writer = csv.DictWriter(f, fieldnames=list(row))
                if is_new:
                    writer.writeheader()
                writer.writerow(row)
        except OSError as exc:
            print(f"could not write {LOG_FILE}: {exc}", file=sys.stderr)

    def _handle_overlay_key(self, key: int) -> None:
        if self.overlay == "help":
            if key == pygame.K_t:
                self.open_tutorial()
            elif key in (pygame.K_h, pygame.K_ESCAPE, pygame.K_RETURN):
                self.overlay = None
        elif self.overlay == "pause":
            if key in (pygame.K_ESCAPE, pygame.K_RETURN):
                self.overlay = None
            elif key == pygame.K_t:
                self.open_tutorial()
            elif key == pygame.K_r:
                self.execute_action("restart")
            elif key == pygame.K_m:
                self.execute_action("menu")
            elif key == pygame.K_q:
                self.quit()

    def handle_event(self, event: pygame.event.Event) -> None:
        """Route a Pygame event to the active modal, practice tutorial, game session, or main menu."""
        if event.type == pygame.QUIT:
            self.quit()
        if event.type == pygame.KEYDOWN:
            if self.overlay:
                self._handle_overlay_key(event.key)
            elif self.session:
                if not self.tutorial_view.handle_key(event.key):
                    self.session.handle_key(event.key)
            else:
                self.menu_view.handle_key(event.key)
        elif event.type == pygame.MOUSEBUTTONDOWN and event.button == 1:
            if self.overlay == "pause":
                for btn in self.overlay_view.pause_buttons:
                    if btn.rect.collidepoint(event.pos):
                        self.execute_action(btn.action)
            elif self.overlay == "help":
                self.overlay = None
            elif self.session:
                if not self.tutorial_view.handle_click(event.pos):
                    self.session.handle_click(event.pos)
            else:
                self.menu_view.handle_click(event.pos)

    def render_frame(self, now_ms: int) -> None:
        """Update and render the active screen and any modal overlay."""
        if self.session:
            if self.overlay is None:
                self.session.update(now_ms)
            self.session.draw(self.screen, now_ms)
        else:
            self.menu_view.draw(self.screen, now_ms)
        if self.overlay:
            self.overlay_view.draw_modal(self.screen, self.overlay)

    def run(self) -> None:
        """Main 60 FPS event and rendering loop."""
        while True:
            for ev in pygame.event.get():
                self.handle_event(ev)
            self.render_frame(pygame.time.get_ticks())
            pygame.display.flip()
            self.clock.tick(60)


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    """Parse CLI arguments for launching the Dungeon Warden Pygame application."""
    parser = argparse.ArgumentParser(description="Dungeon Warden (20x20)")
    parser.add_argument("--map", help="map file or name, e.g. fortress or DungeonWarden/maps/fortress.txt")
    parser.add_argument("--difficulty", default="normal", choices=list(DIFFICULTIES))
    parser.add_argument("--bot", choices=sorted(BOTS), help="let a bot play instead of you")
    parser.add_argument("--T", type=int, help="override the turn limit T")
    parser.add_argument("--energy", type=int, help="override the Warden's starting energy")
    parser.add_argument("--cap", type=int, help="override the Warden's energy cap")
    parser.add_argument("--lock-cost", type=int, help="override the energy cost of LockDoor")
    parser.add_argument("--wall-cost", type=int, help="override the energy cost of PlaceWall")
    parser.add_argument("--seed", type=int, default=0)
    parser.add_argument("--delay", type=int, default=300, help="ms between bot moves")
    parser.add_argument("--skip-menu", action="store_true", help="start the game straight away")
    parser.add_argument("--tutorial", action="store_true", help="open the interactive tutorial straight away")
    return parser.parse_args(argv)

