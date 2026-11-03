"""STRIPS classical planning action schema (Proposal Table 2.1.1)."""
from __future__ import annotations

from dataclasses import replace

from DungeonWarden.core.dungeon_map import Cell, DungeonMap
from DungeonWarden.core.game_state import GameState
from DungeonWarden.core.settings import ENERGY_CAP, LOCK_COST, WALL_COST

Action = tuple[str, Cell | None]
WAIT_ACTION: Action = ("Wait", None)


class StripsActionSchema:
    """Encapsulates STRIPS preconditions and effects for the Warden's actuators."""

    @staticmethod
    def check_preconditions(dmap: DungeonMap, state: GameState, action: Action) -> str | None:
        """Check STRIPS preconditions (Table 2.1.1). Returns an error reason or None if valid."""
        kind, cell = action
        if kind == "LockDoor":
            if cell not in dmap.doors:
                return "not a door"
            if cell in state.locked:
                return "already locked"
            if state.energy < LOCK_COST:
                return "not enough energy"
        elif kind == "PlaceWall":
            if cell is None or not dmap.is_plain_floor(cell) or cell in state.walls:
                return "cell is not empty floor"
            if state.energy < WALL_COST:
                return "not enough energy"
        elif kind == "UnlockDoor":
            if cell not in state.locked:
                return "door is not locked"
        elif kind != "Wait":
            return f"unknown action {kind}"
        return None

    @staticmethod
    def apply_effects(state: GameState, action: Action, cap: int = ENERGY_CAP) -> GameState:
        """Apply STRIPS action effects (Table 2.1.1) and return the resulting GameState."""
        kind, cell = action
        if kind == "LockDoor" and cell is not None:
            return replace(
                state,
                locked=state.locked | {cell},
                energy=state.energy - LOCK_COST,
            )
        if kind == "PlaceWall" and cell is not None:
            return replace(
                state,
                walls=state.walls | {cell},
                energy=state.energy - WALL_COST,
            )
        if kind == "UnlockDoor" and cell is not None:
            return replace(
                state,
                locked=state.locked - {cell},
                energy=min(cap, state.energy + 1),
            )
        return replace(state, energy=min(cap, state.energy + 1))

    @staticmethod
    def format_action(action: Action) -> str:
        """Format an action tuple as a human-readable predicate string."""
        kind, cell = action
        return kind if cell is None else f"{kind}({cell[0]},{cell[1]})"

