"""Boukensha::PromptBuilder port: delegates Context serialization to
whichever backend it's given.

Known upstream quirk, preserved intentionally: ``to_messages`` always calls
``backend.to_messages(context.messages)`` with exactly one argument. This
matches every backend's real signature for ``Anthropic``/``Gemini`` (which
take one arg, ``messages``), but not ``Ollama``/``OllamaCloud``/``OpenAI``
(which take two, ``system, messages``) — calling ``PromptBuilder.to_messages``
directly with one of those three backends will raise a ``TypeError``. This is
a real, unaddressed inconsistency in the Ruby source (confirmed: it isn't
fixed in ``ruby/04_api_client`` either), and it never triggers in practice
because ``to_api_payload`` routes through each backend's own ``to_payload``,
which calls that backend's ``to_messages`` with the correct arity internally.
Ported as-is rather than "fixed" — see the plan's Global Constraints.
"""

from __future__ import annotations

from typing import Any


class PromptBuilder:
    def __init__(self, context: Any, backend: Any) -> None:
        self._context = context
        self._backend = backend

    def to_messages(self) -> list[dict[str, Any]]:
        return self._backend.to_messages(self._context.messages)

    def to_tools(self) -> list[dict[str, Any]]:
        return self._backend.to_tools(self._context.tools)

    def to_api_payload(self, *, max_output_tokens: int = 1024) -> dict[str, Any]:
        return self._backend.to_payload(self._context, max_output_tokens=max_output_tokens)

    @property
    def headers(self) -> dict[str, str]:
        return self._backend.headers

    @property
    def url(self) -> str:
        return self._backend.url
