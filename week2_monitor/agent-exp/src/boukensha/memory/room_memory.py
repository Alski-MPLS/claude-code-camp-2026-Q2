"""Persist unique rooms as JSON files keyed by a stable hash."""

from __future__ import annotations

import hashlib
import json
import os
from pathlib import Path
from typing import Any


class RoomMemory:
    def __init__(self, base_dir: str | Path) -> None:
        self._rooms_dir = Path(base_dir) / "rooms"
        self._rooms_dir.mkdir(parents=True, exist_ok=True)

    def room_hash(self, room: dict[str, Any]) -> str:
        key = room.get("title", "") + "\n" + room.get("description", "")
        return hashlib.sha256(key.encode("utf-8")).hexdigest()[:12]

    def record(self, room: dict[str, Any]) -> tuple[str, dict[str, Any]]:
        h = self.room_hash(room)
        path = self._rooms_dir / f"{h}.json"
        existing = self._load(path)
        diff = self._diff(existing, room)
        if diff:
            merged = {**(existing or {}), **room}
            self._save(path, merged)
        return h, diff

    def get(self, room_hash: str) -> dict[str, Any] | None:
        path = self._rooms_dir / f"{room_hash}.json"
        return self._load(path)

    # ── private ──────────────────────────────────────────────────────────────

    def _load(self, path: Path) -> dict[str, Any] | None:
        if not path.exists():
            return None
        return json.loads(path.read_text(encoding="utf-8"))

    def _save(self, path: Path, data: dict[str, Any]) -> None:
        tmp = path.with_suffix(".tmp")
        tmp.write_text(json.dumps(data, indent=2, ensure_ascii=False), encoding="utf-8")
        os.replace(tmp, path)

    def _diff(
        self, existing: dict[str, Any] | None, incoming: dict[str, Any]
    ) -> dict[str, Any]:
        if existing is None:
            return dict(incoming)
        changed: dict[str, Any] = {}
        for key, val in incoming.items():
            if existing.get(key) != val:
                changed[key] = val
        return changed
