# Dungeon Warden

A single-player, turn-based 2D grid game on a **20x20 dungeon map**. You race to a treasure hidden in a dungeon, and an AI Warden tries to stop you by locking doors and placing walls. The Warden can't see you. It only gets sensor clues (footstep plates, door noise and 2-cell eye sight) and must reason about where you could be. It decides with **First-Order Logic, A\* search, classical (STRIPS) planning and Minimax with alpha-beta pruning**, following the Mini Program Proposal (v1.2).

UC Informatics 26/27, Artificial Intelligence: Angga Dhammika Jaya, Kristoforus Bertrand Wahyudi and Sean Lawton.

## Project Structure

The codebase is organized into two main directories for clarity and separation of concerns:

```text
AI-AFL2/
├── DungeonWarden/                # Main game package (Core, AI, Maps, UI)
│   ├── main.py                   # Entry point to launch the Pygame application
│   ├── core/
│   │   ├── world.py              # Map loading, State, STRIPS actions (preconditions & effects), Percepts
│   │   ├── engine.py             # Match turn loop, ground-truth checks, per-game metrics
│   │   ├── settings.py           # Difficulty presets, 20x20 map discovery, balance.json loader
│   │   └── mapgen.py             # Map generators (dungeon_map, random_map) and route_count
│   ├── ai/
│   │   ├── kb.py                 # Knowledge Base: FOL rules (R1-R4) -> belief set B_t, Valid(a)
│   │   ├── search.py             # A* search, BFS distances, RouteCache
│   │   ├── warden.py             # W0 Random, W1 A*-greedy, W2 Full Minimax Warden, W3 Oracle
│   │   └── bots.py               # Simulated player bots: Rusher and Cautious
│   ├── ui/
│   │   └── game.py               # Pygame UI (Main Menu, Game Screen, Reasoning Panel)
│   ├── maps/                     # Curated 20x20 maps (catacombs, fortress, labyrinth) & balance.json
│   └── logs/                     # In-game play metrics log (games.csv)
│
└── Experiments/                  # Evaluation, calibration, unit tests, and experiment outputs
    ├── experiment.py             # Headless evaluation (W0-W3 vs Rusher/Cautious) & scaling test
    ├── calibrate.py              # Per-map turn-limit (T) calibration per difficulty
    ├── test_core.py              # Unit test suite (Map, Search, KB, STRIPS rules, Game loop)
    └── results/                  # CSV metrics and PNG charts (20x20-normal/, scaling/)
```

## Setup

```bash
python -m venv .venv
.venv/bin/pip install -r requirements.txt
```

The project uses **pygame-ce**, the community edition of pygame.

## Play

```bash
python DungeonWarden/main.py
# or
python -m DungeonWarden.main
```

The Warden in the game is always the **Full Warden (W2)**: belief set, A\*, STRIPS planning and Minimax. The other versions (W0 Random, W1 A\*-greedy, W3 Oracle) exist to evaluate the method in `Experiments/experiment.py`.

The main menu lets you choose:

| Setting | Options |
|---|---|
| **Map (20x20)** | Catacombs, Fortress, Labyrinth. Every map has 4 independent routes (2-3 door-free), so you can improvise. A live preview is shown. |
| **Difficulty** | Easy / Normal / Hard: the turn limit `T` for that map |
| **Player** | You, the Rusher bot or the Cautious bot |

Command-line options skip the menu or set the proposal's input settings (`T`, `energy`, `seed`):

```bash
python DungeonWarden/main.py --skip-menu --map fortress --difficulty hard
python DungeonWarden/main.py --skip-menu --bot rusher
python DungeonWarden/main.py --T 90 --energy 6 --cap 10 --seed 7
```

| Key | Action |
|---|---|
| WASD / arrows | move one cell (you must move every turn) |
| B | belief overlay: red = `B_t`, yellow box = assumed cell, yellow line = predicted route |
| V | reveal hidden sensors (plates, eyes, sight area) |
| H | help and the Warden's FOL rules |
| Tab | switch Human / Rusher bot / Cautious bot |
| P, + / − | pause the bot, change bot speed |
| R | restart |
| Esc | pause menu (resume, restart, main menu, quit) |

The right-hand **reasoning panel** shows:
- the turn and the Warden's energy
- this turn's percepts
- which KB rule fired and how it shrank `|B_t|`
- the worst-case cell the Warden plans against
- the chosen action, its Minimax value, nodes searched, A\* expansions and time
- every root candidate as a bar (`<=` marks a branch alpha-beta pruned)

Every finished game is appended to **`DungeonWarden/logs/games.csv`**.

## Rules (Proposal Section 2.1, Table 2.1.1)

- A 20x20 grid with walls, lockable doors, footstep plates, eyes and one treasure. The Warden wins if **`T` turns pass** first.
- Each turn the **player moves one cell** (waiting is not allowed). The Warden then updates its belief set from the percepts and performs **one** action:

| Action | Preconditions | Effects |
|---|---|---|
| `LockDoor(d)` | `Door(d), ¬Locked(d), energy ≥ 2, Valid` | `Locked(d), energy −2` (stays locked until unlocked) |
| `PlaceWall(c)` | `Empty(c), energy ≥ 3, Valid` | `Wall(c), energy −3` |
| `UnlockDoor(d)` | `Locked(d)` | `¬Locked(d), energy +1` |
| `Wait` | `none` | `energy +1` |

Energy starts at 6 and is capped at 10 (both are input settings).

## Difficulty & 20x20 Maps

The Warden regains 1 energy every turn, so **the turn limit `T` decides how hard a map is.** `Experiments/calibrate.py` plays W2 against both simulated players on every 20x20 map and picks `T` per difficulty, aiming at a player win rate of **Easy 50%, Normal 30% and Hard 15%**.

The result lives in `DungeonWarden/maps/balance.json`:

| Map (20x20) | Shortest path | Routes (door-free) | Easy T | **Normal T** | Hard T |
|---|---|---|---|---|---|
| Catacombs | 30 | 4 (2) | 123 | **120** | 112 |
| Fortress | 28 | 4 (2) | 124 | **112** | 63 |
| Labyrinth | 31 | 4 (3) | 143 | **123** | 62 |

## Experiments & Unit Tests (Proposal Section 2.2)

```bash
python Experiments/experiment.py                  # 4 Wardens x 2 players x 200 games on the 3 fixed-seed 20x20 maps
python Experiments/experiment.py --difficulty hard
python Experiments/experiment.py --scaling        # W2 time and nodes per move on random 8x8 .. 20x20 maps
python Experiments/calibrate.py                   # recompute DungeonWarden/maps/balance.json
python -m unittest discover Experiments           # run unit test suite
```

Each experiment run writes to `Experiments/results/20x20-<difficulty>/`:
- `games.csv`: one row per game
- `moves.csv`: one row per Warden move
- `summary.csv` and `summary_by_map.csv`
- charts: `win_rate.png`, `turns.png`, `path_increase.png`, `belief_precision.png`

The scaling test writes to `Experiments/results/scaling/`.

## Evaluation Summary (20x20 Maps)

Four Wardens play 200 games against each of the two simulated players on the three 20x20 maps at Normal difficulty:

| Version | Role | What it adds | 20x20 Cautious Win % | 20x20 Rusher Win % |
|---|---|---|---|---|
| **W0 Random** | baseline | random valid block each turn | 100.0% | 100.0% |
| **W1 A\*-greedy** | baseline | KB + A\* route, best single block, no lookahead | 89.5% | 87.0% |
| **W2 Full Warden** | our method | KB + A\* + STRIPS planning + Minimax (3 plies, alpha-beta) | **29.5%** | **30.0%** |
| **W3 Oracle** | upper bound | W2, but told the true player cell | 8.0% | 3.0% |

### Key Metrics for W2 on 20x20
- **Path-length increase:** `+93.8` steps (Cautious), `+90.8` steps (Rusher)
- **Belief recall:** **100%** (true player cell is always inside `B_t`)
- **Belief precision (mean `1/|B_t|`):** `0.22`
- **Invalid actions:** **0**
- **A\* vs BFS route length mismatch:** **0**

### Map Format

ASCII files in `DungeonWarden/maps/`. Lines starting with `;` are comments.

```text
#  wall        D  door      o  footstep plate
.  floor       E  eye       T  treasure      P  player start
```
