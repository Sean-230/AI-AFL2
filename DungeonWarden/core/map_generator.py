"""MapGenerator and RouteAnalyzer classes for dungeon creation and topology verification."""
from __future__ import annotations

from collections import deque
import random

from DungeonWarden.ai.pathfinder import Pathfinder
from DungeonWarden.core.dungeon_map import Cell, DungeonMap


class MapGenerator:
    """Procedural generator for random scaling maps and multi-room dungeon maps."""

    @staticmethod
    def _is_corridor(grid: list[list[str]], size: int, cell: Cell) -> bool:
        """Check whether a cell has walls on two opposite sides (forming a doorway/corridor)."""
        x, y = cell

        def is_wall(ax: int, ay: int) -> bool:
            return not (0 <= ax < size and 0 <= ay < size) or grid[ay][ax] == "#"

        horiz_walls = is_wall(x - 1, y) and is_wall(x + 1, y)
        vert_walls = is_wall(x, y - 1) and is_wall(x, y + 1)
        return horiz_walls or vert_walls

    @classmethod
    def generate_random_map(cls, size: int, seed: int = 0, wall_prob: float = 0.22) -> DungeonMap:
        """Generate a random grid map of dimension `size x size` for scaling benchmarks."""
        rng = random.Random(seed)
        for _ in range(1000):
            grid = [
                ["#" if rng.random() < wall_prob else "." for _ in range(size)]
                for _ in range(size)
            ]
            grid[0][0] = "."
            walls = frozenset(
                (x, y) for y in range(size) for x in range(size) if grid[y][x] == "#"
            )
            dist = Pathfinder.bfs_distances_raw((0, 0), size, size, walls)
            if len(dist) < 0.6 * (size * size - len(walls)):
                continue

            treasure = max(dist, key=lambda c: (dist[c], c))
            if dist[treasure] < size:
                continue

            free = [c for c in dist if c not in ((0, 0), treasure)]
            corridors = [c for c in free if cls._is_corridor(grid, size, c)]
            doors = rng.sample(corridors, k=min(size // 2, len(corridors)))
            rest = [c for c in free if c not in doors]
            plates = rng.sample(rest, k=max(2, size * size // 25))
            rest = [c for c in rest if c not in plates]
            eyes = rng.sample(rest, k=max(1, size // 5))

            for tile_char, cells in (("D", doors), ("o", plates), ("E", eyes)):
                for x, y in cells:
                    grid[y][x] = tile_char
            grid[0][0] = "P"
            grid[treasure[1]][treasure[0]] = "T"
            return DungeonMap(["".join(r) for r in grid], f"random{size}x{size}_{seed}")

        raise RuntimeError(f"Could not generate a {size}x{size} map")

    @classmethod
    def generate_dungeon_map(
        cls,
        seed: int,
        size: int = 20,
        name: str = "dungeon",
        room_bounds: tuple[int, int] = (3, 5),
        extra_links: int = 2,
        door_prob: float = 0.7,
        plates_count: int = 10,
        eyes_count: int = 4,
        treasure_sector: tuple[int, int] | None = None,
        winding: bool = False,
        parallel: int = 1,
        grid_n: int = 3,
    ) -> DungeonMap:
        """Generate a room-and-corridor dungeon map on a `size x size` grid."""
        rng = random.Random(seed)
        span = (size - (grid_n - 1)) // grid_n
        target_sector = treasure_sector or (grid_n - 1, grid_n - 1)
        grid = [["#"] * size for _ in range(size)]
        rooms: dict[tuple[int, int], set[Cell]] = {}

        for sy in range(grid_n):
            for sx in range(grid_n):
                rw = rng.randint(*room_bounds)
                rh = rng.randint(*room_bounds)
                x0 = sx * (span + 1) + rng.randint(0, span - rw)
                y0 = sy * (span + 1) + rng.randint(0, span - rh)
                cells = {(x, y) for x in range(x0, x0 + rw) for y in range(y0, y0 + rh)}
                rooms[(sx, sy)] = cells
                for x, y in cells:
                    grid[y][x] = "."

        links = cls._build_sector_links(rng, rooms, grid_n, extra_links)
        room_of = {c: sector for sector, cells in rooms.items() for c in cells}
        corridor_cells, door_spots = cls._carve_corridors(
            rng, grid, rooms, room_of, links, parallel, winding
        )

        doors = {
            c for c in door_spots
            if cls._is_corridor(grid, size, c) and rng.random() < door_prob
        }
        start = cls._room_center(rooms[(0, 0)])
        treasure = cls._room_center(rooms[target_sector])

        free_corr = sorted(c for c in corridor_cells if c not in doors)
        plate_cells = set(rng.sample(free_corr, k=min(plates_count, len(free_corr))))
        centers = [
            cls._room_center(cells)
            for sector, cells in sorted(rooms.items())
            if sector not in ((0, 0), target_sector)
        ]
        eye_cells = set(rng.sample(centers, k=min(eyes_count, len(centers))))

        for tile_char, cells in (("D", doors), ("o", plate_cells), ("E", eye_cells)):
            for x, y in cells:
                grid[y][x] = tile_char
        grid[start[1]][start[0]] = "P"
        grid[treasure[1]][treasure[0]] = "T"
        return DungeonMap(["".join(r) for r in grid], name)

    @staticmethod
    def _room_center(cells: set[Cell]) -> Cell:
        xs = [c[0] for c in cells]
        ys = [c[1] for c in cells]
        return (min(xs) + max(xs)) // 2, (min(ys) + max(ys)) // 2

    @staticmethod
    def _build_sector_links(
        rng: random.Random,
        rooms: dict[tuple[int, int], set[Cell]],
        grid_n: int,
        extra_links: int,
    ) -> set[frozenset[tuple[int, int]]]:
        def adjacent_sectors(sector: tuple[int, int]) -> list[tuple[int, int]]:
            sx, sy = sector
            return [
                (sx + dx, sy + dy)
                for dx, dy in ((1, 0), (-1, 0), (0, 1), (0, -1))
                if 0 <= sx + dx < grid_n and 0 <= sy + dy < grid_n
            ]

        seen = {(0, 0)}
        stack = [(0, 0)]
        links: set[frozenset[tuple[int, int]]] = set()
        while stack:
            current = stack[-1]
            unvisited = [t for t in adjacent_sectors(current) if t not in seen]
            if not unvisited:
                stack.pop()
                continue
            chosen = rng.choice(unvisited)
            links.add(frozenset((current, chosen)))
            seen.add(chosen)
            stack.append(chosen)

        spare = [
            frozenset((s, t))
            for s in rooms
            for t in adjacent_sectors(s)
            if frozenset((s, t)) not in links
        ]
        unique_spare = sorted(set(spare), key=sorted)
        links |= set(rng.sample(unique_spare, k=min(extra_links, len(unique_spare))))
        return links

    @staticmethod
    def _carve_corridors(
        rng: random.Random,
        grid: list[list[str]],
        rooms: dict[tuple[int, int], set[Cell]],
        room_of: dict[Cell, tuple[int, int]],
        links: set[frozenset[tuple[int, int]]],
        parallel: int,
        winding: bool,
    ) -> tuple[set[Cell], list[Cell]]:
        corridor_cells: set[Cell] = set()
        door_spots: list[Cell] = []

        for link in sorted(links, key=sorted) * parallel:
            sec_a, sec_b = sorted(link)
            p = rng.choice(sorted(rooms[sec_a]))
            q = rng.choice(sorted(rooms[sec_b]))
            path: list[Cell] = []
            x, y = p

            def walk_to(tx: int, ty: int, horiz_first: bool) -> None:
                nonlocal x, y
                axes = ("x", "y") if horiz_first else ("y", "x")
                for axis in axes:
                    while (x if axis == "x" else y) != (tx if axis == "x" else ty):
                        if axis == "x":
                            x += 1 if tx > x else -1
                        else:
                            y += 1 if ty > y else -1
                        path.append((x, y))

            if winding:
                bend_x = rng.randint(min(p[0], q[0]), max(p[0], q[0]))
                walk_to(bend_x, y, True)
            walk_to(q[0], q[1], rng.random() < 0.5)

            for c in path:
                if c not in room_of:
                    grid[c[1]][c[0]] = "."
                    corridor_cells.add(c)
            for seq in (path, path[::-1]):
                for c in seq:
                    if c not in room_of:
                        door_spots.append(c)
                        break

        return corridor_cells, door_spots


class RouteAnalyzer:
    """Analyzes dungeon connectivity and vertex-disjoint route diversity."""

    @staticmethod
    def count_disjoint_routes(dmap: DungeonMap, doors_open: bool = True) -> int:
        """Count vertex-disjoint paths from start to treasure using Edmonds-Karp max-flow."""
        blocked = dmap.walls | (frozenset() if doors_open else dmap.doors)
        free = [c for c in dmap.cells if c not in blocked]
        cap: dict[tuple[tuple[Cell, int], tuple[Cell, int]], int] = {}
        adj: dict[tuple[Cell, int], list[tuple[Cell, int]]] = {}

        def add_edge(u: tuple[Cell, int], v: tuple[Cell, int], capacity: int) -> None:
            cap[(u, v)] = cap.get((u, v), 0) + capacity
            cap.setdefault((v, u), 0)
            adj.setdefault(u, []).append(v)
            adj.setdefault(v, []).append(u)

        for cell in free:
            node_cap = 99 if cell in (dmap.start, dmap.treasure) else 1
            add_edge((cell, 0), (cell, 1), node_cap)
            for neighbor in dmap.get_neighbors(cell, blocked):
                add_edge((cell, 1), (neighbor, 0), 1)

        source, sink = (dmap.start, 0), (dmap.treasure, 1)
        flow = 0
        while True:
            prev: dict[tuple[Cell, int], tuple[Cell, int] | None] = {source: None}
            queue = deque([source])
            while queue and sink not in prev:
                u = queue.popleft()
                for v in adj.get(u, ()):
                    if v not in prev and cap[(u, v)] > 0:
                        prev[v] = u
                        queue.append(v)
            if sink not in prev:
                return flow
            curr = sink
            while prev[curr] is not None:
                parent = prev[curr]
                assert parent is not None
                cap[(parent, curr)] -= 1
                cap[(curr, parent)] += 1
                curr = parent
            flow += 1

