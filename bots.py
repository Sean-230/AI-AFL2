"""Simulated players for the experiments (and the in-game autoplay).
Like the human, bots see walls, doors and locks, but not plates or eyes."""
from __future__ import annotations

import random

from search import RouteCache, dijkstra_to
from world import tick

DOOR_COST = 4       # Cautious treats a door like 4 floor tiles (doors creak)
HESITATE = 0.10     # Cautious sometimes stops to listen


class Rusher:
    name = "Rusher"

    def __init__(self, seed: int = 0):
        self.rng = random.Random(seed)
        self.routes = None

    def move(self, match) -> str:
        """Take the move that reaches the treasure in the fewest turns, ties broken at random.
        A door that reopens soon is worth waiting at, so it doesn't always detour."""
        if self.routes is None or self.routes.dmap is not match.dmap:
            self.routes = RouteCache(match.dmap)
        after = tick(match.state)
        opts = [(m, self.routes.length(c, after)) for m, c in match.legal_moves()]
        opts = [(m, t) for m, t in opts if t is not None]
        if not opts:
            return "wait"
        best = min(t for _, t in opts)
        return self.rng.choice([m for m, t in opts if t == best])


class Cautious:
    name = "Cautious"

    def __init__(self, seed: int = 0):
        self.rng = random.Random(seed)

    def move(self, match) -> str:
        """Cheapest path when doors cost extra (plus the wait if locked), and an occasional pause."""
        dmap = match.dmap
        if self.rng.random() < HESITATE and match.rules.player_can_wait:
            return "wait"
        after = tick(match.state)
        cost = lambda c: DOOR_COST + after.lock_left(c) if c in dmap.doors else 1
        dist = dijkstra_to(dmap.treasure, dmap, after.walls, cost)
        # waiting costs one turn and keeps the position; moving costs entering the next cell
        score = lambda m, c: 1 + dist[c] if m == "wait" else cost(c) + dist[c]
        opts = [(m, score(m, c)) for m, c in match.legal_moves() if c in dist]
        if not opts:
            return "wait"
        best = min(s for _, s in opts)
        return self.rng.choice([m for m, s in opts if s == best])


BOTS = {"rusher": Rusher, "cautious": Cautious}
