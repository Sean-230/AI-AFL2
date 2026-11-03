"""MenuView class: renders the main settings menu and live 20x20 map preview."""
from __future__ import annotations

import math
from typing import TYPE_CHECKING

import pygame

from DungeonWarden.core.settings import DIFFICULTIES, SettingsManager
from DungeonWarden.ui.components import Button
from DungeonWarden.ui.theme import COLORS, SCREEN_H, SCREEN_W, Theme

if TYPE_CHECKING:
    from DungeonWarden.ui.app import DungeonWardenApp

CONTROLLERS: dict[str, str] = {
    "human": "Pemain (WASD)",
    "rusher": "Rusher",
    "cautious": "Cautious",
}

DIFFICULTY_LABELS: dict[str, str] = {
    "easy": "Mudah",
    "normal": "Normal",
    "hard": "Sulit",
}

MAP_LABELS: dict[str, str] = {
    "catacombs": "Katakombe",
    "fortress": "Benteng",
    "labyrinth": "Labirin",
}


def format_map_name(stem: str) -> str:
    """Return the Indonesian display name for a map key."""
    return MAP_LABELS.get(stem.lower(), stem.title())


def format_difficulty(key: str) -> str:
    """Return the Indonesian display name for a difficulty key."""
    return DIFFICULTY_LABELS.get(key.lower(), key.title())


class MenuView:
    """View and selection state for the main menu screen."""

    def __init__(self, app: "DungeonWardenApp") -> None:
        self.app = app
        self.sel = 0
        self.buttons = [
            Button("Mulai Main", "start", pygame.Rect(0, 0, 210, 54), primary=True),
            Button("Tutorial", "tutorial", pygame.Rect(0, 0, 165, 54)),
            Button("Panduan", "help", pygame.Rect(0, 0, 165, 54)),
            Button("Keluar", "quit", pygame.Rect(0, 0, 130, 54)),
        ]
        self.rows: list[pygame.Rect] = []

    @property
    def options(self) -> list[tuple[str, str, list[str], object]]:
        maps = [p.stem for p in SettingsManager.map_paths()]
        return [
            ("Lokasi Peta", "map", maps, format_map_name),
            ("Tingkat Kesulitan", "difficulty", list(DIFFICULTIES), format_difficulty),
        ]

    def change_option(self, index: int, step: int) -> None:
        """Cycle the value of option row `index` by `step`."""
        _, key, values, _ = self.options[index]
        cfg = self.app.cfg
        current = values.index(cfg[key]) if cfg[key] in values else 0
        cfg[key] = values[(current + step) % len(values)]

    def handle_key(self, key: int) -> None:
        """Handle keyboard navigation in the main menu."""
        n_opts = len(self.options)
        if key in (pygame.K_UP, pygame.K_w):
            self.sel = (self.sel - 1) % n_opts
        elif key in (pygame.K_DOWN, pygame.K_s):
            self.sel = (self.sel + 1) % n_opts
        elif key in (pygame.K_LEFT, pygame.K_a):
            self.change_option(self.sel, -1)
        elif key in (pygame.K_RIGHT, pygame.K_d):
            self.change_option(self.sel, 1)
        elif key in (pygame.K_RETURN, pygame.K_KP_ENTER, pygame.K_SPACE):
            self.app.start_game()
        elif key == pygame.K_t:
            self.app.open_tutorial()
        elif key == pygame.K_h:
            self.app.overlay = "help"
        elif key == pygame.K_ESCAPE:
            self.app.quit()

    def handle_click(self, pos: tuple[int, int]) -> None:
        """Handle mouse clicks on menu buttons and option rows."""
        for btn in self.buttons:
            if btn.rect.collidepoint(pos):
                self.app.execute_action(btn.action)
                return
        for idx, rect in enumerate(self.rows):
            if rect.collidepoint(pos):
                self.sel = idx
                self.change_option(idx, -1 if pos[0] < rect.centerx + 60 else 1)

    def describe_selected(self) -> list[str]:
        """Return clean informational lines for the currently highlighted setting."""
        cfg = self.app.cfg
        dmap = self.app.preview_map()
        settings = self.app.preview_settings()
        shortest = self.app.preview_shortest()
        diff_desc = {
            "easy": "Mengunci pintu dan memasang tembok sangat mahal bagi penjaga, jadi ia jarang bisa menghalangimu.",
            "normal": "Blokir penjaga cukup mahal, jadi ia harus memilih kapan menghalangimu.",
            "hard": "Biaya blokir standar proposal. Penjaga sering menghalangi, pilih jalurmu dengan cermat!",
        }.get(cfg["difficulty"], "")
        return [
            f"Ukuran Peta: {dmap.w}x{dmap.h}  •  Jarak Terdekat: {shortest} langkah  •  Pintu: {len(dmap.doors)} buah",
            f"Batas Maksimal Langkah: {settings['T']} langkah  •  Biaya Penjaga: Kunci Pintu {settings['lock_cost']} • Tembok {settings['wall_cost']} Energi",
            diff_desc,
        ]

    def draw(self, surf: pygame.Surface, now_ms: int) -> None:
        """Render the complete main menu screen."""
        theme = self.app.theme
        surf.fill(COLORS["bg"])

        glow = 0.5 + 0.5 * math.sin(now_ms / 380) * math.sin(now_ms / 970 + 1)
        hero_surf = theme.f_hero.render("DUNGEON WARDEN", True, COLORS["accent"])
        for radius, alpha in ((10, 30), (5, 55)):
            hero_surf.set_alpha(int(alpha * (0.6 + 0.4 * glow)))
            for dx, dy in ((-radius, 0), (radius, 0), (0, -radius), (0, radius)):
                surf.blit(
                    hero_surf,
                    hero_surf.get_rect(midtop=(SCREEN_W // 2 + dx, 44 + dy)),
                )
        Theme.blit_text(
            surf, theme.f_hero, "DUNGEON WARDEN", "accent", (SCREEN_W // 2, 44), "midtop"
        )
        Theme.blit_text(
            surf,
            theme.f,
            "Temukan jalan menuju Harta Karun Emas sebelum sang Penjaga mengurung langkahmu!",
            "dim",
            (SCREEN_W // 2, 128),
            "midtop",
        )

        x0, y0, row_h, label_w, val_w = 100, 210, 72, 230, 360
        box_w = label_w + val_w + 80
        self.rows = []
        for idx, (label, key, _, fmt_fn) in enumerate(self.options):
            rect = pygame.Rect(x0, y0 + idx * row_h, box_w, row_h - 14)
            self.rows.append(rect)
            is_active = idx == self.sel
            pygame.draw.rect(
                surf, COLORS["card"] if is_active else COLORS["bar"], rect, border_radius=10
            )
            if is_active:
                pygame.draw.rect(surf, COLORS["accent"], rect, 2, border_radius=10)
            Theme.blit_text(
                surf,
                theme.f_b,
                label,
                "accent" if is_active else "dim",
                (rect.x + 22, rect.centery),
                "midleft",
            )
            vx = rect.x + label_w
            Theme.blit_text(
                surf, theme.f_b, "<", "text" if is_active else "faint", (vx + 10, rect.centery), "midleft"
            )
            Theme.blit_text(
                surf,
                theme.f_b,
                fmt_fn(self.app.cfg[key]),
                "text",
                (vx + 40 + val_w // 2, rect.centery),
                "center",
            )
            Theme.blit_text(
                surf,
                theme.f_b,
                ">",
                "text" if is_active else "faint",
                (vx + val_w + 64, rect.centery),
                "midright",
            )

        info_box = pygame.Rect(x0, y0 + len(self.options) * row_h + 12, box_w, 130)
        pygame.draw.rect(surf, COLORS["bar"], info_box, border_radius=10)
        pygame.draw.rect(surf, COLORS["line"], info_box, 1, border_radius=10)
        iy = info_box.y + 18
        for idx, info_line in enumerate(self.describe_selected()):
            col = "accent" if idx == 1 else ("text" if idx == 0 else "dim")
            for wrapped in Theme.wrap_text(info_line, theme.f_s, info_box.w - 36):
                Theme.blit_text(surf, theme.f_s, wrapped, col, (info_box.x + 18, iy))
                iy += 22
            iy += 4

        self._draw_preview(surf, pygame.Rect(850, 200, 310, 310))

        btn_x = x0
        for btn in self.buttons:
            btn.rect.topleft = (btn_x, 640)
            btn_x += btn.rect.w + 18
            btn.draw(surf, theme.f_b, pygame.mouse.get_pos())

        Theme.blit_text(
            surf,
            theme.f_s,
            "Atas/Bawah: Pilih  •  Kiri/Kanan: Ubah  •  Enter: Mulai  •  T: Tutorial  •  H: Panduan  •  Esc: Keluar",
            "faint",
            (SCREEN_W // 2, SCREEN_H - 26),
            "midbottom",
        )

    def _draw_preview(self, surf: pygame.Surface, box: pygame.Rect) -> None:
        theme = self.app.theme
        dmap = self.app.preview_map()
        cell_px = box.w // max(dmap.w, dmap.h)
        ox = box.x + (box.w - cell_px * dmap.w) // 2
        oy = box.y + (box.h - cell_px * dmap.h) // 2
        pygame.draw.rect(surf, COLORS["bar"], box.inflate(28, 28), border_radius=14)
        pygame.draw.rect(surf, COLORS["line"], box.inflate(28, 28), 1, border_radius=14)
        for x, y in dmap.cells:
            cell = (x, y)
            color = (
                COLORS["wall"]
                if cell in dmap.walls
                else COLORS["door"]
                if cell in dmap.doors
                else COLORS["floor"]
            )
            pygame.draw.rect(
                surf, color, (ox + x * cell_px, oy + y * cell_px, cell_px, cell_px)
            )
        for cell, col_key in ((dmap.start, "player"), (dmap.treasure, "treasure")):
            cx = ox + cell[0] * cell_px + cell_px // 2
            cy = oy + cell[1] * cell_px + cell_px // 2
            pygame.draw.circle(surf, COLORS[col_key], (cx, cy), max(3, cell_px // 2))

        Theme.blit_text(
            surf,
            theme.f_b,
            f"Peta: {format_map_name(dmap.name)} ({dmap.w}x{dmap.h})",
            "text",
            (box.centerx, box.bottom + 26),
            "midtop",
        )
        Theme.blit_text(
            surf,
            theme.f_s,
            "biru = titik awal   •   emas = harta karun   •   cokelat = pintu",
            "faint",
            (box.centerx, box.bottom + 50),
            "midtop",
        )
