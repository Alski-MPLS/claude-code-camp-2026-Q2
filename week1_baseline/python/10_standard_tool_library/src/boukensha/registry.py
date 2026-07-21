"""Boukensha::Registry port: registers tools on a Context and dispatches
calls to them by name.

Ruby's ``dispatch`` converts string-keyed args to symbol keys
(``args.transform_keys(&:to_sym)``) before calling the block, because Ruby
blocks with keyword parameters require symbol keys while the args arrive
string-keyed (as they would from parsed JSON). Python has no such gap:
keyword arguments are matched by string name already, so ``tool.block(**args)``
needs no key-transformation step — the "gotcha" the Ruby original calls out
is language-specific and doesn't carry over.
"""

from __future__ import annotations

from collections.abc import Callable
from typing import Any

from .context import Context
from .errors import UnknownToolError
from .tool import Tool


class Registry:
    def __init__(self, context: Context) -> None:
        self._context = context

    def tool(
        self,
        name: str,
        description: str,
        parameters: dict[str, Any] | None = None,
        *,
        block: Callable[..., Any],
    ) -> Tool:
        registered = Tool(str(name), description, parameters or {}, block)
        self._context.register_tool(registered)
        return registered

    def get(self, name: str) -> "Tool | None":
        return self._context.tools.get(str(name))

    def dispatch(self, name: str, args: dict[str, Any] | None = None) -> Any:
        tool = self._context.tools.get(str(name))
        if tool is None:
            raise UnknownToolError(f"No tool registered as '{name}'")
        return tool.block(**(args or {}))
