"""Comparison Wardens used only to evaluate the method (Proposal Table 2.2.1): W0, W1 and W3.

The game itself always plays W2 (MinimaxWarden in DungeonWarden/ai/wardens.py). The versions here are
subclasses of the game's abstract BaseWarden, so the evaluation uses exactly the same engine, knowledge
base and search code as the game.
"""
from __future__ import annotations

from DungeonWarden.ai.knowledge_base import ActionValidator
from DungeonWarden.ai.warden_base import BaseWarden, Decision
from DungeonWarden.ai.wardens import MinimaxWarden
from DungeonWarden.core.action_schema import WAIT_ACTION, Action, StripsActionSchema
from DungeonWarden.core.dungeon_map import Cell
from DungeonWarden.core.game_state import GameState


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


class OracleWarden(MinimaxWarden):
    """W3 Upper Bound: identical to W2 Full Warden but receives the true player position."""

    key = "W3"
    label = "Oracle"
    oracle = True


WARDENS: dict[str, type[BaseWarden]] = {
    w.key: w for w in (RandomWarden, GreedyWarden, MinimaxWarden, OracleWarden)
}
