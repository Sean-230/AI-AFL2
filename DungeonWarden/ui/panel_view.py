"""ReasoningPanelView class: renders the top game header and right-hand player HUD."""
from __future__ import annotations

from typing import TYPE_CHECKING

import pygame

from DungeonWarden.ai.pathfinder import Pathfinder
from DungeonWarden.core.action_schema import StripsActionSchema
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
    """Renders the top game header bar, clean player HUD cards, and live AI Reasoning cards."""

    def __init__(self, theme: Theme) -> None:
        self.theme = theme

    def draw_top_bar(
        self,
        surf: pygame.Surface,
        match: "MatchEngine",
        difficulty: str,
        show_belief: bool = False,
    ) -> None:
        """Render the top application header bar without overlapping chips and shortcuts."""
        theme = self.theme
        dmap = match.dmap
        pygame.draw.rect(surf, COLORS["bar"], (0, 0, SCREEN_W, TOP_BAR_H))
        pygame.draw.line(surf, COLORS["line"], (0, TOP_BAR_H), (SCREEN_W, TOP_BAR_H), 2)
        title_rect = Theme.blit_text(
            surf, theme.f_title, "DUNGEON WARDEN", "accent", (MARGIN, TOP_BAR_H // 2), "midleft"
        )

        x = title_rect.right + 16
        diff_color = {"easy": "good", "normal": "accent", "hard": "bad"}[difficulty]
        chips: list[tuple[str, str]] = [
            (f"Peta: {format_map_name(dmap.name)}", "text"),
            (f"Kesulitan: {format_difficulty(difficulty)}", diff_color),
        ]
        if show_belief:
            chips.append(("Otak AI (B): Aktif", "belief"))

        for label, color_key in chips:
            rendered = theme.f_s.render(label, True, COLORS[color_key])
            chip = pygame.Rect(x, TOP_BAR_H // 2 - 14, rendered.get_width() + 20, 28)
            pygame.draw.rect(surf, COLORS["card"], chip, border_radius=14)
            pygame.draw.rect(surf, COLORS["line_hi"], chip, 1, border_radius=14)
            surf.blit(rendered, rendered.get_rect(center=chip.center))
            x = chip.right + 8

        shortcuts = "WASD: Jalan  •  B: Otak AI  •  T: Tutorial  •  H: Panduan  •  R: Ulangi  •  Esc: Menu"
        Theme.blit_text(
            surf,
            theme.f_s,
            shortcuts,
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
        show_belief: bool = False,
    ) -> None:
        """Render the right-side panel (either Player HUD or AI Reasoning View when B is toggled)."""
        self._draw_status_card(surf, match)
        if tutorial_active:
            return
        if show_belief:
            self._draw_kb_reasoning_card(surf, match)
            self._draw_minimax_card(surf, match)
        else:
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

    def _draw_kb_reasoning_card(self, surf: pygame.Surface, match: "MatchEngine") -> None:
        """Render the First-Order Logic (FOL) belief set B_t and sensor percepts card (y = 206..388)."""
        theme = self.theme
        card = pygame.Rect(PANEL_X, 206, PANEL_W, 182)
        pygame.draw.rect(surf, COLORS["card"], card, border_radius=12)
        pygame.draw.rect(surf, COLORS["line"], card, 1, border_radius=12)

        px = card.x + 18
        pw = card.w - 36
        y = card.y + 12

        Theme.blit_text(surf, theme.f_b, "1. PENALARAN FOL & BELIEF SET (B_t)", "accent", (px, y))
        b_size = len(match.kb.belief)
        in_b = match.player in match.kb.belief
        Theme.blit_text(
            surf,
            theme.f_b,
            f"|B_t| = {b_size} petak ({'Akurat' if in_b else 'Meleset'})",
            "good" if in_b else "bad",
            (px + pw, y),
            "topright",
        )
        y += 25

        p = match.percept
        if p is None:
            percept_str = "Sensor: Menunggu langkah pertama pemain..."
        else:
            step_s = f"({p.stepped[0]},{p.stepped[1]})" if p.stepped else "-"
            noise_s = f"({p.noise[0]},{p.noise[1]})" if p.noise else "-"
            seen_s = f"({p.seen[0]},{p.seen[1]})" if p.seen else "-"
            percept_str = (
                f"Pelat: {step_s}  •  Suara Pintu: {noise_s}  •  "
                f"Terlihat: {seen_s} ({len(p.sight)} dipantau)"
            )
        Theme.blit_text(surf, theme.f_s, percept_str, "text", (px, y))
        y += 22
        pygame.draw.line(surf, COLORS["line"], (px, y), (px + pw, y), 1)
        y += 7

        if not match.kb.log:
            Theme.blit_text(
                surf,
                theme.f_s,
                "B_0 = {titik awal}. Melangkahlah untuk melihat inferensi aturan R1–R4.",
                "dim",
                (px, y),
            )
        else:
            for inf in match.kb.log[:4]:
                badge_col = "accent" if inf.before != inf.after else "dim"
                Theme.blit_text(surf, theme.f_b, f"[{inf.rule}]", badge_col, (px, y))
                Theme.blit_text(surf, theme.f_s, inf.text[:44], "text", (px + 46, y + 1))
                Theme.blit_text(
                    surf,
                    theme.f_s,
                    f"|B| {inf.before} → {inf.after}",
                    "good" if inf.after < inf.before else "dim",
                    (px + pw, y + 1),
                    "topright",
                )
                y += 23

    def _draw_minimax_card(self, surf: pygame.Surface, match: "MatchEngine") -> None:
        """Render the A*, STRIPS, and 3-ply Minimax Alpha-Beta decision card (y = 396..588)."""
        theme = self.theme
        card = pygame.Rect(PANEL_X, 396, PANEL_W, 192)
        pygame.draw.rect(surf, COLORS["card"], card, border_radius=12)
        pygame.draw.rect(surf, COLORS["line"], card, 1, border_radius=12)

        px = card.x + 18
        pw = card.w - 36
        y = card.y + 12

        Theme.blit_text(surf, theme.f_b, "2. KEPUTUSAN MINIMAX + ALPHA-BETA", "accent", (px, y))
        dec = match.decision
        if dec is None:
            Theme.blit_text(surf, theme.f_s, "Belum ada keputusan", "dim", (px + pw, y + 2), "topright")
            Theme.blit_text(
                surf,
                theme.f_s,
                "Warden akan mengevaluasi kandidat aksi STRIPS setelah kamu bergerak.",
                "dim",
                (px, y + 32),
            )
            return

        act_str = StripsActionSchema.format_action(dec.action)
        act_col = "bad" if dec.note.startswith("INVALID") else "good"
        Theme.blit_text(surf, theme.f_b, f"Aksi: {act_str}", act_col, (px + pw, y), "topright")
        y += 24

        route_steps = len(dec.route) - 1 if dec.route else "?"
        assumed_str = f"({dec.assumed[0]},{dec.assumed[1]})" if dec.assumed else "-"
        val_str = f"{dec.value:.1f}" if dec.value is not None else "-"
        meta_line = (
            f"Asumsi: {assumed_str} (rute A*: {route_steps})  •  "
            f"Skor: {val_str}  •  Nodes: {dec.nodes}  •  A* Exp: {dec.expanded}  •  {dec.ms:.1f} ms"
        )
        Theme.blit_text(surf, theme.f_s, meta_line, "dim", (px, y))
        y += 22

        if dec.scored:
            vals = [v for _, v, _ in dec.scored]
            lo, hi = min(vals), max(vals)
            for action, val, exact in sorted(dec.scored, key=lambda item: -item[1])[:5]:
                chosen = action == dec.action
                ratio = 1.0 if hi == lo else (val - lo) / (hi - lo)
                bx = px + 150
                bw = pw - 150 - 62
                pygame.draw.rect(surf, COLORS["bar"], (bx, y + 3, bw, 10), border_radius=5)
                fill_w = max(4, int(bw * (0.15 + 0.85 * ratio)))
                pygame.draw.rect(
                    surf,
                    COLORS["accent" if chosen else "line_hi"],
                    (bx, y + 3, fill_w, 10),
                    border_radius=5,
                )
                prefix = "> " if chosen else "  "
                Theme.blit_text(
                    surf,
                    theme.f_s,
                    prefix + StripsActionSchema.format_action(action),
                    "accent" if chosen else "text",
                    (px, y),
                )
                bound_prefix = "" if exact else "≤"
                Theme.blit_text(
                    surf,
                    theme.f_s,
                    f"{bound_prefix}{val:.1f}",
                    "accent" if chosen else "dim",
                    (px + pw, y),
                    "topright",
                )
                y += 19
            Theme.blit_text(
                surf,
                theme.f_s,
                "Tanda ≤ : cabang dipangkas Alpha-Beta Pruning (batas atas)",
                "faint",
                (px, card.bottom - 20),
            )

