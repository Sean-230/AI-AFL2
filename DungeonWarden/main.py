"""Entry point for the Dungeon Warden Pygame application."""
from __future__ import annotations

from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from DungeonWarden.ui.game import main  # noqa: E402

if __name__ == "__main__":
    main()

