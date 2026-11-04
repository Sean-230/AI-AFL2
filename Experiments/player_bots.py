"""Concrete simulated players used only to evaluate the Warden (Proposal Section 2.2): Rusher and Cautious.

Both subclass the game's abstract BasePlayerBot (DungeonWarden/ai/player_base.py).
"""
from __future__ import annotations

from typing import TYPE_CHECKING

from DungeonWarden.ai.pathfinder import Pathfinder
from DungeonWarden.ai.player_base import BasePlayerBot

if TYPE_CHECKING:
    from DungeonWarden.core.match_engine import MatchEngine

DOOR_PENALTY_COST = 4


class RusherBot(BasePlayerBot):
    """Simulated player that always takes a shortest path (BFS) regardless of doors."""

    name = "Rusher"

    def move(self, match: "MatchEngine") -> str:
        dist = Pathfinder.bfs_distances(
            match.dmap.treasure, match.dmap, match.state.blocked
        )
        options = [(direction, cell) for direction, cell in match.legal_moves() if cell in dist]
        best_dist = min(dist[cell] for _, cell in options)
        best_dirs = [direction for direction, cell in options if dist[cell] == best_dist]
        return self.rng.choice(best_dirs)


class CautiousBot(BasePlayerBot):
    """Simulated player that penalizes doors (cost=4) using weighted A* to avoid door noise."""

    name = "Cautious"

    def move(self, match: "MatchEngine") -> str:
        dmap = match.dmap
        blocked = match.state.blocked

        def step_cost(cell: tuple[int, int]) -> int:
            return DOOR_PENALTY_COST if cell in dmap.doors else 1

        scored: list[tuple[str, int]] = []
        for direction, cell in match.legal_moves():
            path, _ = Pathfinder.astar(cell, dmap.treasure, dmap, blocked, step_cost)
            if path is not None:
                total_cost = step_cost(cell) + sum(step_cost(x) for x in path[1:])
                scored.append((direction, total_cost))

        best_cost = min(score for _, score in scored)
        best_dirs = [direction for direction, score in scored if score == best_cost]
        return self.rng.choice(best_dirs)


BOTS: dict[str, type[BasePlayerBot]] = {
    "rusher": RusherBot,
    "cautious": CautiousBot,
}
