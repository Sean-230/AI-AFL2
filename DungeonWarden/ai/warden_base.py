"""Abstract BaseWarden class and Decision model for AI Warden agents."""
from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
import math
import random
import time

from DungeonWarden.ai.knowledge_base import ActionValidator
from DungeonWarden.ai.pathfinder import Pathfinder, RouteCache
from DungeonWarden.core.action_schema import WAIT_ACTION, Action, StripsActionSchema
from DungeonWarden.core.dungeon_map import Cell, DungeonMap
from DungeonWarden.core.game_state import GameState
from DungeonWarden.core.settings import ENERGY_CAP

LOOKAHEAD_PLIES = 3
MAX_CANDIDATE_BLOCKS = 6


@dataclass
class Decision:
    """Encapsulates the Warden's chosen action and reasoning telemetry for a single turn."""

    action: Action
    assumed: Cell | None = None
    route: list[Cell] = field(default_factory=list)
    value: float | None = None
    scored: list[tuple[Action, float, bool]] = field(default_factory=list)
    nodes: int = 0
    expanded: int = 0
    ms: float = 0.0
    note: str = ""


class BaseWarden(ABC):
    """Abstract base class for all Warden AI implementations (Template Method pattern)."""

    key: str = "W?"
    label: str = "Warden"
    oracle: bool = False

    def __init__(self, dmap: DungeonMap, cap: int = ENERGY_CAP, seed: int = 0) -> None:
        self.dmap = dmap
        self.cap = cap
        self.rng = random.Random(seed)
        self.routes = RouteCache(dmap)
        self.nodes = 0

    def decide(self, state: GameState, belief: set[Cell], turns_left: int) -> Decision:
        """Template method: measure execution time, nodes, and A* expansions around `choose()`."""
        t0 = time.perf_counter()
        self.nodes = 0
        exp_before = self.routes.expanded
        decision = self.choose(state, belief, turns_left)
        decision.nodes = self.nodes
        decision.expanded = self.routes.expanded - exp_before
        decision.ms = (time.perf_counter() - t0) * 1000.0
        return decision

    @abstractmethod
    def choose(self, state: GameState, belief: set[Cell], turns_left: int) -> Decision:
        """Select a valid Warden action for the current turn."""

    def assumed_cell(self, belief: set[Cell], state: GameState) -> Cell:
        """Return the worst-case player position: the cell in `belief` closest to the treasure."""
        if len(belief) == 1:
            return next(iter(belief))
        dist = Pathfinder.bfs_distances(self.dmap.treasure, self.dmap, state.blocked)
        return min(belief, key=lambda c: (dist.get(c, math.inf), c))

    def candidates(
        self,
        state: GameState,
        player: Cell,
        belief: set[Cell],
    ) -> tuple[list[Action], list[Cell]]:
        """Generate up to b <= 8 valid actions near the predicted route, ordered for Alpha-Beta."""
        route = self.routes.path(player, state.blocked) or [player]
        blocks: list[tuple[float, Action]] = []

        for cell in route[1:-1]:
            action: Action = (
                ("LockDoor", cell) if cell in self.dmap.doors else ("PlaceWall", cell)
            )
            if ActionValidator.validate(self.dmap, state, action, belief, self.cap) is None:
                next_state = StripsActionSchema.apply_effects(state, action, self.cap)
                new_len = self.routes.length(player, next_state.blocked)
                score = math.inf if new_len is None else float(new_len)
                blocks.append((score, action))

        blocks.sort(key=lambda item: -item[0])
        actions: list[Action] = [a for _, a in blocks[:MAX_CANDIDATE_BLOCKS]] + [WAIT_ACTION]
        if state.locked:
            farthest_door = max(
                sorted(state.locked),
                key=lambda d: DungeonMap.manhattan(d, player),
            )
            actions.append(("UnlockDoor", farthest_door))
        return actions, route

    def evaluate(self, state: GameState, player: Cell) -> float:
        """Utility function for MAX (Warden): player's A* shortest route length to the treasure."""
        if player == self.dmap.treasure:
            return 0.0
        length = self.routes.length(player, state.blocked)
        return 999.0 if length is None else float(length)
