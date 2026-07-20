"""Boukensha::Message port: a single unit of conversation."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any


@dataclass
class Message:
    role: str
    content: Any
    tool_use_id: str | None = None

    def __str__(self) -> str:
        preview = str(self.content)[:61]
        id_tag = f" [{self.tool_use_id}]" if self.tool_use_id else ""
        return f"#<Message role={self.role}{id_tag} content={preview}...>"
