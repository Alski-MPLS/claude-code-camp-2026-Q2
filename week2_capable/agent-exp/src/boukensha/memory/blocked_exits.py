"""Persist exits confirmed to need something the agent doesn't have yet
(a locked door, a key, a dark room needing a light source) so exploration
stops retrying them on every pass and instead moves on to the next
unexplored exit."""

from __future__ import annotations

import json
import os
from pathlib import Path
from typing import Any

_DEFAULT_REASON = "blocked"


class BlockedExits:
    def __init__(self, base_dir: str | Path) -> None:
        self._path = Path(base_dir) / "blocked_exits.json"

    def read_all(self) -> dict[str, dict[str, str]]:
        if not self._path.exists():
            return {}
        try:
            return json.loads(self._path.read_text(encoding="utf-8"))
        except (json.JSONDecodeError, OSError):
            return {}

    def get(self, room_hash: str) -> set[str]:
        return set(self.read_all().get(room_hash, {}).keys())

    def reason(self, room_hash: str, direction: str) -> str | None:
        return self.read_all().get(room_hash, {}).get(direction)

    def mark_blocked(self, room_hash: str, direction: str, reason: str = _DEFAULT_REASON) -> None:
        data = self.read_all()
        room_data = dict(data.get(room_hash, {}))
        room_data[direction] = reason
        data[room_hash] = room_data
        self._write(data)

    def unmark(self, room_hash: str, direction: str) -> None:
        """Clear a previously-blocked exit (e.g. once the agent has picked up
        the key, or acquired a light source, or otherwise found a way
        through), so it re-enters the exploration frontier."""
        data = self.read_all()
        room_data = dict(data.get(room_hash, {}))
        room_data.pop(direction, None)
        if room_data:
            data[room_hash] = room_data
        else:
            data.pop(room_hash, None)
        self._write(data)

    def _write(self, data: dict[str, Any]) -> None:
        tmp = self._path.with_suffix(".tmp")
        tmp.write_text(json.dumps(data, indent=2, ensure_ascii=False), encoding="utf-8")
        os.replace(tmp, self._path)
