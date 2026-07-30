from __future__ import annotations

import os
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import yaml


class KnowledgeManager:
    def __init__(self, base_dir: str | Path) -> None:
        self._path = Path(base_dir) / "knowledge.yaml"
        self._path.parent.mkdir(parents=True, exist_ok=True)

    def add(self, topic: str, fact: str, source: str) -> None:
        entries = self._load()
        topic_lower = topic.lower()
        entries = [e for e in entries if e["topic"].lower() != topic_lower]
        entries.append({
            "topic": topic,
            "fact": fact,
            "source": source,
            "timestamp": datetime.now(timezone.utc).isoformat(),
        })
        self._save(entries)

    def search(self, query: str) -> list[dict[str, Any]]:
        query_lower = query.lower()
        return [
            e for e in self._load()
            if query_lower in e.get("topic", "").lower()
            or query_lower in e.get("fact", "").lower()
            or query_lower in e.get("source", "").lower()
        ]

    def read_all(self) -> list[dict[str, Any]]:
        entries = self._load()
        return list(reversed(entries))

    # ── private ──────────────────────────────────────────────────────────────

    def _load(self) -> list[dict[str, Any]]:
        if not self._path.exists():
            return []
        raw = yaml.safe_load(self._path.read_text(encoding="utf-8"))
        return raw if isinstance(raw, list) else []

    def _save(self, entries: list[dict[str, Any]]) -> None:
        tmp = self._path.with_suffix(".tmp")
        tmp.write_text(
            yaml.dump(entries, default_flow_style=False, allow_unicode=True),
            encoding="utf-8",
        )
        os.replace(tmp, self._path)
