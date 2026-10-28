"""One game of Dungeon Warden. Shared by the pygame front end and the headless simulator.

Turn order: the player moves one cell (the variant also allows waiting) -> percepts -> the Warden updates B_t
-> the Warden performs one action. The player wins on reaching the treasure. Under the
proposal rules (the default) the Warden wins once T turns have passed; under the variant rules
there is no limit, the game runs until the player gets there and the turn count is the score.
"""
from __future__ import annotations

import math
from dataclasses import dataclass

from kb import KnowledgeBase
from search import astar, bfs_distances
from world import (ENERGY_CAP, ENERGY_START, MOVES, PROPOSAL, T_DEFAULT, WAIT, Cell, DungeonMap,
                   Percept, Rules, apply, initial_state, neighbors, preconditions, sense, tick)
from warden import WARDENS, Decision


@dataclass
class TurnRecord:
    turn: int
    player: Cell
    belief_size: int
    true_in_belief: bool
    action: str
    invalid: bool
    ms: float
    nodes: int
    expanded: int
    astar_ok: bool | None   # A* length == BFS length (None when not checked)


class Match:
    def __init__(self, dmap: DungeonMap, warden: str = "W2", T: int | None = T_DEFAULT,
                 energy: int = ENERGY_START, cap: int = ENERGY_CAP, seed: int = 0,
                 check_astar: bool = False, rules: Rules = PROPOSAL):
        self.dmap, self.cap, self.rules = dmap, cap, rules
        self.T = T if rules.turn_limit else None
        self.state = initial_state(dmap, min(energy, cap), rules)
        self.player = dmap.start
        self.kb = KnowledgeBase(dmap, dmap.start)
        self.warden = WARDENS[warden](dmap, cap, seed)
        self.check_astar = check_astar
        self.winner: str | None = None
        self.percept: Percept | None = None
        self.decision: Decision | None = None
        self.records: list[TurnRecord] = []
        self.invalid = 0
        self.original_len = bfs_distances(dmap.start, dmap, self.state.blocked).get(dmap.treasure)
        if self.original_len is None:
            raise ValueError(f"{dmap.name}: treasure is unreachable from the start")

    @property
    def turns_left(self) -> float:
        return math.inf if self.T is None else self.T - self.state.turn

    def legal_moves(self) -> list[tuple[str, Cell]]:
        x, y = self.player
        out = [("wait", self.player)] if self.rules.player_can_wait else []
        free = set(neighbors(self.player, self.dmap, self.state.blocked))
        for m, (dx, dy) in MOVES.items():
            if m != "wait" and (x + dx, y + dy) in free:
                out.append((m, (x + dx, y + dy)))
        return out

    def step(self, move: str) -> bool:
        """Play one full turn. Returns False if the move is illegal (no turn is used)."""
        if self.winner:
            return False
        target = dict(self.legal_moves()).get(move)
        if target is None:
            return False
        prev, self.player = self.player, target
        moved_in = self.state       # the doors and walls the player actually moved through
        self.state = tick(self.state)
        if self.player == self.dmap.treasure:
            self.winner = "player"
            return True

        self.percept = sense(self.dmap, self.state, prev, self.player)
        self.kb.update(self.percept, moved_in)
        belief = {self.player} if self.warden.oracle else self.kb.belief

        d = self.warden.decide(self.state, belief, self.turns_left)
        problem = self.ground_truth_problem(d.action)
        if problem:     # the simulator knows the real cell, so it can catch an unfair action
            self.invalid += 1
            d.note = f"INVALID ({problem}) -> Wait"
            d.action = WAIT
        self.state = apply(self.state, d.action, self.cap)
        self.decision = d

        astar_ok = None
        if self.check_astar:
            path, _ = astar(self.player, self.dmap.treasure, self.dmap, self.state.blocked)
            bfs = bfs_distances(self.player, self.dmap, self.state.blocked).get(self.dmap.treasure)
            astar_ok = (path is None and bfs is None) or (path is not None and len(path) - 1 == bfs)
        self.records.append(TurnRecord(
            self.state.turn, self.player, len(self.kb.belief), self.player in self.kb.belief,
            d.action[0] if d.action[1] is None else f"{d.action[0]}{d.action[1]}",
            bool(problem), d.ms, d.nodes, d.expanded, astar_ok))

        if self.T is not None and self.state.turn >= self.T:
            self.winner = "warden"
        return True

    def ground_truth_problem(self, action) -> str | None:
        why = preconditions(self.dmap, self.state, action)
        if why:
            return why
        kind, c = action
        if kind in ("PlaceWall", "LockDoor"):
            if c == self.player:
                return "blocked the player's cell"
            after = apply(self.state, action, self.cap)
            if self.dmap.treasure not in bfs_distances(self.player, self.dmap, after.blocked):
                return "treasure unreachable for the player"
        return None

    def remaining_distance(self) -> int | None:
        return bfs_distances(self.player, self.dmap, self.state.blocked).get(self.dmap.treasure)

    def path_increase(self) -> int:
        """Length of the route the player was forced into (moves made + distance still left)
        minus the original shortest path."""
        return self.state.turn + (self.remaining_distance() or 0) - self.original_len

    def summary(self) -> dict:
        """One row of the metrics log (proposal 2.2), used by the game and the experiments."""
        recs = self.records
        n = max(1, len(recs))
        ms = [r.ms for r in recs] or [0.0]
        dm = self.dmap
        return {
            "map": dm.name, "size": f"{dm.w}x{dm.h}", "cells": dm.w * dm.h, "rules": self.rules.name,
            "warden": self.warden.key, "T": self.T or "", "winner": self.winner or "timeout",
            "player_won": int(self.winner == "player"), "turns": self.state.turn,
            "original_len": self.original_len, "path_increase": self.path_increase(), "invalid": self.invalid,
            "recall": sum(r.true_in_belief for r in recs) / n,
            "precision": sum(1 / r.belief_size for r in recs) / n,
            "mean_belief": sum(r.belief_size for r in recs) / n,
            "nodes_per_move": sum(r.nodes for r in recs) / n,
            "astar_exp_per_move": sum(r.expanded for r in recs) / n,
            "ms_mean": sum(ms) / len(ms), "ms_max": max(ms),
            "astar_checks": sum(r.astar_ok is not None for r in recs),
            "astar_mismatch": sum(r.astar_ok is False for r in recs),
        }
