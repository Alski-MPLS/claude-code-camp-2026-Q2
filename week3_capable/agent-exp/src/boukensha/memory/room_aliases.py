"""Persist LLM-learned shorthand aliases (e.g. "bakery", "your guild") to the
room hash they were confirmed to resolve to, so a fuzzy destination that
navigate_to's deterministic title/landmark matching cannot reliably resolve
on its own only ever needs the agent's help once."""

from __future__ import annotations

import json
import os
from pathlib import Path
from typing import Any


class RoomAliases:
    def __init__(self, base_dir: str | Path) -> None:
        self._path = Path(base_dir) / "room_aliases.json"

    def get(self, alias: str) -> str | None:
        return self.read_all().get(alias.lower())

    def add(self, alias: str, room_hash: str) -> None:
        data = self.read_all()
        data[alias.lower()] = room_hash
        self._write(data)

    def read_all(self) -> dict[str, str]:
        if not self._path.exists():
            return {}
        try:
            data = json.loads(self._path.read_text(encoding="utf-8"))
        except (json.JSONDecodeError, OSError):
            return {}
        return data if isinstance(data, dict) else {}

    def _write(self, data: dict[str, Any]) -> None:
        tmp = self._path.with_suffix(".tmp")
        tmp.write_text(json.dumps(data, indent=2, ensure_ascii=False), encoding="utf-8")
        os.replace(tmp, self._path)
