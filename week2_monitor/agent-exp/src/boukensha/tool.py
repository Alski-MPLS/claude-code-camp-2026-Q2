"""Boukensha::Tool port: an action the agent can invoke.

Ruby represents this with ``Struct.new(:name, :description, :parameters,
:block)``; the direct Python equivalent of a Struct — a lightweight,
auto-``__init__``, mutable field container — is a plain ``@dataclass``.
"""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from typing import Any


@dataclass
class Tool:
    name: str
    description: str
    parameters: dict[str, Any]
    block: Callable[..., Any]

    def __str__(self) -> str:
        return (
            f"#<Tool name={self.name} description={self.description[:41]} "
            f"params={list(self.parameters.keys())}>"
        )
