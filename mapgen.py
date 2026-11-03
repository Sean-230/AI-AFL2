"""Map generators: random_map (noise, for the 8x8 to 20x20 scaling test) and dungeon_map
(rooms and corridors, used once to make the curated 20x20 maps in maps/20x20/)."""
from __future__ import annotations

import random
from types import SimpleNamespace

from search import bfs_distances
from world import DungeonMap, neighbors


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
                door_p: float = 0.7, plates: int = 10, eyes: int = 4, treasure_sector=None,
                winding: bool = False, parallel: int = 1, grid_n: int = 3) -> DungeonMap:
    """Rooms in a grid_n x grid_n layout (3x3 for 20x20 maps, 2x2 for 10x10) joined by corridors: a random spanning tree plus `extra_links` loops,
    so the player always has a detour. Doors sit where corridors leave rooms, plates on corridors,
    eyes in room centres. The player starts in the top-left room. `parallel` carves that many
    separate corridors per link and extra_links=4 links every neighbouring pair of rooms, which gives
    the player many independent routes (see route_count)."""
    rng = random.Random(seed)
    span = (n - (grid_n - 1)) // grid_n         # sector width; sectors are 1 wall apart
    treasure_sector = treasure_sector or (grid_n - 1, grid_n - 1)
    origin = lambda k: k * (span + 1)
    grid = [["#"] * n for _ in range(n)]
    rooms = {}
    for sy in range(grid_n):
        for sx in range(grid_n):
            w, h = rng.randint(*room), rng.randint(*room)
            x0 = origin(sx) + rng.randint(0, span - w)
            y0 = origin(sy) + rng.randint(0, span - h)
            cells = {(x, y) for x in range(x0, x0 + w) for y in range(y0, y0 + h)}
            rooms[(sx, sy)] = cells
            for x, y in cells:
                grid[y][x] = "."

    # spanning tree by randomized DFS over the sector grid, then extra loop links
    adj = lambda s: [(s[0] + dx, s[1] + dy) for dx, dy in ((1, 0), (-1, 0), (0, 1), (0, -1))
                     if 0 <= s[0] + dx < grid_n and 0 <= s[1] + dy < grid_n]
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
    for link in sorted(links, key=sorted) * parallel:
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
    def centre(cells):      # a room's middle cell has 4 open neighbours, so routes can leave it 4 ways
        xs, ys = [c[0] for c in cells], [c[1] for c in cells]
        return (min(xs) + max(xs)) // 2, (min(ys) + max(ys)) // 2
    start, treasure = centre(rooms[(0, 0)]), centre(rooms[treasure_sector])
    free_corr = sorted(c for c in corridor_cells if c not in doors)
    plate_cells = set(rng.sample(free_corr, k=min(plates, len(free_corr))))
    centres = [centre(cells) for s, cells in sorted(rooms.items())
               if s not in ((0, 0), treasure_sector)]
    eye_cells = set(rng.sample(centres, k=min(eyes, len(centres))))
    for ch, cells in (("D", doors), ("o", plate_cells), ("E", eye_cells)):
        for x, y in cells:
            grid[y][x] = ch
    grid[start[1]][start[0]] = "P"
    grid[treasure[1]][treasure[0]] = "T"
    return DungeonMap(["".join(r) for r in grid], name)


def route_count(dmap: DungeonMap, doors_open: bool = True) -> int:
    """How many routes from start to treasure share no cell (vertex-disjoint paths, by max-flow).
    Each one is an independent way round the Warden, so this is the map's route variety.
    doors_open=False counts only door-free routes, the ones a LockDoor can never cut."""
    from collections import deque
    blocked = dmap.walls | (set() if doors_open else dmap.doors)
    free = [c for c in dmap.cells if c not in blocked]
    cap = {}                                # residual capacities of the split graph, (cell, 0=in/1=out)
    adj = {}
    def edge(u, v, c):
        cap[(u, v)] = cap.get((u, v), 0) + c
        cap.setdefault((v, u), 0)
        adj.setdefault(u, []).append(v)
        adj.setdefault(v, []).append(u)
    for c in free:
        edge((c, 0), (c, 1), 99 if c in (dmap.start, dmap.treasure) else 1)
        for n in neighbors(c, dmap, frozenset(blocked)):
            edge((c, 1), (n, 0), 1)
    s, t, flow = (dmap.start, 0), (dmap.treasure, 1), 0
    while True:
        prev = {s: None}
        q = deque([s])
        while q and t not in prev:
            u = q.popleft()
            for v in adj.get(u, ()):
                if v not in prev and cap[(u, v)] > 0:
                    prev[v] = u
                    q.append(v)
        if t not in prev:
            return flow
        v = t
        while prev[v] is not None:
            cap[(prev[v], v)] -= 1
            cap[(v, prev[v])] += 1
            v = prev[v]
        flow += 1
