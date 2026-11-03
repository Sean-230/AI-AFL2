"""MatchEngine class: executes a single match of Dungeon Warden (Environment + Agent loop)."""
from __future__ import annotations

from DungeonWarden.ai.knowledge_base import KnowledgeBase
from DungeonWarden.ai.pathfinder import Pathfinder
from DungeonWarden.ai.warden_base import Decision
from DungeonWarden.ai.wardens import WARDENS
from DungeonWarden.core.action_schema import WAIT_ACTION, Action, StripsActionSchema
from DungeonWarden.core.dungeon_map import MOVES, Cell, DungeonMap
from DungeonWarden.core.game_state import GameState, Percept, TurnRecord
from DungeonWarden.core.sensor_system import SensorSystem
from DungeonWarden.core.settings import ENERGY_CAP, ENERGY_START, LOCK_COST, T_DEFAULT, WALL_COST


class MatchEngine:
    """Manages turn-by-turn environment execution, ground-truth validation, and telemetry."""

    def __init__(
        self,
        dmap: DungeonMap,
        warden: str = "W2",
        T: int = T_DEFAULT,
        energy: int = ENERGY_START,
        cap: int = ENERGY_CAP,
        seed: int = 0,
        check_astar: bool = False,
        lock_cost: int = LOCK_COST,
        wall_cost: int = WALL_COST,
    ) -> None:
        self.dmap = dmap
        self.cap = cap
        self.T = T
        self.state = GameState.create_initial(dmap, min(energy, cap), lock_cost, wall_cost)
        self.player: Cell = dmap.start
        self.kb = KnowledgeBase(dmap, dmap.start)
        self.warden = WARDENS[warden](dmap, cap, seed)
        self.check_astar = check_astar
        self.winner: str | None = None
        self.percept: Percept | None = None
        self.decision: Decision | None = None
        self.records: list[TurnRecord] = []
        self.invalid = 0

        orig_len = Pathfinder.bfs_distances(dmap.start, dmap, self.state.blocked).get(
            dmap.treasure
        )
        if orig_len is None:
            raise ValueError(f"{dmap.name}: treasure is unreachable from the start")
        self.original_len: int = orig_len

    @property
    def turns_left(self) -> int:
        """Return the number of remaining turns before the Warden wins by timeout."""
        return self.T - self.state.turn

    def legal_moves(self) -> list[tuple[str, Cell]]:
        """Return all valid (direction, target_cell) moves for the player's current cell."""
        x, y = self.player
        free = set(self.dmap.get_neighbors(self.player, self.state.blocked))
        return [
            (move_name, (x + dx, y + dy))
            for move_name, (dx, dy) in MOVES.items()
            if (x + dx, y + dy) in free
        ]

    def step(self, move: str) -> bool:
        """Execute one full turn (Player Move -> Percepts -> KB Update -> Warden Action)."""
        if self.winner is not None:
            return False
        target = dict(self.legal_moves()).get(move)
        if target is None:
            return False

        prev_cell, self.player = self.player, target
        self.state = self.state.next_turn()
        if self.player == self.dmap.treasure:
            self.winner = "player"
            return True

        self.percept = SensorSystem.sense(self.dmap, self.state, prev_cell, self.player)
        self.kb.update(self.percept, self.state)
        belief = {self.player} if self.warden.oracle else self.kb.belief

        decision = self.warden.decide(self.state, belief, self.turns_left)
        problem = self.ground_truth_problem(decision.action)
        if problem is not None:
            self.invalid += 1
            decision.note = f"INVALID ({problem}) -> Wait"
            decision.action = WAIT_ACTION

        self.state = StripsActionSchema.apply_effects(self.state, decision.action, self.cap)
        self.decision = decision

        astar_ok: bool | None = None
        if self.check_astar:
            path, _ = Pathfinder.astar(
                self.player, self.dmap.treasure, self.dmap, self.state.blocked
            )
            bfs_len = Pathfinder.bfs_distances(
                self.player, self.dmap, self.state.blocked
            ).get(self.dmap.treasure)
            astar_ok = (path is None and bfs_len is None) or (
                path is not None and len(path) - 1 == bfs_len
            )

        act_name, act_cell = decision.action
        act_str = act_name if act_cell is None else f"{act_name}{act_cell}"
        self.records.append(
            TurnRecord(
                turn=self.state.turn,
                player=self.player,
                belief_size=len(self.kb.belief),
                true_in_belief=(self.player in self.kb.belief),
                action=act_str,
                invalid=bool(problem),
                ms=decision.ms,
                nodes=decision.nodes,
                expanded=decision.expanded,
                astar_ok=astar_ok,
            )
        )

        if self.state.turn >= self.T:
            self.winner = "warden"
        return True

    def ground_truth_problem(self, action: Action) -> str | None:
        """Verify using simulator ground truth that the Warden's action is legal and fair."""
        precond_err = StripsActionSchema.check_preconditions(self.dmap, self.state, action)
        if precond_err is not None:
            return precond_err
        kind, cell = action
        if kind in ("PlaceWall", "LockDoor"):
            if cell == self.player:
                return "blocked the player's cell"
            after = StripsActionSchema.apply_effects(self.state, action, self.cap)
            if self.dmap.treasure not in Pathfinder.bfs_distances(
                self.player, self.dmap, after.blocked
            ):
                return "treasure unreachable for the player"
        return None

    def remaining_distance(self) -> int | None:
        """Return the player's current BFS shortest-path distance to the treasure."""
        return Pathfinder.bfs_distances(
            self.player, self.dmap, self.state.blocked
        ).get(self.dmap.treasure)

    def path_increase(self) -> int:
        """Compute extra steps forced on the player compared to the initial shortest path."""
        return self.state.turn + (self.remaining_distance() or 0) - self.original_len

    def summary(self) -> dict[str, object]:
        """Aggregate per-game evaluation metrics (Proposal Section 2.2)."""
        recs = self.records
        n = max(1, len(recs))
        ms_list = [r.ms for r in recs] or [0.0]
        dm = self.dmap
        return {
            "map": dm.name,
            "size": f"{dm.w}x{dm.h}",
            "cells": dm.w * dm.h,
            "warden": self.warden.key,
            "T": self.T or "",
            "winner": self.winner or "timeout",
            "player_won": int(self.winner == "player"),
            "turns": self.state.turn,
            "original_len": self.original_len,
            "path_increase": self.path_increase(),
            "invalid": self.invalid,
            "recall": sum(r.true_in_belief for r in recs) / n,
            "precision": sum(1 / r.belief_size for r in recs) / n,
            "mean_belief": sum(r.belief_size for r in recs) / n,
            "nodes_per_move": sum(r.nodes for r in recs) / n,
            "astar_exp_per_move": sum(r.expanded for r in recs) / n,
            "ms_mean": sum(ms_list) / len(ms_list),
            "ms_max": max(ms_list),
            "astar_checks": sum(r.astar_ok is not None for r in recs),
            "astar_mismatch": sum(r.astar_ok is False for r in recs),
        }


Match = MatchEngine

