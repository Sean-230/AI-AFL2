"""The game's Warden AI: W2 Full Warden (KB belief set + A* + STRIPS planning + 3-ply Minimax with alpha-beta).

The comparison versions W0, W1 and W3 are only used for evaluation and live in Experiments/evaluation_wardens.py.
"""
from __future__ import annotations

import math

from DungeonWarden.ai.warden_base import LOOKAHEAD_PLIES, BaseWarden, Decision
from DungeonWarden.core.action_schema import WAIT_ACTION, Action, StripsActionSchema
from DungeonWarden.core.dungeon_map import Cell
from DungeonWarden.core.game_state import GameState


def _len_or_inf(length: int | None) -> float:
    return math.inf if length is None else float(length)


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
