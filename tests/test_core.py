"""Run with:  .venv/bin/python -m unittest discover tests"""
import random
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from bots import BOTS                                  # noqa: E402
from engine import Match                               # noqa: E402
from kb import KnowledgeBase, is_valid                 # noqa: E402
from mapgen import random_map                          # noqa: E402
from search import astar, bfs_distances                # noqa: E402
from warden import WARDENS                             # noqa: E402
from settings import DIFFICULTIES, game_settings, load_balance, map_key, map_paths  # noqa: E402
from world import (PROPOSAL, RULESETS, VARIANT, DungeonMap, State, apply, initial_state,  # noqa: E402
                   preconditions, sense, tick)

MAPS = [DungeonMap.load(p) for p in map_paths("10x10")]
BIG_MAPS = [DungeonMap.load(p) for p in map_paths("20x20")]
LOCK_TURNS, DOOR_REST, WALL_COOLDOWN = VARIANT.lock_turns, VARIANT.door_rest, VARIANT.wall_cooldown


def play_out(m, warden, bot, seed, rules=PROPOSAL, limit=500, **kw):
    g = Match(m, warden, seed=seed, check_astar=True, rules=rules, **kw)
    b = BOTS[bot](seed)
    while not g.winner and g.state.turn < limit:
        g.step(b.move(g))
    return g


class MapTests(unittest.TestCase):
    def test_maps_load_and_are_solvable(self):
        self.assertEqual(len(MAPS), 3)
        self.assertEqual(len(BIG_MAPS), 3)
        for m in MAPS + BIG_MAPS:
            self.assertEqual((m.w, m.h), (10, 10) if m in MAPS else (20, 20), m.name)
            self.assertIn(m.treasure, bfs_distances(m.start, m, m.walls), m.name)

    def test_every_map_is_calibrated(self):
        balance = load_balance()
        for p in map_paths("all"):
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

    def test_r2_player_must_move_under_proposal(self):
        kb = KnowledgeBase(self.m, (3, 2))
        kb.update(sense(self.m, self.s, (3, 2), (4, 2)), self.s)
        self.assertNotIn((3, 2), kb.belief)      # staying put is not Connected
        self.assertIn((4, 2), kb.belief)
        kb = KnowledgeBase(self.m, (3, 2))
        variant = State(self.s.walls, frozenset(), 6, 0, rules=VARIANT)
        kb.update(sense(self.m, variant, (3, 2), (4, 2)), variant)
        self.assertIn((3, 2), kb.belief)         # the variant lets the player wait

    def test_only_proposal_rules(self):
        from kb import RULES
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
        s2 = State(s2.walls, s2.locks, 10, 0)
        self.assertEqual(is_valid(self.m, s2, ("PlaceWall", (3, 2)), belief, 10), "treasure would become unreachable")


class ProposalRulesTests(unittest.TestCase):
    """The default rules must be exactly Table 2.1.1 of the proposal."""

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
            s = tick(s)
        self.assertIn(self.door, s.blocked)

    def test_turn_limit(self):
        self.assertEqual(Match(self.m).T, 40)
        g = Match(self.m, "W0", T=3)
        self.assertFalse(g.step("wait"))          # the player must move every turn
        for _ in range(3):
            self.assertTrue(g.step(g.legal_moves()[0][0]))
        self.assertEqual(g.winner, "warden")


class GameTests(unittest.TestCase):
    def test_every_warden_is_fair_and_sound(self):
        """Over many games and both rule sets: true cell always in B_t (recall 100%) and no invalid action."""
        for rules in RULESETS.values():
            for m in MAPS:
                for w in WARDENS:
                    for b in BOTS:
                        for seed in range(3):
                            g = play_out(m, w, b, seed, rules)
                            tag = (rules.name, m.name, w, b, seed)
                            self.assertIsNotNone(g.winner, (*tag, "game never ended"))
                            self.assertEqual(g.invalid, 0, tag)
                            self.assertTrue(all(r.true_in_belief for r in g.records), tag)
                            self.assertTrue(all(r.astar_ok for r in g.records), tag)

    def test_big_maps_are_fair_and_fast(self):
        for m in BIG_MAPS:
            for rules in RULESETS.values():
                g = play_out(m, "W2", "rusher", 1, rules, T=150)
                self.assertIsNotNone(g.winner, (m.name, rules.name))
                self.assertEqual(g.invalid, 0, m.name)
                self.assertTrue(all(r.true_in_belief for r in g.records), m.name)
                self.assertLess(max(r.ms for r in g.records), 1000, m.name)

    def test_illegal_move_uses_no_turn(self):
        g = Match(MAPS[0])
        x, y = MAPS[0].start
        illegal = "up" if y == 0 else "left"
        self.assertFalse(g.step(illegal))
        self.assertEqual(g.state.turn, 0)

    def test_variant_has_no_turn_limit(self):
        g = Match(MAPS[0], "W0", rules=VARIANT)
        for _ in range(60):
            g.step("wait")
        self.assertIsNone(g.winner)
        self.assertEqual(g.state.turn, 60)

    def test_full_warden_beats_baselines_proposal(self):
        def player_wins(w):
            return sum(play_out(MAPS[i % 3], w, "rusher", 1000 + i).winner == "player" for i in range(60))
        w2 = player_wins("W2")
        self.assertLess(w2, player_wins("W0"))
        self.assertLessEqual(w2, player_wins("W1"))

    def test_full_warden_delays_more_than_baselines_variant(self):
        def total_turns(w):     # W2's edge over W1 is ~2 turns/game, 30 games is too noisy
            return sum(play_out(MAPS[i % 3], w, "rusher", 1000 + i, VARIANT).state.turn for i in range(150))
        w2 = total_turns("W2")
        self.assertGreater(w2, total_turns("W0"))
        # regression: the horizon effect once let greedy W1 beat W2 against Rusher
        self.assertGreaterEqual(w2, total_turns("W1"))

    def test_difficulty_settings(self):
        m, path = MAPS[0], map_paths("10x10")[0]
        shortest = Match(m).original_len
        T = {d: game_settings(path, shortest, d, PROPOSAL)["T"] for d in DIFFICULTIES}
        self.assertTrue(T["easy"] > T["normal"] > T["hard"] >= shortest, T)
        self.assertIsNone(game_settings(path, shortest, "normal", VARIANT)["T"])
        self.assertEqual(game_settings("custom.txt", 10, "normal", PROPOSAL, balance={})["T"], 40)


class VariantRulesTests(unittest.TestCase):
    def setUp(self):
        self.m = MAPS[0]
        self.door = sorted(self.m.doors)[0]
        self.s = State(self.m.walls, frozenset(), 10, 0, rules=VARIANT)

    def test_lock_reopens_after_lock_turns(self):
        s = apply(self.s, ("LockDoor", self.door))
        for i in range(LOCK_TURNS):
            self.assertIn(self.door, s.blocked, f"should still be locked before move {i + 1}")
            self.assertEqual(s.lock_left(self.door), LOCK_TURNS - i)
            s = tick(s)
        self.assertNotIn(self.door, s.blocked)

    def test_wall_cooldown_does_not_block_locks(self):
        floors = [c for c in self.m.cells if self.m.is_plain_floor(c)]
        s = apply(self.s, ("PlaceWall", floors[0]))
        self.assertEqual(s.cooldown, WALL_COOLDOWN)
        for _ in range(WALL_COOLDOWN - 1):
            s = tick(s)
            self.assertIn("cooldown", preconditions(self.m, s, ("PlaceWall", floors[1])))
            self.assertIsNone(preconditions(self.m, s, ("LockDoor", self.door)))
        s = tick(s)
        self.assertIsNone(preconditions(self.m, s, ("PlaceWall", floors[1])))

    def test_door_cannot_be_relocked_right_away(self):
        """Regression: cheap locks used to keep one door shut forever."""
        s = apply(self.s, ("LockDoor", self.door))
        for _ in range(LOCK_TURNS):
            s = tick(s)
        self.assertNotIn(self.door, s.blocked)
        for _ in range(DOOR_REST):
            self.assertEqual(preconditions(self.m, s, ("LockDoor", self.door)), "door just reopened")
            s = tick(s)
        self.assertIsNone(preconditions(self.m, s, ("LockDoor", self.door)))

    def test_lock_triggers_no_cooldown(self):
        s = apply(self.s, ("LockDoor", self.door))
        self.assertEqual(s.cooldown, 0)
        self.assertIsNone(preconditions(self.m, s, ("LockDoor", sorted(self.m.doors)[1])))

    def test_route_waits_at_soon_open_door(self):
        """The Warden's route length counts waiting at a locked door, never more than walking around."""
        from search import RouteCache
        rc = RouteCache(self.m)
        start = self.m.start
        free = rc.length(start, self.s)
        locked = rc.length(start, apply(self.s, ("LockDoor", self.door)))
        self.assertGreaterEqual(locked, free)
        self.assertLessEqual(locked, free + LOCK_TURNS)


if __name__ == "__main__":
    unittest.main()
