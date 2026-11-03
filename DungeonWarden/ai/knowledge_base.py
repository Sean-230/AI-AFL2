"""First-Order Logic (FOL) Knowledge Base and ActionValidator classes (Proposal Section 2.1)."""
from __future__ import annotations

from dataclasses import dataclass
from typing import Callable

from DungeonWarden.ai.pathfinder import Pathfinder
from DungeonWarden.core.action_schema import Action, StripsActionSchema
from DungeonWarden.core.dungeon_map import Cell, DungeonMap
from DungeonWarden.core.game_state import GameState, Percept

FOL_RULES: dict[str, str] = {
    "R1": "∀c,c′,t: Stepped(c,t) ∧ c′≠c → ¬PossibleAt(c′,t)",
    "R2": "∀c1,c2,t: PossibleAt(c1,t) ∧ Connected(c1,c2,t) → PossibleAt(c2,t+1)",
    "R3": "∀c,t: InSight(c,t) ∧ ¬PlayerSeen(c,t) → ¬PossibleAt(c,t)",
    "R4": "∀c,d,t: Noise(d,t) ∧ ¬Adjacent(c,d) → ¬PossibleAt(c,t)",
    "V": "∀a: Valid(a) ↔ ∀c∈B_t: ∃path(c,Treasure) after a",
}


@dataclass
class Inference:
    """Represents a single FOL inference step that updates the belief set B_t."""

    rule: str
    text: str
    before: int
    after: int

    def __str__(self) -> str:
        return f"{self.rule}: {self.text}  |B| {self.before}→{self.after}"


class KnowledgeBase:
    """Maintains the Warden's belief set B_t using Universal Instantiation and Modus Ponens."""

    def __init__(self, dmap: DungeonMap, start: Cell) -> None:
        self.dmap = dmap
        self.belief: set[Cell] = {start}
        self.log: list[Inference] = []

    def update(self, percept: Percept, state: GameState) -> list[Inference]:
        """Update belief set B_t from sensor percepts using FOL rules R1 through R4."""
        log: list[Inference] = []

        # Rule R2: Universal instantiation over c1 in B_{t-1} and orthogonal neighbors c2
        next_belief: set[Cell] = set()
        for cell in self.belief:
            next_belief.update(self.dmap.get_neighbors(cell, state.blocked))
        log.append(Inference("R2", "expand by one move", len(self.belief), len(next_belief)))

        def restrict_belief(rule_id: str, predicate: Callable[[Cell], bool], note: str) -> None:
            nonlocal next_belief
            filtered = {c for c in next_belief if predicate(c)}
            if filtered:
                log.append(Inference(rule_id, note, len(next_belief), len(filtered)))
                next_belief = filtered
            else:
                log.append(
                    Inference(rule_id, "!! contradiction, rule skipped", len(next_belief), len(next_belief))
                )

        # Rule R1: Footstep plate pinpoints the exact cell
        if percept.stepped is not None:
            stepped_cell = percept.stepped
            restrict_belief(
                "R1",
                lambda c: c == stepped_cell,
                f"Stepped({stepped_cell[0]},{stepped_cell[1]})",
            )

        # Rule R3: Watched cells where the player is not seen are eliminated
        watched_empty = {c for c in (percept.sight & next_belief) if c != percept.seen}
        if watched_empty:
            seen_suffix = f", PlayerSeen{percept.seen}" if percept.seen else ""
            restrict_belief(
                "R3",
                lambda c: c not in watched_empty,
                f"{len(watched_empty)} watched cells empty{seen_suffix}",
            )

        # Rule R4: Door noise restricts possibilities to cells on or adjacent to the door
        if percept.noise is not None:
            door_cell = percept.noise
            restrict_belief(
                "R4",
                lambda c: DungeonMap.manhattan(c, door_cell) <= 1,
                f"Noise(door {door_cell[0]},{door_cell[1]})",
            )

        self.belief = next_belief
        self.log = log
        return log


class ActionValidator:
    """Evaluates the FOL validity rule Valid(a) and STRIPS preconditions for candidate actions."""

    @staticmethod
    def validate(
        dmap: DungeonMap,
        state: GameState,
        action: Action,
        belief: set[Cell],
        cap: int,
    ) -> str | None:
        """Return None if `action` is legal and fair (Valid(a)), or an error string otherwise."""
        precond_error = StripsActionSchema.check_preconditions(dmap, state, action)
        if precond_error is not None:
            return precond_error

        kind, cell = action
        if kind in ("PlaceWall", "LockDoor"):
            if cell in belief:
                return "player may be on that cell"
            next_state = StripsActionSchema.apply_effects(state, action, cap)
            reachable = Pathfinder.bfs_distances(dmap.treasure, dmap, next_state.blocked)
            if not all(b_cell in reachable for b_cell in belief):
                return "treasure would become unreachable"
        return None
