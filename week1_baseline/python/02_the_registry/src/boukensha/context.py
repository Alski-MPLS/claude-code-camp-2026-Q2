"""Boukensha::Context port: holds everything needed to make an API call.

Unlike ``Tool``/``Message`` (simple Struct-style data), Ruby's ``Context`` is
a hand-written class with behavior (``register_tool``, ``add_message``) and
derived counts — so it stays a plain Python class, not a dataclass, matching
the precedent set by ``Config``.
"""

from __future__ import annotations

from .message import Message
from .tasks.base import Base
from .tool import Tool


class Context:
    def __init__(self, task: type[Base], system: str | None = None) -> None:
        self.task = task
        self.system = system
        self.messages: list[Message] = []
        self.tools: dict[str, Tool] = {}

    def register_tool(self, tool: Tool) -> None:
        self.tools[tool.name] = tool

    def add_message(self, role: str, content: str, tool_use_id: str | None = None) -> None:
        self.messages.append(Message(role, content, tool_use_id))

    @property
    def tool_count(self) -> int:
        return len(self.tools)

    @property
    def turn_count(self) -> int:
        return len(self.messages)

    def __str__(self) -> str:
        task_name = self.task.task_name() if self.task is not None else None
        return f"#<Context task={task_name} turns={self.turn_count} tools={self.tool_count}>"
