"""Save and load world tile maps to a JSON file."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any


class MapStorage:
    """Persistent storage for the board layout.

    The map is stored as a 2D list of tile integers.  If the file does not
    exist, a default empty map is created on first save.
    """

    DEFAULT_FILENAME = "world_map.json"

    def __init__(self, path: Path | str | None = None) -> None:
        if path is None:
            path = Path(self.DEFAULT_FILENAME)
        self.path = Path(path)

    def exists(self) -> bool:
        return self.path.exists()

    def load(self) -> list[list[int]] | None:
        if not self.exists():
            return None
        try:
            with self.path.open("r", encoding="utf-8") as f:
                data: dict[str, Any] = json.load(f)
            return data.get("tiles")
        except (json.JSONDecodeError, OSError, ValueError, KeyError):
            return None

    def save(self, tiles: list[list[int]]) -> None:
        data = {"tiles": tiles}
        with self.path.open("w", encoding="utf-8") as f:
            json.dump(data, f, indent=2)

    def clear(self) -> None:
        """Remove the saved map file."""
        if self.exists():
            self.path.unlink()
