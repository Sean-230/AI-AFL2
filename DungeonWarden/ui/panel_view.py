"""ReasoningPanelView class: renders the top game header and right-hand player HUD."""
from __future__ import annotations

from typing import TYPE_CHECKING

import pygame

from DungeonWarden.ai.pathfinder import Pathfinder
from DungeonWarden.ui.menu_view import format_difficulty, format_map_name
from DungeonWarden.ui.theme import (
    COLORS,
    MARGIN,
    PANEL_W,
    PANEL_X,
    SCREEN_H,
    SCREEN_W,
    TOP_BAR_H,
    Theme,
)

if TYPE_CHECKING:
    from DungeonWarden.core.match_engine import MatchEngine


class ReasoningPanelView:
    """Renders the top game header bar and clean right-hand player HUD cards."""

    def __init__(self, theme: Theme) -> None:
        self.theme = theme

    def draw_top_bar(
        self,
        surf: pygame.Surface,
        match: "MatchEngine",
        difficulty: str,
    ) -> None:
        """Render the top application header bar without overlapping chips and shortcuts."""
        theme = self.theme
        dmap = match.dmap
        pygame.draw.rect(surf, COLORS["bar"], (0, 0, SCREEN_W, TOP_BAR_H))
        pygame.draw.line(surf, COLORS["line"], (0, TOP_BAR_H), (SCREEN_W, TOP_BAR_H), 2)
        title_rect = Theme.blit_text(
            surf, theme.f_title, "DUNGEON WARDEN", "accent", (MARGIN, TOP_BAR_H // 2), "midleft"
        )

        x = title_rect.right + 20
        diff_color = {"easy": "good", "normal": "accent", "hard": "bad"}[difficulty]
        chips = (
            (f"Peta: {format_map_name(dmap.name)}", "text"),
            (f"Kesulitan: {format_difficulty(difficulty)}", diff_color),
        )
        for label, color_key in chips:
            rendered = theme.f_s.render(label, True, COLORS[color_key])
            chip = pygame.Rect(x, TOP_BAR_H // 2 - 14, rendered.get_width() + 22, 28)
            pygame.draw.rect(surf, COLORS["card"], chip, border_radius=14)
            pygame.draw.rect(surf, COLORS["line_hi"], chip, 1, border_radius=14)
            surf.blit(rendered, rendered.get_rect(center=chip.center))
            x = chip.right + 10

        Theme.blit_text(
            surf,
            theme.f_s,
            "WASD/Panah: Jalan  •  T: Tutorial  •  H: Panduan  •  R: Ulangi  •  Esc: Menu",
            "dim",
            (SCREEN_W - MARGIN, TOP_BAR_H // 2),
            "midright",
        )

    def draw_panel(
        self,
        surf: pygame.Surface,
        match: "MatchEngine",
        event_log: list[tuple[str, str]],
        tutorial_active: bool = False,
    ) -> None:
        """Render the player HUD panel on the right side without overlapping cards."""
        self._draw_status_card(surf, match)
        if tutorial_active:
            return
        self._draw_mission_card(surf, match)
        self._draw_legend_card(surf)
        self._draw_log_card(surf, event_log)

    def _draw_status_card(self, surf: pygame.Surface, match: "MatchEngine") -> None:
        """Render the top status card (y = 68..196) showing Turn and Warden Energy bars."""
        theme = self.theme
        st = match.state
        card = pygame.Rect(PANEL_X, TOP_BAR_H + 8, PANEL_W, 128)
        pygame.draw.rect(surf, COLORS["card"], card, border_radius=12)
        pygame.draw.rect(surf, COLORS["line"], card, 1, border_radius=12)

        px = card.x + 18
        pw = card.w - 36
        y = card.y + 12

        Theme.blit_text(surf, theme.f_b, "STATUS PERMAINAN", "accent", (px, y))
        rem_turns = max(0, match.T - st.turn)
        rem_color = "bad" if rem_turns <= 5 else "good"
        Theme.blit_text(
            surf,
            theme.f_b,
            f"Sisa {rem_turns} langkah",
            rem_color,
            (px + pw, y),
            "topright",
        )
        y += 28

        turn_col = "bad" if rem_turns <= 5 else "sight"
        self._draw_bar_row(
            surf,
            px,
            y,
            pw,
            "Langkah",
            st.turn,
            match.T,
            turn_col,
            f"{st.turn} / {match.T}",
        )
        y += 26

        self._draw_bar_row(
            surf,
            px,
            y,
            pw,
            "Energi Penjaga",
            st.energy,
            match.cap,
            "accent",
            f"{st.energy} / {match.cap}",
        )
        y += 26

        Theme.blit_text(
            surf,
            theme.f_s,
            f"Kunci Pintu: {st.lock_cost} Energi   •   Tembok Bata: {st.wall_cost} Energi   •   Rehat: +1 Energi",
            "dim",
            (px, y),
        )

    def _draw_bar_row(
        self,
        surf: pygame.Surface,
        x: int,
        y: int,
        w: int,
        label: str,
        value: int,
        maximum: int,
        color_key: str,
        right_text: str,
    ) -> None:
        theme = self.theme
        Theme.blit_text(surf, theme.f_s, label, "text", (x, y))
        bx = x + 120
        bw = w - 120 - 70
        pygame.draw.rect(surf, COLORS["bar"], (bx, y + 4, bw, 11), border_radius=5)
        if maximum > 0:
            fill_w = int(bw * min(1.0, max(0.0, value / maximum)))
            if fill_w > 0:
                pygame.draw.rect(surf, COLORS[color_key], (bx, y + 4, fill_w, 11), border_radius=5)
        Theme.blit_text(surf, theme.f_s, right_text, "text", (x + w, y), "topright")

    def _draw_mission_card(self, surf: pygame.Surface, match: "MatchEngine") -> None:
        """Render the objective and live dungeon stats card (y = 206..382)."""
        theme = self.theme
        st = match.state
        dmap = match.dmap
        card = pygame.Rect(PANEL_X, 206, PANEL_W, 176)
        pygame.draw.rect(surf, COLORS["card"], card, border_radius=12)
        pygame.draw.rect(surf, COLORS["line"], card, 1, border_radius=12)

        px = card.x + 18
        pw = card.w - 36
        y = card.y + 12

        Theme.blit_text(surf, theme.f_b, "OBJEKTIF & SITUASI RUANG BAWAH TANAH", "accent", (px, y))
        y += 26

        dist_map = Pathfinder.bfs_distances(dmap.treasure, dmap, st.blocked)
        cur_dist = dist_map.get(match.player, -1)
        placed_count = len(st.walls - dmap.walls)
        locked_count = len(st.locked)

        stats = (
            ("Jarak Rute Terdekat ke Harta Karun", f"{cur_dist} langkah" if cur_dist >= 0 else "-"),
            ("Pintu yang Sedang Dikunci Penjaga", f"{locked_count} dari {len(dmap.doors)} pintu"),
            ("Tembok Baru yang Diangkat Penjaga", f"{placed_count} tembok bata"),
        )
        for label, val in stats:
            Theme.blit_text(surf, theme.f_s, label, "dim", (px, y))
            Theme.blit_text(surf, theme.f_b, val, "text", (px + pw, y - 1), "topright")
            y += 23

        y += 4
        pygame.draw.line(surf, COLORS["line"], (px, y), (px + pw, y), 1)
        y += 8
        tip = (
            "Tips: Hindari pelat jebakan & area pantau biru agar Penjaga tidak melacakmu. "
            f"Terobos lorong saat energi Penjaga di bawah {min(st.lock_cost, st.wall_cost)}!"
        )
        for line in Theme.wrap_text(tip, theme.f_s, pw)[:2]:
            Theme.blit_text(surf, theme.f_s, line, "good", (px, y))
            y += 18

    def _draw_legend_card(self, surf: pygame.Surface) -> None:
        """Render the 2-column visual object legend card (y = 392..588) without horizontal overlap."""
        theme = self.theme
        card = pygame.Rect(PANEL_X, 392, PANEL_W, 196)
        pygame.draw.rect(surf, COLORS["card"], card, border_radius=12)
        pygame.draw.rect(surf, COLORS["line"], card, 1, border_radius=12)

        px = card.x + 18
        pw = card.w - 36
        y = card.y + 12
        Theme.blit_text(surf, theme.f_b, "ELEMEN DI PAPAN PERMAINAN", "accent", (px, y))
        y += 28

        items = (
            ("player", "Karaktermu (Biru)", "Gerak dengan WASD / Panah"),
            ("treasure", "Harta Karun (Emas)", "Capai sebelum langkah habis"),
            ("locked", "Pintu & Gembok Merah", "Terkunci tak bisa dilewati"),
            ("placed", "Tembok Bata Merah", "Rintangan baru dari Penjaga"),
            ("plate", "Pelat Jebakan (Kuning)", "Terinjak = lokasi terbongkar"),
            ("eye", "Mata & Area Biru", "Memantau 2 petak lurus"),
        )
        col_w = (pw - 16) // 2
        row_h = 50
        for idx, (col_key, title, desc) in enumerate(items):
            col = idx % 2
            row = idx // 2
            ix = px + col * (col_w + 16)
            iy = y + row * row_h
            box = pygame.Rect(ix, iy, col_w, row_h - 6)
            pygame.draw.rect(surf, COLORS["bar"], box, border_radius=8)
            pygame.draw.rect(surf, COLORS[col_key], (box.x + 10, box.y + 8, 12, 12), border_radius=3)
            Theme.blit_text(surf, theme.f_b, title, "text", (box.x + 28, box.y + 4))
            Theme.blit_text(surf, theme.f_s, desc, "dim", (box.x + 28, box.y + 23))

    def _draw_log_card(
        self,
        surf: pygame.Surface,
        event_log: list[tuple[str, str]],
    ) -> None:
        """Render the dungeon event log card (y = 598..754)."""
        theme = self.theme
        card = pygame.Rect(PANEL_X, 598, PANEL_W, 156)
        pygame.draw.rect(surf, COLORS["card"], card, border_radius=12)
        pygame.draw.rect(surf, COLORS["line"], card, 1, border_radius=12)

        px = card.x + 18
        y = card.y + 12
        Theme.blit_text(surf, theme.f_b, "CATATAN PERISTIWA", "accent", (px, y))
        y += 26

        for col_key, msg in event_log[-5:]:
            Theme.blit_text(surf, theme.f_s, msg, col_key, (px, y))
            y += 22
