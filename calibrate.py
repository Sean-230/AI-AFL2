"""Calibrate the turn limit T of every map for each difficulty (proposal rules).

  python calibrate.py                  # all maps, writes maps/balance.json
  python calibrate.py --games 30       # more games per test point (slower, steadier)

Step 1 plays the Full Warden (W2) against both simulated players at T = 2x..6x the map's
shortest path. Step 2 bisects, per map and difficulty, between the two T values that bracket the
target player win rate (Easy 70%, Normal 45%, Hard 20%), because some maps jump from 0% to ~100%
within a few turns. The bots are greedy, so these numbers are a guide for a human, not a guarantee.
"""
from __future__ import annotations

import argparse
import json
import math
import os
from concurrent.futures import ProcessPoolExecutor

from bots import BOTS
from engine import Match
from settings import BALANCE_FILE, DIFFICULTIES, map_key, map_paths
from world import PROPOSAL, DungeonMap

FACTORS = (2.0, 2.5, 3.0, 3.5, 4.0, 5.0, 6.0)


def rate_at(path: str, T: int, games: int, seed: int) -> float:
    dmap = DungeonMap.load(path)
    wins = n = 0
    for i in range(games):
        for bot in BOTS:
            m = Match(dmap, "W2", T=T, seed=seed + i, rules=PROPOSAL)
            b = BOTS[bot](seed + i)
            while not m.winner:
                m.step(b.move(m))
            wins += m.winner == "player"
            n += 1
    return 100 * wins / n


def coarse(job):
    path, T, games, seed = job
    return job, rate_at(path, T, games, seed)


def bisect(job):
    """Win rate grows with T. Narrow (lo, hi) until they are 1 turn apart; return every point tried."""
    path, target, lo, hi, known, games, seed = job
    tried = dict(known)
    while hi - lo > 1:
        mid = (lo + hi) // 2
        tried[mid] = rate_at(path, mid, games, seed)
        lo, hi = (mid, hi) if tried[mid] < target else (lo, mid)
    return job[:2], tried


def separate(table: dict, curve: dict) -> dict:
    """Some maps jump from ~0% to ~90% within one or two turns, so two difficulties can land on the
    same T. Keep Easy > Normal > Hard by at least one turn; the win rate is the nearest one measured."""
    keys = list(DIFFICULTIES)       # easy, normal, hard
    for harder, easier in zip(keys[1:], keys):
        if table[harder] >= table[easier]:
            table[harder] = table[easier] - 1
            T = min(curve, key=lambda t: abs(t - table[harder]))
            table[f"{harder}_win"] = round(curve[T])
    return table


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--games", type=int, default=15, help="games per bot per test point")
    ap.add_argument("--seed", type=int, default=5000)
    ap.add_argument("--jobs", type=int, default=os.cpu_count())
    args = ap.parse_args(argv)
    paths = [str(p) for p in map_paths("all")]

    jobs = []
    for path in paths:
        shortest = Match(DungeonMap.load(path)).original_len
        for T in sorted({math.ceil(f * shortest) for f in FACTORS}):
            jobs.append((path, T, args.games, args.seed))
    print(f"Step 1: {len(paths)} maps, {len(jobs)} test points...", flush=True)
    curves = {p: {} for p in paths}
    with ProcessPoolExecutor(max_workers=args.jobs) as ex:
        for i, ((path, T, *_), rate) in enumerate(ex.map(coarse, jobs), 1):
            curves[path][T] = rate
            print(f"  {i}/{len(jobs)}  {map_key(path)} T={T}: {rate:.0f}%", flush=True)

    refine = []
    for path in paths:
        curve = sorted(curves[path].items())
        for d in DIFFICULTIES.values():
            below = [T for T, r in curve if r < d.target]
            above = [T for T, r in curve if r >= d.target]
            if below and above and min(above) - max(below) > 1:
                lo, hi = max(below), min(above)
                refine.append((path, d.target, lo, hi, {lo: curves[path][lo], hi: curves[path][hi]},
                               args.games, args.seed))
    print(f"Step 2: bisecting {len(refine)} brackets...", flush=True)
    with ProcessPoolExecutor(max_workers=args.jobs) as ex:
        for (path, target), tried in ex.map(bisect, refine):
            curves[path].update(tried)
            print(f"  {map_key(path)} target {target}%: " +
                  "  ".join(f"T={T}:{r:.0f}%" for T, r in sorted(tried.items())), flush=True)

    balance = {}
    for path in paths:
        curve = sorted(curves[path].items())
        print(f"\n{map_key(path)}:  " + "  ".join(f"T={T}:{r:.0f}%" for T, r in curve))
        table = {}
        for d in DIFFICULTIES.values():
            T, rate = min(curve, key=lambda tr: (abs(tr[1] - d.target), tr[0]))
            table[d.key], table[f"{d.key}_win"] = T, round(rate)
        balance[map_key(path)] = separate(table, curves[path])
        for d in DIFFICULTIES.values():
            print(f"   {d.label:<7} target {d.target}% -> T={table[d.key]} ({table[d.key + '_win']}%)")
    BALANCE_FILE.write_text(json.dumps(balance, indent=2) + "\n")
    print(f"\nWrote {BALANCE_FILE}")


if __name__ == "__main__":
    main()
