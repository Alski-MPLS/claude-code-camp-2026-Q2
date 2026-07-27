"""Read/write the agent's current goal as structured YAML."""

from __future__ import annotations

import os
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import yaml


class GoalManager:
    DEFAULT_FIELDS: dict[str, Any] = {
        "current_goal": "Explore the MUD",
        "priority": "explore",
        "hp_flee_threshold": 5,
        "status": "active",
        "notes": "",
        "last_updated": None,
        "mud_basics": (
            "- Use 'score' to check HP/mana/moves\n"
            "- Use 'look' to describe current room\n"
            "- Use 'exits' to list available exits\n"
            "- north/south/east/west/up/down to move\n"
            "- 'kill <target>' to attack\n"
            "- 'flee' to escape combat\n"
        ),
    }

    def __init__(self, base_dir: str | Path) -> None:
        self._goals_dir = Path(base_dir) / "goals"
        self._goals_dir.mkdir(parents=True, exist_ok=True)
        self._path = self._goals_dir / "current.yaml"

    def read(self) -> dict[str, Any]:
        if not self._path.exists():
            return dict(self.DEFAULT_FIELDS)
        raw = yaml.safe_load(self._path.read_text(encoding="utf-8")) or {}
        return {**self.DEFAULT_FIELDS, **raw}

    def update(self, **kwargs: Any) -> None:
        current = self.read()
        current.update(kwargs)
        current["last_updated"] = datetime.now(timezone.utc).isoformat()
        self._write(current)

    def reset(self) -> None:
        self._write(dict(self.DEFAULT_FIELDS))

    def _write(self, data: dict[str, Any]) -> None:
        tmp = self._path.with_suffix(".tmp")
        tmp.write_text(yaml.dump(data, default_flow_style=False, allow_unicode=True), encoding="utf-8")
        os.replace(tmp, self._path)
