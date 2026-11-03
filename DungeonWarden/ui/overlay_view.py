"""OverlayView class: renders Pause, Game Guide, and Game Over modal overlays."""
from __future__ import annotations

from typing import TYPE_CHECKING

import pygame

from DungeonWarden.ui.components import Button
from DungeonWarden.ui.theme import COLORS, SCREEN_H, SCREEN_W, Theme

if TYPE_CHECKING:
    from DungeonWarden.core.match_engine import MatchEngine


class OverlayView:
    """Renders modal overlays (Pause menu, How-to-Play guide, and Game Over summary)."""

    def __init__(self, theme: Theme) -> None:
        self.theme = theme
        self.pause_buttons: list[Button] = []
        self.over_buttons: list[Button] = [
            Button("Main Lagi", "restart", pygame.Rect(0, 0, 165, 46), primary=True),
            Button("Peta Berikutnya", "next", pygame.Rect(0, 0, 185, 46)),
            Button("Menu Utama", "menu", pygame.Rect(0, 0, 145, 46)),
        ]

    def draw_game_over(
        self,
        surf: pygame.Surface,
        grid_rect: pygame.Rect,
        match: "MatchEngine",
    ) -> None:
        """Render the end-of-match summary overlay on top of the dungeon board."""
        theme = self.theme
        veil = pygame.Surface(grid_rect.size, pygame.SRCALPHA)
        veil.fill((10, 8, 14, 215))
        surf.blit(veil, grid_rect.topleft)

        won = match.winner == "player"
        cx, cy = grid_rect.centerx, grid_rect.centery
        Theme.blit_text(
            surf,
            theme.f_hero_s,
            "HARTA KARUN DITEMUKAN!" if won else "KEHABISAN LANGKAH!",
            "good" if won else "bad",
            (cx, cy - 95),
            "center",
        )
        limit_str = f" dari {match.T}" if match.T else ""
        placed_walls = len(match.state.walls - match.dmap.walls)
        locked_doors = len(match.state.locked)
        lines = [
            f"Total langkah digunakan: {match.state.turn}{limit_str} langkah",
            f"Jarak terpendek awal: {match.original_len} langkah  (Rute memutar: +{match.path_increase()} langkah)",
            f"Rintangan di peta: {placed_walls} tembok baru  •  {locked_doors} pintu terkunci",
        ]
        for idx, line in enumerate(lines):
            Theme.blit_text(surf, theme.f, line, "text", (cx, cy - 36 + idx * 28), "center")

        total_w = sum(b.rect.w for b in self.over_buttons) + 16 * (len(self.over_buttons) - 1)
        bx = cx - total_w // 2
        mouse_pos = pygame.mouse.get_pos()
        for btn in self.over_buttons:
            btn.rect.topleft = (bx, cy + 58)
            bx += btn.rect.w + 16
            btn.draw(surf, theme.f_b, mouse_pos)

        Theme.blit_text(
            surf,
            theme.f_s,
            "R: Main lagi   •   N: Peta berikutnya   •   M: Menu utama",
            "faint",
            (cx, cy + 124),
            "center",
        )

    def draw_modal(self, surf: pygame.Surface, mode: str) -> None:
        """Render either the 'pause' modal or the 'help' modal over the entire screen."""
        theme = self.theme
        veil = pygame.Surface((SCREEN_W, SCREEN_H), pygame.SRCALPHA)
        veil.fill((8, 6, 12, 200))
        surf.blit(veil, (0, 0))

        if mode == "pause":
            box = pygame.Rect(0, 0, 360, 390)
            box.center = (SCREEN_W // 2, SCREEN_H // 2)
            pygame.draw.rect(surf, COLORS["panel"], box, border_radius=16)
            pygame.draw.rect(surf, COLORS["accent"], box, 2, border_radius=16)
            Theme.blit_text(surf, theme.f_hero_s, "Jeda Permainan", "accent", (box.centerx, box.y + 24), "midtop")
            self.pause_buttons = []
            items = (
                ("Lanjutkan", "resume"),
                ("Tutorial Praktek", "tutorial"),
                ("Ulangi Peta", "restart"),
                ("Menu Utama", "menu"),
                ("Keluar", "quit"),
            )
            mouse_pos = pygame.mouse.get_pos()
            for idx, (label, action) in enumerate(items):
                btn = Button(
                    label,
                    action,
                    pygame.Rect(box.x + 60, box.y + 94 + idx * 54, 240, 44),
                    primary=(idx == 0),
                )
                btn.draw(surf, theme.f_b, mouse_pos)
                self.pause_buttons.append(btn)

        elif mode == "help":
            box = pygame.Rect(70, 50, SCREEN_W - 140, SCREEN_H - 100)
            pygame.draw.rect(surf, COLORS["panel"], box, border_radius=16)
            pygame.draw.rect(surf, COLORS["accent"], box, 2, border_radius=16)
            Theme.blit_text(surf, theme.f_hero_s, "Panduan Bermain", "accent", (box.x + 36, box.y + 24))
            pygame.draw.line(
                surf,
                COLORS["line"],
                (box.x + 36, box.y + 78),
                (box.right - 36, box.y + 78),
                1,
            )

            col_w = box.w // 2 - 56
            x1 = box.x + 36
            y = box.y + 96
            Theme.blit_text(surf, theme.f_b, "ATURAN & OBJEKTIF PERMAINAN", "accent", (x1, y))
            y += 30
            paragraphs = (
                "Tujuan utamamu adalah mengarahkan Petualang (bola biru) menuju Harta Karun (berlian emas) "
                "di dalam peta berukuran 20x20.",
                "Permainan berjalan secara bergiliran. Setiap kali kamu melangkah 1 petak, "
                "sang Penjaga (Warden) akan mengambil 1 tindakan balasan.",
                "Penjaga dapat mengunci pintu kayu dan mengangkat tembok batu baru untuk menutup jalurmu, "
                "tetapi ia tidak pernah bisa mengurungmu sepenuhnya—selalu ada jalan terbuka menuju Harta Karun.",
                "Kamu menang jika berhasil menginjak Harta Karun sebelum batas langkah habis!",
            )
            for para in paragraphs:
                for line in Theme.wrap_text(para, theme.f_s, col_w):
                    Theme.blit_text(surf, theme.f_s, line, "text", (x1, y))
                    y += 20
                y += 10

            y += 10
            Theme.blit_text(surf, theme.f_b, "KONTROL KEYBOARD", "accent", (x1, y))
            y += 28
            shortcuts = (
                ("W, A, S, D / Panah", "Melangkah 1 petak (Atas, Kiri, Bawah, Kanan)"),
                ("T", "Membuka / menutup Tutorial Sambil Praktek"),
                ("H", "Membuka / menutup layar Panduan ini"),
                ("R", "Mengulang peta saat ini dari awal"),
                ("Esc", "Membuka menu Jeda Permainan"),
            )
            for key_label, desc in shortcuts:
                Theme.blit_text(surf, theme.f_b, key_label, "text", (x1, y))
                Theme.blit_text(surf, theme.f_s, desc, "dim", (x1 + 190, y + 2))
                y += 26

            x2 = box.centerx + 20
            y2 = box.y + 96
            Theme.blit_text(surf, theme.f_b, "TIPS & STRATEGI MENGALAHKAN WARDEN", "accent", (x2, y2))
            y2 += 30
            tips = (
                (
                    "1. Perhatikan Energi Warden",
                    "Mengunci pintu dan mengangkat tembok membutuhkan Energi (biayanya tergantung tingkat kesulitan, "
                    "lihat panel Status). Saat energi Warden tidak cukup, ia harus beristirahat (+1 Energi). "
                    "Gunakan momen itu untuk menerobos!",
                ),
                (
                    "2. Hindari Pelat Jebakan & Area Mata Pengintai",
                    "Menginjak pelat jebakan kuning, melewati pintu kayu, atau masuk ke area biru Mata Pengintai "
                    "akan membuat Penjaga langsung mengetahui keberadaanmu dan menutup jalur di depanmu.",
                ),
                (
                    "3. Pancing & Putar Haluan",
                    "Jika sebuah lorong utama mulai ditutup tembok atau pintunya dikunci, jangan memaksakan diri. "
                    "Segera berpindah ke lorong alternatif saat energi Warden sudah terkuras!",
                ),
                (
                    "4. Kelola Sisa Langkahmu",
                    "Setiap rintangan dari Warden bertujuan memaksamu memutar jalan. Selalu cek sisa langkah "
                    "di panel kanan atas agar tidak kehabisan waktu!",
                ),
            )
            for title, body in tips:
                card_r = pygame.Rect(x2, y2, col_w, 110)
                pygame.draw.rect(surf, COLORS["card"], card_r, border_radius=10)
                pygame.draw.rect(surf, COLORS["line"], card_r, 1, border_radius=10)
                Theme.blit_text(surf, theme.f_b, title, "good", (card_r.x + 14, card_r.y + 10))
                ty = card_r.y + 34
                for line in Theme.wrap_text(body, theme.f_s, col_w - 28)[:3]:
                    Theme.blit_text(surf, theme.f_s, line, "text", (card_r.x + 14, ty))
                    ty += 19
                y2 += 122

            Theme.blit_text(
                surf,
                theme.f_s,
                "Tekan T untuk Tutorial Praktek   •   Tekan H, Enter, atau Esc untuk menutup",
                "faint",
                (box.centerx, box.bottom - 22),
                "center",
            )
