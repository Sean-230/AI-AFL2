"""DifficultyCalibrator class: calibrates the turn limit T per map and checks the cost-based difficulties.

Difficulty is the Warden's action costs (see DungeonWarden/core/settings.py), so T is the same for every
difficulty. T is calibrated once per map at the reference costs (Hard, the proposal's 2/3) so that
the Full Warden (W2) loses to the simulated players about `target_win_rate`% of the time. Then every
difficulty is measured at that T, which shows how much easier Easy and Normal really are.
"""
from __future__ import annotations

import argparse
from concurrent.futures import ProcessPoolExecutor
import json
import math
import os
from pathlib import Path
import sys

HERE = Path(__file__).resolve().parent
ROOT = HERE.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from DungeonWarden.ai.player_bots import BOTS  # noqa: E402
from DungeonWarden.core.dungeon_map import DungeonMap  # noqa: E402
from DungeonWarden.core.match_engine import MatchEngine  # noqa: E402
from DungeonWarden.core.settings import BALANCE_FILE, DIFFICULTIES, SettingsManager  # noqa: E402

SCAN_FACTORS = (1.2, 1.5, 1.8, 2.0, 2.5, 3.0, 3.5, 4.0, 5.0, 6.0)
REFERENCE = DIFFICULTIES["hard"]   # the proposal's default costs, T is calibrated against them


def _measure_win_rate(
    path: str, turn_limit: int, lock_cost: int, wall_cost: int, games: int, seed: int
) -> float:
    """Player win rate (%) of both simulated players against W2 with the given turn limit and costs."""
    dmap = DungeonMap.load(path)
    wins = total = 0
    for i in range(games):
        for bot_key in BOTS:
            match = MatchEngine(
                dmap, "W2", T=turn_limit, seed=seed + i, lock_cost=lock_cost, wall_cost=wall_cost
            )
            bot = BOTS[bot_key](seed + i)
            while not match.winner:
                match.step(bot.move(match))
            wins += int(match.winner == "player")
            total += 1
    return 100.0 * wins / total


def _coarse_worker(job: tuple[str, int, int, int]) -> tuple[tuple[str, int, int, int], float]:
    path, turn_limit, games, seed = job
    return job, _measure_win_rate(path, turn_limit, REFERENCE.lock_cost, REFERENCE.wall_cost, games, seed)


def _bisect_worker(
    job: tuple[str, int, int, int, dict[int, float], int, int],
) -> tuple[str, dict[int, float]]:
    path, target, lo, hi, known, games, seed = job
    tried = dict(known)
    while hi - lo > 1:
        mid = (lo + hi) // 2
        tried[mid] = _measure_win_rate(path, mid, REFERENCE.lock_cost, REFERENCE.wall_cost, games, seed)
        lo, hi = (mid, hi) if tried[mid] < target else (lo, mid)
    return path, tried


def _difficulty_worker(job: tuple[str, str, int, int, int]) -> tuple[tuple[str, str], float]:
    path, diff_key, turn_limit, games, seed = job
    diff = DIFFICULTIES[diff_key]
    rate = _measure_win_rate(path, turn_limit, diff.lock_cost, diff.wall_cost, games, seed)
    return (path, diff_key), rate


class DifficultyCalibrator:
    """Calibrates T per map at the reference energy, then measures every difficulty at that T."""

    def __init__(self, games: int = 15, seed: int = 5000, jobs: int | None = None) -> None:
        self.games = games
        self.seed = seed
        self.jobs = jobs or os.cpu_count()

    def calibrate_turn_limits(self, paths: list[str]) -> dict[str, int]:
        """Step 1 (coarse scan) and Step 2 (bisection): the T where the reference Warden gets
        the target player win rate on each map."""
        target = REFERENCE.target_win_rate
        coarse_jobs: list[tuple[str, int, int, int]] = []
        for path in paths:
            shortest = MatchEngine(DungeonMap.load(path)).original_len
            for t_val in sorted({math.ceil(f * shortest) for f in SCAN_FACTORS}):
                coarse_jobs.append((path, t_val, self.games, self.seed))

        print(f"Step 1: {len(paths)} maps, {len(coarse_jobs)} test points...", flush=True)
        curves: dict[str, dict[int, float]] = {p: {} for p in paths}
        with ProcessPoolExecutor(max_workers=self.jobs) as executor:
            for idx, ((path, t_val, *_), rate) in enumerate(executor.map(_coarse_worker, coarse_jobs), 1):
                curves[path][t_val] = rate
                print(f"  {idx}/{len(coarse_jobs)}  {SettingsManager.map_key(path)} T={t_val}: {rate:.0f}%", flush=True)

        refine_jobs = []
        for path in paths:
            curve = sorted(curves[path].items())
            below = [t for t, r in curve if r < target]
            above = [t for t, r in curve if r >= target]
            if below and above and min(above) - max(below) > 1:
                lo, hi = max(below), min(above)
                refine_jobs.append(
                    (path, target, lo, hi, {lo: curves[path][lo], hi: curves[path][hi]}, self.games, self.seed)
                )

        print(f"Step 2: bisecting {len(refine_jobs)} brackets...", flush=True)
        with ProcessPoolExecutor(max_workers=self.jobs) as executor:
            for path, tried in executor.map(_bisect_worker, refine_jobs):
                curves[path].update(tried)

        limits: dict[str, int] = {}
        for path in paths:
            curve = sorted(curves[path].items())
            best_t, best_rate = min(curve, key=lambda tr: (abs(tr[1] - target), tr[0]))
            limits[path] = best_t
            print(f"  {SettingsManager.map_key(path)}: T={best_t} ({best_rate:.0f}% at the reference costs)")
        return limits

    def measure_difficulties(self, limits: dict[str, int]) -> dict[str, dict[str, int]]:
        """Step 3: the simulated players' win rate against each difficulty at the calibrated T."""
        jobs = [(p, d, t, self.games, self.seed) for p, t in limits.items() for d in DIFFICULTIES]
        print(f"Step 3: measuring {len(jobs)} map/difficulty pairs...", flush=True)
        table: dict[str, dict[str, int]] = {
            SettingsManager.map_key(p): {"T": t} for p, t in limits.items()
        }
        with ProcessPoolExecutor(max_workers=self.jobs) as executor:
            for (path, diff_key), rate in executor.map(_difficulty_worker, jobs):
                table[SettingsManager.map_key(path)][f"{diff_key}_win"] = round(rate)
        return table

    def write(self, table: dict[str, dict[str, int]]) -> None:
        BALANCE_FILE.write_text(json.dumps(table, indent=2) + "\n", encoding="utf-8")
        print("\nmap            T   " + "".join(f"{d.label:>8}" for d in DIFFICULTIES.values()))
        for mkey, row in table.items():
            wins = "".join(f"{row[d + '_win']:>7}%" for d in DIFFICULTIES)
            print(f"{mkey:<13}{row['T']:>4}   {wins}")
        print(f"\nWrote {BALANCE_FILE}")

    def calibrate_all(self) -> None:
        paths = [str(p) for p in SettingsManager.map_paths()]
        self.write(self.measure_difficulties(self.calibrate_turn_limits(paths)))

    def verify(self) -> None:
        """Re-measure every difficulty at the T values already in balance.json."""
        balance = SettingsManager.load_balance()
        limits = {str(p): balance[SettingsManager.map_key(p)]["T"] for p in SettingsManager.map_paths()}
        self.write(self.measure_difficulties(limits))


def main(argv: list[str] | None = None) -> None:
    """CLI entry point for calibrating map turn limits and checking the difficulties."""
    ap = argparse.ArgumentParser(description="Calibrate 20x20 map turn limits and check the difficulties")
    ap.add_argument("--games", type=int, default=15, help="games per bot per test point")
    ap.add_argument("--seed", type=int, default=5000)
    ap.add_argument("--jobs", type=int, default=os.cpu_count())
    ap.add_argument("--verify", action="store_true", help="only re-measure the difficulties at the saved T")
    args = ap.parse_args(argv)
    calibrator = DifficultyCalibrator(games=args.games, seed=args.seed, jobs=args.jobs)
    calibrator.verify() if args.verify else calibrator.calibrate_all()


if __name__ == "__main__":
    main()
