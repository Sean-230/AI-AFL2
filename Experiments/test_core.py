"""Unit test suite for the OOP Agent-Environment Dungeon Warden architecture (20x20 maps).

Run with:
    python -m unittest discover Experiments -v
"""
from __future__ import annotations

from pathlib import Path
import random
import sys
import unittest

ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from DungeonWarden.ai.knowledge_base import FOL_RULES, ActionValidator, KnowledgeBase  # noqa: E402
from DungeonWarden.ai.pathfinder import Pathfinder  # noqa: E402
from DungeonWarden.core.action_schema import StripsActionSchema  # noqa: E402
from DungeonWarden.core.dungeon_map import DungeonMap  # noqa: E402
from DungeonWarden.core.game_state import GameState  # noqa: E402
from DungeonWarden.core.map_generator import MapGenerator, RouteAnalyzer  # noqa: E402
from DungeonWarden.core.match_engine import MatchEngine  # noqa: E402
from DungeonWarden.core.sensor_system import SensorSystem  # noqa: E402
from DungeonWarden.core.settings import DIFFICULTIES, SettingsManager  # noqa: E402
from Experiments.evaluation_wardens import WARDENS  # noqa: E402
from Experiments.player_bots import BOTS  # noqa: E402

MAPS = [DungeonMap.load(p) for p in SettingsManager.map_paths()]


def play_out(dmap: DungeonMap, warden: str, bot: str, seed: int, **kwargs) -> MatchEngine:
    """Helper to run a complete headless match to completion."""
    match = MatchEngine(dmap, WARDENS[warden], seed=seed, check_astar=True, **kwargs)
    bot_agent = BOTS[bot](seed)
    while not match.winner:
        match.step(bot_agent.move(match))
    return match


class MapTests(unittest.TestCase):
    """Verify 20x20 map models, route diversity, and difficulty calibration."""

    def test_maps_load_and_are_solvable(self) -> None:
        self.assertEqual(len(MAPS), 3)
        for m in MAPS:
            self.assertEqual((m.w, m.h), (20, 20), m.name)
            self.assertIn(m.treasure, Pathfinder.bfs_distances(m.start, m, m.walls), m.name)

    def test_maps_have_many_routes(self) -> None:
        for m in MAPS:
            self.assertGreaterEqual(RouteAnalyzer.count_disjoint_routes(m), 4, m.name)
            self.assertGreaterEqual(
                RouteAnalyzer.count_disjoint_routes(m, doors_open=False), 2, m.name
            )

    def test_route_count(self) -> None:
        corridor = DungeonMap(["P.T"])
        self.assertEqual(RouteAnalyzer.count_disjoint_routes(corridor), 1)
        ring = DungeonMap(["P..", ".#.", "..T"])
        self.assertEqual(RouteAnalyzer.count_disjoint_routes(ring), 2)
        gated = DungeonMap(["PDT", "...", "..."])
        self.assertEqual(RouteAnalyzer.count_disjoint_routes(gated, doors_open=False), 1)
        self.assertGreaterEqual(RouteAnalyzer.count_disjoint_routes(gated), 2)

    def test_every_map_is_calibrated(self) -> None:
        balance = SettingsManager.load_balance()
        for p in SettingsManager.map_paths():
            key = SettingsManager.map_key(p)
            self.assertIn(key, balance, f"run calibrate.py: {p} has no turn limits")
            self.assertGreater(balance[key]["T"], 0, f"{p}: {balance[key]}")

    def test_bad_map_rejected(self) -> None:
        with self.assertRaises(ValueError):
            DungeonMap(["P..", "..."])
        with self.assertRaises(ValueError):
            DungeonMap(["P.T", ".."])
        with self.assertRaises(ValueError):
            DungeonMap(["P?T"])


class SearchTests(unittest.TestCase):
    """Verify A* completeness and optimality against BFS ground truth."""

    def test_astar_matches_bfs(self) -> None:
        rng = random.Random(7)
        for n in (8, 12, 20):
            for k in range(5):
                m = MapGenerator.generate_random_map(n, seed=k)
                cells = [c for c in m.cells if c not in m.walls]
                for _ in range(40):
                    a, b = rng.choice(cells), rng.choice(cells)
                    path, _ = Pathfinder.astar(a, b, m, m.walls)
                    d = Pathfinder.bfs_distances(a, m, m.walls).get(b)
                    if d is None:
                        self.assertIsNone(path)
                    else:
                        assert path is not None
                        self.assertEqual(len(path) - 1, d)
                        self.assertTrue(
                            all(
                                DungeonMap.manhattan(p, q) == 1
                                for p, q in zip(path, path[1:])
                            )
                        )


class KnowledgeBaseTests(unittest.TestCase):
    """Verify First-Order Logic rules R1-R4 and Valid(a)."""

    def setUp(self) -> None:
        self.m = DungeonMap(["P....", ".##D.", ".#o..", "E#..T"])
        self.s = GameState.create_initial(self.m)

    def test_plate_pins_player(self) -> None:
        kb = KnowledgeBase(self.m, (3, 2))
        kb.update(SensorSystem.sense(self.m, self.s, (3, 2), (2, 2)), self.s)
        self.assertEqual(kb.belief, {(2, 2)})

    def test_r2_player_must_move(self) -> None:
        kb = KnowledgeBase(self.m, (3, 2))
        kb.update(SensorSystem.sense(self.m, self.s, (3, 2), (4, 2)), self.s)
        self.assertNotIn((3, 2), kb.belief)
        self.assertIn((4, 2), kb.belief)

    def test_only_proposal_rules(self) -> None:
        self.assertEqual(list(FOL_RULES), ["R1", "R2", "R3", "R4", "V"])

    def test_noise_keeps_cells_next_to_door(self) -> None:
        kb = KnowledgeBase(self.m, (4, 1))
        kb.update(SensorSystem.sense(self.m, self.s, (4, 1), (3, 1)), self.s)
        self.assertTrue(all(DungeonMap.manhattan(c, (3, 1)) <= 1 for c in kb.belief))
        self.assertIn((3, 1), kb.belief)

    def test_eye_sight_rule(self) -> None:
        kb = KnowledgeBase(self.m, (0, 1))
        p = SensorSystem.sense(self.m, self.s, (0, 1), (0, 2))
        kb.update(p, self.s)
        self.assertIn((0, 2), kb.belief)
        self.assertFalse((kb.belief & p.sight) - {(0, 2)})

    def test_valid_rejects_trapping_and_disconnecting(self) -> None:
        belief = {(4, 0)}
        self.assertEqual(
            ActionValidator.validate(self.m, self.s, ("PlaceWall", (4, 0)), belief, 10),
            "player may be on that cell",
        )
        s2 = StripsActionSchema.apply_effects(self.s, ("PlaceWall", (4, 2)))
        s2 = GameState(s2.walls, s2.locked, 10, 0)
        self.assertEqual(
            ActionValidator.validate(self.m, s2, ("PlaceWall", (3, 2)), belief, 10),
            "treasure would become unreachable",
        )


class ProposalRulesTests(unittest.TestCase):
    """Verify STRIPS action schema preconditions, effects, and turn timer."""

    def setUp(self) -> None:
        self.m = MAPS[0]
        self.s = GameState(self.m.walls, frozenset(), 6, 0)
        self.door = sorted(self.m.doors)[0]
        self.floor = next(c for c in self.m.cells if self.m.is_plain_floor(c))

    def test_action_schema(self) -> None:
        self.assertEqual(
            StripsActionSchema.apply_effects(self.s, ("LockDoor", self.door)).energy, 4
        )
        self.assertEqual(
            StripsActionSchema.apply_effects(self.s, ("PlaceWall", self.floor)).energy, 3
        )
        self.assertEqual(
            StripsActionSchema.apply_effects(self.s, ("Wait", None)).energy, 7
        )
        locked = StripsActionSchema.apply_effects(self.s, ("LockDoor", self.door))
        self.assertEqual(
            StripsActionSchema.apply_effects(locked, ("UnlockDoor", self.door)).energy, 5
        )
        self.assertEqual(
            StripsActionSchema.check_preconditions(
                self.m, GameState(self.m.walls, frozenset(), 1, 0), ("LockDoor", self.door)
            ),
            "not enough energy",
        )
        self.assertEqual(
            StripsActionSchema.check_preconditions(
                self.m, GameState(self.m.walls, frozenset(), 2, 0), ("PlaceWall", self.floor)
            ),
            "not enough energy",
        )

    def test_action_costs_come_from_the_state(self) -> None:
        dear = GameState.create_initial(self.m, 6, lock_cost=5, wall_cost=8)
        self.assertEqual(
            StripsActionSchema.check_preconditions(self.m, dear, ("PlaceWall", self.floor)), "not enough energy"
        )   # 6 < 8
        rich = GameState.create_initial(self.m, 10, lock_cost=5, wall_cost=8)
        self.assertEqual(StripsActionSchema.apply_effects(rich, ("PlaceWall", self.floor)).energy, 2)
        self.assertEqual(StripsActionSchema.apply_effects(rich, ("LockDoor", self.door)).energy, 5)

    def test_locks_stay_and_no_cooldown(self) -> None:
        s = StripsActionSchema.apply_effects(self.s, ("PlaceWall", self.floor))
        self.assertIsNone(
            StripsActionSchema.check_preconditions(self.m, s, ("LockDoor", self.door))
        )
        s = StripsActionSchema.apply_effects(s, ("LockDoor", self.door))
        for _ in range(50):
            s = s.next_turn()
        self.assertIn(self.door, s.blocked)

    def test_turn_limit(self) -> None:
        self.assertEqual(MatchEngine(self.m).T, 120)
        g = MatchEngine(self.m, WARDENS["W0"], T=3)
        self.assertFalse(g.step("wait"))
        for _ in range(3):
            self.assertTrue(g.step(g.legal_moves()[0][0]))
        self.assertEqual(g.winner, "warden")


class GameTests(unittest.TestCase):
    """Verify full match execution, fairness, recall, and W2 superiority."""

    def test_every_warden_is_fair_and_sound(self) -> None:
        for m in MAPS:
            for w in WARDENS:
                for b in BOTS:
                    g = play_out(m, w, b, seed=1, T=35)
                    tag = (m.name, w, b)
                    self.assertIsNotNone(g.winner, (*tag, "game never ended"))
                    self.assertEqual(g.invalid, 0, tag)
                    self.assertTrue(all(r.true_in_belief for r in g.records), tag)
                    self.assertTrue(all(r.astar_ok for r in g.records), tag)

    def test_big_maps_are_fair_and_fast(self) -> None:
        for m in MAPS:
            g = play_out(m, "W2", "rusher", 1, T=120)
            self.assertIsNotNone(g.winner, m.name)
            self.assertEqual(g.invalid, 0, m.name)
            self.assertTrue(all(r.true_in_belief for r in g.records), m.name)
            self.assertLess(max(r.ms for r in g.records), 1000, m.name)

    def test_illegal_move_uses_no_turn(self) -> None:
        g = MatchEngine(MAPS[0])
        self.assertFalse(g.step("wait"))
        self.assertFalse(g.step("nonsense"))
        self.assertEqual(g.state.turn, 0)

    def test_full_warden_beats_baselines(self) -> None:
        def extra_steps(w: str) -> int:
            return sum(
                play_out(MAPS[i % 3], w, "rusher", 1000 + i, T=60).path_increase()
                for i in range(6)
            )

        w2 = extra_steps("W2")
        self.assertGreater(w2, extra_steps("W0"))
        self.assertGreaterEqual(w2, extra_steps("W1"))

    def test_difficulty_settings(self) -> None:
        m, path = MAPS[0], SettingsManager.map_paths()[0]
        shortest = MatchEngine(m).original_len
        cfg = {d: SettingsManager.get_match_settings(path, shortest, d) for d in DIFFICULTIES}
        # difficulty is the Warden's action costs: T and energy are the same, easier = dearer blocks
        self.assertEqual(len({c["T"] for c in cfg.values()}), 1)
        self.assertEqual({(c["energy"], c["cap"]) for c in cfg.values()}, {(6, 10)})
        self.assertTrue(cfg["easy"]["wall_cost"] > cfg["normal"]["wall_cost"] > cfg["hard"]["wall_cost"], cfg)
        self.assertTrue(cfg["easy"]["lock_cost"] >= cfg["normal"]["lock_cost"] > cfg["hard"]["lock_cost"], cfg)
        self.assertEqual((cfg["hard"]["lock_cost"], cfg["hard"]["wall_cost"]), (2, 3))   # Table 2.1.1
        self.assertEqual(
            SettingsManager.get_match_settings("custom.txt", 10, "normal", balance={})["T"],
            40,
        )

    def test_difficulty_costs_apply_in_a_match(self) -> None:
        """The costs of the difficulty are really charged, and the Warden still never plays an invalid action."""
        m, path = MAPS[0], SettingsManager.map_paths()[0]
        cfg = SettingsManager.get_match_settings(path, MatchEngine(m).original_len, "easy")
        game = play_out(m, "W2", "rusher", 1, **cfg)
        self.assertEqual((game.state.lock_cost, game.state.wall_cost), (cfg["lock_cost"], cfg["wall_cost"]))
        self.assertEqual(game.invalid, 0)
        self.assertTrue(all(r.true_in_belief for r in game.records))


class ArchitectureTests(unittest.TestCase):
    """The game ships only W2; bots and comparison Wardens belong to the evaluation suite."""

    def test_game_package_does_not_contain_evaluation_code(self) -> None:
        forbidden = ("Experiments", "RandomWarden", "GreedyWarden", "OracleWarden", "RusherBot", "CautiousBot")
        for path in (ROOT / "DungeonWarden").rglob("*.py"):
            code = path.read_text(encoding="utf-8")
            for name in forbidden:
                if path.name == "wardens.py" and name == "Experiments":
                    continue   # only mentioned in the module docstring
                self.assertNotIn(name, code, f"{path.relative_to(ROOT)} mentions {name}")

    def test_default_warden_is_the_full_warden(self) -> None:
        self.assertEqual(MatchEngine(MAPS[0]).warden.key, "W2")
        self.assertIs(WARDENS["W2"], type(MatchEngine(MAPS[0]).warden))
        self.assertEqual(set(WARDENS), {"W0", "W1", "W2", "W3"})


if __name__ == "__main__":
    unittest.main()
