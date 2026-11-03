"""The two simulated players of the evaluation (proposal 2.2) and the in-game autoplay.
Like the human, bots see walls, doors and locks, but not plates or eyes."""
from __future__ import annotations

import random

from search import astar, bfs_distances

DOOR_COST = 4       # Cautious treats a door like 4 floor tiles (doors creak)


class Rusher:
    name = "Rusher"

    def __init__(self, seed: int = 0):
        self.rng = random.Random(seed)

    def move(self, match) -> str:
        """Step along a shortest path to the treasure (BFS), ties broken at random."""
        dist = bfs_distances(match.dmap.treasure, match.dmap, match.state.blocked)
        opts = [(m, c) for m, c in match.legal_moves() if c in dist]
        best = min(dist[c] for _, c in opts)
        return self.rng.choice([m for m, c in opts if dist[c] == best])


class Cautious:
    name = "Cautious"

    def __init__(self, seed: int = 0):
        self.rng = random.Random(seed)

    def move(self, match) -> str:
        """Cheapest route when stepping through a door costs DOOR_COST (A* with a cost), so it
        prefers open corridors. Ties broken at random."""
        dmap, blocked = match.dmap, match.state.blocked
        cost = lambda c: DOOR_COST if c in dmap.doors else 1
        scored = []
        for m, c in match.legal_moves():
            path, _ = astar(c, dmap.treasure, dmap, blocked, cost)
            if path is not None:
                scored.append((m, cost(c) + sum(cost(x) for x in path[1:])))
        best = min(s for _, s in scored)
        return self.rng.choice([m for m, s in scored if s == best])


BOTS = {"rusher": Rusher, "cautious": Cautious}
