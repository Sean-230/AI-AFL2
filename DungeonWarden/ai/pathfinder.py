"""Pathfinder (A* and BFS) and RouteCache classes for route prediction and reachability."""
from __future__ import annotations

from collections import deque
import heapq
from itertools import count
from typing import Callable

from DungeonWarden.core.dungeon_map import Cell, DungeonMap


class Pathfinder:
    """Provides A* shortest-path search and Breadth-First Search (BFS) distance maps."""

    @staticmethod
    def astar(
        start: Cell,
        goal: Cell,
        dmap: DungeonMap,
        blocked: frozenset[Cell],
        cost_fn: Callable[[Cell], int] | None = None,
    ) -> tuple[list[Cell] | None, int]:
        """Find the optimal path from `start` to `goal` using A* with Manhattan heuristic."""
        if start == goal:
            return [start], 0

        tie_breaker = count()
        heap: list[tuple[int, int, int, Cell]] = [
            (DungeonMap.manhattan(start, goal), 0, next(tie_breaker), start)
        ]
        g_score: dict[Cell, int] = {start: 0}
        parent: dict[Cell, Cell | None] = {start: None}
        closed: set[Cell] = set()
        expanded = 0

        while heap:
            _, neg_g, _, current = heapq.heappop(heap)
            g_curr = -neg_g
            if current in closed:
                continue
            closed.add(current)
            expanded += 1

            if current == goal:
                path: list[Cell] = []
                node: Cell | None = current
                while node is not None:
                    path.append(node)
                    node = parent[node]
                return path[::-1], expanded

            for neighbor in dmap.get_neighbors(current, blocked):
                step_cost = cost_fn(neighbor) if cost_fn else 1
                tentative_g = g_curr + step_cost
                if tentative_g < g_score.get(neighbor, float("inf")):
                    g_score[neighbor] = tentative_g
                    parent[neighbor] = current
                    f_score = tentative_g + DungeonMap.manhattan(neighbor, goal)
                    heapq.heappush(
                        heap, (f_score, -tentative_g, next(tie_breaker), neighbor)
                    )

        return None, expanded

    @staticmethod
    def bfs_distances(
        src: Cell,
        dmap: DungeonMap,
        blocked: frozenset[Cell],
    ) -> dict[Cell, int]:
        """Compute exact shortest-path step distances from `src` to all reachable cells via BFS."""
        dist: dict[Cell, int] = {src: 0}
        queue: deque[Cell] = deque([src])
        while queue:
            current = queue.popleft()
            for neighbor in dmap.get_neighbors(current, blocked):
                if neighbor not in dist:
                    dist[neighbor] = dist[current] + 1
                    queue.append(neighbor)
        return dist

    @staticmethod
    def bfs_distances_raw(
        src: Cell,
        width: int,
        height: int,
        blocked: frozenset[Cell],
    ) -> dict[Cell, int]:
        """Compute BFS distances on raw grid dimensions before a DungeonMap is instantiated."""
        dist: dict[Cell, int] = {src: 0}
        queue: deque[Cell] = deque([src])
        while queue:
            x, y = queue.popleft()
            for nx, ny in ((x + 1, y), (x - 1, y), (x, y + 1), (x, y - 1)):
                if 0 <= nx < width and 0 <= ny < height and (nx, ny) not in blocked:
                    if (nx, ny) not in dist:
                        dist[(nx, ny)] = dist[(x, y)] + 1
                        queue.append((nx, ny))
        return dist


class RouteCache:
    """Memoizes predicted A* routes from candidate cells to the treasure for a given obstacle set."""

    def __init__(self, dmap: DungeonMap, limit: int = 200_000) -> None:
        self.dmap = dmap
        self.limit = limit
        self.cache: dict[tuple[Cell, frozenset[Cell]], list[Cell] | None] = {}
        self.expanded = 0

    def path(self, start: Cell, blocked: frozenset[Cell]) -> list[Cell] | None:
        """Return the cached A* path from `start` to the treasure, computing it on a cache miss."""
        key = (start, blocked)
        if key not in self.cache:
            if len(self.cache) >= self.limit:
                self.cache.clear()
            route, exp = Pathfinder.astar(start, self.dmap.treasure, self.dmap, blocked)
            self.expanded += exp
            self.cache[key] = route
        return self.cache[key]

    def length(self, start: Cell, blocked: frozenset[Cell]) -> int | None:
        """Return the number of steps along the shortest path to the treasure, or None if unreachable."""
        route = self.path(start, blocked)
        return None if route is None else len(route) - 1
