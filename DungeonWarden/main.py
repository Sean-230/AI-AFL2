"""Main entry point for the Dungeon Warden Pygame application."""
from __future__ import annotations

from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from DungeonWarden.ui.app import DungeonWardenApp, parse_args  # noqa: E402


def main(argv: list[str] | None = None) -> None:
    """Launch the Dungeon Warden application."""
    args = parse_args(argv)
    DungeonWardenApp(args).run()


if __name__ == "__main__":
    main()
