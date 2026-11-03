"""ExperimentController CLI: runs 20x20 Warden evaluations and complexity scaling benchmarks."""
from __future__ import annotations

import argparse
import os
from pathlib import Path
import sys

HERE = Path(__file__).resolve().parent
ROOT = HERE.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from DungeonWarden.ai.player_bots import BOTS  # noqa: E402
from DungeonWarden.ai.wardens import WARDENS  # noqa: E402
from DungeonWarden.core.dungeon_map import DungeonMap  # noqa: E402
from DungeonWarden.core.map_generator import MapGenerator  # noqa: E402
from DungeonWarden.core.match_engine import MatchEngine  # noqa: E402
from DungeonWarden.core.settings import (  # noqa: E402
    DIFFICULTIES,
    ENERGY_CAP,
    ENERGY_START,
    MAP_SIZE,
    SettingsManager,
)
from Experiments.metrics import MetricsAggregator, ReportWriter  # noqa: E402
from Experiments.plotter import ExperimentPlotter  # noqa: E402
from Experiments.runner import SimulationRunner  # noqa: E402


class ExperimentController:
    """Orchestrates benchmark job creation, execution, aggregation, and reporting."""

    def __init__(self, args: argparse.Namespace) -> None:
        self.args = args
        default_sub = (
            "scaling"
            if args.scaling
            else f"{'custom' if args.maps else MAP_SIZE}-{args.difficulty}"
        )
        self.out_dir = Path(args.out or HERE / "results" / default_sub)
        self.out_dir.mkdir(parents=True, exist_ok=True)
        self.runner = SimulationRunner(max_workers=args.jobs)

    def run(self) -> None:
        """Dispatch either the scaling benchmark or the standard W0-W3 evaluation."""
        if self.args.scaling:
            self.run_scaling()
        else:
            self.run_evaluation()

    def run_evaluation(self) -> None:
        """Evaluate W0-W3 against Rusher and Cautious across the 20x20 maps."""
        args = self.args
        paths = args.maps or [str(p) for p in SettingsManager.map_paths()]
        setups: list[tuple[DungeonMap, dict[str, int]]] = []

        for path in paths:
            dmap = DungeonMap.load(path)
            cfg = SettingsManager.get_match_settings(
                path, MatchEngine(dmap).original_len, args.difficulty
            )
            for key in ("T", "energy", "cap", "lock_cost", "wall_cost"):
                if getattr(args, key) is not None:
                    cfg[key] = getattr(args, key)
            setups.append((dmap, cfg))
            print(
                f"  {dmap.name:<10} {dmap.w}x{dmap.h}  T={cfg['T']}  "
                f"energy {cfg['energy']}/{cfg['cap']}  lock {cfg['lock_cost']}e  wall {cfg['wall_cost']}e"
            )

        jobs = [
            dict(
                dmap=setups[i % len(setups)][0],
                warden=w,
                bot=b,
                seed=args.seed + i,
                **setups[i % len(setups)][1],
            )
            for w in args.wardens
            for b in args.bots
            for i in range(args.games)
        ]
        print(
            f"Running {len(jobs)} games ({len(args.wardens)} Wardens x "
            f"{len(args.bots)} bots x {args.games}), {args.difficulty}, with {args.jobs} workers"
        )
        results = self.runner.run_batch(jobs)
        games = [g for g, _ in results]
        moves = [mv for _, ms in results for mv in ms]

        by_pair = MetricsAggregator.summarize_groups(games, moves, ["warden", "bot"])
        by_map = MetricsAggregator.summarize_groups(games, moves, ["warden", "bot", "map"])

        ReportWriter.write_csv(self.out_dir / "games.csv", games)
        ReportWriter.write_csv(self.out_dir / "moves.csv", moves)
        ReportWriter.write_csv(self.out_dir / "summary.csv", by_pair)
        ReportWriter.write_csv(self.out_dir / "summary_by_map.csv", by_map)

        print("\nResults per Warden and bot:")
        ReportWriter.print_summary_table(by_pair, ["warden", "bot"])
        has_charts = ExperimentPlotter.plot_all_evaluation_charts(by_pair, self.out_dir)
        suffix = "  (+ PNG charts)" if has_charts else ""
        print(f"\nCSV files in {self.out_dir}/{suffix}")

    def run_scaling(self) -> None:
        """Benchmark W2 runtime and node expansions across 8x8 to 20x20 grids."""
        args = self.args
        sizes = [8, 10, 12, 14, 16, 18, 20]
        jobs: list[dict] = []
        for n in sizes:
            for k in range(args.scaling_maps):
                dmap = MapGenerator.generate_random_map(n, seed=n * 100 + k)
                for g in range(args.scaling_games):
                    jobs.append(
                        dict(
                            dmap=dmap,
                            warden="W2",
                            bot="rusher",
                            seed=args.seed + g,
                            T=4 * n,
                            energy=args.energy or ENERGY_START,
                            cap=args.cap or ENERGY_CAP,
                        )
                    )
        print(
            f"Scaling test: W2 vs Rusher on {len(jobs)} games, "
            f"sizes {sizes[0]}x{sizes[0]}..{sizes[-1]}x{sizes[-1]}"
        )
        results = self.runner.run_batch(jobs)
        rows = MetricsAggregator.summarize_scaling(sizes, results)

        ReportWriter.write_csv(self.out_dir / "scaling.csv", rows)
        ReportWriter.print_scaling_table(rows)
        if ExperimentPlotter.plot_scaling_chart(rows, self.out_dir / "scaling.png"):
            print(f"\nWrote {self.out_dir}/scaling.csv and scaling.png")
        else:
            print(f"\nWrote {self.out_dir}/scaling.csv")


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    """Parse CLI arguments for the experiment suite."""
    ap = argparse.ArgumentParser(description="Dungeon Warden 20x20 experiments")
    ap.add_argument("--games", type=int, default=200, help="games per (Warden, bot) pair")
    ap.add_argument("--maps", nargs="+", help="explicit map files instead of all 20x20 maps")
    ap.add_argument("--difficulty", default="hard", choices=list(DIFFICULTIES),
                    help="Warden action costs: hard = the proposal's 2/3 (default), easy/normal = dearer")
    ap.add_argument("--wardens", nargs="+", default=sorted(WARDENS), choices=sorted(WARDENS))
    ap.add_argument("--bots", nargs="+", default=sorted(BOTS), choices=sorted(BOTS))
    ap.add_argument("--T", type=int, help="override the turn limit for every map")
    ap.add_argument("--energy", type=int, help="override starting energy")
    ap.add_argument("--cap", type=int, help="override energy cap")
    ap.add_argument("--lock-cost", type=int, help="override the energy cost of LockDoor")
    ap.add_argument("--wall-cost", type=int, help="override the energy cost of PlaceWall")
    ap.add_argument("--seed", type=int, default=1000)
    ap.add_argument("--jobs", type=int, default=os.cpu_count())
    ap.add_argument("--out", help="output folder")
    ap.add_argument("--scaling", action="store_true", help="run grid-size scaling benchmark")
    ap.add_argument("--scaling-maps", type=int, default=5)
    ap.add_argument("--scaling-games", type=int, default=4)
    return ap.parse_args(argv)


def main(argv: list[str] | None = None) -> None:
    """Entry point for running headless experiments."""
    ExperimentController(parse_args(argv)).run()


if __name__ == "__main__":
    main()
