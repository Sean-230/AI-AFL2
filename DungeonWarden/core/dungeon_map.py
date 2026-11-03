"""DungeonMap class: encapsulates the static 2D grid layout and spatial queries."""
from __future__ import annotations

from pathlib import Path
from typing import Iterator

Cell = tuple[int, int]  # (x, y) where x = column, y = row

MOVES: dict[str, Cell] = {
    "up": (0, -1),
    "down": (0, 1),
    "left": (-1, 0),
    "right": (1, 0),
}

TILES: dict[str, str] = {
    "#": "wall",
    ".": "floor",
    "D": "door",
    "o": "plate",
    "E": "eye",
    "T": "treasure",
    "P": "start",
}


class DungeonMap:
    """Immutable model of a 2D dungeon grid loaded from an ASCII map definition."""

    def __init__(self, rows: list[str], name: str = "map") -> None:
        cleaned = [r.rstrip("\n") for r in rows]
        if not cleaned:
            raise ValueError(f"{name}: map is empty")

        self.name = name
        self.w = len(cleaned[0])
        self.h = len(cleaned)
        if any(len(r) != self.w for r in cleaned):
            raise ValueError(f"{name}: every row must have the same width")

        walls: set[Cell] = set()
        doors: set[Cell] = set()
        plates: set[Cell] = set()
        eyes: set[Cell] = set()
        treasures: list[Cell] = []
        starts: list[Cell] = []

        for y, row in enumerate(cleaned):
            for x, ch in enumerate(row):
                if ch not in TILES:
                    raise ValueError(f"{name}: unknown tile {ch!r} at ({x},{y})")
                cell = (x, y)
                if ch == "#":
                    walls.add(cell)
                elif ch == "D":
                    doors.add(cell)
                elif ch == "o":
                    plates.add(cell)
                elif ch == "E":
                    eyes.add(cell)
                elif ch == "T":
                    treasures.append(cell)
                elif ch == "P":
                    starts.append(cell)

        if len(treasures) != 1 or len(starts) != 1:
            raise ValueError(f"{name}: need exactly one T and one P")

        self.rows = cleaned
        self.walls = frozenset(walls)
        self.doors = frozenset(doors)
        self.plates = frozenset(plates)
        self.eyes = frozenset(eyes)
        self.treasure: Cell = treasures[0]
        self.start: Cell = starts[0]
        self.cells: list[Cell] = [(x, y) for y in range(self.h) for x in range(self.w)]

    @classmethod
    def load(cls, path: str | Path) -> "DungeonMap":
        """Load a DungeonMap from an ASCII file, ignoring comment lines starting with ';'."""
        p = Path(path)
        rows = [
            line
            for line in p.read_text(encoding="utf-8").splitlines()
            if line.strip() and not line.startswith(";")
        ]
        return cls(rows, p.stem)

    def in_bounds(self, cell: Cell) -> bool:
        """Check whether a coordinate lies within the grid boundaries."""
        return 0 <= cell[0] < self.w and 0 <= cell[1] < self.h

    def is_plain_floor(self, cell: Cell) -> bool:
        """Check if a cell is empty floor (Empty(c)) where the Warden is allowed to place a wall."""
        return (
            self.in_bounds(cell)
            and cell not in self.walls
            and cell not in self.doors
            and cell not in self.plates
            and cell not in self.eyes
            and cell != self.treasure
        )

    def get_neighbors(self, cell: Cell, blocked: frozenset[Cell]) -> Iterator[Cell]:
        """Yield orthogonal neighbor cells that are within bounds and not blocked."""
        x, y = cell
        for nx, ny in ((x + 1, y), (x - 1, y), (x, y + 1), (x, y - 1)):
            if 0 <= nx < self.w and 0 <= ny < self.h and (nx, ny) not in blocked:
                yield (nx, ny)

    @staticmethod
    def manhattan(a: Cell, b: Cell) -> int:
        """Compute the Manhattan (L1) distance between two grid cells."""
        return abs(a[0] - b[0]) + abs(a[1] - b[1])

