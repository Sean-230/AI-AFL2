"""DifficultyCalibrator class: calibrates turn limits (T) per difficulty on 20x20 maps."""
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


def _measure_win_rate(path: str, turn_limit: int, games: int, seed: int) -> float:
    dmap = DungeonMap.load(path)
    wins = total = 0
    for i in range(games):
        for bot_key in BOTS:
            match = MatchEngine(dmap, "W2", T=turn_limit, seed=seed + i)
            bot = BOTS[bot_key](seed + i)
            while not match.winner:
                match.step(bot.move(match))
            wins += int(match.winner == "player")
            total += 1
    return 100.0 * wins / total


def _coarse_worker(job: tuple[str, int, int, int]) -> tuple[tuple[str, int, int, int], float]:
    path, turn_limit, games, seed = job
    return job, _measure_win_rate(path, turn_limit, games, seed)


def _bisect_worker(
    job: tuple[str, int, int, int, dict[int, float], int, int],
) -> tuple[tuple[str, int], dict[int, float]]:
    path, target, lo, hi, known, games, seed = job
    tried = dict(known)
    while hi - lo > 1:
        mid = (lo + hi) // 2
        tried[mid] = _measure_win_rate(path, mid, games, seed)
        lo, hi = (mid, hi) if tried[mid] < target else (lo, mid)
    return (path, target), tried


class DifficultyCalibrator:
    """Calibrates turn limits (T) for Easy (50%), Normal (30%), and Hard (15%) player win rates."""

    def __init__(self, games: int = 15, seed: int = 5000, jobs: int | None = None) -> None:
        self.games = games
        self.seed = seed
        self.jobs = jobs or os.cpu_count()

    @staticmethod
    def ensure_strict_separation(table: dict[str, int], curve: dict[int, float]) -> dict[str, int]:
        """Ensure Easy > Normal > Hard by at least 1 turn."""
        keys = list(DIFFICULTIES)[::-1]  # hard, normal, easy
        for harder, easier in zip(keys, keys[1:]):
            if table[easier] <= table[harder]:
                table[easier] = table[harder] + 1
                nearest_t = min(curve, key=lambda t: abs(t - table[easier]))
                table[f"{easier}_win"] = round(curve[nearest_t])
        return table

    def calibrate_all(self) -> None:
        """Run Step 1 (coarse scan) and Step 2 (bisection) across all 20x20 maps."""
        paths = [str(p) for p in SettingsManager.map_paths()]
        coarse_jobs: list[tuple[str, int, int, int]] = []
        for path in paths:
            shortest = MatchEngine(DungeonMap.load(path)).original_len
            for t_val in sorted({math.ceil(f * shortest) for f in SCAN_FACTORS}):
                coarse_jobs.append((path, t_val, self.games, self.seed))

        print(f"Step 1: {len(paths)} maps, {len(coarse_jobs)} test points...", flush=True)
        curves: dict[str, dict[int, float]] = {p: {} for p in paths}
        with ProcessPoolExecutor(max_workers=self.jobs) as executor:
            for idx, ((path, t_val, *_), rate) in enumerate(
                executor.map(_coarse_worker, coarse_jobs), 1
            ):
                curves[path][t_val] = rate
                mkey = SettingsManager.map_key(path)
                print(f"  {idx}/{len(coarse_jobs)}  {mkey} T={t_val}: {rate:.0f}%", flush=True)

        refine_jobs = []
        for path in paths:
            curve = sorted(curves[path].items())
            for diff in DIFFICULTIES.values():
                below = [t for t, r in curve if r < diff.target_win_rate]
                above = [t for t, r in curve if r >= diff.target_win_rate]
                if below and above and min(above) - max(below) > 1:
                    lo, hi = max(below), min(above)
                    refine_jobs.append(
                        (
                            path,
                            diff.target_win_rate,
                            lo,
                            hi,
                            {lo: curves[path][lo], hi: curves[path][hi]},
                            self.games,
                            self.seed,
                        )
                    )

        print(f"Step 2: bisecting {len(refine_jobs)} brackets...", flush=True)
        with ProcessPoolExecutor(max_workers=self.jobs) as executor:
            for (path, target), tried in executor.map(_bisect_worker, refine_jobs):
                curves[path].update(tried)
                mkey = SettingsManager.map_key(path)
                pts = "  ".join(f"T={t}:{r:.0f}%" for t, r in sorted(tried.items()))
                print(f"  {mkey} target {target}%: {pts}", flush=True)

        balance: dict[str, dict[str, int]] = {}
        for path in paths:
            mkey = SettingsManager.map_key(path)
            curve = sorted(curves[path].items())
            print(f"\n{mkey}:  " + "  ".join(f"T={t}:{r:.0f}%" for t, r in curve))
            table: dict[str, int] = {}
            for diff in DIFFICULTIES.values():
                best_t, best_rate = min(
                    curve, key=lambda tr: (abs(tr[1] - diff.target_win_rate), tr[0])
                )
                table[diff.key] = best_t
                table[f"{diff.key}_win"] = round(best_rate)
            balance[mkey] = self.ensure_strict_separation(table, curves[path])
            for diff in DIFFICULTIES.values():
                print(
                    f"   {diff.label:<7} target {diff.target_win_rate}% -> "
                    f"T={table[diff.key]} ({table[diff.key + '_win']}%)"
                )

        BALANCE_FILE.write_text(json.dumps(balance, indent=2) + "\n", encoding="utf-8")
        print(f"\nWrote {BALANCE_FILE}")


def main(argv: list[str] | None = None) -> None:
    """CLI entry point for calibrating map turn limits."""
    ap = argparse.ArgumentParser(description="Calibrate 20x20 map turn limits per difficulty")
    ap.add_argument("--games", type=int, default=15, help="games per bot per test point")
    ap.add_argument("--seed", type=int, default=5000)
    ap.add_argument("--jobs", type=int, default=os.cpu_count())
    args = ap.parse_args(argv)
    DifficultyCalibrator(games=args.games, seed=args.seed, jobs=args.jobs).calibrate_all()


if __name__ == "__main__":
    main()
