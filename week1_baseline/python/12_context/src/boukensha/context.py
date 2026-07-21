"""Boukensha::Context port: holds everything needed to make an API call."""

from __future__ import annotations

import math
from pathlib import Path
from typing import Any

from .message import Message
from .tasks.base import Base
from .tool import Tool


class Context:
    def __init__(
        self,
        task: type[Base],
        system: str | None = None,
        working_dir: str | None = None,
        context_window: int = 200_000,
        compaction_threshold: float = 0.85,
    ) -> None:
        self.task = task
        self.system = system
        self.working_dir = str(Path(working_dir).expanduser().resolve()) if working_dir else None
        self.context_window = context_window
        self.compaction_threshold = compaction_threshold
        self.messages: list[Message] = []
        self.tools: dict[str, Tool] = {}
        self.current_tokens: int = 0
        self.turn_tokens: int = 0

    def register_tool(self, tool: Tool) -> None:
        self.tools[tool.name] = tool

    def add_message(self, role: str, content: Any, tool_use_id: str | None = None) -> None:
        self.messages.append(Message(role, content, tool_use_id))

    def update_tokens(self, n: int | str) -> None:
        self.current_tokens = int(n)

    def reset_turn_tokens(self) -> None:
        self.turn_tokens = 0

    def add_turn_tokens(self, input_tokens: int | str, output_tokens: int | str) -> None:
        self.turn_tokens += int(input_tokens) + int(output_tokens)

    @property
    def usage_fraction(self) -> float:
        if self.context_window <= 0:
            return 0.0
        return self.current_tokens / self.context_window

    @property
    def usage_pct(self) -> int:
        return math.floor(self.usage_fraction * 100)

    def needs_compaction(self, threshold: float | None = None) -> bool:
        t = threshold if threshold is not None else self.compaction_threshold
        return self.usage_fraction >= t

    def compact_messages(self, target_fraction: float = 0.60) -> int:
        if not self.messages:
            return 0
        drop_fraction = 1.0 - target_fraction
        drop_count = math.ceil(len(self.messages) * drop_fraction)
        drop_count = min(drop_count, len(self.messages) - 2)
        drop_count = max(drop_count, 0)
        self.messages = self.messages[drop_count:]
        self.current_tokens = 0
        return drop_count

    def clear_messages(self) -> None:
        self.messages = []
        self.current_tokens = 0

    @property
    def tool_count(self) -> int:
        return len(self.tools)

    @property
    def turn_count(self) -> int:
        return len(self.messages)

    def __str__(self) -> str:
        task_name = self.task.task_name() if self.task is not None else None
        return (
            f"#<Context task={task_name} turns={self.turn_count} "
            f"tools={self.tool_count} window={self.context_window} "
            f"current={self.current_tokens}>"
        )
