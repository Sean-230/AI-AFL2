"""Concrete Warden AI implementations: W0 Random, W1 Greedy, W2 Full Minimax, and W3 Oracle."""
from __future__ import annotations

import math

from DungeonWarden.ai.knowledge_base import ActionValidator
from DungeonWarden.ai.warden_base import LOOKAHEAD_PLIES, BaseWarden, Decision
from DungeonWarden.core.action_schema import WAIT_ACTION, Action, StripsActionSchema
from DungeonWarden.core.dungeon_map import Cell
from DungeonWarden.core.game_state import GameState


def _len_or_inf(length: int | None) -> float:
    return math.inf if length is None else float(length)


class RandomWarden(BaseWarden):
    """W0 Baseline: selects a random valid blocking action each turn."""

    key = "W0"
    label = "Random"

    def choose(self, state: GameState, belief: set[Cell], turns_left: int) -> Decision:
        blocks: list[Action] = [("LockDoor", d) for d in sorted(self.dmap.doors)]
        blocks += [
            ("PlaceWall", c) for c in self.dmap.cells if self.dmap.is_plain_floor(c)
        ]
        self.rng.shuffle(blocks)
        for action in blocks:
            self.nodes += 1
            if ActionValidator.validate(self.dmap, state, action, belief, self.cap) is None:
                return Decision(action, note="random valid block")
        return Decision(WAIT_ACTION, note="no valid block affordable")


class GreedyWarden(BaseWarden):
    """W1 Baseline: uses KB belief set + A* route prediction with 1-ply greedy blocking."""

    key = "W1"
    label = "A*-greedy"

    def choose(self, state: GameState, belief: set[Cell], turns_left: int) -> Decision:
        player = self.assumed_cell(belief, state)
        actions, route = self.candidates(state, player, belief)
        actions.sort(key=lambda a: a != WAIT_ACTION)
        scored: list[tuple[Action, float, bool]] = []
        for action in actions:
            self.nodes += 1
            next_state = StripsActionSchema.apply_effects(state, action, self.cap)
            scored.append((action, self.evaluate(next_state, player), True))
        best = max(scored, key=lambda item: item[1])
        return Decision(best[0], player, route, best[1], scored, note="1-ply greedy")


class MinimaxWarden(BaseWarden):
    """W2 Full Warden: KB belief set + A* + STRIPS planning + 3-ply Minimax with Alpha-Beta."""

    key = "W2"
    label = "Full Warden"

    def choose(self, state: GameState, belief: set[Cell], turns_left: int) -> Decision:
        player = self.assumed_cell(belief, state)
        actions, route = self.candidates(state, player, belief)
        actions.sort(key=lambda a: a != WAIT_ACTION)

        alpha = -math.inf
        best_action: Action = WAIT_ACTION
        best_value = -math.inf
        scored: list[tuple[Action, float, bool]] = []

        for action in actions:
            next_state = StripsActionSchema.apply_effects(state, action, self.cap)
            value = self.minimax(
                next_state,
                player,
                LOOKAHEAD_PLIES - 1,
                alpha,
                math.inf,
                False,
                turns_left,
            )
            scored.append((action, value, value > alpha))
            if value > best_value:
                best_action, best_value = action, value
            alpha = max(alpha, value)

        return Decision(
            best_action,
            player,
            route,
            best_value,
            scored,
            note=f"minimax depth {LOOKAHEAD_PLIES}, alpha-beta",
        )

    def minimax(
        self,
        state: GameState,
        player: Cell,
        depth: int,
        alpha: float,
        beta: float,
        maximizing: bool,
        turns_left: int,
    ) -> float:
        """Recursive Minimax search with Alpha-Beta pruning."""
        self.nodes += 1
        if depth == 0 or player == self.dmap.treasure or turns_left <= 0:
            return self.evaluate(state, player)

        if maximizing:
            best = -math.inf
            candidate_actions, _ = self.candidates(state, player, {player})
            for action in candidate_actions:
                next_state = StripsActionSchema.apply_effects(state, action, self.cap)
                best = max(
                    best,
                    self.minimax(
                        next_state, player, depth - 1, alpha, beta, False, turns_left
                    ),
                )
                alpha = max(alpha, best)
                if alpha >= beta:
                    break
            return best

        best = math.inf
        moves = list(self.dmap.get_neighbors(player, state.blocked)) or [player]
        moves.sort(key=lambda m: _len_or_inf(self.routes.length(m, state.blocked)))
        for move_cell in moves:
            best = min(
                best,
                self.minimax(
                    state, move_cell, depth - 1, alpha, beta, True, turns_left - 1
                ),
            )
            beta = min(beta, best)
            if alpha >= beta:
                break
        return best


class OracleWarden(MinimaxWarden):
    """W3 Upper Bound: identical to W2 Full Warden but receives the true player position."""

    key = "W3"
    label = "Oracle"
    oracle = True


WARDENS: dict[str, type[BaseWarden]] = {
    w.key: w for w in (RandomWarden, GreedyWarden, MinimaxWarden, OracleWarden)
}
