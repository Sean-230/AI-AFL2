"""Knowledge Base: FOL rules that maintain the Warden's belief set B_t and check Valid(a).

Each rule is applied by Universal Instantiation (the loop grounds it for every cell c)
followed by Modus Ponens (when the grounded premise holds, the conclusion is added).
The PossibleAt facts are stored as a set of cells, so every rule becomes a set operation.
"""
from __future__ import annotations

from dataclasses import dataclass

from search import bfs_distances
from world import Action, Cell, DungeonMap, Percept, State, apply, manhattan, neighbors, preconditions

RULES = {     # exactly the five rules of proposal section 2.1
    "R1": "∀c,c′,t: Stepped(c,t) ∧ c′≠c → ¬PossibleAt(c′,t)",
    "R2": "∀c1,c2,t: PossibleAt(c1,t) ∧ Connected(c1,c2,t) → PossibleAt(c2,t+1)",
    "R3": "∀c,t: InSight(c,t) ∧ ¬PlayerSeen(c,t) → ¬PossibleAt(c,t)",
    "R4": "∀c,d,t: Noise(d,t) ∧ ¬Adjacent(c,d) → ¬PossibleAt(c,t)",
    "V":  "∀a: Valid(a) ↔ ∀c∈B_t: ∃path(c,Treasure) after a",
}


@dataclass
class Inference:
    rule: str
    text: str
    before: int
    after: int

    def __str__(self):
        return f"{self.rule}: {self.text}  |B| {self.before}→{self.after}"


class KnowledgeBase:
    def __init__(self, dmap: DungeonMap, start: Cell):
        self.dmap = dmap
        self.belief: set[Cell] = {start}     # the entrance is public knowledge
        self.log: list[Inference] = []

    def update(self, p: Percept, state: State) -> list[Inference]:
        dmap, log = self.dmap, []

        # R2: the player moved one cell from some cell of B_t-1. Under the proposal rules the player
        # must move, so staying put is not Connected; the variant lets the player wait (reflexive).
        b = set(self.belief) if state.rules.player_can_wait else set()
        for c in self.belief:
            b.update(neighbors(c, dmap, state.blocked))
        log.append(Inference("R2", "expand by one move", len(self.belief), len(b)))

        def restrict(rule, keep, text):
            nonlocal b
            nb = {c for c in b if keep(c)}
            if nb:
                log.append(Inference(rule, text, len(b), len(nb)))
                b = nb
            else:   # percepts are ground truth, so an empty set would mean a bug, not a real contradiction
                log.append(Inference(rule, "!! contradiction, rule skipped", len(b), len(b)))

        if p.stepped:
            restrict("R1", lambda c: c == p.stepped, f"Stepped({p.stepped[0]},{p.stepped[1]})")

        watched_empty = {c for c in p.sight & b if c != p.seen}
        if watched_empty:
            restrict("R3", lambda c: c not in watched_empty,
                     f"{len(watched_empty)} watched cells empty" + (f", PlayerSeen{p.seen}" if p.seen else ""))

        if p.noise:
            d = p.noise
            restrict("R4", lambda c: manhattan(c, d) <= 1, f"Noise(door {d[0]},{d[1]})")

        self.belief = b
        self.log = log
        return log


def is_valid(dmap: DungeonMap, state: State, action: Action, belief: set[Cell], cap: int) -> str | None:
    """Valid(a): STRIPS preconditions hold, the block is not on a cell the player may occupy,
    and the treasure is still reachable from every cell in the belief set. Returns the reason it fails."""
    why = preconditions(dmap, state, action)
    if why:
        return why
    kind, c = action
    if kind in ("PlaceWall", "LockDoor"):
        if c in belief:
            return "player may be on that cell"
        reach = bfs_distances(dmap.treasure, dmap, apply(state, action, cap).blocked)
        if not all(b in reach for b in belief):
            return "treasure would become unreachable"
    return None
