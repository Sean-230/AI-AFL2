# Dungeon Warden

A single-player, turn-based 2D grid game. You race to a treasure hidden in a dungeon, and an AI Warden tries to stop you by locking doors and placing walls. The Warden can't see you. It only gets sensor clues (footstep plates, door noise and 2-cell eye sight) and must reason about where you could be. It decides with **First-Order Logic, A\* search, classical (STRIPS) planning and Minimax with alpha-beta pruning**, exactly as in the Mini Program Proposal (v1.2).

UC Informatics 26/27, Artificial Intelligence: Angga Dhammika Jaya, Kristoforus Bertrand Wahyudi and Sean Lawton.

## Setup

```bash
python3 -m venv .venv
.venv/bin/pip install -r requirements.txt
```

The project uses **pygame-ce**, the community edition of pygame. The original `pygame` has no wheel for Python 3.14. The code still does `import pygame`.

## Play

```bash
.venv/bin/python game.py
or 
cd "/Users/seantandjaja/Documents/Codes/AI AFL2" && .venv/bin/python game.py
```

The Warden in the game is always the **Full Warden (W2)**: belief set, A\*, planning and Minimax. The other versions (W0 Random, W1 A\*-greedy, W3 Oracle) exist only to evaluate the method in `experiment.py`.

The main menu lets you choose:

| Setting | Options |
|---|---|
| **Map size** | 10x10 (as in the proposal) or 20x20 |
| **Map** | 10x10: Crypt, Halls, Maze. 20x20: Catacombs, Fortress, Labyrinth. Every map has 3-4 routes that share no cell, so you can improvise. A live preview is shown. |
| **Difficulty** | Easy / Normal / Hard: the turn limit T for that map (see *Difficulty*) |
| **Player** | You, the Rusher bot or the Cautious bot |

Command-line options skip the menu or set the proposal's input settings (T, energy, seed):

```bash
.venv/bin/python game.py --skip-menu --map maps/20x20/fortress.txt --difficulty hard
.venv/bin/python game.py --skip-menu --bot rusher
.venv/bin/python game.py --T 30 --energy 4 --cap 8 --seed 7
```

| Key | Action |
|---|---|
| WASD / arrows | move one cell (you must move every turn) |
| B | belief overlay: red = B_t, yellow box = assumed cell, yellow line = predicted route |
| V | reveal hidden sensors (plates, eyes, sight area) |
| H | help and the Warden's FOL rules |
| Tab | switch Human / Rusher bot / Cautious bot |
| P, + / − | pause the bot, change bot speed |
| R | restart |
| Esc | pause menu (resume, restart, main menu, quit) |

The right-hand **reasoning panel** shows:
- the turn and the Warden's energy
- this turn's percepts
- which KB rule fired and how it shrank |B_t|
- the worst-case cell the Warden plans against
- the chosen action, its Minimax value, nodes searched, A\* expansions and time
- every root candidate as a bar (`<=` marks a branch alpha-beta pruned)

An event log shows walls rising, doors locking and eyes spotting you. Every finished game is appended to **`logs/games.csv`**, the proposal's "CSV log of metrics".

## Rules (proposal section 2.1, Table 2.1.1)

- A grid with walls, lockable doors, footstep plates, eyes and one treasure. The Warden wins if **T turns pass** first.
- Each turn the **player moves one cell** (waiting is not allowed). The Warden then updates its belief set from the percepts and performs **one** action:

| Action | Preconditions | Effects |
|---|---|---|
| LockDoor(d) | Door(d), ¬Locked(d), energy ≥ 2, Valid | Locked(d), energy −2 (stays locked until unlocked) |
| PlaceWall(c) | Empty(c), energy ≥ 3, Valid | Wall(c), energy −3 |
| UnlockDoor(d) | Locked(d) | ¬Locked(d), energy +1 |
| Wait | none | energy +1 |

Energy starts at 6 and is capped at 10 (both are input settings).

## Difficulty

The Warden regains 1 energy every turn, so its starting energy barely changes how many blocks it places over a game. **The turn limit T decides how hard a map is.** `calibrate.py` plays W2 against both simulated players on every map and picks T per difficulty, aiming at a player win rate of **Easy 50%, Normal 30% and Hard 15%**:
1. It scans T from 1.2× to 6× the shortest path.
2. It bisects to the exact turn.
3. If two difficulties land on the same T it raises the easier one.

The result lives in `maps/balance.json`:

| Map | Shortest path | Routes (door-free) | Easy T | **Normal T** | Hard T |
|---|---|---|---|---|---|
| Crypt 10x10 | 12 | 3 (2) | 25 | **24** | 15 |
| Halls 10x10 | 11 | 4 (4) | 35 | **17** | 14 |
| Maze 10x10 | 11 | 3 (2) | 33 | **31** | 28 |
| Catacombs 20x20 | 30 | 4 (2) | 123 | **120** | 112 |
| Fortress 20x20 | 28 | 4 (2) | 124 | **112** | 63 |
| Labyrinth 20x20 | 31 | 4 (3) | 143 | **123** | 62 |

The numbers come from the greedy bots, so treat them as a guide for a human player.

## Experiments (proposal section 2.2)

```bash
.venv/bin/python experiment.py                  # 4 Wardens x 2 players x 200 games on the 3 fixed-seed 10x10 maps
.venv/bin/python experiment.py --size 20x20     # the same on the 20x20 maps
.venv/bin/python experiment.py --difficulty hard
.venv/bin/python experiment.py --scaling        # W2 time and nodes per move on random 8x8 .. 20x20 maps
.venv/bin/python calibrate.py                   # recompute maps/balance.json
.venv/bin/python -m unittest discover tests     # 20 tests
```

Each run writes to `results/<size>-<difficulty>/`:
- `games.csv`: one row per game
- `moves.csv`: one row per Warden move
- `summary.csv` and `summary_by_map.csv`
- charts: `win_rate.png`, `turns.png`, `path_increase.png`, `belief_precision.png`

The scaling test writes to `results/scaling/`. Game *i* uses seed `1000 + i` for every Warden, so all four face the same player behaviour. The simulator knows the true player cell, so every metric is exact.

## Evaluation of the method

Four Wardens play 200 games against each of the two simulated players on the three maps, at Normal difficulty (3,200 games in total, 169,151 Warden moves).

| Version | Role | What it adds |
|---|---|---|
| **W0 Random** | baseline | random valid block each turn |
| **W1 A\*-greedy** | baseline | knowledge base + A\* route, best single block, no lookahead |
| **W2 Full Warden** | our method | knowledge base + A\* + planning + Minimax (3 plies, alpha-beta) |
| **W3 Oracle** | upper bound | W2, but it is told the true player cell |

### Player win rate (lower is better for the Warden)

| Version | 10x10 Cautious | 10x10 Rusher | 20x20 Cautious | 20x20 Rusher |
|---|---|---|---|---|
| W0 Random | 100.0% | 100.0% | 100.0% | 100.0% |
| W1 A\*-greedy | 71.0% | 56.0% | 89.5% | 87.0% |
| **W2 Full** | **46.0%** | **21.5%** | **29.5%** | **30.0%** |
| W3 Oracle | 43.0% | 30.0% | 8.0% | 3.0% |

With 200 games per cell, one number is accurate to about ±7 points (95%).

**Is the player win rate about 30%?** Yes. Averaged over both players, W2 lets the player win **33.8% on 10x10** and **29.8% on 20x20**. Per map (average of both players): Crypt 35.8%, Halls 26.1%, Maze 39.4%, Catacombs 32.9%, Fortress 26.9%, Labyrinth 29.5%.

### Other proposal metrics (W2)

| Metric | 10x10 | 20x20 |
|---|---|---|
| Path-length increase (final − original shortest path) | +15.4 (Cautious), +19.7 (Rusher) | +93.8, +90.8 |
| Same for W1 / W0 | +9.5, +12.1 / +0.2, +2.9 | +59.4, +60.4 / +0.8, +2.4 |
| Belief recall (must be 100%) | **100%** | **100%** |
| Belief precision (mean 1/\|B_t\|) | 0.34, 0.38 | 0.22, 0.22 |
| Invalid actions (must be 0) | **0** | **0** |
| Time per move: mean / 95th percentile / max | 1.7-2.4 ms / 6-8 ms / 29 ms | 35-36 ms / 90-98 ms / 384 ms |
| Nodes per move (Minimax) | 25-31 | 49-51 |
| A\* expansions per move | 301-502 | 6,068-6,549 |
| A\* ≠ BFS route length | **0 of 169,151 checks** | |

### Scaling (W2 on random maps, 8x8 to 20x20)

| Size | ms/move | p95 | max | nodes/move | A\* expansions/move | proposal's estimate b^(d/2)·V·log V (relative) |
|---|---|---|---|---|---|---|
| 8x8 | 1.5 | 5.3 | 12.8 | 25 | 407 | 1.0 |
| 10x10 | 3.6 | 13.3 | 27.7 | 39 | 918 | 1.7 |
| 14x14 | 13.8 | 40.5 | 75.9 | 46 | 3,364 | 3.9 |
| 20x20 | 29.1 | 82.8 | 148 | 45 | 6,261 | 9.0 |

### What the results say

**1. The method works, and every part of it earns its place.** Going from W0 to W1 to W2 lowers the player win rate step by step: 100% → 56-90% → 21-46% on the same knowledge base. The two extra components, planning with Minimax lookahead and its use of the worst-case belief cell, are what separate a Warden that merely blocks the shortest route (W1) from one that actually delays the player. On 20x20, W2 forces a detour of about 91-94 extra turns, roughly 50-60% more than W1 (+59-60) and far more than W0 (+1-2).

**2. The logic is sound.** Belief recall was 100% in all 3,200 games, so the true player cell was never excluded from B_t, and no action was ever invalid (the Warden never walled a possible player cell, never cut the treasure off, never overspent energy). A\* matched BFS on every one of the 169,151 checks, which confirms completeness and optimality empirically.

**3. Partial observability costs the Warden a lot on big maps.** The Oracle (W3) knows the player cell. On 10x10 it is no better than W2 (30% vs 21.5% against Rusher, 43% vs 46% against Cautious, within noise): the belief set is small and planning against its worst-case cell is already close to knowing. On 20x20 the Oracle lets the player win only 3-8% against W2's 30%. So about **25 percentage points of win rate are lost to uncertainty**. This matches the belief precision, which drops from 0.34-0.38 (roughly 3 candidate cells) to 0.22 (roughly 4.5 cells).

**4. The simulated players differ a lot.** On the same map the Rusher and Cautious can differ by 50 points, for example Halls (Cautious 50.7%, Rusher 1.5%) and Labyrinth (Cautious 4.5%, Rusher 54.5%). Which player does better depends on the layout and goes in opposite directions on different maps, so there is no single explanation. A plausible cause is that Cautious avoids doors (good where open corridors exist, as in Halls whose 4 routes are all door-free) while Rusher takes the shortest route whatever it passes through; this was not tested separately. It is why one map can't be balanced to exactly 30% for both players, and why the two players are used together.

**5. Time per move meets the proposal's target on 10x10, not always on 20x20.** On 10x10 the slowest move took 29 ms, far below the 200 ms target. On 20x20 the mean is about 35 ms and the 95th percentile about 95 ms, but rare moves reach 384 ms. The proposal only requires the target on 10x10 and a test up to 20x20.

**6. The real cost grows faster than the proposal's estimate.** From 8x8 to 20x20 the time per move grows 20 times while the estimate b^(d/2)·V·log V grows 9 times (about V^1.6 instead of V^1.2). The number of Minimax nodes barely changes (25 → 45) because the branching factor is capped at 8. The growth comes from A\*: every node generates its own candidate blocks and each needs one A\* and one validity BFS, so the real cost is closer to O(b^(d/2) · b · V log V). Caching routes keeps it practical.

**7. Findings that shaped the maps and the AI.**
- *Lock swapping.* On maps where every route passes a door, Minimax discovers that it can lock the door the player is heading for and unlock another one (unlocking refunds energy, and Valid forces it to keep a route open). A memoryless player turns around every time. The first maps were unwinnable because of it, so every map now has at least two door-free routes.
- *Spending energy for nothing.* The proposal's utility is only the route length, so many actions tie. Without a rule, W2 spent its energy early on blocks that gained nothing and had none left when a block really mattered (on the earlier Halls map the player won 100% of games). Breaking ties in favour of Wait fixed this (see *Choices the proposal leaves open*).
- *Narrow maps.* Maps with one or two routes can't be balanced: the Warden is not allowed to cut the only route, so the player wins either always or never. The maps now have 3-4 independent routes.

**Limits.** The simulated players are greedy, so win rates against humans will differ. Each calibration point uses 15 games per player, so a single map's Normal can be off by roughly ±10 points. Results come from one set of 200 seeded games per cell.

## Proposal checklist

| Proposal (v1.2) | Implementation | Status |
|---|---|---|
| Single-player, turn-based 2D grid, player vs AI Warden | `engine.Match`, `game.py` | ✅ |
| 10x10 grid, T-turn timer, Warden wins when T turns pass | 10x10 is the default map size and the experiment set; `Match.T` | ✅ (20x20 maps added for play and the scaling test the proposal asks for) |
| Each turn the player moves one cell, then the Warden updates B_t and performs one action | `Match.step`; waiting is illegal | ✅ |
| Formulation: initial state, actions, result, terminal test, utility = player's shortest route (Warden MAX, player MIN) | `world.State`, `world.apply`, `warden.MinimaxWarden` | ✅ utility is exactly the A\* route length |
| Percepts: plates, door noise, 2-cell sight | `world.sense`, `world.sight_cells` | ✅ |
| FOL rules R1-R4 and Valid(a), via Universal Instantiation and Modus Ponens | `kb.py`: exactly these five rules, each grounded per cell | ✅ |
| Worst case: player at the belief cell closest to the treasure, scored by A\* route length | `Warden.assumed_cell`, `Warden.evaluate` | ✅ |
| 3 plies with alpha-beta, only the first Warden action executed | `LOOKAHEAD = 3`, `MinimaxWarden.minimax` | ✅ |
| Table 2.1.1 action schema | `world.preconditions`, `world.apply` (tested in `ProposalRulesTests`) | ✅ |
| b ≤ 8 actions near the predicted route, paths cached, < 200 ms on 10x10 | `Warden.candidates` (6 blocks + Wait + Unlock), `search.RouteCache` | ✅ max 29 ms on 10x10 |
| PEAS and environment properties | deterministic, sequential, static, discrete, partially observable | ✅ |
| Input: map file, settings (T, energy, seed), moves (WASD / bot) | `maps/*.txt`, `--T --energy --cap --seed`, WASD or `--bot` | ✅ |
| Output: Warden's action, reasoning panel, game result, CSV log of metrics | right-hand panel, game-over screen, `logs/games.csv`, `results/` | ✅ |
| Evaluation: W0-W3, 200 games each vs Rusher and Cautious, 3 fixed-seed maps | `experiment.py` | ✅ |
| Metrics: win rate, path increase, belief recall (100%) and precision, invalid actions (0), nodes and time 8x8-20x20, A\* vs BFS | `Match.summary`, `experiment.py --scaling` | ✅ |

Algorithms in the code: **A\*, BFS, FOL inference, STRIPS planning and Minimax with alpha-beta**, and nothing else. The Cautious player uses the same A\* with a higher cost for doors.

### Choices the proposal leaves open

- **Sight** comes from fixed eye tiles (`E`). Each sees cells within 2 steps, and walls block the view.
- **Door noise** happens when the player steps onto or off a door. "Adjacent(c, d)" includes c = d, so the player is always on the door or next to it.
- **Empty(c)** means plain floor. Doors, plates, eyes and the treasure can't be walled.
- **Fair** (proposal 1.2, problem 2): besides Valid(a), the Warden never walls or locks a cell in B_t. B_t always contains the true cell, so it can never trap the player.
- **B_0 = {start}**: the entrance is public knowledge.
- **Ties between equally valued actions go to Wait**, so energy is not spent on blocks that gain nothing. This changes no value, only which of several equal actions is played.
- **What you see:** walls, doors and locks. Plates and eyes are hidden sensors (V reveals them).
- **Path increase** = moves made + distance still left − the original shortest path.
- **Maps:** the 10x10 and 20x20 maps are made by `mapgen.dungeon_map` (rooms joined by corridors; seeds are in each file's header) and chosen so every map has 3-4 independent routes.

## Code map

| File | Contents |
|---|---|
| `world.py` | map loading, `State`, STRIPS preconditions and effects (Table 2.1.1), percepts |
| `kb.py` | Knowledge Base: FOL rules → belief set, Valid(a) |
| `search.py` | A\*, BFS, route cache |
| `warden.py` | W0-W3, Minimax with alpha-beta |
| `bots.py` | Rusher and Cautious players |
| `engine.py` | turn loop, ground-truth checks, per-game metrics |
| `settings.py` | difficulty presets, map lists, `balance.json` |
| `calibrate.py` | per-map turn-limit calibration |
| `game.py` | pygame UI |
| `experiment.py` | experiments and charts |
| `mapgen.py` | map generators and `route_count` (route variety) |
| `maps/10x10`, `maps/20x20` | the six maps; `balance.json` holds the turn limits |
| `tests/test_core.py` | 20 tests |

### Map format

ASCII files. Lines starting with `;` are comments.

```
#  wall        D  door      o  footstep plate
.  floor       E  eye       T  treasure      P  player start
```
