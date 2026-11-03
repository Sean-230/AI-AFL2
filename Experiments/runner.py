"""SimulationRunner class: executes parallel headless matches for evaluation and scaling."""
from __future__ import annotations

from concurrent.futures import ProcessPoolExecutor
from dataclasses import asdict
from pathlib import Path
import sys
import time

ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from DungeonWarden.ai.player_bots import BOTS  # noqa: E402
from DungeonWarden.core.dungeon_map import DungeonMap  # noqa: E402
from DungeonWarden.core.match_engine import MatchEngine  # noqa: E402


def execute_single_match(job: dict) -> tuple[dict, list[dict]]:
    """Worker function executed by ProcessPoolExecutor for a single headless game."""
    dmap: DungeonMap = job["dmap"]
    match = MatchEngine(
        dmap,
        warden=job["warden"],
        T=job["T"],
        energy=job["energy"],
        cap=job["cap"],
        seed=job["seed"],
        check_astar=True,
        **{k: job[k] for k in ("lock_cost", "wall_cost") if k in job},
    )
    bot = BOTS[job["bot"]](job["seed"])
    while not match.winner:
        match.step(bot.move(match))

    game_row = {**match.summary(), "bot": job["bot"], "seed": job["seed"]}
    move_rows = [
        {
            "map": dmap.name,
            "warden": job["warden"],
            "bot": job["bot"],
            "seed": job["seed"],
            **asdict(rec),
        }
        for rec in match.records
    ]
    return game_row, move_rows


class SimulationRunner:
    """Runs batches of headless Dungeon Warden simulations across multiple CPU cores."""

    def __init__(self, max_workers: int | None = None) -> None:
        self.max_workers = max_workers

    def run_batch(self, jobs: list[dict]) -> list[tuple[dict, list[dict]]]:
        """Execute `jobs` in parallel and display progress on stdout."""
        t0 = time.perf_counter()
        results: list[tuple[dict, list[dict]]] = []
        step = max(1, len(jobs) // 20)
        with ProcessPoolExecutor(max_workers=self.max_workers) as executor:
            for idx, res in enumerate(executor.map(execute_single_match, jobs, chunksize=4), 1):
                results.append(res)
                if idx % step == 0 or idx == len(jobs):
                    elapsed = time.perf_counter() - t0
                    print(f"\r  {idx}/{len(jobs)} games  {elapsed:5.1f}s", end="", flush=True)
        print()
        return results
