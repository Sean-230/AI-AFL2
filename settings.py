"""Difficulty presets and map lists, shared by the game, the experiments and calibrate.py.

Under the proposal rules the Warden regains 1 energy every turn, so its starting energy barely changes
how many blocks it can place over a whole game; the turn limit T (an input setting, proposal 2.1) is
what decides how hard a map is. Every map therefore has its own T per difficulty, calibrated by
calibrate.py so that the Full Warden (W2) loses to the simulated players about `target`% of the time.
The results live in maps/balance.json.
"""
from __future__ import annotations

import json
import math
from dataclasses import dataclass
from pathlib import Path

from world import ENERGY_CAP, ENERGY_START

HERE = Path(__file__).parent
MAPS_DIR = HERE / "maps"
BALANCE_FILE = MAPS_DIR / "balance.json"
SIZES = ("10x10", "20x20")


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
    """'maps/20x20/fortress.txt' -> '20x20/fortress'."""
    p = Path(path).resolve()
    try:
        return str(p.relative_to(MAPS_DIR.resolve()).with_suffix(""))
    except ValueError:
        return p.stem


def map_paths(size: str | None = None) -> list[Path]:
    sizes = SIZES if size in (None, "all") else (size,)
    return [p for s in sizes for p in sorted((MAPS_DIR / s).glob("*.txt"))]


def load_balance() -> dict:
    try:
        return json.loads(BALANCE_FILE.read_text())
    except (FileNotFoundError, json.JSONDecodeError):
        return {}


def game_settings(path: str | Path, shortest: int, difficulty: str, balance: dict | None = None) -> dict:
    """Match keyword arguments (T, energy, cap) for a map at a difficulty."""
    table = (load_balance() if balance is None else balance).get(map_key(path), {})
    T = table.get(difficulty) or math.ceil(DIFFICULTIES[difficulty].fallback_factor * shortest)
    return {"T": T, "energy": ENERGY_START, "cap": ENERGY_CAP}
