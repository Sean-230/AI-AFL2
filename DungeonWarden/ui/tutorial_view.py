"""TutorialView class: interactive hands-on (learn-by-playing) game tutorial in Bahasa Indonesia."""
from __future__ import annotations

from dataclasses import dataclass
import math
from typing import TYPE_CHECKING

import pygame

from DungeonWarden.ui.components import Button
from DungeonWarden.ui.theme import (
    COLORS,
    PANEL_W,
    PANEL_X,
    SCREEN_H,
    SCREEN_W,
    TOP_BAR_H,
    Theme,
)

if TYPE_CHECKING:
    from DungeonWarden.ui.app import DungeonWardenApp


@dataclass(frozen=True)
class TutorialFeature:
    """One visual feature item inside a tutorial step (icon + title + description)."""

    icon: str
    title: str
    desc: str


@dataclass(frozen=True)
class PracticeStep:
    """Data definition for one hands-on practice step in the guided tutorial."""

    title: str
    spotlight: str  # "player_treasure", "obstacles", "traps", "status", "board"
    intro: str
    features: tuple[TutorialFeature, ...]
    task_text: str
    req_moves: int


PRACTICE_STEPS: tuple[PracticeStep, ...] = (
    PracticeStep(
        title="1. Objektif & Cara Bergerak",
        spotlight="player_treasure",
        intro=(
            "Selamat datang! Kamu adalah Petualang (bola biru) di dalam ruang bawah tanah 20x20. "
            "Tutorial ini langsung SAMBIL PRAKTEK bermain di papan sebelah kiri!"
        ),
        features=(
            TutorialFeature(
                icon="treasure",
                title="Capai Harta Karun Emas",
                desc="Arahkan karaktermu ke berlian emas sebelum batas langkah di kanan atas habis.",
            ),
            TutorialFeature(
                icon="player",
                title="Gerak dengan WASD / Panah",
                desc="Tekan W, A, S, D atau Tombol Panah untuk melangkah 1 petak setiap giliran.",
            ),
            TutorialFeature(
                icon="energy",
                title="Permainan Bergiliran",
                desc="Setiap kamu melangkah 1 petak, sang Penjaga akan membalas 1 tindakan.",
            ),
        ),
        task_text="Tekan tombol W, A, S, D atau Panah untuk melangkah 2 kali menuju Harta Karun!",
        req_moves=2,
    ),
    PracticeStep(
        title="2. Rintangan Pintu & Tembok",
        spotlight="obstacles",
        intro=(
            "Saat kamu bergerak, sang Penjaga berusaha menutup jalur tercepatmu "
            "agar kamu terpaksa memutar jauh:"
        ),
        features=(
            TutorialFeature(
                icon="locked_door",
                title="Pintu Kayu & Gembok Merah",
                desc="Pintu cokelat terbuka bisa dilewati, namun pintu bergembok merah terkunci rapat.",
            ),
            TutorialFeature(
                icon="placed_wall",
                title="Tembok Bata Baru",
                desc="Penjaga dapat mengangkat tembok bata merah permanen di lantai kosong untuk memblokirmu.",
            ),
            TutorialFeature(
                icon="treasure",
                title="Selalu Ada Jalan Keluar",
                desc="Penjaga tidak bisa mengurungmu sepenuhnya—selalu ada minimal 1 jalur ke Harta Karun!",
            ),
        ),
        task_text="Melangkahlah 2 kali lagi dengan WASD dan amati rintangan yang dipasang Penjaga!",
        req_moves=2,
    ),
    PracticeStep(
        title="3. Pelat Jebakan & Area Pengintai",
        spotlight="traps",
        intro=(
            "Perhatikan kotak kuning dan mata ungu di peta! Penjaga memakai alat pemantau ini "
            "untuk mengetahui posisimu:"
        ),
        features=(
            TutorialFeature(
                icon="plate",
                title="Pelat Jebakan Lantai (Kotak Kuning)",
                desc="Jika kamu menginjak petak berbingkai kuning ini, Penjaga langsung tahu posisi pastimu!",
            ),
            TutorialFeature(
                icon="eye",
                title="Mata Pengintai & Area Biru",
                desc="Mata ungu memantau 2 petak lurus (area biru). Masuk ke area biru membuatmu terlihat!",
            ),
            TutorialFeature(
                icon="door",
                title="Suara Derit Pintu Kayu",
                desc="Melewati pintu cokelat juga menimbulkan suara yang memberi tahu Penjaga keberadaanmu.",
            ),
        ),
        task_text="Melangkahlah 3 kali dengan WASD sambil berusaha menghindari pelat kuning & area biru!",
        req_moves=3,
    ),
    PracticeStep(
        title="4. Energi Penjaga & Taktik",
        spotlight="status",
        intro=(
            "Lihat kartu STATUS PERMAINAN di kanan atas! Kunci kemenangan adalah "
            "menguras energi Penjaga lalu menerobos lorong lain:"
        ),
        features=(
            TutorialFeature(
                icon="energy",
                title="Perhatikan Energi Penjaga",
                desc="Kunci pintu butuh 2 Energi & tembok butuh 3 Energi. Jika habis, Penjaga harus rehat (+1 Energi).",
            ),
            TutorialFeature(
                icon="player",
                title="Pancing & Belok Jalur",
                desc="Jika satu lorong ditutup tembok, segera belok ke rute alternatif saat energi Penjaga menipis!",
            ),
            TutorialFeature(
                icon="treasure",
                title="Jaga Sisa Langkahmu",
                desc="Setiap kali dipaksa memutar jalan, langkahmu berkurang. Cari rute paling efisien!",
            ),
        ),
        task_text="Melangkahlah 2 kali lagi sambil perhatikan perubahan bar Energi di kanan atas!",
        req_moves=2,
    ),
    PracticeStep(
        title="5. Kontrol & Siap Bermain!",
        spotlight="board",
        intro=(
            "Luar biasa! Kamu sudah memahami tujuan permainan, fungsi jebakan & objek peta, "
            "serta strategi mengalahkan sang Penjaga."
        ),
        features=(
            TutorialFeature(
                icon="controls",
                title="Ulangi atau Menu Jeda (R / Esc)",
                desc="Tekan R untuk mengulang peta dari awal, atau Esc untuk membuka menu jeda.",
            ),
            TutorialFeature(
                icon="door",
                title="Buka Panduan Kapan Saja (T / H)",
                desc="Tekan T untuk membuka kembali tutorial praktek ini, atau H untuk ringkasan aturan.",
            ),
            TutorialFeature(
                icon="treasure",
                title="Tantang 3 Peta & 3 Tingkat Kesulitan",
                desc="Taklukkan peta Katakombe, Benteng, dan Labirin pada tingkat Mudah, Normal, hingga Sulit!",
            ),
        ),
        task_text="Melangkah 2 kali lagi atau klik 'Selesai & Main' untuk lanjut bermain bebas!",
        req_moves=2,
    ),
)


class TutorialView:
    """Manages and renders the interactive learn-by-playing tutorial card in the right HUD space."""

    def __init__(self, app: "DungeonWardenApp") -> None:
        self.app = app
        self.theme = app.theme
        self.active = False
        self.step_idx = 0
        self.step_moves = 0

        self.prev_btn = Button("< Sebelumnya", "prev", pygame.Rect(0, 0, 130, 36))
        self.next_btn = Button("Berikutnya >", "next", pygame.Rect(0, 0, 148, 36), primary=True)
        self.close_btn = Button("Lewati (T)", "close", pygame.Rect(0, 0, 104, 26))
        self.step_dot_rects: list[pygame.Rect] = []

    @property
    def steps(self) -> tuple[PracticeStep, ...]:
        """Return the practice tutorial steps."""
        return PRACTICE_STEPS

    @property
    def current_step(self) -> PracticeStep:
        """Return the active PracticeStep."""
        return self.steps[self.step_idx]

    def start(self) -> None:
        """Start or restart the interactive practice tutorial from Step 1."""
        self.active = True
        self.step_idx = 0
        self.step_moves = 0

    def stop(self) -> None:
        """Close the practice tutorial overlay so the user plays freely."""
        self.active = False

    def _go_to_step(self, idx: int) -> None:
        if idx >= len(self.steps):
            self.stop()
            return
        self.step_idx = max(0, idx)
        self.step_moves = 0

    def on_player_moved(self) -> None:
        """Called by GameSession whenever the player makes a valid move during gameplay."""
        if not self.active:
            return
        self.step_moves += 1
        if self.step_moves >= self.current_step.req_moves:
            self._go_to_step(self.step_idx + 1)

    def handle_key(self, key: int) -> bool:
        """Handle tutorial-specific keys; return False for game keys (WASD, etc.) so GameSession processes them."""
        if not self.active:
            return False
        if key in (pygame.K_PAGEUP, pygame.K_LEFTBRACKET):
            self._go_to_step(self.step_idx - 1)
            return True
        if key in (pygame.K_PAGEDOWN, pygame.K_RIGHTBRACKET):
            self._go_to_step(self.step_idx + 1)
            return True
        if pygame.K_1 <= key <= pygame.K_5:
            self._go_to_step(key - pygame.K_1)
            return True
        return False

    def handle_click(self, pos: tuple[int, int]) -> bool:
        """Handle mouse clicks on the tutorial coach card; return True if consumed."""
        if not self.active:
            return False
        if self.close_btn.rect.collidepoint(pos):
            self.stop()
            return True
        if self.step_idx > 0 and self.prev_btn.rect.collidepoint(pos):
            self._go_to_step(self.step_idx - 1)
            return True
        if self.next_btn.rect.collidepoint(pos):
            self._go_to_step(self.step_idx + 1)
            return True
        for idx, dot_rect in enumerate(self.step_dot_rects):
            if dot_rect.collidepoint(pos):
                self._go_to_step(idx)
                return True
        return False

    def draw(self, surf: pygame.Surface, now_ms: int) -> None:
        """Render non-blocking spotlight highlights on the board and the practice card in the right HUD."""
        if not self.active or self.app.session is None:
            return
        self._draw_highlights(surf, now_ms)
        card = pygame.Rect(PANEL_X, 206, PANEL_W, 548)
        self._draw_card(surf, card, self.current_step)

    def _draw_highlights(self, surf: pygame.Surface, now_ms: int) -> None:
        """Draw glowing amber highlight borders around the elements relevant to the current step."""
        session = self.app.session
        if session is None:
            return
        bv = session.board_view
        pulse = 0.5 + 0.5 * math.sin(now_ms / 220)
        glow_col = (255, int(175 + 50 * pulse), int(65 + 55 * pulse))
        target = self.current_step.spotlight

        if target == "player_treasure":
            p_rect = bv.cell_rect(session.match.player).inflate(14, 14)
            t_rect = bv.cell_rect(session.dmap.treasure).inflate(16, 16)
            pygame.draw.rect(surf, glow_col, p_rect, 3, border_radius=8)
            pygame.draw.rect(surf, glow_col, t_rect, 3, border_radius=8)
            self._draw_tag(surf, "KAMU (WASD)", (p_rect.centerx, p_rect.top - 10), glow_col)
            self._draw_tag(surf, "HARTA KARUN", (t_rect.centerx, t_rect.top - 10), glow_col)

        elif target == "obstacles":
            for c in session.match.state.walls - session.dmap.walls:
                pygame.draw.rect(surf, glow_col, bv.cell_rect(c).inflate(8, 8), 2, border_radius=5)
            for c in session.match.state.locked:
                pygame.draw.rect(surf, glow_col, bv.cell_rect(c).inflate(8, 8), 2, border_radius=5)

        elif target == "traps":
            for c in session.dmap.plates:
                pygame.draw.rect(surf, glow_col, bv.cell_rect(c).inflate(8, 8), 2, border_radius=5)
            for c in session.dmap.eyes:
                pygame.draw.rect(surf, glow_col, bv.cell_rect(c).inflate(8, 8), 2, border_radius=5)

        elif target == "status":
            status_rect = pygame.Rect(PANEL_X, TOP_BAR_H + 8, PANEL_W, 128)
            pygame.draw.rect(surf, glow_col, status_rect, 3, border_radius=12)

        elif target == "board":
            pygame.draw.rect(surf, glow_col, bv.grid.inflate(10, 10), 2, border_radius=8)

    def _draw_tag(
        self,
        surf: pygame.Surface,
        text: str,
        midbottom: tuple[int, int],
        bg_color: tuple[int, int, int],
    ) -> None:
        rendered = self.theme.f_s.render(text, True, COLORS["bg"])
        rect = rendered.get_rect(midbottom=midbottom).inflate(12, 4)
        rect.clamp_ip(pygame.Rect(4, TOP_BAR_H + 4, SCREEN_W - 8, SCREEN_H - TOP_BAR_H - 8))
        pygame.draw.rect(surf, bg_color, rect, border_radius=5)
        surf.blit(rendered, rendered.get_rect(center=rect.center))

    def _draw_card(
        self,
        surf: pygame.Surface,
        card: pygame.Rect,
        step: PracticeStep,
    ) -> None:
        """Render the tutorial coach card inside `card` (y = 206..754) with strict non-overlapping slots."""
        theme = self.theme
        mouse_pos = pygame.mouse.get_pos()

        pygame.draw.rect(surf, COLORS["card"], card, border_radius=12)
        pygame.draw.rect(surf, COLORS["accent"], card, 2, border_radius=12)

        pad_x = 18
        inner_w = card.w - pad_x * 2
        y = card.y + 12

        badge_str = f"TUTORIAL PRAKTEK  •  TAHAP {self.step_idx + 1} / {len(self.steps)}"
        Theme.blit_text(surf, theme.f_b, badge_str, "accent", (card.x + pad_x, y + 3))

        self.close_btn.rect.topright = (card.right - pad_x, y)
        self.close_btn.draw(surf, theme.f_s, mouse_pos)

        y += 32
        pygame.draw.line(surf, COLORS["line"], (card.x + pad_x, y), (card.right - pad_x, y), 1)
        y += 10

        Theme.blit_text(surf, theme.f_title, step.title, "text", (card.x + pad_x, y))
        y += 28

        for line in Theme.wrap_text(step.intro, theme.f_s, inner_w)[:2]:
            Theme.blit_text(surf, theme.f_s, line, "dim", (card.x + pad_x, y))
            y += 18
        y += 8

        item_h = 66
        item_gap = 8
        for feat in step.features:
            item_rect = pygame.Rect(card.x + pad_x, y, inner_w, item_h)
            pygame.draw.rect(surf, COLORS["bar"], item_rect, border_radius=10)
            pygame.draw.rect(surf, COLORS["line"], item_rect, 1, border_radius=10)

            icon_box = pygame.Rect(item_rect.x + 12, item_rect.centery - 20, 40, 40)
            pygame.draw.rect(surf, COLORS["card"], icon_box, border_radius=8)
            pygame.draw.rect(surf, COLORS["line_hi"], icon_box, 1, border_radius=8)
            self._draw_feature_icon(surf, feat.icon, icon_box)

            tx = icon_box.right + 14
            tw = item_rect.right - tx - 12
            Theme.blit_text(surf, theme.f_b, feat.title, "accent", (tx, item_rect.y + 7))
            desc_lines = Theme.wrap_text(feat.desc, theme.f_s, tw)[:2]
            for l_idx, d_line in enumerate(desc_lines):
                Theme.blit_text(
                    surf, theme.f_s, d_line, "text", (tx, item_rect.y + 28 + l_idx * 17)
                )
            y += item_h + item_gap

        self._draw_practice_box(surf, card, pad_x, inner_w, step)
        self._draw_footer(surf, card, pad_x, mouse_pos)

    def _draw_practice_box(
        self,
        surf: pygame.Surface,
        card: pygame.Rect,
        pad_x: int,
        inner_w: int,
        step: PracticeStep,
    ) -> None:
        """Render the interactive practice task banner and progress bar in a dedicated 100px slot."""
        theme = self.theme
        task_rect = pygame.Rect(card.x + pad_x, card.bottom - 158, inner_w, 100)
        pygame.draw.rect(surf, COLORS["bar"], task_rect, border_radius=10)
        pygame.draw.rect(surf, COLORS["good"], task_rect, 2, border_radius=10)

        Theme.blit_text(
            surf, theme.f_b, "MISI PRAKTEK SEKARANG:", "good", (task_rect.x + 14, task_rect.y + 8)
        )

        task_lines = Theme.wrap_text(step.task_text, theme.f_s, inner_w - 28)[:2]
        for l_idx, t_line in enumerate(task_lines):
            Theme.blit_text(
                surf,
                theme.f_s,
                t_line,
                "text",
                (task_rect.x + 14, task_rect.y + 32 + l_idx * 17),
            )

        done_units = min(step.req_moves, self.step_moves)
        total_units = max(1, step.req_moves)
        prog_label = f"{done_units} / {total_units} langkah"

        bar_x = task_rect.x + 14
        bar_y = task_rect.bottom - 20
        bar_w = inner_w - 150
        pygame.draw.rect(surf, COLORS["card"], (bar_x, bar_y, bar_w, 10), border_radius=5)
        fill_w = int(bar_w * min(1.0, done_units / total_units))
        if fill_w > 0:
            pygame.draw.rect(surf, COLORS["good"], (bar_x, bar_y, fill_w, 10), border_radius=5)
        Theme.blit_text(
            surf, theme.f_b, prog_label, "good", (task_rect.right - 14, bar_y - 4), "topright"
        )

    def _draw_footer(
        self,
        surf: pygame.Surface,
        card: pygame.Rect,
        pad_x: int,
        mouse_pos: tuple[int, int],
    ) -> None:
        """Render step dots and manual Previous / Next buttons at the bottom of the card."""
        theme = self.theme
        btn_y = card.bottom - 46

        self.prev_btn.label = "< Sebelumnya"
        self.prev_btn.rect.topleft = (card.x + pad_x, btn_y)
        if self.step_idx > 0:
            self.prev_btn.draw(surf, theme.f_s, mouse_pos)

        dots_y = btn_y + 18
        n_steps = len(self.steps)
        dot_spacing = 24
        start_x = card.centerx - ((n_steps - 1) * dot_spacing) // 2
        self.step_dot_rects = []
        for idx in range(n_steps):
            cx = start_x + idx * dot_spacing
            rect = pygame.Rect(cx - 8, dots_y - 8, 16, 16)
            self.step_dot_rects.append(rect)
            is_cur = idx == self.step_idx
            is_done = idx < self.step_idx
            radius = 6 if is_cur else 4
            color = (
                COLORS["accent"]
                if is_cur
                else COLORS["good"]
                if is_done
                else COLORS["line_hi"]
            )
            pygame.draw.circle(surf, color, (cx, dots_y), radius)

        is_last = self.step_idx == len(self.steps) - 1
        self.next_btn.label = "Selesai & Main" if is_last else "Berikutnya >"
        self.next_btn.rect.topright = (card.right - pad_x, btn_y)
        self.next_btn.draw(surf, theme.f_s, mouse_pos)

    def _draw_feature_icon(
        self,
        surf: pygame.Surface,
        kind: str,
        box: pygame.Rect,
    ) -> None:
        """Render a miniature game sprite or visual diagram inside `box`."""
        cx, cy = box.center
        if kind == "player":
            pygame.draw.circle(surf, (*COLORS["player"], 70), (cx, cy), 14)
            pygame.draw.circle(surf, COLORS["player"], (cx, cy), 9)
            pygame.draw.circle(surf, COLORS["player_hi"], (cx, cy), 9, 2)
        elif kind == "treasure":
            pts = [(cx, cy - 11), (cx + 11, cy), (cx, cy + 11), (cx - 11, cy)]
            pygame.draw.polygon(surf, COLORS["treasure"], pts)
            pygame.draw.polygon(surf, COLORS["treasure_hi"], pts, 2)
        elif kind in ("door", "locked_door"):
            r = box.inflate(-12, -12)
            pygame.draw.rect(surf, COLORS["door"], r, border_radius=3)
            for i in (1, 2):
                lx = r.x + r.w * i // 3
                pygame.draw.line(surf, COLORS["door_hi"], (lx, r.y + 2), (lx, r.bottom - 2), 1)
            if kind == "locked_door":
                pygame.draw.rect(surf, COLORS["locked"], r, 2, border_radius=3)
                lock_body = pygame.Rect(cx - 5, cy - 1, 10, 8)
                pygame.draw.rect(surf, COLORS["locked"], lock_body, border_radius=2)
                pygame.draw.arc(
                    surf, COLORS["locked"], pygame.Rect(cx - 4, cy - 7, 8, 8), 0, 3.14, 2
                )
        elif kind == "placed_wall":
            r = box.inflate(-12, -12)
            pygame.draw.rect(surf, COLORS["placed"], r, border_radius=2)
            pygame.draw.rect(surf, COLORS["placed_top"], (r.x, r.y, r.w, 5))
            pygame.draw.line(surf, COLORS["wall_shadow"], (r.x, cy), (r.right, cy), 2)
            pygame.draw.line(surf, COLORS["wall_shadow"], (cx, r.y + 5), (cx, cy), 2)
        elif kind == "plate":
            r = box.inflate(-10, -10)
            pygame.draw.rect(surf, COLORS["floor"], r, border_radius=3)
            pygame.draw.rect(surf, COLORS["plate"], r.inflate(-6, -6), 2, border_radius=3)
        elif kind == "eye":
            sight_r = pygame.Rect(cx + 2, cy - 6, 15, 12)
            pygame.draw.rect(surf, (*COLORS["sight"], 90), sight_r, border_radius=2)
            er = pygame.Rect(cx - 12, cy - 7, 20, 14)
            pygame.draw.ellipse(surf, COLORS["eye"], er, 2)
            pygame.draw.circle(surf, COLORS["eye"], er.center, 3)
        elif kind == "energy":
            bar1 = pygame.Rect(box.x + 6, cy - 7, box.w - 12, 6)
            bar2 = pygame.Rect(box.x + 6, cy + 3, box.w - 12, 6)
            pygame.draw.rect(surf, COLORS["card"], bar1, border_radius=3)
            pygame.draw.rect(surf, COLORS["sight"], (bar1.x, bar1.y, int(bar1.w * 0.65), bar1.h), border_radius=3)
            pygame.draw.rect(surf, COLORS["card"], bar2, border_radius=3)
            pygame.draw.rect(surf, COLORS["accent"], (bar2.x, bar2.y, int(bar2.w * 0.8), bar2.h), border_radius=3)
        elif kind == "controls":
            for dx, dy in ((0, -6), (-10, 5), (0, 5), (10, 5)):
                kr = pygame.Rect(cx + dx - 4, cy + dy - 4, 9, 9)
                pygame.draw.rect(surf, COLORS["line_hi"], kr, border_radius=2)
