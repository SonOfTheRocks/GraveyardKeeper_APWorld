"""Standalone launcher that avoids importing worlds.graveyard_keeper and Archipelago runtime modules."""

from __future__ import annotations

from flow_analysis.cli import main


if __name__ == "__main__":
    raise SystemExit(main())
