"""Abstract BasePlayerBot: the interface of a simulated player agent.

It belongs to the game package, next to BaseWarden (warden_base.py). The concrete bots used to evaluate the
Warden (RusherBot, CautiousBot) live in Experiments/player_bots.py and subclass this class.
"""
from __future__ import annotations

from abc import ABC, abstractmethod
import random
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from DungeonWarden.core.match_engine import MatchEngine


class BasePlayerBot(ABC):
    """Abstract base class for simulated player agents."""

    name: str = "Bot"

    def __init__(self, seed: int = 0) -> None:
        self.rng = random.Random(seed)

    @abstractmethod
    def move(self, match: "MatchEngine") -> str:
        """Select a legal movement direction ('up', 'down', 'left', 'right') for the current turn."""
