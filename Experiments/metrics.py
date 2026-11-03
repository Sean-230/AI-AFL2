"""MetricsAggregator and ReportWriter classes for experiment statistics and CSV/console output."""
from __future__ import annotations

import csv
import math
from pathlib import Path
import statistics as stats

from DungeonWarden.ai.warden_base import LOOKAHEAD_PLIES, MAX_CANDIDATE_BLOCKS


class MetricsAggregator:
    """Computes aggregated evaluation metrics (Proposal Section 2.2) from match and move records."""

    @staticmethod
    def percentile_95(values: list[float]) -> float:
        """Compute the 95th percentile of a numeric sequence."""
        if not values:
            return 0.0
        sorted_vals = sorted(values)
        idx = min(len(sorted_vals) - 1, int(0.95 * len(sorted_vals)))
        return sorted_vals[idx]

    @classmethod
    def summarize_groups(
        cls,
        games: list[dict],
        moves: list[dict],
        group_keys: list[str],
    ) -> list[dict]:
        """Group game and move records by `group_keys` and compute summary metrics."""
        rows: list[dict] = []
        unique_groups = sorted({tuple(g[k] for k in group_keys) for g in games})
        for group in unique_groups:
            group_games = [g for g in games if tuple(g[k] for k in group_keys) == group]
            group_ms = [mv["ms"] for mv in moves if tuple(mv[k] for k in group_keys) == group]
            rows.append(
                {
                    **dict(zip(group_keys, group)),
                    "games": len(group_games),
                    "player_win_rate": float(stats.mean(g["player_won"] for g in group_games)),
                    "turns": float(stats.mean(g["turns"] for g in group_games)),
                    "path_increase": float(stats.mean(g["path_increase"] for g in group_games)),
                    "belief_recall": stats.mean(g["recall"] for g in group_games),
                    "belief_precision": stats.mean(g["precision"] for g in group_games),
                    "invalid_actions": sum(g["invalid"] for g in group_games),
                    "nodes_per_move": stats.mean(g["nodes_per_move"] for g in group_games),
                    "astar_exp_per_move": stats.mean(g["astar_exp_per_move"] for g in group_games),
                    "ms_mean": stats.mean(group_ms) if group_ms else 0.0,
                    "ms_p95": cls.percentile_95(group_ms),
                    "ms_max": max(group_ms, default=0.0),
                    "astar_mismatch": sum(g["astar_mismatch"] for g in group_games),
                }
            )
        return rows

    @classmethod
    def summarize_scaling(
        cls,
        sizes: list[int],
        results: list[tuple[dict, list[dict]]],
    ) -> list[dict]:
        """Aggregate complexity scaling metrics across grid dimensions `sizes`."""
        rows: list[dict] = []
        branching = MAX_CANDIDATE_BLOCKS + 2
        for n in sizes:
            size_Moves = [
                mv for game, move_list in results if game["size"] == f"{n}x{n}" for mv in move_list
            ]
            vertices = n * n
            ms_vals = [m["ms"] for m in size_Moves]
            rows.append(
                {
                    "n": n,
                    "cells": vertices,
                    "moves": len(size_Moves),
                    "nodes_per_move": stats.mean(m["nodes"] for m in size_Moves),
                    "astar_exp_per_move": stats.mean(m["expanded"] for m in size_Moves),
                    "ms_mean": stats.mean(ms_vals),
                    "ms_p95": cls.percentile_95(ms_vals),
                    "ms_max": max(ms_vals),
                    "estimate": (branching ** (LOOKAHEAD_PLIES / 2)) * vertices * math.log2(vertices),
                    "astar_mismatch": sum(not m["astar_ok"] for m in size_Moves),
                }
            )
        return rows


class ReportWriter:
    """Handles writing CSV datasets and formatting console summary tables."""

    @staticmethod
    def write_csv(path: Path, rows: list[dict]) -> None:
        """Write a list of dictionaries to a CSV file."""
        if not rows:
            return
        with path.open("w", newline="", encoding="utf-8") as f:
            writer = csv.DictWriter(f, fieldnames=list(rows[0]))
            writer.writeheader()
            writer.writerows(rows)

    @staticmethod
    def print_summary_table(rows: list[dict], group_keys: list[str]) -> None:
        """Print an aligned ASCII summary table of Warden evaluation metrics."""
        cols = group_keys + [
            "games",
            "player_win_rate",
            "turns",
            "path_increase",
            "belief_recall",
            "belief_precision",
            "invalid_actions",
            "nodes_per_move",
            "ms_mean",
            "ms_max",
            "astar_mismatch",
        ]
        headers = {
            "player_win_rate": "p.win%",
            "path_increase": "+path",
            "belief_recall": "recall",
            "belief_precision": "prec",
            "invalid_actions": "invalid",
            "nodes_per_move": "nodes/mv",
            "ms_mean": "ms/mv",
            "ms_max": "ms max",
            "astar_mismatch": "A*≠BFS",
        }

        def fmt_cell(col: str, val: object) -> str:
            if col in ("player_win_rate", "belief_recall") and isinstance(val, (int, float)):
                return f"{100 * val:.1f}"
            return f"{val:.2f}" if isinstance(val, float) else str(val)

        table = [[headers.get(c, c) for c in cols]] + [
            [fmt_cell(c, r[c]) for c in cols] for r in rows
        ]
        widths = [max(len(row[i]) for row in table) for i in range(len(cols))]
        for idx, row in enumerate(table):
            print("  " + "  ".join(val.rjust(w) for val, w in zip(row, widths)))
            if idx == 0:
                print("  " + "  ".join("-" * w for w in widths))

    @staticmethod
    def print_scaling_table(rows: list[dict]) -> None:
        """Print an aligned ASCII summary table for grid-size scaling benchmarks."""
        print(
            f"\n  {'size':>6} {'moves':>6} {'nodes/mv':>9} {'A*exp/mv':>9} "
            f"{'ms/mv':>7} {'p95':>7} {'max':>7} {'A*≠BFS':>7}"
        )
        for r in rows:
            print(
                f"  {r['n']:>3}x{r['n']:<2} {r['moves']:>6} {r['nodes_per_move']:>9.1f} "
                f"{r['astar_exp_per_move']:>9.0f} {r['ms_mean']:>7.2f} {r['ms_p95']:>7.2f} "
                f"{r['ms_max']:>7.2f} {r['astar_mismatch']:>7}"
            )

