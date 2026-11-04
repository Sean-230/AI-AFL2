# Dungeon Warden

A single-player, turn-based 2D grid game on a **20x20 dungeon map**. You race to a treasure hidden in a dungeon, and an AI Warden tries to stop you by locking doors and placing walls. The Warden can't see you. It only gets sensor clues (footstep plates, door noise and 2-cell eye sight) and must reason about where you could be. It decides with **First-Order Logic, A\* search, classical (STRIPS) planning and Minimax with alpha-beta pruning**, following the Mini Program Proposal (v1.2).

UC Informatics 26/27, Artificial Intelligence: Angga Dhammika Jaya, Kristoforus Bertrand Wahyudi and Sean Lawton.

## Architecture (Agent-Environment + OOP)

The project is organized into two main directories (`DungeonWarden/` and `Experiments/`) following the **Agent-Environment (PEAS) Layered Architecture**, **Object-Oriented Programming (OOP)** principles, and **Single Responsibility Principle (SRP)**:

```text
AI-AFL2/
├── DungeonWarden/                # Main Game Package (Core, AI, UI, Maps)
│   ├── main.py                   # Entry point to launch the Pygame application
│   ├── core/                     # ENVIRONMENT LAYER: Grid, State, Sensors, Actuators, & Match Engine
│   │   ├── settings.py           # SettingsManager & Difficulty presets
│   │   ├── dungeon_map.py        # DungeonMap class (20x20 grid geometry & spatial queries)
│   │   ├── game_state.py         # Immutable GameState, Percept, & TurnRecord models
│   │   ├── action_schema.py      # StripsActionSchema (STRIPS preconditions & effects, Table 2.1.1)
│   │   ├── sensor_system.py      # SensorSystem (plates, door noise, 2-cell sight)
│   │   ├── map_generator.py      # MapGenerator & RouteAnalyzer (max-flow disjoint routes)
│   │   └── match_engine.py       # MatchEngine (turn loop, ground-truth validation, metrics)
│   ├── ai/                       # AGENT LAYER: FOL Reasoning, Search, & the game's Minimax Warden (W2)
│   │   ├── pathfinder.py         # Pathfinder (A* & BFS) and RouteCache
│   │   ├── knowledge_base.py     # KnowledgeBase (FOL rules R1-R4) & ActionValidator (Valid(a))
│   │   ├── warden_base.py        # Abstract BaseWarden (ABC) & Decision telemetry
│   │   └── wardens.py            # MinimaxWarden (W2, Full Warden): the only Warden the game plays
│   ├── ui/                       # PRESENTATION LAYER: Modular Pygame UI
│   │   ├── theme.py              # Theme, color palette, typography, & easing helpers
│   │   ├── components.py         # Reusable Button UI widget
│   │   ├── menu_view.py          # MenuView (main menu & live 20x20 map preview)
│   │   ├── board_view.py         # BoardView (20x20 dungeon grid, torch light, animations, sensor preview)
│   │   ├── panel_view.py         # ReasoningPanelView (status, percepts, KB log, Minimax candidate bars)
│   │   ├── overlay_view.py       # OverlayView (Pause modal, Help/FOL modal, Game Over overlay)
│   │   ├── tutorial_view.py      # TutorialView (5-step hands-on practice tutorial in ID/EN)
│   │   ├── game_session.py       # GameSession (active match loop & input handling)
│   │   └── app.py                # DungeonWardenApp (window lifecycle, event routing, CSV logging)
│   ├── maps/                     # Curated 20x20 maps (catacombs, fortress, labyrinth) & balance.json
│   └── logs/                     # In-game play metrics log (games.csv)
│
└── Experiments/                  # Evaluation Suite, Calibration, & Unit Tests
    ├── experiment.py             # ExperimentController CLI entry point
    ├── runner.py                 # SimulationRunner (parallel multiprocessing execution)
    ├── metrics.py                # MetricsAggregator & ReportWriter (statistics, CSV, console tables)
    ├── plotter.py                # ExperimentPlotter (Matplotlib chart generation)
    ├── calibrate.py              # DifficultyCalibrator (turn limit T per map, checks the cost-based difficulties)
    ├── evaluation_wardens.py     # RandomWarden (W0), GreedyWarden (W1), OracleWarden (W3) + WARDENS registry (subclasses of BaseWarden)
    ├── player_bots.py            # Abstract BasePlayerBot (ABC), RusherBot, & CautiousBot (simulated players)
    ├── test_core.py              # Unit test suite (24 tests verifying Core, AI & architecture rules)
    └── results/                  # CSV metrics and PNG charts (20x20-hard/, scaling/)
```

The game always plays the **Full Warden (W2)** against a human. The simulated players (`RusherBot`, `CautiousBot`) and the comparison Wardens (W0, W1, W3) are only tools to evaluate the method, so they live in `Experiments/` and subclass the game's `BaseWarden`. `Experiments/` depends on `DungeonWarden/`, never the other way round (a unit test checks this).

## Setup

```bash
python -m venv .venv
.venv/bin/pip install -r requirements.txt
```

## Play

```bash
python DungeonWarden/main.py
python DungeonWarden/main.py --tutorial
```

Command-line options skip the menu or set the proposal's input settings (`T`, `energy`, `seed`):

```bash
python DungeonWarden/main.py --skip-menu --map fortress --difficulty hard
python DungeonWarden/main.py --T 90 --energy 6 --cap 10 --lock-cost 2 --wall-cost 3 --seed 7
```

## Difficulty

Difficulty is the **energy price of the Warden's two blocking actions**. Hard uses the proposal's costs (Table 2.1.1); the easier levels make `LockDoor` and `PlaceWall` more expensive. The Warden regains only 1 energy per turn (and `Wait` is its only way to do so), so a dearer action simply means fewer blocks: a wall that costs 8 can be placed about once every 9 turns. Energy start/cap stay at 6/10 and the turn limit `T` is the same for every difficulty.

| Difficulty | LockDoor | PlaceWall | Player win rate vs W2 (average of the 3 maps) |
|---|---|---|---|
| **Easy** | 5 energy | 8 energy | 97% |
| **Normal** | 3 energy | 5 energy | 63% |
| **Hard** | 2 energy | 3 energy (proposal) | 29% |

| Map | T | Easy | Normal | Hard |
|---|---|---|---|---|
| Catacombs | 120 | 90% | 35% | 25% |
| Fortress | 112 | 100% | 60% | 35% |
| Labyrinth | 123 | 100% | 93% | 28% |

Each cell is 60 games (both simulated players), so it is accurate to about ±12 points. Normal differs a lot between maps: Labyrinth is almost as easy as Easy, Catacombs is close to Hard.

`T` is calibrated per map at the Hard costs so that the simulated players win about 30% of the time, which is the proposal's default setting and the one used by the experiments. The exact win rate of every map and difficulty is stored in `DungeonWarden/maps/balance.json`. The numbers come from greedy bots, so humans will usually do worse. To try other costs: `--lock-cost` and `--wall-cost`.

## Experiments & Unit Tests (Proposal Section 2.2)

```bash
python Experiments/experiment.py                  # 4 Wardens x 2 players x 200 games on the 3 fixed-seed 20x20 maps
python Experiments/experiment.py --difficulty hard
python Experiments/experiment.py --scaling        # W2 time and nodes per move on random 8x8 .. 20x20 maps
python Experiments/calibrate.py                   # recompute DungeonWarden/maps/balance.json
python Experiments/calibrate.py --verify          # re-measure the three difficulties at the saved T
python -m unittest discover Experiments -v        # run unit test suite
```
