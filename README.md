# Dungeon Warden

A single-player, turn-based 2D grid game. You race to a treasure hidden in a dungeon, and an AI Warden tries to stop you by locking doors and placing walls. The Warden can't see you. It only gets sensor clues (footstep plates, door noise and 2-cell eye sight) and must reason about where you could be. It decides with **First-Order Logic, A\* search, classical (STRIPS) planning and Minimax with alpha-beta pruning**, as described in the Mini Program Proposal (v1.2).

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

The main menu lets you choose:

| Setting | Options |
|---|---|
| **Map size** | 10x10 (as in the proposal) or 20x20 |
| **Map** | 10x10: Crypt, Halls, Maze. 20x20: Catacombs, Fortress, Labyrinth. A live preview is shown. |
| **Difficulty** | Easy / Normal / Hard: the turn limit T for that map (see *Difficulty*) |
| **Warden AI** | W0 Random, W1 A*-greedy, W2 Full Warden, W3 Oracle |
| **Rules** | Proposal (default) or Variant (optional house rules) |
| **Player** | You, the Rusher bot or the Cautious bot |

Command-line options skip the menu or set the proposal's input settings (T, energy, seed):

```bash
.venv/bin/python game.py --skip-menu --map maps/20x20/fortress.txt --difficulty hard
.venv/bin/python game.py --skip-menu --bot rusher --warden W1
.venv/bin/python game.py --T 60 --energy 4 --cap 8 --seed 7
```

| Key | Action |
|---|---|
| WASD / arrows | move one cell (you must move every turn under the proposal rules) |
| Space | wait (variant rules only) |
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
- the chosen action, its Minimax value, nodes searched, A* expansions and time
- every root candidate as a bar (`<=` marks a branch alpha-beta pruned)

An event log shows walls rising, doors locking and eyes spotting you. Every finished game is appended to **`logs/games.csv`**, the proposal's "CSV log of metrics".

## Rules

### Proposal rules (default): exactly proposal section 2.1 and Table 2.1.1

- Grid with walls, lockable doors, footstep plates, eyes and one treasure. The Warden wins if **T turns pass** first.
- Each turn the **player moves one cell**. The Warden then updates its belief set from the percepts and performs **one** action:

| Action | Preconditions | Effects |
|---|---|---|
| LockDoor(d) | Door(d), ¬Locked(d), energy ≥ 2, Valid | Locked(d), energy −2 (stays locked until unlocked) |
| PlaceWall(c) | Empty(c), energy ≥ 3, Valid | Wall(c), energy −3 |
| UnlockDoor(d) | Locked(d) | ¬Locked(d), energy +1 |
| Wait | none | energy +1 |

Energy starts at 6 and is capped at 10 (both settings).

### Variant rules (optional, not part of the proposal)

These are the house rules tried earlier, kept as a menu option:
- doors reopen by themselves after 3 turns and can't be relocked for 2 turns
- a wall costs 5 energy and has a 3-turn cooldown
- the player may wait
- there is no turn limit, so the score is the turns used

Because of the cooldown, Minimax suffered a *horizon effect* here (see *Findings*). Under these rules only, a Minimax leaf adds 0.35 × leftover energy.

## Difficulty

Under the proposal rules the Warden regains 1 energy every turn, so its starting energy barely changes how many blocks it places over a game. **The turn limit T decides how hard a map is.** `calibrate.py` plays W2 against both bots on every map to choose T per difficulty, aiming at a player win rate of **Easy 70%, Normal 45% and Hard 20%**:
1. It scans T from 2× to 6× the shortest path.
2. It bisects to the exact turn.

The result lives in `maps/balance.json`:

| Map | Shortest path | Easy T (bot win %) | Normal T | Hard T |
|---|---|---|---|---|
| Crypt 10x10 | 18 | 100 (70%) | 88 (43%) | 69 (13%) |
| Halls 10x10 | 18 | 60 (70%) | 56 (63%) | 54 (7%) |
| Maze 10x10 | 18 | 50 (87%) | 48 (37%) | 47 (0%) |
| Catacombs 20x20 | 36 | 132 (63%) | 130 (43%) | 126 (10%) |
| Fortress 20x20 | 19 | 103 (70%) | 93 (43%) | 89 (23%) |
| Labyrinth 20x20 | 36 | 132 (73%) | 103 (43%) | 88 (13%) |

Some maps have a cliff: on Maze the bots win 0% at 47 turns and 87% at 50. Their difficulties are therefore further from the target, but still ordered Easy > Normal > Hard. The numbers come from the greedy bots, so treat them as a guide for a human player. Under the variant rules, difficulty sets the Warden's energy instead: Easy 3/6, Normal 6/10, Hard 10/14.

## Experiments (proposal section 2.2)

```bash
.venv/bin/python experiment.py                  # 4 Wardens x 2 bots x 200 games, 3 fixed-seed 10x10 maps, proposal rules
.venv/bin/python experiment.py --size 20x20     # the same on the 20x20 maps
.venv/bin/python experiment.py --rules variant  # the optional variant
.venv/bin/python experiment.py --scaling        # W2 time and nodes per move on random 8x8 .. 20x20 maps
.venv/bin/python calibrate.py                   # recompute maps/balance.json
.venv/bin/python -m unittest discover tests     # 25 tests
```

Each run writes to `results/<rules>-<size>-<difficulty>/`:
- `games.csv`: one row per game
- `moves.csv`: one row per Warden move
- `summary.csv` and `summary_by_map.csv`
- charts: `win_rate.png`, `turns.png`, `path_increase.png`, `belief_precision.png`

The scaling test writes to `results/scaling/`. Game *i* uses seed `1000 + i` for every Warden, so all four face the same bot behaviour. The simulator knows the true player cell, so every metric is exact.

### Results: proposal rules, Normal difficulty, 200 games per Warden and bot

**10x10 maps** (T = 88 / 56 / 48 for Crypt / Halls / Maze)

| Warden | Bot | Player win % | Turns | Path increase | Belief recall | Belief precision | Invalid | ms/move (max) |
|---|---|---|---|---|---|---|---|---|
| W0 Random | Cautious | 100.0 | 21.4 | +3.4 | 100% | 0.29 | 0 | 0.06 (3.3) |
| W0 Random | Rusher | 100.0 | 22.3 | +4.3 | 100% | 0.31 | 0 | 0.06 (3.5) |
| W1 A*-greedy | Cautious | 100.0 | 42.8 | +24.8 | 100% | 0.31 | 0 | 0.43 (8.6) |
| W1 A*-greedy | Rusher | 100.0 | 39.7 | +21.7 | 100% | 0.33 | 0 | 0.41 (20.4) |
| **W2 Full** | Cautious | **49.5** | 63.9 | **+50.4** | 100% | 0.29 | 0 | 2.03 (50.1) |
| **W2 Full** | Rusher | **45.0** | 59.9 | **+46.5** | 100% | 0.35 | 0 | 2.16 (72.8) |
| W3 Oracle | Cautious | 67.0 | 51.5 | +37.4 | 100% | 0.33 | 0 | 3.03 (34.0) |
| W3 Oracle | Rusher | 45.5 | 56.5 | +45.5 | 100% | 0.38 | 0 | 2.58 (43.6) |

**20x20 maps** (T = 130 / 93 / 103 for Catacombs / Fortress / Labyrinth)

| Warden | Bot | Player win % | Turns | Path increase | Belief recall | Belief precision | Invalid | ms/move (max) |
|---|---|---|---|---|---|---|---|---|
| W0 Random | Cautious | 100.0 | 35.7 | +5.4 | 100% | 0.44 | 0 | 0.18 (7.7) |
| W0 Random | Rusher | 100.0 | 35.7 | +5.4 | 100% | 0.44 | 0 | 0.18 (5.2) |
| W1 A*-greedy | Cautious | 100.0 | 83.7 | +53.4 | 100% | 0.37 | 0 | 1.78 (18.5) |
| W1 A*-greedy | Rusher | 98.0 | 84.1 | +53.9 | 100% | 0.37 | 0 | 1.79 (24.9) |
| **W2 Full** | Cautious | **43.0** | 105.6 | **+86.8** | 100% | 0.39 | 0 | 15.4 (157) |
| **W2 Full** | Rusher | **45.5** | 107.0 | **+86.9** | 100% | 0.39 | 0 | 15.2 (169) |
| W3 Oracle | Cautious | 62.0 | 104.5 | +87.2 | 100% | 0.31 | 0 | 13.4 (219) |
| W3 Oracle | Rusher | 56.5 | 103.2 | +86.5 | 100% | 0.35 | 0 | 13.2 (212) |

**Variant rules** (10x10, no turn limit; turns the player needed, higher is better for the Warden):

| Bot | W0 | W1 | W2 | W3 |
|---|---|---|---|---|
| Cautious | 22.3 | 34.7 | 40.1 | 45.5 |
| Rusher | 19.7 | 34.2 | 36.7 | 39.9 |

Across all runs, **invalid actions were always 0**, **belief recall was always 100%**, and **A\* matched BFS on every check**, so it was complete and optimal.

**Scaling** (`results/scaling/`, W2 on random maps):

| Size | ms/move | p95 | max | nodes/move | A* expansions/move |
|---|---|---|---|---|---|
| 8x8 | 1.4 | 7.0 | 20 | 21 | 351 |
| 10x10 | 3.1 | 12.9 | 32 | 32 | 672 |
| 20x20 | 22.9 | 103 | 251 | 37 | 5,666 |

This meets the target of **under 200 ms per move on 10x10**. 20x20 averages 23 ms, with a rare worst case of about 250 ms.

### Findings worth discussing in the report

- **Lookahead is what makes the Warden work.** With the same knowledge base, greedy W1 never stops a bot at these T values (98-100% player wins). W2 holds the player to 43-50% and forces a detour about twice as long.
- **Lock swapping.** Minimax discovered a strategy on its own. It locks the door the player is heading for, while the Valid rule forces it to keep another route open, so it unlocks a different door; unlocking refunds 1 energy. A greedy, memoryless player turns around every time. On a map where every route passes a door, this stalls the player forever. The first Halls and Fortress layouts were unwinnable because of it, so one gate on each became an open archway.
- **The Oracle (W3) is not strictly better than W2.** Planning against the worst-case belief cell (closest to the treasure) is more robust than reacting to the exact cell. Against Cautious, W3 lets the player win more often than W2 does.
- **Horizon effect (variant rules only).** With a wall cooldown, the Warden's last Minimax ply is never answered by the player, so a wall planned for that ply looks free. The search then kept postponing walls, and greedy W1 beat W2. Searching one ply deeper (4) changes nothing. Valuing leftover energy at the leaf fixes it, and a regression test checks it. Under the proposal rules this does not happen, so the utility there is exactly the route length.
- **Complexity.** The cost per move grows faster than the proposal's O(b^(d/2) · V log V). Each tree node also generates its own candidates, at one A* and one validity BFS each, so the real cost is closer to O(b^(d/2) · b · V log V).

## Proposal checklist

| Proposal (v1.2) | Implementation | Status |
|---|---|---|
| Single-player, turn-based 2D grid, player vs AI Warden | `engine.Match`, `game.py` | ✅ |
| 10x10 grid, T-turn timer, Warden wins when T turns pass | 10x10 maps are the default and the experiment set; `Match.T` | ✅ (20x20 maps added for play and testing; the proposal tests "up to 20x20") |
| Each turn the player moves one cell, then the Warden updates B_t and performs one action | `Match.step`; Wait is illegal for the player under the proposal rules | ✅ |
| Formulation: initial state, actions, result, terminal test, utility = player's shortest route (Warden MAX, player MIN) | `world.State`, `world.apply`, `warden.MinimaxWarden` | ✅ utility is exactly the A* route length |
| Percepts: plates, door noise, 2-cell sight | `world.sense`, `world.sight_cells` | ✅ |
| FOL rules R1-R4 and Valid(a), via Universal Instantiation and Modus Ponens | `kb.py`: exactly these five rules, each grounded per cell | ✅ |
| Worst case: player at the belief cell closest to the treasure, scored by A* route length | `Warden.assumed_cell`, `Warden.evaluate` | ✅ |
| 3 plies with alpha-beta, only the first Warden action executed | `LOOKAHEAD = 3`, `MinimaxWarden.minimax` | ✅ |
| Table 2.1.1 action schema | `world.PROPOSAL`, `world.preconditions`, `world.apply` (tested in `ProposalRulesTests`) | ✅ |
| b ≤ 8 actions near the predicted route, paths cached, < 200 ms on 10x10 | `Warden.candidates` (6 blocks + Wait + Unlock), `search.RouteCache` | ✅ max 73 ms in 1,600 games |
| PEAS and environment properties | as described; deterministic, sequential, static, discrete, partially observable | ✅ |
| Input: map file, settings (T, energy, seed), moves (WASD / bot) | `maps/*.txt`, `--T --energy --cap --seed`, WASD or `--bot` | ✅ |
| Output: Warden's action, reasoning panel, game result, CSV log of metrics | right-hand panel, game-over screen, `logs/games.csv`, `results/` | ✅ |
| Evaluation: W0-W3, 200 games each vs Rusher and Cautious, 3 fixed-seed maps | `experiment.py` | ✅ |
| Metrics: win rate, path increase, belief recall (100%) and precision, invalid actions (0), nodes and time 8x8-20x20, A* vs BFS | `Match.summary`, `experiment.py --scaling` | ✅ |

### Choices the proposal leaves open

- **Sight** comes from fixed eye tiles (`E`). Each sees cells within 2 steps, and walls block the view.
- **Door noise** happens when the player steps onto or off a door. "Adjacent(c, d)" includes c = d, so the player is always on the door or next to it.
- **Empty(c)** means plain floor. Doors, plates, eyes and the treasure can't be walled.
- **Fair** (proposal 1.2, problem 2): besides Valid(a), the Warden never walls or locks a cell in B_t. B_t always contains the true cell, so it can never trap the player.
- **B_0 = {start}**: the entrance is public knowledge.
- **Ties** between equally valued actions go to the bigger immediate gain, then to more energy left. This only breaks ties; it does not change the utility.
- **What you see:** walls, doors and locks. Plates and eyes are hidden sensors (V reveals them).
- **Path increase** = moves made + distance still left − the original shortest path.

## Code map

| File | Contents |
|---|---|
| `world.py` | map loading, `State`, rule presets, STRIPS preconditions and effects, percepts |
| `kb.py` | Knowledge Base: FOL rules → belief set, Valid(a) |
| `search.py` | A*, BFS, route cache |
| `warden.py` | W0-W3, Minimax with alpha-beta |
| `bots.py` | Rusher and Cautious players |
| `engine.py` | turn loop, ground-truth checks, per-game metrics |
| `settings.py` | difficulty presets, map lists, `balance.json` |
| `calibrate.py` | per-map turn-limit calibration |
| `game.py` | pygame UI |
| `experiment.py` | experiments and charts |
| `mapgen.py` | random maps (scaling test) and the rooms-and-corridors generator used for the 20x20 maps |
| `maps/10x10`, `maps/20x20` | the six maps; `balance.json` holds the turn limits |
| `tests/test_core.py` | 25 tests |

### Map format

ASCII files. Lines starting with `;` are comments.

```
#  wall        D  door      o  footstep plate
.  floor       E  eye       T  treasure      P  player start
```
# AI-AFL2
