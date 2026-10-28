"""The four Wardens compared in the evaluation (proposal Table 2.2.1).

W0 Random     random valid block each turn                         (baseline)
W1 A*-greedy  KB belief + A* route, best single block, no lookahead (baseline)
W2 Full       KB belief + A* + STRIPS actions + Minimax/alpha-beta  (our method)
W3 Oracle     W2 but it is told the true player cell                (upper bound)
"""
from __future__ import annotations

import math
import random
import time
from dataclasses import dataclass, field

from kb import is_valid
from search import RouteCache, bfs_distances
from world import (ENERGY_CAP, WAIT, Action, Cell, DungeonMap, State, apply, manhattan,
                   neighbors, tick)

LOOKAHEAD = 3       # plies: Warden, player, Warden
MAX_BLOCKS = 6      # blocks kept per node; + Wait + one Unlock gives b <= 8


@dataclass
class Decision:
    action: Action
    assumed: Cell | None = None             # worst-case player cell Minimax plans against
    route: list = field(default_factory=list)  # predicted player route from that cell
    value: float | None = None
    scored: list = field(default_factory=list)  # (action, value, exact) for every root action
    nodes: int = 0                          # game-tree nodes / actions evaluated
    expanded: int = 0                       # A* node expansions (cache misses only)
    ms: float = 0.0
    note: str = ""


class Warden:
    key = "W?"
    label = "Warden"
    oracle = False

    def __init__(self, dmap: DungeonMap, cap: int = ENERGY_CAP, seed: int = 0):
        self.dmap = dmap
        self.cap = cap
        self.rng = random.Random(seed)
        self.routes = RouteCache(dmap)
        self.nodes = 0

    def decide(self, state: State, belief: set[Cell], turns_left: int) -> Decision:
        t0 = time.perf_counter()
        self.nodes = 0
        e0 = self.routes.expanded
        d = self.choose(state, belief, turns_left)
        d.nodes, d.expanded = self.nodes, self.routes.expanded - e0
        d.ms = (time.perf_counter() - t0) * 1000
        return d

    def choose(self, state: State, belief: set[Cell], turns_left: int) -> Decision:
        raise NotImplementedError

    # ---- shared helpers

    def assumed_cell(self, belief: set[Cell], state: State) -> Cell:
        """Worst case for the Warden: the belief cell closest to the treasure."""
        if len(belief) == 1:
            return next(iter(belief))
        dist = bfs_distances(self.dmap.treasure, self.dmap, state.blocked)
        return min(belief, key=lambda c: (dist.get(c, math.inf), c))

    def candidates(self, state: State, player: Cell, belief: set[Cell]):
        """Valid actions near the predicted route, most promising first (good alpha-beta ordering)."""
        route = self.routes.path(player, state) or [player]
        blocks = []
        for c in route[1:-1]:
            a = ("LockDoor", c) if c in self.dmap.doors else ("PlaceWall", c)
            if is_valid(self.dmap, state, a, belief, self.cap) is None:
                blocks.append((_or_inf(self.routes.length(player, apply(state, a, self.cap))), a))
        blocks.sort(key=lambda t: -t[0])
        acts = [a for _, a in blocks[:MAX_BLOCKS]] + [WAIT]
        if state.locked:
            acts.append(("UnlockDoor", max(sorted(state.locked), key=lambda d: manhattan(d, player))))
        return acts, route

    def evaluate(self, state: State, player: Cell, energy_value: float = 0.0) -> float:
        """Utility for MAX (proposal 2.1): the player's shortest route length to the treasure, by A*.
        energy_value adds a bonus per leftover energy point; it is 0 under the proposal rules and only
        used by the variant rules (see world.VARIANT)."""
        if player == self.dmap.treasure:
            return 0.0
        length = self.routes.length(player, state)
        if length is None:      # unreachable can't happen for valid actions
            length = 999
        return length + energy_value * state.energy

    def tiebreak(self, state: State, player: Cell, after: State) -> tuple:
        """Between actions of equal value: prefer the bigger gain right now, then more energy left,
        so energy is never spent on a block that gains nothing."""
        return self.evaluate(after, player), after.energy


def _or_inf(x):
    return math.inf if x is None else x


class RandomWarden(Warden):
    key, label = "W0", "Random"

    def choose(self, state, belief, turns_left):
        blocks = [("LockDoor", d) for d in sorted(self.dmap.doors)]
        blocks += [("PlaceWall", c) for c in self.dmap.cells if self.dmap.is_plain_floor(c)]
        self.rng.shuffle(blocks)
        for a in blocks:
            self.nodes += 1
            if is_valid(self.dmap, state, a, belief, self.cap) is None:
                return Decision(a, note="random valid block")
        return Decision(WAIT, note="no valid block affordable")


class GreedyWarden(Warden):
    key, label = "W1", "A*-greedy"

    def choose(self, state, belief, turns_left):
        player = self.assumed_cell(belief, state)
        acts, route = self.candidates(state, player, belief)
        scored, best, best_key = [], WAIT, None
        for a in acts:
            self.nodes += 1
            after = apply(state, a, self.cap)
            v = self.evaluate(after, player)
            scored.append((a, v, True))
            key = (v, after.energy)
            if best_key is None or key > best_key:
                best, best_key = a, key
        return Decision(best, player, route, best_key[0], scored, note="1-ply greedy")


class MinimaxWarden(Warden):
    key, label = "W2", "Full Warden"

    def choose(self, state, belief, turns_left):
        player = self.assumed_cell(belief, state)
        acts, route = self.candidates(state, player, belief)
        best, best_key, scored = WAIT, (-math.inf,), []
        for a in acts:
            after = apply(state, a, self.cap)
            alpha = best_key[0] - 1e-6   # a slightly lower window still returns ties with the best exactly
            v = self.minimax(after, player, LOOKAHEAD - 1, alpha, math.inf, False, turns_left)
            exact = v > alpha   # v <= alpha is only an upper bound (pruned)
            scored.append((a, v, exact))
            # Equal lookahead values are broken by the gain realised right now. Without this the
            # Warden keeps postponing a wall it only "threatens" at its last, unanswered ply.
            key = (v, *self.tiebreak(state, player, after))
            if exact and key > best_key:
                best, best_key = a, key
        return Decision(best, player, route, best_key[0], scored,
                        note=f"minimax depth {LOOKAHEAD}, alpha-beta, ties -> immediate gain")

    def minimax(self, state, player, depth, alpha, beta, maximizing, turns_left):
        self.nodes += 1
        if depth == 0 or player == self.dmap.treasure or turns_left <= 0:
            return self.evaluate(state, player, state.rules.energy_value)
        if maximizing:
            best = -math.inf
            for a in self.candidates(state, player, {player})[0]:
                best = max(best, self.minimax(apply(state, a, self.cap), player, depth - 1,
                                              alpha, beta, False, turns_left))
                alpha = max(alpha, best)
                if alpha >= beta:
                    break
            return best
        best = math.inf
        moves = [*neighbors(player, self.dmap, state.blocked)]
        if state.rules.player_can_wait or not moves:
            moves.append(player)
        after = tick(state)     # a turn passes: locks run down and may reopen, cooldown drops
        moves.sort(key=lambda m: _or_inf(self.routes.length(m, after)))  # best replies first
        for m in moves:
            best = min(best, self.minimax(after, m, depth - 1, alpha, beta, True, turns_left - 1))
            beta = min(beta, best)
            if alpha >= beta:
                break
        return best


class OracleWarden(MinimaxWarden):
    key, label = "W3", "Oracle"
    oracle = True   # Match hands it {true player cell} instead of the KB belief set


WARDENS = {w.key: w for w in (RandomWarden, GreedyWarden, MinimaxWarden, OracleWarden)}
