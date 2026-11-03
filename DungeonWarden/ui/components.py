"""Reusable UI widget components for Pygame views."""
from __future__ import annotations

import pygame

from DungeonWarden.ui.theme import COLORS, Theme


class Button:
    """Interactive clickable button component with hover highlighting."""

    def __init__(
        self,
        label: str,
        action: str,
        rect: pygame.Rect,
        primary: bool = False,
    ) -> None:
        self.label = label
        self.action = action
        self.rect = rect
        self.primary = primary

    def draw(
        self,
        surf: pygame.Surface,
        font_obj: pygame.font.Font,
        mouse_pos: tuple[int, int],
    ) -> None:
        """Render the button onto `surf`, brightening its background when hovered."""
        is_hovered = self.rect.collidepoint(mouse_pos)
        base_color = COLORS["accent"] if self.primary else COLORS["card"]
        fill_color = (
            tuple(min(255, c + 22) for c in base_color) if is_hovered else base_color
        )
        border_color = COLORS["treasure_hi"] if self.primary else COLORS["line_hi"]
        text_color = COLORS["bg"] if self.primary else COLORS["text"]

        pygame.draw.rect(surf, fill_color, self.rect, border_radius=10)
        pygame.draw.rect(surf, border_color, self.rect, 2, border_radius=10)
        Theme.blit_text(surf, font_obj, self.label, text_color, self.rect.center, "center")

