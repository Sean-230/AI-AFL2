"""Application configuration, difficulty presets, and 20x20 map path management.

Difficulty is the Warden's action costs (energy is an input setting of the proposal, Table 2.1.1 gives
the default costs). Hard uses the proposal's costs; the easier levels make LockDoor and PlaceWall more
expensive. The Warden regains only 1 energy per turn, so a dearer action means fewer blocks:
a wall that costs 6 can only be placed about once every 7 turns. Energy start/cap stay at 6/10 and the
turn limit T is the same for every difficulty (maps/balance.json).
"""
from __future__ import annotations

from dataclasses import dataclass
import json
import math
from pathlib import Path

PACKAGE_DIR = Path(__file__).resolve().parent.parent
MAPS_DIR = PACKAGE_DIR / "maps"
BALANCE_FILE = MAPS_DIR / "balance.json"
LOGS_DIR = PACKAGE_DIR / "logs"
MAP_SIZE = "20x20"

T_DEFAULT = 120
ENERGY_START = 6
ENERGY_CAP = 10
SIGHT_RANGE = 2
LOCK_COST = 2
WALL_COST = 3


@dataclass(frozen=True)
class Difficulty:
    """A difficulty level: what the Warden's two blocking actions cost in energy."""

    key: str
    label: str
    lock_cost: int
    wall_cost: int
    target_win_rate: int    # expected win rate of the simulated players against W2 (calibrate.py checks it)


DIFFICULTIES: dict[str, Difficulty] = {
    d.key: d
    for d in (
        Difficulty("easy", "Easy", 5, 8, 90),
        Difficulty("normal", "Normal", 3, 5, 60),
        Difficulty("hard", "Hard", LOCK_COST, WALL_COST, 30),
    )
}
FALLBACK_T_FACTOR = 4.0   # T = factor x shortest path for maps that aren't calibrated yet


class SettingsManager:
    """Manages map discovery, difficulty calibration data, and match configuration."""

    @staticmethod
    def map_key(path: str | Path) -> str:
        """Convert a map file path into its canonical identifier (e.g., 'fortress')."""
        return Path(path).stem

    @staticmethod
    def map_paths() -> list[Path]:
        """Return all curated 20x20 dungeon map files sorted alphabetically."""
        return sorted(MAPS_DIR.glob("*.txt"))

    @staticmethod
    def load_balance() -> dict[str, dict[str, int]]:
        """Load the calibrated turn limit T per map from balance.json."""
        try:
            return json.loads(BALANCE_FILE.read_text(encoding="utf-8"))
        except (FileNotFoundError, json.JSONDecodeError):
            return {}

    @classmethod
    def get_match_settings(
        cls,
        path: str | Path,
        shortest_path: int,
        difficulty: str,
        balance: dict | None = None,
    ) -> dict[str, int]:
        """Compute match parameters (T, energy, cap) for a map at a chosen difficulty."""
        bal = cls.load_balance() if balance is None else balance
        table = bal.get(cls.map_key(path), {})
        diff = DIFFICULTIES[difficulty]
        return {
            "T": table.get("T") or math.ceil(FALLBACK_T_FACTOR * shortest_path),
            "energy": ENERGY_START,
            "cap": ENERGY_CAP,
            "lock_cost": diff.lock_cost,
            "wall_cost": diff.wall_cost,
        }

