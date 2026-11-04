"""UI theme, color palette, layout dimensions, and typography utilities."""
from __future__ import annotations

import pygame

SCREEN_W, SCREEN_H = 1280, 800
TOP_BAR_H = 60
MARGIN = 24
BOARD_SIZE = SCREEN_H - TOP_BAR_H - MARGIN - 40
PANEL_X = MARGIN * 2 + BOARD_SIZE
PANEL_W = SCREEN_W - PANEL_X - MARGIN
MOVE_ANIM_MS = 110
WALL_ANIM_MS = 320

COLORS: dict[str, tuple[int, int, int]] = {
    "bg": (14, 12, 19),
    "bar": (22, 19, 29),
    "panel": (24, 21, 31),
    "card": (32, 28, 41),
    "line": (52, 47, 66),
    "line_hi": (78, 70, 98),
    "floor": (92, 84, 100),
    "floor_dark": (83, 76, 91),
    "crack": (70, 64, 78),
    "wall": (34, 30, 43),
    "wall_top": (62, 57, 76),
    "wall_shadow": (20, 17, 26),
    "placed": (156, 66, 52),
    "placed_top": (198, 98, 74),
    "door": (139, 96, 52),
    "door_hi": (178, 128, 74),
    "locked": (232, 72, 72),
    "treasure": (246, 204, 64),
    "treasure_hi": (255, 240, 170),
    "player": (84, 170, 255),
    "player_hi": (200, 230, 255),
    "belief": (255, 64, 96),
    "assumed": (255, 206, 60),
    "sight": (110, 190, 255),
    "plate": (190, 180, 110),
    "eye": (176, 126, 255),
    "text": (230, 228, 240),
    "dim": (146, 141, 165),
    "faint": (98, 94, 116),
    "accent": (255, 186, 90),
    "good": (120, 222, 140),
    "bad": (255, 108, 108),
}


class Theme:
    """Provides typography, text wrapping, easing, and Pygame text rendering helpers."""

    def __init__(self) -> None:
        self.f_hero = self.load_font(60, bold=True, mono=False)
        self.f_hero_s = self.load_font(34, bold=True, mono=False)
        self.f_title = self.load_font(20, bold=True, mono=False)
        self.f = self.load_font(15, mono=False)
        self.f_b = self.load_font(15, bold=True, mono=False)
        self.f_s = self.load_font(13, mono=False)

    @staticmethod
    def load_font(size: int, bold: bool = False, mono: bool = False) -> pygame.font.Font:
        """Create a system font with cross-platform fallbacks."""
        families = (
            "consolas,menlo,dejavusansmono,couriernew"
            if mono
            else "segoeui,avenirnext,helveticaneue,arial,verdana"
        )
        try:
            return pygame.font.SysFont(families, size, bold=bold)
        except OSError:
            return pygame.font.Font(None, size)

    @staticmethod
    def wrap_text(text: str, font_obj: pygame.font.Font, max_width: int) -> list[str]:
        """Wrap a string into multiple lines constrained to `max_width` pixels."""
        lines: list[str] = []
        current = ""
        for word in text.split(" "):
            trial = f"{current} {word}".strip()
            if font_obj.size(trial)[0] <= max_width or not current:
                current = trial
            else:
                lines.append(current)
                current = word
        return lines + [current] if current else lines

    @staticmethod
    def blit_text(
        surf: pygame.Surface,
        font_obj: pygame.font.Font,
        text: str,
        color: str | tuple[int, int, int],
        pos: tuple[int, int],
        anchor: str = "topleft",
    ) -> pygame.Rect:
        """Render and blit a text surface onto `surf` aligned by `anchor`."""
        rgb = COLORS[color] if isinstance(color, str) else color
        rendered = font_obj.render(text, True, rgb)
        rect = rendered.get_rect(**{anchor: pos})
        surf.blit(rendered, rect)
        return rect

    @staticmethod
    def ease_out(progress: float) -> float:
        """Cubic ease-out interpolation for smooth UI and tile animations."""
        clamped = min(1.0, max(0.0, progress))
        return 1.0 - (1.0 - clamped) ** 3

