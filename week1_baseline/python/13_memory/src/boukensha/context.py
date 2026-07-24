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
        goal_path: str | Path | None = None,
    ) -> None:
        self.task = task
        self._base_system = system
        self.working_dir = str(Path(working_dir).expanduser().resolve()) if working_dir else None
        self.context_window = context_window
        self.compaction_threshold = compaction_threshold
        self.goal_path = Path(goal_path) if goal_path else None
        self.messages: list[Message] = []
        self.tools: dict[str, Tool] = {}
        self.current_tokens: int = 0
        self.turn_tokens: int = 0

    @property
    def system(self) -> str | None:
        """Static system prompt plus the current goal, re-read from disk on
        every access so a mid-session goal change is picked up immediately —
        not just at the start of a turn."""
        if self._base_system is None:
            return None
        goal_text = self._read_goal()
        if not goal_text:
            return self._base_system
        return f"{self._base_system}\n\n## Current Goal\n{goal_text}"

    def set_goal(self, text: str) -> None:
        """Persist *text* as the active goal, superseding whatever came before.

        No-op if this context wasn't given a goal_path (e.g. no MUD session),
        since there's nowhere durable to put it.
        """
        if self.goal_path is None:
            return
        self.goal_path.parent.mkdir(parents=True, exist_ok=True)
        self.goal_path.write_text(text.strip() + "\n")

    def _read_goal(self) -> str | None:
        if self.goal_path is None or not self.goal_path.exists():
            return None
        try:
            return self.goal_path.read_text().strip() or None
        except OSError:
            return None

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
