"""A* (route prediction) and BFS (validity check, ground truth for A* tests)."""
from __future__ import annotations

import heapq
import math
from collections import deque
from itertools import count

from world import Cell, DungeonMap, manhattan, neighbors


def astar(start: Cell, goal: Cell, dmap: DungeonMap, blocked: frozenset, cost=None):
    """Shortest path start -> goal. Returns (path or None, nodes expanded).
    cost(cell, g) is the price of entering a cell when g has been spent so far (default 1).
    Manhattan stays admissible while cost >= 1, and waiting never lets you arrive earlier,
    so A* stays optimal with the time-dependent door costs."""
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
            ng = gc + (cost(n, gc) if cost else 1)
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


def dijkstra_to(goal: Cell, dmap: DungeonMap, blocked: frozenset, cost) -> dict[Cell, float]:
    """Cost-to-goal for every cell, where cost(c) is the price of entering c."""
    dist = {goal: 0.0}
    heap = [(0.0, goal)]
    while heap:
        d, c = heapq.heappop(heap)
        if d > dist[c]:
            continue
        for n in neighbors(c, dmap, blocked):
            nd = d + cost(c)    # walking n -> c costs entering c
            if nd < dist.get(n, float("inf")):
                dist[n] = nd
                heapq.heappush(heap, (nd, n))
    return dist


class RouteCache:
    """The Warden's predicted player route to the treasure, cached per state. Counts real A* expansions.

    Walls and doors that stay locked (proposal rules) block. A door that reopens by itself only
    delays the player: the next `lock_left` moves can't enter it, so entering it after g moves
    costs max(1, lock_left + 1 - g), i.e. the player waits at the door.
    The route length is therefore the number of turns the player needs, waiting included."""

    def __init__(self, dmap: DungeonMap, limit: int = 200_000):
        self.dmap = dmap
        self.limit = limit
        self.cache: dict = {}
        self.expanded = 0

    def _get(self, start: Cell, state):
        timers = frozenset((d, state.lock_left(d)) for d in state.locked)
        shut = frozenset(d for d, left in timers if left == math.inf)
        timers -= {(d, math.inf) for d in shut}
        key = (start, state.walls, shut, timers)
        if key not in self.cache:
            if len(self.cache) >= self.limit:
                self.cache.clear()
            wait = dict(timers)
            cost = (lambda c, g: max(1, wait[c] + 1 - g) if c in wait else 1) if wait else None
            p, e = astar(start, self.dmap.treasure, self.dmap, state.walls | shut, cost)
            self.expanded += e
            turns = None
            if p is not None:
                turns = 0
                for c in p[1:]:
                    turns += cost(c, turns) if cost else 1
            self.cache[key] = (p, turns)
        return self.cache[key]

    def path(self, start: Cell, state):
        return self._get(start, state)[0]

    def length(self, start: Cell, state) -> int | None:
        return self._get(start, state)[1]
