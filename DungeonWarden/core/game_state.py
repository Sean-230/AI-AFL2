"""Dynamic game state, sensor percepts, and turn telemetry classes."""
from __future__ import annotations

from dataclasses import dataclass, replace
from functools import cached_property

from DungeonWarden.core.dungeon_map import Cell, DungeonMap
from DungeonWarden.core.settings import ENERGY_START, LOCK_COST, WALL_COST


@dataclass(frozen=True)
class GameState:
    """Immutable snapshot of the changing game world used by the match engine and Minimax tree."""

    walls: frozenset[Cell]
    locked: frozenset[Cell]
    energy: int
    turn: int = 0
    lock_cost: int = LOCK_COST      # energy price of LockDoor and PlaceWall (set by the difficulty)
    wall_cost: int = WALL_COST

    @classmethod
    def create_initial(
        cls,
        dmap: DungeonMap,
        energy: int = ENERGY_START,
        lock_cost: int = LOCK_COST,
        wall_cost: int = WALL_COST,
    ) -> "GameState":
        """Create the initial state at turn 0 from a static dungeon map."""
        return cls(
            walls=dmap.walls, locked=frozenset(), energy=energy, turn=0,
            lock_cost=lock_cost, wall_cost=wall_cost,
        )

    @cached_property
    def blocked(self) -> frozenset[Cell]:
        """Return all currently impassable cells (walls plus locked doors)."""
        return self.walls | self.locked

    def next_turn(self) -> "GameState":
        """Return a new GameState with the turn counter incremented by 1."""
        return replace(self, turn=self.turn + 1)


@dataclass(frozen=True)
class Percept:
    """Sensor readings received by the Warden after the player moves."""

    stepped: Cell | None
    noise: Cell | None
    sight: frozenset[Cell]
    seen: Cell | None


@dataclass
class TurnRecord:
    """Telemetry record for a single turn, used for evaluation metrics and CSV logging."""

    turn: int
    player: Cell
    belief_size: int
    true_in_belief: bool
    action: str
    invalid: bool
    ms: float
    nodes: int
    expanded: int
    astar_ok: bool | None

