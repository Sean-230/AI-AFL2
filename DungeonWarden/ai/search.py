"""A* (route prediction) and BFS (validity check, ground truth for A* tests)."""
from __future__ import annotations

from collections import deque
import heapq
from itertools import count

from DungeonWarden.core.world import Cell, DungeonMap, manhattan, neighbors


def astar(start: Cell, goal: Cell, dmap: DungeonMap, blocked: frozenset, cost=None):
    """Shortest path start -> goal. Returns (path or None, nodes expanded).
    cost(cell) is the price of entering a cell (default 1). Manhattan stays admissible while
    every cost is >= 1, so A* stays optimal."""
    if start == goal:
        return [start], 0
    tie = count()
    heap = [(manhattan(start, goal), 0, next(tie), start)]
    g = {start: 0}
    parent = {start: None}
    closed = set()
    expanded = 0
    while heap:
        _, neg_g, _, c = heapq.heappop(heap)
        gc = -neg_g
        if c in closed:
            continue
        closed.add(c)
        expanded += 1
        if c == goal:
            path = []
            while c is not None:
                path.append(c)
                c = parent[c]
            return path[::-1], expanded
        for n in neighbors(c, dmap, blocked):
            ng = gc + (cost(n) if cost else 1)
            if ng < g.get(n, float("inf")):
                g[n] = ng
                parent[n] = c
                # -ng breaks f-ties toward deeper nodes, which expands fewer cells
                heapq.heappush(heap, (ng + manhattan(n, goal), -ng, next(tie), n))
    return None, expanded


def bfs_distances(src: Cell, dmap: DungeonMap, blocked: frozenset) -> dict[Cell, int]:
    dist = {src: 0}
    q = deque([src])
    while q:
        c = q.popleft()
        for n in neighbors(c, dmap, blocked):
            if n not in dist:
                dist[n] = dist[c] + 1
                q.append(n)
    return dist


class RouteCache:
    """The Warden's predicted player route to the treasure (A*), cached per (start, blocked cells).
    Counts real A* node expansions, which the experiments report."""

    def __init__(self, dmap: DungeonMap, limit: int = 200_000):
        self.dmap = dmap
        self.limit = limit
        self.cache: dict = {}
        self.expanded = 0

    def path(self, start: Cell, blocked: frozenset):
        key = (start, blocked)
        if key not in self.cache:
            if len(self.cache) >= self.limit:
                self.cache.clear()
            p, e = astar(start, self.dmap.treasure, self.dmap, blocked)
            self.expanded += e
            self.cache[key] = p
        return self.cache[key]

    def length(self, start: Cell, blocked: frozenset) -> int | None:
        p = self.path(start, blocked)
        return None if p is None else len(p) - 1

