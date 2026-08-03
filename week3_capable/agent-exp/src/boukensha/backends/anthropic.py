"""Boukensha::Backends::Anthropic port: serializes context into the
Anthropic Messages API format (https://api.anthropic.com/v1/messages).
"""

from __future__ import annotations

from typing import Any

from .base import Base


def _with_cache_control(content: Any) -> Any:
    """Attach a cache_control breakpoint to the last content block.

    ``content`` is either a plain string (simple text turns) or a list of
    content blocks (tool_use / tool_result turns). The Anthropic API only
    accepts cache_control on block dicts, so a bare string is first wrapped
    into a single text block.
    """
    if isinstance(content, str):
        return [{"type": "text", "text": content, "cache_control": {"type": "ephemeral"}}]
    if isinstance(content, list) and content:
        blocks = list(content)
        blocks[-1] = {**blocks[-1], "cache_control": {"type": "ephemeral"}}
        return blocks
    return content


class Anthropic(Base):
    BASE_URL = "https://api.anthropic.com/v1/messages"
    MODELS: dict[str, dict[str, Any]] = {
        "claude-haiku-4-5": {
            "context_window": 200_000,
            "cost_per_million": {"input": 1.0, "output": 5.0},
            "usage_unit": "tokens",
        },
        "claude-haiku-4-5-20251001": {
            "context_window": 200_000,
            "cost_per_million": {"input": 1.0, "output": 5.0},
            "usage_unit": "tokens",
        },
        "claude-sonnet-4-6": {
            "context_window": 1_000_000,
            "cost_per_million": {"input": 3.0, "output": 15.0},
            "usage_unit": "tokens",
        },
        "claude-opus-4-8": {
            "context_window": 1_000_000,
            "cost_per_million": {"input": 5.0, "output": 25.0},
            "usage_unit": "tokens",
        },
    }

    def __init__(self, *, api_key: str, model: str) -> None:
        self._api_key = api_key
        self._configure_model(model)

    def to_messages(self, messages: list[Any]) -> list[dict[str, Any]]:
        result: list[dict[str, Any]] = []
        for msg in messages:
            if msg.role == "tool_result":
                result.append(
                    {
                        "role": "user",
                        "content": [
                            {
                                "type": "tool_result",
                                "tool_use_id": msg.tool_use_id,
                                "content": msg.content,
                            }
                        ],
                    }
                )
            else:
                result.append({"role": msg.role, "content": msg.content})
        # Mark a fresh cache breakpoint at the tail of the conversation each
        # turn. Everything before this point was already sent (and cached)
        # on a prior iteration of the same agent loop, so this lets the API
        # reuse that prefix at the ~10%-of-input-price cache-read rate
        # instead of re-billing the whole growing history at full price on
        # every single tool-calling round.
        if result:
            result[-1] = {**result[-1], "content": _with_cache_control(result[-1]["content"])}
        return result

    def to_tools(self, tools: dict[str, Any]) -> list[dict[str, Any]]:
        result = [
            {
                "name": tool.name,
                "description": tool.description,
                "input_schema": {
                    "type": "object",
                    "properties": tool.parameters,
                    "required": list(tool.parameters.keys()),
                },
            }
            for tool in tools.values()
        ]
        # Tool definitions are identical on every call for the life of the
        # session — caching the last one caches the whole preceding block.
        if result:
            result[-1] = {**result[-1], "cache_control": {"type": "ephemeral"}}
        return result

    def to_payload(self, context: Any, *, max_output_tokens: int = 1024, tools: list | None = None) -> dict[str, Any]:
        return {
            "model": self.model,
            # The system prompt is static for the whole session — caching
            # it means it's billed at full price once, then at the cheap
            # cache-read rate on every subsequent iteration and turn.
            "system": [
                {"type": "text", "text": context.system, "cache_control": {"type": "ephemeral"}}
            ] if context.system else context.system,
            "max_tokens": max_output_tokens,
            "tools": tools if tools is not None else self.to_tools(context.tools),
            "messages": self.to_messages(context.messages),
        }

    def parse_response(self, response: dict[str, Any]) -> dict[str, Any]:
        stop_reason = "tool_use" if response.get("stop_reason") == "tool_use" else "end_turn"
        return {"stop_reason": stop_reason, "content": response.get("content") or []}

    @property
    def headers(self) -> dict[str, str]:
        return {
            "Content-Type": "application/json",
            "x-api-key": self._api_key,
            "anthropic-version": "2023-06-01",
        }

    @property
    def url(self) -> str:
        return self.BASE_URL
