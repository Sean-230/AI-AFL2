"""SensorSystem class: computes Warden percepts (plates, door noise, and 2-cell sight)."""
from __future__ import annotations

from collections import deque

from DungeonWarden.core.dungeon_map import Cell, DungeonMap
from DungeonWarden.core.game_state import GameState, Percept
from DungeonWarden.core.settings import SIGHT_RANGE


class SensorSystem:
    """Simulates the dungeon sensors that provide partial observability to the Warden."""

    @staticmethod
    def compute_sight_cells(
        dmap: DungeonMap,
        walls: frozenset[Cell],
        sight_range: int = SIGHT_RANGE,
    ) -> frozenset[Cell]:
        """Return all cells within `sight_range` steps of any eye sensor, blocked by walls."""
        visible: set[Cell] = set()
        for eye in dmap.eyes:
            frontier: deque[tuple[Cell, int]] = deque([(eye, 0)])
            local_seen: set[Cell] = {eye}
            while frontier:
                cell, dist = frontier.popleft()
                if dist == sight_range:
                    continue
                for neighbor in dmap.get_neighbors(cell, walls):
                    if neighbor not in local_seen:
                        local_seen.add(neighbor)
                        frontier.append((neighbor, dist + 1))
            visible |= local_seen
        return frozenset(visible)

    @classmethod
    def sense(
        cls,
        dmap: DungeonMap,
        state: GameState,
        prev_cell: Cell,
        cur_cell: Cell,
    ) -> Percept:
        """Generate the Warden's Percept after the player moves from `prev_cell` to `cur_cell`."""
        stepped = cur_cell if cur_cell in dmap.plates else None
        noise: Cell | None = None
        if cur_cell != prev_cell:
            if cur_cell in dmap.doors:
                noise = cur_cell
            elif prev_cell in dmap.doors:
                noise = prev_cell
        sight = cls.compute_sight_cells(dmap, state.walls)
        seen = cur_cell if cur_cell in sight else None
        return Percept(stepped=stepped, noise=noise, sight=sight, seen=seen)

