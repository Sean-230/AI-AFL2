"""Difficulty presets and 20x20 map lists, shared by the game, experiments and calibrate.py.

Under the proposal rules the Warden regains 1 energy every turn, so its starting energy barely changes
how many blocks it can place over a whole game; the turn limit T (an input setting, proposal 2.1) is
what decides how hard a map is. Every 20x20 map has its own T per difficulty, calibrated by
calibrate.py so that the Full Warden (W2) loses to the simulated players about `target`% of the time.
The results live in DungeonWarden/maps/balance.json.
"""
from __future__ import annotations

import json
import math
from dataclasses import dataclass
from pathlib import Path

from DungeonWarden.core.world import ENERGY_CAP, ENERGY_START

PACKAGE_DIR = Path(__file__).resolve().parent.parent
MAPS_DIR = PACKAGE_DIR / "maps"
BALANCE_FILE = MAPS_DIR / "balance.json"
LOGS_DIR = PACKAGE_DIR / "logs"
MAP_SIZE = "20x20"


@dataclass(frozen=True)
class Difficulty:
    key: str
    label: str
    target: int             # player win % against W2 that calibrate.py aims for
    fallback_factor: float  # T = factor x shortest path for maps that aren't calibrated yet


DIFFICULTIES = {d.key: d for d in (
    Difficulty("easy", "Easy", 50, 4.0),
    Difficulty("normal", "Normal", 30, 3.0),
    Difficulty("hard", "Hard", 15, 2.5),
)}


def map_key(path: str | Path) -> str:
    """'DungeonWarden/maps/fortress.txt' -> 'fortress'."""
    return Path(path).stem


def map_paths() -> list[Path]:
    """Return all 20x20 dungeon map files sorted by name."""
    return sorted(MAPS_DIR.glob("*.txt"))


def load_balance() -> dict:
    try:
        return json.loads(BALANCE_FILE.read_text())
    except (FileNotFoundError, json.JSONDecodeError):
        return {}


def game_settings(path: str | Path, shortest: int, difficulty: str, balance: dict | None = None) -> dict:
    """Match keyword arguments (T, energy, cap) for a map at a difficulty."""
    bal = load_balance() if balance is None else balance
    key = map_key(path)
    table = bal.get(key) or bal.get(f"20x20/{key}", {})
    T = table.get(difficulty) or math.ceil(DIFFICULTIES[difficulty].fallback_factor * shortest)
    return {"T": T, "energy": ENERGY_START, "cap": ENERGY_CAP}

