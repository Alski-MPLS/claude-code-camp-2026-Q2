"""World-scoped store of identified item stats (AC, hitroll, damroll, stat mods)."""

from __future__ import annotations

import os
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import yaml


class ItemStatsStore:
    def __init__(self, base_dir: str | Path) -> None:
        self._path = Path(base_dir) / "item_stats.yaml"
        self._path.parent.mkdir(parents=True, exist_ok=True)

    def save(self, item_name: str, stats: dict[str, Any]) -> None:
        data = self._load()
        data[item_name.strip().lower()] = {
            **stats,
            "timestamp": datetime.now(timezone.utc).isoformat(),
        }
        self._save(data)

    def get(self, item_name: str) -> dict[str, Any] | None:
        return self._load().get(item_name.strip().lower())

    def read_all(self) -> dict[str, dict[str, Any]]:
        return self._load()

    # ── private ──────────────────────────────────────────────────────────────

    def _load(self) -> dict[str, dict[str, Any]]:
        if not self._path.exists():
            return {}
        raw = yaml.safe_load(self._path.read_text(encoding="utf-8"))
        return raw if isinstance(raw, dict) else {}

    def _save(self, data: dict[str, dict[str, Any]]) -> None:
        tmp = self._path.with_suffix(".tmp")
        tmp.write_text(
            yaml.dump(data, default_flow_style=False, allow_unicode=True),
            encoding="utf-8",
        )
        os.replace(tmp, self._path)
