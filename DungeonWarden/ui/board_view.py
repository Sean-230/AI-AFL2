"""BoardView class: renders the 20x20 dungeon map, tiles, animations, and belief overlay."""
from __future__ import annotations

import math
from typing import TYPE_CHECKING

import pygame

from DungeonWarden.core.dungeon_map import Cell, DungeonMap
from DungeonWarden.core.sensor_system import SensorSystem
from DungeonWarden.ui.theme import (
    BOARD_SIZE,
    COLORS,
    MARGIN,
    PANEL_X,
    TOP_BAR_H,
    WALL_ANIM_MS,
    Theme,
)

if TYPE_CHECKING:
    from DungeonWarden.core.match_engine import MatchEngine


class BoardView:
    """Renders the 2D dungeon grid, torch lighting, animations, and AI belief overlays."""

    def __init__(self, dmap: DungeonMap, theme: Theme) -> None:
        self.dmap = dmap
        self.theme = theme
        self.cell = max(16, min(64, BOARD_SIZE // max(dmap.w, dmap.h)))
        gw, gh = self.cell * dmap.w, self.cell * dmap.h
        self.grid = pygame.Rect(
            MARGIN + (BOARD_SIZE - gw) // 2,
            TOP_BAR_H + 8,
            gw,
            gh,
        )
        self.base_surface = self._bake_static_board()
        self.light_surface = self._bake_torch_light()
        self.anims: dict[Cell, tuple[str, int]] = {}

    def cell_rect(self, cell: Cell, inset: int = 0) -> pygame.Rect:
        """Return the screen-space rectangle for a grid cell."""
        s = self.cell
        return pygame.Rect(
            self.grid.x + cell[0] * s + inset,
            self.grid.y + cell[1] * s + inset,
            s - 2 * inset,
            s - 2 * inset,
        )

    def cell_center(self, cell: Cell) -> tuple[int, int]:
        """Return the pixel center of a grid cell."""
        return self.cell_rect(cell).center

    def _bake_static_board(self) -> pygame.Surface:
        dmap, s = self.dmap, self.cell
        surf = pygame.Surface(self.grid.size)
        for x, y in dmap.cells:
            rect = pygame.Rect(x * s, y * s, s, s)
            noise = ((x * 73856093) ^ (y * 19349663)) % 13 - 6
            if (x, y) in dmap.walls:
                pygame.draw.rect(surf, tuple(max(0, c + noise) for c in COLORS["wall"]), rect)
                pygame.draw.rect(surf, COLORS["wall_top"], (rect.x, rect.y, rect.w, max(3, s // 7)))
                pygame.draw.line(
                    surf, COLORS["wall_shadow"], (rect.x, rect.bottom - 1), (rect.right, rect.bottom - 1), 2
                )
            else:
                base = COLORS["floor"] if (x + y) % 2 else COLORS["floor_dark"]
                pygame.draw.rect(surf, tuple(max(0, c + noise) for c in base), rect)
                if s >= 24 and noise > 3:
                    pygame.draw.line(
                        surf,
                        COLORS["crack"],
                        (rect.x + s // 4, rect.y + s // 3),
                        (rect.x + s // 2, rect.y + s // 2),
                        1,
                    )
                if (x, y - 1) in dmap.walls:
                    shade = pygame.Surface((s, max(4, s // 5)), pygame.SRCALPHA)
                    shade.fill((0, 0, 0, 60))
                    surf.blit(shade, rect.topleft)
        return surf

    def _bake_torch_light(self) -> pygame.Surface:
        gw, gh = self.grid.size
        size = (gw * 2, gh * 2)
        surf = pygame.Surface(size, pygame.SRCALPHA)
        surf.fill((0, 0, 0, 110))
        radius = max(gw, gh) * 0.6
        for idx in range(40, 0, -1):
            k = idx / 40
            pygame.draw.circle(
                surf,
                (0, 0, 0, int(110 * k ** 1.6)),
                (size[0] // 2, size[1] // 2),
                int(radius * k),
            )
        return surf

    def draw(
        self,
        surf: pygame.Surface,
        match: "MatchEngine",
        player_px: pygame.Vector2,
        reveal_sensors: bool,
        message: tuple[str, int],
        now_ms: int,
    ) -> None:
        """Render the board, dynamic objects, sensor preview, and legend."""
        st, dm, s = match.state, self.dmap, self.cell
        pygame.draw.rect(surf, COLORS["line"], self.grid.inflate(10, 10), 5, border_radius=6)
        surf.blit(self.base_surface, self.grid.topleft)

        if reveal_sensors:
            for c in SensorSystem.compute_sight_cells(dm, st.walls):
                self._tint_cell(surf, c, COLORS["sight"], 38)
            for c in dm.plates:
                pygame.draw.rect(surf, COLORS["plate"], self.cell_rect(c, s // 4), 2, border_radius=3)
            for c in dm.eyes:
                er = self.cell_rect(c, s // 5)
                pygame.draw.ellipse(surf, COLORS["eye"], er.inflate(0, -er.h // 3), 2)
                pygame.draw.circle(surf, COLORS["eye"], er.center, max(2, s // 10))

        for c in dm.doors:
            self._draw_door(surf, c, c in st.locked, now_ms)
        for c in st.walls - dm.walls:
            self._draw_placed_wall(surf, c, now_ms)
        self._draw_treasure(surf, now_ms)

        px, py = int(player_px.x), int(player_px.y)
        glow = pygame.Surface((s * 2, s * 2), pygame.SRCALPHA)
        pygame.draw.circle(glow, (*COLORS["player"], 60), (s, s), int(s * 0.75))
        surf.blit(glow, (px - s, py - s))
        pygame.draw.circle(surf, COLORS["player"], (px, py), max(5, s // 3))
        pygame.draw.circle(surf, COLORS["player_hi"], (px, py), max(5, s // 3), 2)

        lw, lh = self.light_surface.get_size()
        prev_clip = surf.get_clip()
        surf.set_clip(self.grid)
        surf.blit(self.light_surface, (px - lw // 2, py - lh // 2))
        surf.set_clip(prev_clip)

        self._draw_legend(surf, message, now_ms)

    def _tint_cell(
        self, surf: pygame.Surface, cell: Cell, color: tuple[int, int, int], alpha: int
    ) -> None:
        overlay = pygame.Surface((self.cell, self.cell), pygame.SRCALPHA)
        overlay.fill((*color, alpha))
        surf.blit(overlay, self.cell_rect(cell).topleft)

    def _draw_door(self, surf: pygame.Surface, cell: Cell, locked: bool, now_ms: int) -> None:
        s = self.cell
        rect = self.cell_rect(cell, max(2, s // 7))
        pygame.draw.rect(surf, COLORS["door"], rect, border_radius=3)
        for i in (1, 2):
            x = rect.x + rect.w * i // 3
            pygame.draw.line(surf, COLORS["door_hi"], (x, rect.y + 2), (x, rect.bottom - 3), 1)
        if not locked:
            return
        anim = self.anims.get(cell)
        k = Theme.ease_out((now_ms - anim[1]) / 300) if anim and anim[0] == "lock" else 1.0
        pygame.draw.rect(surf, COLORS["locked"], rect, 3, border_radius=3)
        body = pygame.Rect(
            0, 0, max(4, int(s / 3 * (0.6 + 0.4 * k))), max(3, int(s / 4 * (0.6 + 0.4 * k)))
        )
        body.center = (rect.centerx, rect.centery + s // 12)
        pygame.draw.arc(
            surf,
            COLORS["locked"],
            body.move(0, -body.h // 2 - 2).inflate(-body.w // 4, 0),
            0,
            3.15,
            max(1, s // 20),
        )
        pygame.draw.rect(surf, COLORS["locked"], body, border_radius=2)

    def _draw_placed_wall(self, surf: pygame.Surface, cell: Cell, now_ms: int) -> None:
        s = self.cell
        rect = self.cell_rect(cell)
        anim = self.anims.get(cell)
        k = Theme.ease_out((now_ms - anim[1]) / WALL_ANIM_MS) if anim and anim[0] == "wall" else 1.0
        h = max(1, int(s * k))
        wr = pygame.Rect(rect.x, rect.bottom - h, s, h)
        pygame.draw.rect(surf, COLORS["placed"], wr)
        pygame.draw.rect(surf, COLORS["placed_top"], (wr.x, wr.y, wr.w, max(3, s // 7)))
        if k >= 1.0:
            pygame.draw.line(surf, COLORS["wall_shadow"], (rect.x, rect.centery), (rect.right, rect.centery), 2)
            pygame.draw.line(surf, COLORS["wall_shadow"], (rect.centerx, rect.y + s // 7), (rect.centerx, rect.centery), 2)
            pygame.draw.line(surf, COLORS["wall_shadow"], (rect.x + s // 4, rect.centery), (rect.x + s // 4, rect.bottom), 2)
        else:
            pygame.draw.circle(surf, COLORS["accent"], rect.center, int(s * (0.4 + 0.5 * k)), 2)

    def _draw_treasure(self, surf: pygame.Surface, now_ms: int) -> None:
        s = self.cell
        rect = self.cell_rect(self.dmap.treasure, s // 6).move(
            0, int(math.sin(now_ms / 300) * s * 0.06)
        )
        halo = pygame.Surface((s * 2, s * 2), pygame.SRCALPHA)
        pygame.draw.circle(
            halo, (*COLORS["treasure"], 46 + int(20 * math.sin(now_ms / 420))), (s, s), int(s * 0.8)
        )
        surf.blit(halo, (rect.centerx - s, rect.centery - s))
        pts = [(rect.centerx, rect.y), (rect.right, rect.centery), (rect.centerx, rect.bottom), (rect.x, rect.centery)]
        pygame.draw.polygon(surf, COLORS["treasure"], pts)
        pygame.draw.polygon(surf, COLORS["treasure_hi"], pts, 2)

    def _draw_legend(
        self,
        surf: pygame.Surface,
        message: tuple[str, int],
        now_ms: int,
    ) -> None:
        y = self.grid.bottom + 10
        msg_text, msg_at = message
        if msg_text and now_ms - msg_at < 1500:
            Theme.blit_text(surf, self.theme.f_b, msg_text, "bad", (self.grid.x, y))
            return
        items = [
            ("player", "kamu"),
            ("treasure", "harta karun"),
            ("placed", "tembok"),
            ("locked", "pintu terkunci"),
            ("plate", "pelat jebakan"),
            ("eye", "mata & area pantau"),
        ]
        x = self.grid.x
        for key, label in items:
            if x + 16 + self.theme.f_s.size(label)[0] > PANEL_X - 12:
                break
            pygame.draw.rect(surf, COLORS[key], (x, y + 3, 12, 12), border_radius=3)
            x = Theme.blit_text(surf, self.theme.f_s, label, "dim", (x + 16, y)).right + 14

