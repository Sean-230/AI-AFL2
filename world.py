"""Dungeon map, game state, STRIPS-style Warden actions and player percepts."""
from __future__ import annotations

import math
from collections import deque
from dataclasses import dataclass, field, replace
from functools import cached_property
from pathlib import Path

Cell = tuple[int, int]          # (x, y), x = column, y = row
Action = tuple[str, Cell | None]

# Default settings. T, energy and cap can be overridden from the command line.
T_DEFAULT = 40          # proposal: the Warden wins when T turns pass
ENERGY_START = 6
ENERGY_CAP = 10
SIGHT_RANGE = 2


@dataclass(frozen=True)
class Rules:
    """Action costs and timers. PROPOSAL is Table 2.1.1 of the proposal; VARIANT is the house-rule
    version (doors reopen, walls cost more and have a cooldown, no turn limit)."""
    name: str
    lock_cost: int
    wall_cost: int
    lock_turns: int | None      # a locked door reopens after this many player turns (None: stays locked)
    door_rest: int              # a door that just reopened can't be locked again for this many turns
    wall_cooldown: int          # after PlaceWall the Warden must wait this many turns to wall again
    turn_limit: bool            # True: the Warden wins when T turns pass
    player_can_wait: bool       # False: the player must move one cell every turn (proposal 2.1)
    energy_value: float         # Minimax leaf bonus per leftover energy point (0 = utility is route length)

    def describe(self) -> str:
        lock = f"reopens after {self.lock_turns}" if self.lock_turns else "until unlocked"
        cd = f" + {self.wall_cooldown}-turn cooldown" if self.wall_cooldown else ""
        return f"Lock {self.lock_cost}e ({lock}) · Wall {self.wall_cost}e{cd}"


PROPOSAL = Rules("proposal", lock_cost=2, wall_cost=3, lock_turns=None, door_rest=0, wall_cooldown=0,
                 turn_limit=True, player_can_wait=False, energy_value=0.0)
# energy_value 0.35: with a wall cooldown the unanswered last Warden ply makes Minimax hoard energy for
# a wall it keeps postponing (the horizon effect); valuing leftover energy fixes that. Calibrated.
VARIANT = Rules("variant", lock_cost=2, wall_cost=5, lock_turns=3, door_rest=2, wall_cooldown=3,
                turn_limit=False, player_can_wait=True, energy_value=0.35)
RULESETS = {r.name: r for r in (PROPOSAL, VARIANT)}

MOVES = {"up": (0, -1), "down": (0, 1), "left": (-1, 0), "right": (1, 0), "wait": (0, 0)}
WAIT: Action = ("Wait", None)

TILES = {
    "#": "wall", ".": "floor", "D": "door", "o": "plate",
    "E": "eye", "T": "treasure", "P": "start",
}


class DungeonMap:
    """Static layout loaded from an ASCII file. Everything the Warden changes lives in State."""

    def __init__(self, rows: list[str], name: str = "map"):
        rows = [r.rstrip("\n") for r in rows]
        if not rows:
            raise ValueError(f"{name}: map is empty")
        self.name = name
        self.w, self.h = len(rows[0]), len(rows)
        if any(len(r) != self.w for r in rows):
            raise ValueError(f"{name}: every row must have the same width")

        walls, doors, plates, eyes, treasures, starts = set(), set(), set(), set(), [], []
        for y, row in enumerate(rows):
            for x, ch in enumerate(row):
                if ch not in TILES:
                    raise ValueError(f"{name}: unknown tile {ch!r} at ({x},{y})")
                c = (x, y)
                {"#": walls, "D": doors, "o": plates, "E": eyes}.get(ch, set()).add(c)
                if ch == "T":
                    treasures.append(c)
                elif ch == "P":
                    starts.append(c)
        if len(treasures) != 1 or len(starts) != 1:
            raise ValueError(f"{name}: need exactly one T and one P")

        self.rows = rows
        self.walls = frozenset(walls)
        self.doors = frozenset(doors)
        self.plates = frozenset(plates)
        self.eyes = frozenset(eyes)
        self.treasure: Cell = treasures[0]
        self.start: Cell = starts[0]
        self.cells = [(x, y) for y in range(self.h) for x in range(self.w)]

    @classmethod
    def load(cls, path: str | Path) -> "DungeonMap":
        p = Path(path)
        rows = [line for line in p.read_text().splitlines() if line.strip() and not line.startswith(";")]
        return cls(rows, p.stem)

    def in_bounds(self, c: Cell) -> bool:
        return 0 <= c[0] < self.w and 0 <= c[1] < self.h

    def is_plain_floor(self, c: Cell) -> bool:
        """Empty(c): a floor tile the Warden may wall. Sensors, doors and the treasure are never walled."""
        return (self.in_bounds(c) and c not in self.walls and c not in self.doors
                and c not in self.plates and c not in self.eyes and c != self.treasure)


@dataclass(frozen=True)
class State:
    """The changing part of the world. Immutable so Minimax can branch on it cheaply."""
    walls: frozenset            # map walls + walls placed by the Warden
    locks: frozenset            # (door, turn it reopens or None) for every locked door
    energy: int
    turn: int = 0               # player moves made so far
    cooldown: int = 0           # turns until the Warden may place a wall again
    resting: frozenset = frozenset()  # (door, turn it may be locked again) after it reopened
    rules: Rules = field(default=PROPOSAL, compare=False)

    @cached_property
    def locked(self) -> frozenset:
        return frozenset(d for d, _ in self.locks)

    @cached_property
    def blocked(self) -> frozenset:
        return self.walls | self.locked

    def lock_left(self, door: Cell) -> float:
        """Player turns until this door reopens: 0 when it is open, inf when it stays locked."""
        for d, until in self.locks:
            if d == door:
                return math.inf if until is None else until - self.turn
        return 0


def initial_state(dmap: DungeonMap, energy: int = ENERGY_START, rules: Rules = PROPOSAL) -> State:
    return State(dmap.walls, frozenset(), energy, 0, rules=rules)


def tick(state: State) -> State:
    """One player turn passes: the clock advances, expired locks reopen, the cooldown runs down."""
    turn = state.turn + 1
    expired = lambda until: until is not None and until <= turn
    reopened = {(d, turn + state.rules.door_rest) for d, until in state.locks if expired(until)}
    return replace(state, turn=turn, locks=frozenset(l for l in state.locks if not expired(l[1])),
                   cooldown=max(0, state.cooldown - 1),
                   resting=frozenset(r for r in state.resting if r[1] > turn) | reopened)


def neighbors(c: Cell, dmap: DungeonMap, blocked: frozenset):
    x, y = c
    for n in ((x + 1, y), (x - 1, y), (x, y + 1), (x, y - 1)):
        if 0 <= n[0] < dmap.w and 0 <= n[1] < dmap.h and n not in blocked:
            yield n


def manhattan(a: Cell, b: Cell) -> int:
    return abs(a[0] - b[0]) + abs(a[1] - b[1])


# ---------------------------------------------------------------- STRIPS actions

def preconditions(dmap: DungeonMap, state: State, action: Action) -> str | None:
    """Return why the action's STRIPS preconditions fail, or None when they hold.
    The KB's Valid(a) check (treasure stays reachable) is separate, see kb.is_valid."""
    kind, c = action
    if kind == "PlaceWall" and state.cooldown > 0:
        return f"on cooldown ({state.cooldown} turns)"
    if kind == "LockDoor":
        if c not in dmap.doors:
            return "not a door"
        if c in state.locked:
            return "already locked"
        if any(d == c for d, _ in state.resting):
            return "door just reopened"
        if state.energy < state.rules.lock_cost:
            return "not enough energy"
    elif kind == "PlaceWall":
        if not dmap.is_plain_floor(c) or c in state.walls:
            return "cell is not empty floor"
        if state.energy < state.rules.wall_cost:
            return "not enough energy"
    elif kind == "UnlockDoor":
        if c not in state.locked:
            return "door is not locked"
    elif kind != "Wait":
        return f"unknown action {kind}"
    return None


def apply(state: State, action: Action, cap: int = ENERGY_CAP) -> State:
    """Apply the action's effects. Assumes preconditions already hold."""
    kind, c = action
    r = state.rules
    if kind == "LockDoor":
        until = None if r.lock_turns is None else state.turn + r.lock_turns
        return replace(state, locks=state.locks | {(c, until)}, energy=state.energy - r.lock_cost)
    if kind == "PlaceWall":
        return replace(state, walls=state.walls | {c}, energy=state.energy - r.wall_cost,
                       cooldown=r.wall_cooldown)
    if kind == "UnlockDoor":
        rest = {(c, state.turn + r.door_rest)} if r.door_rest else set()
        return replace(state, locks=frozenset(l for l in state.locks if l[0] != c),
                       resting=state.resting | rest, energy=min(cap, state.energy + 1))
    return replace(state, energy=min(cap, state.energy + 1))   # Wait


def action_str(action: Action) -> str:
    kind, c = action
    return kind if c is None else f"{kind}({c[0]},{c[1]})"


# ---------------------------------------------------------------- percepts

@dataclass(frozen=True)
class Percept:
    stepped: Cell | None        # plate the player is standing on
    noise: Cell | None          # door that creaked this turn
    sight: frozenset            # cells the eyes can see this turn
    seen: Cell | None           # player cell if it is in sight


def sight_cells(dmap: DungeonMap, walls: frozenset, rng: int = SIGHT_RANGE) -> frozenset:
    """Cells within `rng` steps of an eye, flood-filled so walls block the view."""
    seen = set()
    for eye in dmap.eyes:
        frontier = deque([(eye, 0)])
        local = {eye}
        while frontier:
            c, d = frontier.popleft()
            if d == rng:
                continue
            for n in neighbors(c, dmap, walls):
                if n not in local:
                    local.add(n)
                    frontier.append((n, d + 1))
        seen |= local
    return frozenset(seen)


def sense(dmap: DungeonMap, state: State, prev: Cell, cur: Cell) -> Percept:
    """What the Warden's sensors report after the player moved prev -> cur.
    A door creaks when the player steps onto it or off it, so the player is always on or next to it."""
    stepped = cur if cur in dmap.plates else None
    noise = None
    if cur != prev:
        if cur in dmap.doors:
            noise = cur
        elif prev in dmap.doors:
            noise = prev
    sight = sight_cells(dmap, state.walls)
    return Percept(stepped, noise, sight, cur if cur in sight else None)
