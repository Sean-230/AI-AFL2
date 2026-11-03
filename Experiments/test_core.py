"""Run with:  python -m unittest discover Experiments"""
from pathlib import Path
import random
import sys
import unittest

ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from DungeonWarden.ai.bots import BOTS  # noqa: E402
from DungeonWarden.ai.kb import KnowledgeBase, is_valid  # noqa: E402
from DungeonWarden.ai.search import astar, bfs_distances  # noqa: E402
from DungeonWarden.ai.warden import WARDENS  # noqa: E402
from DungeonWarden.core.engine import Match  # noqa: E402
from DungeonWarden.core.mapgen import random_map, route_count  # noqa: E402
from DungeonWarden.core.settings import (  # noqa: E402
    DIFFICULTIES, game_settings, load_balance, map_key, map_paths,
)
from DungeonWarden.core.world import (  # noqa: E402
    DungeonMap, State, apply, initial_state, next_turn, preconditions, sense,
)

MAPS = [DungeonMap.load(p) for p in map_paths()]


def play_out(m, warden, bot, seed, **kw):
    g = Match(m, warden, seed=seed, check_astar=True, **kw)
    b = BOTS[bot](seed)
    while not g.winner:
        g.step(b.move(g))
    return g


class MapTests(unittest.TestCase):
    def test_maps_load_and_are_solvable(self):
        self.assertEqual(len(MAPS), 3)
        for m in MAPS:
            self.assertEqual((m.w, m.h), (20, 20), m.name)
            self.assertIn(m.treasure, bfs_distances(m.start, m, m.walls), m.name)

    def test_maps_have_many_routes(self):
        """The player needs room to improvise: several routes sharing no cell, some without doors
        (so locks can never cut everything). 20x20 maps need at least 4 routes (2 door-free)."""
        for m in MAPS:
            self.assertGreaterEqual(route_count(m), 4, m.name)
            self.assertGreaterEqual(route_count(m, doors_open=False), 2, m.name)

    def test_route_count(self):
        corridor = DungeonMap(["P.T"])
        self.assertEqual(route_count(corridor), 1)
        ring = DungeonMap(["P..", ".#.", "..T"])       # two ways round the wall
        self.assertEqual(route_count(ring), 2)
        gated = DungeonMap(["PDT", "...", "..."])
        self.assertEqual(route_count(gated, doors_open=False), 1)    # only the open row below counts
        self.assertGreaterEqual(route_count(gated), 2)

    def test_every_map_is_calibrated(self):
        balance = load_balance()
        for p in map_paths():
            self.assertIn(map_key(p), balance, f"run calibrate.py: {p} has no turn limits")
            t = balance[map_key(p)]
            self.assertTrue(t["easy"] > t["normal"] > t["hard"], f"{p}: difficulties must differ: {t}")

    def test_bad_map_rejected(self):
        with self.assertRaises(ValueError):
            DungeonMap(["P..", "..."])          # no treasure
        with self.assertRaises(ValueError):
            DungeonMap(["P.T", ".."])           # ragged rows
        with self.assertRaises(ValueError):
            DungeonMap(["P?T"])                 # unknown tile


class SearchTests(unittest.TestCase):
    def test_astar_matches_bfs(self):
        """Completeness and optimality: A* finds a path iff BFS does, with the same length."""
        rng = random.Random(7)
        for n in (8, 12, 20):
            for k in range(5):
                m = random_map(n, seed=k)
                cells = [c for c in m.cells if c not in m.walls]
                for _ in range(40):
                    a, b = rng.choice(cells), rng.choice(cells)
                    path, _ = astar(a, b, m, m.walls)
                    d = bfs_distances(a, m, m.walls).get(b)
                    if d is None:
                        self.assertIsNone(path)
                    else:
                        self.assertEqual(len(path) - 1, d)
                        self.assertTrue(all(abs(p[0] - q[0]) + abs(p[1] - q[1]) == 1 for p, q in zip(path, path[1:])))


class KnowledgeBaseTests(unittest.TestCase):
    def setUp(self):
        self.m = DungeonMap([
            "P....",
            ".##D.",
            ".#o..",
            "E#..T",
        ])
        self.s = initial_state(self.m)

    def test_plate_pins_player(self):
        kb = KnowledgeBase(self.m, (3, 2))
        kb.update(sense(self.m, self.s, (3, 2), (2, 2)), self.s)
        self.assertEqual(kb.belief, {(2, 2)})

    def test_r2_player_must_move(self):
        kb = KnowledgeBase(self.m, (3, 2))
        kb.update(sense(self.m, self.s, (3, 2), (4, 2)), self.s)
        self.assertNotIn((3, 2), kb.belief)      # staying put is not Connected
        self.assertIn((4, 2), kb.belief)

    def test_only_proposal_rules(self):
        from DungeonWarden.ai.kb import RULES
        self.assertEqual(list(RULES), ["R1", "R2", "R3", "R4", "V"])

    def test_noise_keeps_cells_next_to_door(self):
        kb = KnowledgeBase(self.m, (4, 1))
        kb.update(sense(self.m, self.s, (4, 1), (3, 1)), self.s)   # step onto the door
        self.assertTrue(all(abs(c[0] - 3) + abs(c[1] - 1) <= 1 for c in kb.belief))
        self.assertIn((3, 1), kb.belief)

    def test_eye_sight_rule(self):
        """R3 removes watched cells where the player is not seen; the seen cell stays."""
        kb = KnowledgeBase(self.m, (0, 1))
        p = sense(self.m, self.s, (0, 1), (0, 2))
        kb.update(p, self.s)
        self.assertIn((0, 2), kb.belief)
        self.assertFalse((kb.belief & p.sight) - {(0, 2)})

    def test_valid_rejects_trapping_and_disconnecting(self):
        belief = {(4, 0)}
        self.assertEqual(is_valid(self.m, self.s, ("PlaceWall", (4, 0)), belief, 10), "player may be on that cell")
        # walling (4,2) leaves the route through (3,2); walling both disconnects the treasure
        s2 = apply(self.s, ("PlaceWall", (4, 2)))
        s2 = State(s2.walls, s2.locked, 10, 0)
        self.assertEqual(is_valid(self.m, s2, ("PlaceWall", (3, 2)), belief, 10), "treasure would become unreachable")


class ProposalRulesTests(unittest.TestCase):
    """The rules must be exactly Table 2.1.1 of the proposal."""

    def setUp(self):
        self.m = MAPS[0]
        self.s = State(self.m.walls, frozenset(), 6, 0)
        self.door = sorted(self.m.doors)[0]
        self.floor = next(c for c in self.m.cells if self.m.is_plain_floor(c))

    def test_action_schema(self):
        self.assertEqual(apply(self.s, ("LockDoor", self.door)).energy, 4)
        self.assertEqual(apply(self.s, ("PlaceWall", self.floor)).energy, 3)
        self.assertEqual(apply(self.s, ("Wait", None)).energy, 7)
        locked = apply(self.s, ("LockDoor", self.door))
        self.assertEqual(apply(locked, ("UnlockDoor", self.door)).energy, 5)
        self.assertEqual(preconditions(self.m, State(self.m.walls, frozenset(), 1, 0), ("LockDoor", self.door)),
                         "not enough energy")
        self.assertEqual(preconditions(self.m, State(self.m.walls, frozenset(), 2, 0), ("PlaceWall", self.floor)),
                         "not enough energy")

    def test_locks_stay_and_no_cooldown(self):
        s = apply(self.s, ("PlaceWall", self.floor))
        self.assertIsNone(preconditions(self.m, s, ("LockDoor", self.door)))
        s = apply(s, ("LockDoor", self.door))
        for _ in range(50):
            s = next_turn(s)
        self.assertIn(self.door, s.blocked)

    def test_turn_limit(self):
        self.assertEqual(Match(self.m).T, 120)
        g = Match(self.m, "W0", T=3)
        self.assertFalse(g.step("wait"))          # the player must move every turn
        for _ in range(3):
            self.assertTrue(g.step(g.legal_moves()[0][0]))
        self.assertEqual(g.winner, "warden")


class GameTests(unittest.TestCase):
    def test_every_warden_is_fair_and_sound(self):
        """Over all 20x20 maps and Wardens: true cell always in B_t (recall 100%), no invalid action, A* = BFS."""
        for m in MAPS:
            for w in WARDENS:
                for b in BOTS:
                    g = play_out(m, w, b, seed=1, T=35)
                    tag = (m.name, w, b)
                    self.assertIsNotNone(g.winner, (*tag, "game never ended"))
                    self.assertEqual(g.invalid, 0, tag)
                    self.assertTrue(all(r.true_in_belief for r in g.records), tag)
                    self.assertTrue(all(r.astar_ok for r in g.records), tag)

    def test_big_maps_are_fair_and_fast(self):
        for m in MAPS:
            g = play_out(m, "W2", "rusher", 1, T=120)
            self.assertIsNotNone(g.winner, m.name)
            self.assertEqual(g.invalid, 0, m.name)
            self.assertTrue(all(r.true_in_belief for r in g.records), m.name)
            self.assertLess(max(r.ms for r in g.records), 1000, m.name)

    def test_illegal_move_uses_no_turn(self):
        g = Match(MAPS[0])
        self.assertFalse(g.step("wait"))      # the player must move; a refused move costs no turn
        self.assertFalse(g.step("nonsense"))
        self.assertEqual(g.state.turn, 0)

    def test_full_warden_beats_baselines(self):
        def extra_steps(w):
            return sum(play_out(MAPS[i % 3], w, "rusher", 1000 + i, T=60).path_increase() for i in range(6))
        w2 = extra_steps("W2")
        self.assertGreater(w2, extra_steps("W0"))
        self.assertGreaterEqual(w2, extra_steps("W1"))

    def test_difficulty_settings(self):
        m, path = MAPS[0], map_paths()[0]
        shortest = Match(m).original_len
        T = {d: game_settings(path, shortest, d)["T"] for d in DIFFICULTIES}
        self.assertTrue(T["easy"] > T["normal"] > T["hard"] >= shortest, T)
        self.assertEqual(game_settings("custom.txt", 10, "normal", balance={})["T"], 30)   # 3.0 x shortest


if __name__ == "__main__":
    unittest.main()

