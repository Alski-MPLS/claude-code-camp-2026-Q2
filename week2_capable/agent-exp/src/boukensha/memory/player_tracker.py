"""Tracks each character's current room, for the dashboard's live map marker."""

from __future__ import annotations

import json
import os
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


class PlayerTracker:
    def __init__(self, base_dir: str | Path) -> None:
        self._path = Path(base_dir) / "players.json"
        self._path.parent.mkdir(parents=True, exist_ok=True)

    def update(self, name: str, room_hash: str, title: str) -> None:
        data = self.read_all()
        data[name] = {
            "room_hash": room_hash,
            "title": title,
            "updated_at": datetime.now(timezone.utc).isoformat(),
        }
        self._write(data)

    def read_all(self) -> dict[str, Any]:
        if not self._path.exists():
            return {}
        try:
            return json.loads(self._path.read_text(encoding="utf-8"))
        except (json.JSONDecodeError, OSError):
            return {}

    def _write(self, data: dict[str, Any]) -> None:
        tmp = self._path.with_suffix(".tmp")
        tmp.write_text(json.dumps(data, indent=2, ensure_ascii=False), encoding="utf-8")
        os.replace(tmp, self._path)
