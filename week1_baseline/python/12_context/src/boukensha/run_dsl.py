"""RunDSL: the object that ``self`` becomes inside a ``boukensha.run`` block.

Exposes only ``tool()``, keeping the DSL surface intentionally minimal so
callers cannot reach internal state.
"""

from __future__ import annotations

from collections.abc import Callable
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from .registry import Registry
    from .tool import Tool


class RunDSL:
    def __init__(self, registry: Registry) -> None:
        self._registry = registry

    def tool(
        self,
        name: str,
        description: str,
        parameters: dict[str, Any] | None = None,
        *,
        block: Callable[..., Any],
    ) -> Tool:
        return self._registry.tool(name, description, parameters, block=block)
