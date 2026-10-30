from __future__ import annotations

import json
import os
from typing import Dict

DEFAULT_PATH = os.path.join(os.path.expanduser("~"), ".decision_flow_progress.json")


class Progress:
    """Best star count per level, saved as a small JSON file. A missing or
    unreadable save just starts fresh, so the game never fails to launch."""

    def __init__(self, path: str = DEFAULT_PATH) -> None:
        self.path = path
        self.best: Dict[str, int] = {}
        self.muted = False
        self._load()

    def _load(self) -> None:
        try:
            with open(self.path, "r", encoding="utf-8") as handle:
                data = json.load(handle)
        except (OSError, ValueError):
            return
        if isinstance(data, dict):
            best = data.get("best", {})
            if isinstance(best, dict):
                self.best = {str(k): int(v) for k, v in best.items() if isinstance(v, int)}
            self.muted = bool(data.get("muted", False))

    def save(self) -> None:
        try:
            with open(self.path, "w", encoding="utf-8") as handle:
                json.dump({"best": self.best, "muted": self.muted}, handle, indent=2)
        except OSError:
            pass

    def stars(self, index: int) -> int:
        return self.best.get(str(index), 0)

    def record(self, index: int, stars: int) -> bool:
        """Store a result; returns True if it beat the previous best."""
        if stars > self.stars(index):
            self.best[str(index)] = stars
            self.save()
            return True
        return False

    def is_unlocked(self, index: int) -> bool:
        return index == 0 or self.stars(index - 1) > 0

    @property
    def total_stars(self) -> int:
        return sum(self.best.values())
