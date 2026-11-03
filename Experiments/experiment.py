"""Headless experiments covering all six metrics from Proposal Section 2.2 (20x20 Dungeon Maps).

Evaluated Metrics:
  1. Player win rate (lower is better for the Warden)
  2. Path-length increase (final minus original shortest path)
  3. Belief recall (must be 100%) and precision (mean 1/|B_t|)
  4. Invalid actions (must be 0)
  5. Nodes expanded and time per move (8x8 to 20x20) vs complexity estimates
  6. A* completeness and optimality, checked against BFS route lengths

Usage:
  python Experiments/experiment.py                    # 4 Wardens x 2 bots x 200 games on 20x20 maps
  python Experiments/experiment.py --scaling          # Grid-size scaling (8x8..20x20) for Metric 5
  python Experiments/experiment.py --verify-astar     # Standalone A* completeness & optimality verification (Metric 6)
  python Experiments/experiment.py --all              # Run full evaluation suite (20x20 games, scaling, & A* check)
  python Experiments/experiment.py --difficulty hard  # Turn limit from DungeonWarden/maps/balance.json
  python Experiments/experiment.py --games 20         # Quick benchmark run

Each run writes to Experiments/results/20x20-<difficulty>/: games.csv, moves.csv, summary.csv,
summary_by_map.csv, and PNG charts. Scaling outputs write to Experiments/results/scaling/.
"""
from __future__ import annotations

import argparse
from concurrent.futures import ProcessPoolExecutor
import csv
from dataclasses import asdict
import math
import os
from pathlib import Path
import statistics as stats
import sys
import time

HERE = Path(__file__).resolve().parent
ROOT = HERE.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from DungeonWarden.ai.bots import BOTS  # noqa: E402
from DungeonWarden.ai.search import astar, bfs_distances  # noqa: E402
from DungeonWarden.ai.warden import LOOKAHEAD, MAX_BLOCKS, WARDENS  # noqa: E402
from DungeonWarden.core.engine import Match  # noqa: E402
from DungeonWarden.core.mapgen import random_map  # noqa: E402
from DungeonWarden.core.settings import DIFFICULTIES, MAP_SIZE, game_settings, map_paths  # noqa: E402
from DungeonWarden.core.world import ENERGY_CAP, ENERGY_START, DungeonMap  # noqa: E402

# validated categorical palette (dataviz reference), fixed order W0..W3
SERIES = {"W0": "#2a78d6", "W1": "#eb6834", "W2": "#1baf7a", "W3": "#eda100"}


def play(job: dict):
    dmap: DungeonMap = job["dmap"]
    m = Match(dmap, job["warden"], job["T"], job["energy"], job["cap"], job["seed"], check_astar=True)
    bot = BOTS[job["bot"]](job["seed"])
    while not m.winner:
        m.step(bot.move(m))
    recs = m.records
    game = {**m.summary(), "bot": job["bot"], "seed": job["seed"]}
    moves = [{"map": dmap.name, "warden": job["warden"], "bot": job["bot"], "seed": job["seed"], **asdict(r)}
             for r in recs]
    return game, moves


def run_jobs(jobs, workers):
    t0 = time.perf_counter()
    out = []
    with ProcessPoolExecutor(max_workers=workers) as ex:
        for i, res in enumerate(ex.map(play, jobs, chunksize=4), 1):
            out.append(res)
            if i % max(1, len(jobs) // 20) == 0 or i == len(jobs):
                print(f"\r  {i}/{len(jobs)} games  {time.perf_counter() - t0:5.1f}s", end="", flush=True)
    print()
    return out


def write_csv(path: Path, rows: list[dict]):
    if not rows:
        return
    with path.open("w", newline="") as f:
        w = csv.DictWriter(f, fieldnames=list(rows[0]))
        w.writeheader()
        w.writerows(rows)


def p95(xs):
    xs = sorted(xs)
    return xs[min(len(xs) - 1, int(0.95 * len(xs)))] if xs else 0.0


def summarize(games, moves, keys):
    rows = []
    groups = sorted({tuple(g[k] for k in keys) for g in games})
    for key in groups:
        gs = [g for g in games if tuple(g[k] for k in keys) == key]
        ms = [mv["ms"] for mv in moves if tuple(mv[k] for k in keys) == key]
        rows.append({
            **dict(zip(keys, key)), "games": len(gs),
            "player_win_rate": float(stats.mean(g["player_won"] for g in gs)),
            "turns": float(stats.mean(g["turns"] for g in gs)),
            "path_increase": float(stats.mean(g["path_increase"] for g in gs)),
            "belief_recall": stats.mean(g["recall"] for g in gs),
            "belief_precision": stats.mean(g["precision"] for g in gs),
            "invalid_actions": sum(g["invalid"] for g in gs),
            "nodes_per_move": stats.mean(g["nodes_per_move"] for g in gs),
            "astar_exp_per_move": stats.mean(g["astar_exp_per_move"] for g in gs),
            "ms_mean": stats.mean(ms) if ms else 0.0, "ms_p95": p95(ms), "ms_max": max(ms, default=0.0),
            "astar_mismatch": sum(g["astar_mismatch"] for g in gs),
        })
    return rows


def print_table(rows, keys):
    cols = keys + ["games", "player_win_rate", "turns", "path_increase", "belief_recall", "belief_precision",
                   "invalid_actions", "nodes_per_move", "ms_mean", "ms_max", "astar_mismatch"]
    short = {"player_win_rate": "p.win%", "path_increase": "+path", "belief_recall": "recall",
             "belief_precision": "prec", "invalid_actions": "invalid", "nodes_per_move": "nodes/mv",
             "ms_mean": "ms/mv", "ms_max": "ms max", "astar_mismatch": "A*!=BFS"}

    def fmt(c, v):
        if c in ("player_win_rate", "belief_recall"):
            return f"{100 * v:.1f}"
        return f"{v:.2f}" if isinstance(v, float) else str(v)

    table = [[short.get(c, c) for c in cols]] + [[fmt(c, r[c]) for c in cols] for r in rows]
    widths = [max(len(row[i]) for row in table) for i in range(len(cols))]
    for i, row in enumerate(table):
        print("  " + "  ".join(v.rjust(w) for v, w in zip(row, widths)))
        if i == 0:
            print("  " + "  ".join("-" * w for w in widths))


# ------------------------------------------------------------------ charts

def _style(ax, title, ylabel):
    ax.set_title(title, loc="left", fontsize=12, color="#1a1a19", pad=12)
    ax.set_ylabel(ylabel, color="#5f5e5a")
    ax.grid(axis="y", color="#e6e5e0", linewidth=0.8)
    ax.set_axisbelow(True)
    for s in ("top", "right", "left"):
        ax.spines[s].set_visible(False)
    ax.spines["bottom"].set_color("#c3c2b7")
    ax.tick_params(colors="#5f5e5a", length=0)


def chart_by_warden(rows, metric, title, ylabel, path, pct=False):
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt

    bots = sorted({r["bot"] for r in rows})
    wardens = sorted({r["warden"] for r in rows})
    fig, ax = plt.subplots(figsize=(7.5, 4.2), dpi=150)
    width = 0.8 / len(wardens)
    for i, w in enumerate(wardens):
        for j, b in enumerate(bots):
            r = next((r for r in rows if r["warden"] == w and r["bot"] == b), None)
            if r is None:
                continue
            v = r[metric] * (100 if pct else 1)
            x = j + (i - (len(wardens) - 1) / 2) * width
            ax.bar(x, v, width - 0.03, color=SERIES.get(w, "#888"), label=f"{w} {WARDENS[w].label}" if j == 0 else None)
            ax.text(x, v, f"{v:.0f}" if pct else f"{v:.1f}", ha="center", va="bottom", fontsize=8, color="#5f5e5a")
    ax.set_xticks(range(len(bots)), [b.title() for b in bots])
    _style(ax, title, ylabel)
    ax.legend(frameon=False, ncols=len(wardens), loc="upper center", bbox_to_anchor=(0.5, -0.1), fontsize=9)
    fig.tight_layout()
    fig.savefig(path)
    plt.close(fig)


def chart_scaling(rows, path):
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt

    xs = [r["n"] for r in rows]
    base_ms, base_est = rows[0]["ms_mean"] or 1e-9, rows[0]["estimate"]
    measured_time = [r["ms_mean"] / base_ms for r in rows]
    estimate_time = [r["estimate"] / base_est for r in rows]

    nodes_measured = [r["nodes_per_move"] for r in rows]
    # Theoretical branching bounds: alpha-beta effective b^(d/2) vs worst-case b^d (b=8, d=3)
    ab_estimate = [8 ** 1.5] * len(xs)     # ~22.6 nodes
    worst_estimate = [8 ** 3] * len(xs)   # 512 nodes

    fig, (ax1, ax2) = plt.subplots(1, 2, figsize=(13, 4.5), dpi=150)

    # Subplot 1: Time per move vs Theoretical Time Complexity O(b^(d/2) · V · log V)
    ax1.plot(xs, measured_time, color=SERIES["W0"], linewidth=2, marker="o", markersize=5, label="measured time / move")
    ax1.plot(xs, estimate_time, color=SERIES["W1"], linewidth=2, marker="s", markersize=5, linestyle="--",
             label="estimate b^(d/2)·V·log V")
    ax1.annotate("measured", (xs[-1], measured_time[-1]), xytext=(6, 0), textcoords="offset points", va="center", fontsize=9, color="#1a1a19")
    ax1.annotate("estimate", (xs[-1], estimate_time[-1]), xytext=(6, 0), textcoords="offset points", va="center", fontsize=9, color="#1a1a19")
    ax1.set_xticks(xs, [f"{n}x{n}" for n in xs])
    _style(ax1, f"Time per move vs grid size (indexed, {xs[0]}x{xs[0]} = 1)", "relative to smallest grid")
    ax1.legend(frameon=False, loc="upper left", fontsize=8.5)

    # Subplot 2: Minimax Nodes Evaluated per move vs Theoretical Branching
    ax2.plot(xs, nodes_measured, color=SERIES["W2"], linewidth=2, marker="^", markersize=6, label="measured Minimax nodes / move")
    ax2.plot(xs, ab_estimate, color=SERIES["W3"], linewidth=1.8, linestyle="--", label="alpha-beta effective b^(d/2) ≈ 22.6")
    ax2.plot(xs, worst_estimate, color="#999999", linewidth=1.5, linestyle=":", label="worst-case Minimax b^d = 512")
    for x, n_val in zip(xs, nodes_measured):
        ax2.annotate(f"{n_val:.1f}", (x, n_val), textcoords="offset points", xytext=(0, 6), ha="center", fontsize=8, color="#1a1a19")
    ax2.set_xticks(xs, [f"{n}x{n}" for n in xs])
    ax2.set_ylim(0, max(max(nodes_measured) * 1.35, 60))
    _style(ax2, "Nodes evaluated per move vs Branching Complexity", "evaluated game-tree nodes")
    ax2.legend(frameon=False, loc="upper left", fontsize=8.5)

    fig.tight_layout()
    fig.savefig(path)
    plt.close(fig)
def charts(summary, out: Path):
    try:
        chart_by_warden(summary, "turns", "Turns the player needed to reach the treasure (higher is better for the Warden)", "turns", out / "turns.png")
        if any(r["player_win_rate"] < 1 for r in summary):     # only meaningful with a turn limit
            chart_by_warden(summary, "player_win_rate", "Player win rate (lower is better for the Warden)", "% games won by player", out / "win_rate.png", pct=True)
        chart_by_warden(summary, "path_increase", "Path-length increase forced on the player", "extra steps vs shortest path", out / "path_increase.png")
        chart_by_warden(summary, "belief_precision", "Belief precision (mean 1/|B_t|)", "precision", out / "belief_precision.png")
        return True
    except ImportError:
        return False


def verify_astar(samples_per_size: int = 60, sizes=(8, 10, 12, 14, 16, 18, 20), seed: int = 42) -> dict:
    """Proposal Metric 6: Verify A* completeness and optimality against BFS ground truth.
    Tests both reachable and unreachable pairs across multiple grid dimensions."""
    import random
    rng = random.Random(seed)
    total_checks = 0
    connected_checks = 0
    unconnected_checks = 0
    optimal_matches = 0
    completeness_matches = 0

    print(f"\nVerifying A* Completeness & Optimality against BFS (sizes: {list(sizes)})...")
    for n in sizes:
        for k in range(3):
            dmap = random_map(n, seed=n * 100 + k)
            cells = [c for c in dmap.cells if c not in dmap.walls]
            num_samples = max(4, samples_per_size // 3)
            for _ in range(num_samples):
                a, b = rng.choice(cells), rng.choice(cells)
                blocked = dmap.walls
                # Inject additional blocking walls in 30% of cases to test unreachable scenarios
                if rng.random() < 0.3:
                    subset = rng.sample(cells, min(len(cells) // 3, 15))
                    blocked = blocked | frozenset(c for c in subset if c != a and c != b)

                total_checks += 1
                path, _ = astar(a, b, dmap, blocked)
                bfs_d = bfs_distances(a, dmap, blocked).get(b)

                if bfs_d is not None:
                    connected_checks += 1
                    # Optimality: A* path length matches BFS shortest path
                    # Completeness (solvable): path is found when BFS finds path
                    if path is not None and len(path) - 1 == bfs_d:
                        optimal_matches += 1
                        completeness_matches += 1
                else:
                    unconnected_checks += 1
                    # Completeness (unsolvable): A* returns None when BFS proves unreachable
                    if path is None:
                        completeness_matches += 1

    report = {
        "total_checks": total_checks,
        "connected_checks": connected_checks,
        "unconnected_checks": unconnected_checks,
        "optimal_matches": optimal_matches,
        "completeness_matches": completeness_matches,
        "completeness_rate": completeness_matches / total_checks if total_checks else 1.0,
        "optimality_rate": optimal_matches / connected_checks if connected_checks else 1.0,
    }

    print("  +-------------------------------------------------------------+")
    print("  | Metric 6: A* Completeness and Optimality Verification       |")
    print("  +-------------------------------------------------------------+")
    print(f"  | Total pairs checked      : {report['total_checks']:<32} |")
    print(f"  |   - Reachable pairs      : {report['connected_checks']:<32} |")
    print(f"  |   - Unreachable pairs    : {report['unconnected_checks']:<32} |")
    print(f"  | Completeness rate        : {report['completeness_rate'] * 100:.2f}% (A* finds path iff path exists)|")
    print(f"  | Optimality rate          : {report['optimality_rate'] * 100:.2f}% (A* length == BFS length)      |")
    print("  +-------------------------------------------------------------+\n")
    return report


def run_main(args, out: Path):
    paths = args.maps or [str(p) for p in map_paths()]
    setups = []
    for path in paths:
        dmap = DungeonMap.load(path)
        cfg = game_settings(path, Match(dmap).original_len, args.difficulty)
        for key in ("T", "energy", "cap"):
            if getattr(args, key) is not None:
                cfg[key] = getattr(args, key)
        setups.append((dmap, cfg))
        print(f"  {dmap.name:<10} {dmap.w}x{dmap.h}  T={cfg['T']}  energy {cfg['energy']}/{cfg['cap']}")
    jobs = [dict(dmap=setups[i % len(setups)][0], warden=w, bot=b, seed=args.seed + i,
                 **setups[i % len(setups)][1])
            for w in args.wardens for b in args.bots for i in range(args.games)]
    print(f"Running {len(jobs)} games ({len(args.wardens)} Wardens x {len(args.bots)} bots x {args.games}), "
          f"{args.difficulty}, with {args.jobs} workers")
    results = run_jobs(jobs, args.jobs)
    games = [g for g, _ in results]
    moves = [mv for _, ms in results for mv in ms]

    by_pair = summarize(games, moves, ["warden", "bot"])
    by_map = summarize(games, moves, ["warden", "bot", "map"])
    write_csv(out / "games.csv", games)
    write_csv(out / "moves.csv", moves)
    write_csv(out / "summary.csv", by_pair)
    write_csv(out / "summary_by_map.csv", by_map)
    print("\nResults per Warden and bot:")
    print_table(by_pair, ["warden", "bot"])
    print(f"\nCSV files in {out}/" + ("  (+ PNG charts)" if charts(by_pair, out) else ""))

# ------------------------------------------------------------------ main

def main(argv=None):
    ap = argparse.ArgumentParser(description="Dungeon Warden 20x20 experiments")
    ap.add_argument("--games", type=int, default=200, help="games per (Warden, bot) pair, spread over the 20x20 maps")
    ap.add_argument("--maps", nargs="+", help="explicit map files instead of all 20x20 maps")
    ap.add_argument("--difficulty", default="normal", choices=list(DIFFICULTIES),
                    help="sets T per map from DungeonWarden/maps/balance.json")
    ap.add_argument("--wardens", nargs="+", default=sorted(WARDENS), choices=sorted(WARDENS))
    ap.add_argument("--bots", nargs="+", default=sorted(BOTS), choices=sorted(BOTS))
    ap.add_argument("--T", type=int, help="override the turn limit for every map")
    ap.add_argument("--energy", type=int, help="override the Warden's starting energy")
    ap.add_argument("--cap", type=int, help="override the Warden's energy cap")
    ap.add_argument("--seed", type=int, default=1000, help="base seed; game i uses seed+i for every Warden")
    ap.add_argument("--jobs", type=int, default=os.cpu_count(), help="worker processes")
    ap.add_argument("--out", help="output folder (default: Experiments/results/20x20-<difficulty>)")
    ap.add_argument("--scaling", action="store_true", help="run the grid-size scaling test instead (Metric 5)")
    ap.add_argument("--scaling-maps", type=int, default=5, help="random maps per size")
    ap.add_argument("--scaling-games", type=int, default=4, help="games per random map")
    ap.add_argument("--verify-astar", action="store_true", help="verify A* completeness and optimality vs BFS (Metric 6)")
    ap.add_argument("--all", action="store_true", help="run 20x20 experiments, scaling test, and A* verification")
    args = ap.parse_args(argv)
    default_out = "scaling" if args.scaling else f"{'custom' if args.maps else MAP_SIZE}-{args.difficulty}"
    out = Path(args.out or HERE / "results" / default_out)
    out.mkdir(parents=True, exist_ok=True)

    if args.verify_astar:
        return verify_astar()

    if args.scaling:
        return scaling(args, out)

    if args.all:
        print("=== Step 1/3: 20x20 Map Experiments (4 Wardens x 2 Bots) ===")
        run_main(args, out)
        print("\n=== Step 2/3: Grid Scaling Test (8x8 to 20x20) ===")
        scaling_out = Path(HERE / "results" / "scaling")
        scaling_out.mkdir(parents=True, exist_ok=True)
        scaling(args, scaling_out)
        print("\n=== Step 3/3: A* Completeness & Optimality Verification ===")
        verify_astar()
        return

    run_main(args, out)


def scaling(args, out: Path):
    sizes = [8, 10, 12, 14, 16, 18, 20]
    jobs = []
    for n in sizes:
        for k in range(args.scaling_maps):
            dmap = random_map(n, seed=n * 100 + k)
            for g in range(args.scaling_games):
                jobs.append(dict(dmap=dmap, warden="W2", bot="rusher", seed=args.seed + g,
                                 T=4 * n, energy=args.energy or ENERGY_START, cap=args.cap or ENERGY_CAP))
    print(f"Scaling test: W2 vs Rusher on {len(jobs)} games, sizes {sizes[0]}x{sizes[0]}..{sizes[-1]}x{sizes[-1]}")
    results = run_jobs(jobs, args.jobs)
    rows = []
    b = MAX_BLOCKS + 2
    for n in sizes:
        mv = [m for g, ms in results if g["size"] == f"{n}x{n}" for m in ms]
        v = n * n
        rows.append({
            "n": n, "cells": v, "moves": len(mv),
            "nodes_per_move": stats.mean(m["nodes"] for m in mv),
            "astar_exp_per_move": stats.mean(m["expanded"] for m in mv),
            "ms_mean": stats.mean(m["ms"] for m in mv), "ms_p95": p95([m["ms"] for m in mv]),
            "ms_max": max(m["ms"] for m in mv),
            "estimate": b ** (LOOKAHEAD / 2) * v * math.log2(v),
            "astar_mismatch": sum(not m["astar_ok"] for m in mv),
        })
    write_csv(out / "scaling.csv", rows)
    print(f"\n  {'size':>6} {'moves':>6} {'nodes/mv':>9} {'A*exp/mv':>9} {'ms/mv':>7} {'p95':>7} {'max':>7} {'A*!=BFS':>7}")
    for r in rows:
        print(f"  {r['n']:>3}x{r['n']:<2} {r['moves']:>6} {r['nodes_per_move']:>9.1f} {r['astar_exp_per_move']:>9.0f} "
              f"{r['ms_mean']:>7.2f} {r['ms_p95']:>7.2f} {r['ms_max']:>7.2f} {r['astar_mismatch']:>7}")
    try:
        chart_scaling(rows, out / "scaling.png")
        print(f"\nWrote {out}/scaling.csv and scaling.png")
    except ImportError:
        print(f"\nWrote {out}/scaling.csv")


if __name__ == "__main__":
    main()

