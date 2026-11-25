from __future__ import annotations

import json
import re
from pathlib import Path


def _normalized(value: str) -> str:
    return re.sub(r"[^a-z0-9]", "", value.casefold())


class APWorldIndex:
    def __init__(self, data_root: Path | None):
        self.by_normalized: dict[str, list[tuple[str, str, Path]]] = {}
        if data_root is None or not data_root.exists():
            return
        for path in sorted((data_root / "items").rglob("*.json")):
            try:
                data = json.loads(path.read_text(encoding="utf-8-sig"))
            except (OSError, json.JSONDecodeError):
                continue
            if not isinstance(data, dict):
                continue
            for key, details in data.items():
                label = details.get("label") if isinstance(details, dict) else None
                for candidate in (key.removeprefix("ITEM_"), label):
                    if candidate:
                        self.by_normalized.setdefault(_normalized(str(candidate)), []).append((key, str(label or key), path))

    def suggest(self, game_id: str | None) -> list[str]:
        if not game_id:
            return []
        matches = self.by_normalized.get(_normalized(game_id), [])
        unique: dict[str, tuple[str, str, Path]] = {match[0]: match for match in matches}
        return [f"{key} ({label}; Quelle: {path.as_posix()})" for key, label, path in sorted(unique.values())]
