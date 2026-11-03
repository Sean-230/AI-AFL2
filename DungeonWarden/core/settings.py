"""Application configuration, difficulty presets, and 20x20 map path management."""
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
    """Represents a game difficulty level and its target player win rate."""

    key: str
    label: str
    target_win_rate: int
    fallback_factor: float


DIFFICULTIES: dict[str, Difficulty] = {
    d.key: d
    for d in (
        Difficulty("easy", "Easy", 50, 4.0),
        Difficulty("normal", "Normal", 30, 3.0),
        Difficulty("hard", "Hard", 15, 2.5),
    )
}


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
        """Load calibrated turn limits (T) per map and difficulty from balance.json."""
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
        key = cls.map_key(path)
        table = bal.get(key) or bal.get(f"20x20/{key}", {})
        diff_cfg = DIFFICULTIES[difficulty]
        turn_limit = table.get(difficulty) or math.ceil(diff_cfg.fallback_factor * shortest_path)
        return {
            "T": turn_limit,
            "energy": ENERGY_START,
            "cap": ENERGY_CAP,
        }

