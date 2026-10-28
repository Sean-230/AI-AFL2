"""Map generators: random_map (noise, for the 8x8 to 20x20 scaling test) and dungeon_map
(rooms and corridors, used once to make the curated 20x20 maps in maps/20x20/)."""
from __future__ import annotations

import random
from types import SimpleNamespace

from search import bfs_distances
from world import DungeonMap


def random_map(n: int, seed: int = 0, wall_p: float = 0.22) -> DungeonMap:
    rng = random.Random(seed)
    for _ in range(1000):
        grid = [["#" if rng.random() < wall_p else "." for _ in range(n)] for _ in range(n)]
        grid[0][0] = "."
        walls = frozenset((x, y) for y in range(n) for x in range(n) if grid[y][x] == "#")
        dist = bfs_distances((0, 0), SimpleNamespace(w=n, h=n), walls)   # BFS only needs the size
        if len(dist) < 0.6 * (n * n - len(walls)):
            continue
        treasure = max(dist, key=lambda c: (dist[c], c))
        if dist[treasure] < n:
            continue

        free = [c for c in dist if c not in ((0, 0), treasure)]
        # doors go in corridor cells: walls on two opposite sides
        def corridor(c):
            x, y = c
            wall = lambda a, b: not (0 <= a < n and 0 <= b < n) or grid[b][a] == "#"
            return (wall(x - 1, y) and wall(x + 1, y)) or (wall(x, y - 1) and wall(x, y + 1))
        doors = rng.sample([c for c in free if corridor(c)], k=min(n // 2, sum(map(corridor, free))))
        rest = [c for c in free if c not in doors]
        plates = rng.sample(rest, k=max(2, n * n // 25))
        rest = [c for c in rest if c not in plates]
        eyes = rng.sample(rest, k=max(1, n // 5))

        for ch, cells in (("D", doors), ("o", plates), ("E", eyes)):
            for x, y in cells:
                grid[y][x] = ch
        grid[0][0] = "P"
        grid[treasure[1]][treasure[0]] = "T"
        return DungeonMap(["".join(r) for r in grid], f"random{n}x{n}_{seed}")
    raise RuntimeError(f"could not generate a {n}x{n} map")


def dungeon_map(seed: int, n: int = 20, name: str = "dungeon", room=(3, 5), extra_links: int = 2,
                door_p: float = 0.7, plates: int = 10, eyes: int = 4, treasure_sector=(2, 2),
                winding: bool = False) -> DungeonMap:
    """Rooms in a 3x3 layout joined by corridors: a random spanning tree plus `extra_links` loops,
    so the player always has a detour. Doors sit where corridors leave rooms, plates on corridors,
    eyes in room centres. The player starts in the top-left room."""
    rng = random.Random(seed)
    span = (n - 2) // 3                         # sector width; sectors are 1 wall apart
    origin = lambda k: k * (span + 1)
    grid = [["#"] * n for _ in range(n)]
    rooms = {}
    for sy in range(3):
        for sx in range(3):
            w, h = rng.randint(*room), rng.randint(*room)
            x0 = origin(sx) + rng.randint(0, span - w)
            y0 = origin(sy) + rng.randint(0, span - h)
            cells = {(x, y) for x in range(x0, x0 + w) for y in range(y0, y0 + h)}
            rooms[(sx, sy)] = cells
            for x, y in cells:
                grid[y][x] = "."

    # spanning tree by randomized DFS over the sector grid, then extra loop links
    adj = lambda s: [(s[0] + dx, s[1] + dy) for dx, dy in ((1, 0), (-1, 0), (0, 1), (0, -1))
                     if 0 <= s[0] + dx < 3 and 0 <= s[1] + dy < 3]
    seen, stack, links = {(0, 0)}, [(0, 0)], set()
    while stack:
        s = stack[-1]
        nxt = [t for t in adj(s) if t not in seen]
        if not nxt:
            stack.pop()
            continue
        t = rng.choice(nxt)
        links.add(frozenset((s, t)))
        seen.add(t)
        stack.append(t)
    spare = [frozenset((s, t)) for s in rooms for t in adj(s) if frozenset((s, t)) not in links]
    links |= set(rng.sample(sorted(spare, key=sorted), k=min(extra_links, len(set(spare)))))

    room_of = {c: s for s, cells in rooms.items() for c in cells}
    corridor_cells, door_spots = set(), []
    for link in sorted(links, key=sorted):
        a, b = sorted(link)
        p = rng.choice(sorted(rooms[a]))
        q = rng.choice(sorted(rooms[b]))
        path = []
        x, y = p
        bends = [(rng.randint(min(p[0], q[0]), max(p[0], q[0])), None)] if winding else []
        def walk_to(tx, ty, horizontal_first):
            nonlocal x, y
            order = ("x", "y") if horizontal_first else ("y", "x")
            for axis in order:
                while (x if axis == "x" else y) != (tx if axis == "x" else ty):
                    if axis == "x":
                        x += 1 if tx > x else -1
                    else:
                        y += 1 if ty > y else -1
                    path.append((x, y))
        if bends:
            walk_to(bends[0][0], y, True)
        walk_to(q[0], q[1], rng.random() < 0.5)
        for c in path:
            if c not in room_of:
                grid[c[1]][c[0]] = "."
                corridor_cells.add(c)
        # door candidates: first corridor cell after leaving each room
        for seq in (path, path[::-1]):
            for c in seq:
                if c not in room_of:
                    door_spots.append(c)
                    break

    def is_corridor(c):
        x, y = c
        wall = lambda a, b: not (0 <= a < n and 0 <= b < n) or grid[b][a] == "#"
        return (wall(x - 1, y) and wall(x + 1, y)) or (wall(x, y - 1) and wall(x, y + 1))

    doors = {c for c in door_spots if is_corridor(c) and rng.random() < door_p}
    start = min(rooms[(0, 0)])
    treasure = max(rooms[treasure_sector]) if treasure_sector != (1, 1) else sorted(rooms[(1, 1)])[len(rooms[(1, 1)]) // 2]
    free_corr = sorted(c for c in corridor_cells if c not in doors)
    plate_cells = set(rng.sample(free_corr, k=min(plates, len(free_corr))))
    centres = [sorted(cells)[len(cells) // 2] for s, cells in sorted(rooms.items())
               if s not in ((0, 0), treasure_sector)]
    eye_cells = set(rng.sample(centres, k=min(eyes, len(centres))))
    for ch, cells in (("D", doors), ("o", plate_cells), ("E", eye_cells)):
        for x, y in cells:
            grid[y][x] = ch
    grid[start[1]][start[0]] = "P"
    grid[treasure[1]][treasure[0]] = "T"
    return DungeonMap(["".join(r) for r in grid], name)
