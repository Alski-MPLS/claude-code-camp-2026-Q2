"""Boukensha::Backends::Gemini port: serializes context into the Gemini
``generateContent`` API format.
"""

from __future__ import annotations

from typing import Any

from .base import Base


class Gemini(Base):
    BASE_URL = "https://generativelanguage.googleapis.com/v1beta/models"
    MODELS: dict[str, dict[str, Any]] = {
        "gemini-3.5-flash": {
            "context_window": 1_048_576,
            "cost_per_million": {"input": 1.5, "output": 9.0},
            "usage_unit": "tokens",
        },
        "gemini-3.1-flash-lite": {
            "context_window": 1_048_576,
            "cost_per_million": {"input": 0.25, "output": 1.5},
            "usage_unit": "tokens",
        },
        "gemini-2.5-pro": {
            "context_window": 1_048_576,
            "cost_per_million": {"input": 1.25, "output": 10.0},
            "usage_unit": "tokens",
        },
        "gemini-2.5-flash": {
            "context_window": 1_048_576,
            "cost_per_million": {"input": 0.30, "output": 2.50},
            "usage_unit": "tokens",
        },
        "gemini-2.5-flash-lite": {
            "context_window": 1_048_576,
            "cost_per_million": {"input": 0.10, "output": 0.40},
            "usage_unit": "tokens",
        },
    }

    def __init__(self, *, api_key: str, model: str) -> None:
        self._api_key = api_key
        self._configure_model(model)

    def to_messages(self, messages: list[Any]) -> list[dict[str, Any]]:
        result: list[dict[str, Any]] = []
        for msg in messages:
            if msg.role == "assistant":
                result.append({"role": "model", "parts": self._assistant_parts(msg.content)})
            elif msg.role == "tool_result":
                result.append(
                    {
                        "role": "user",
                        "parts": [{"functionResponse": {"name": msg.tool_use_id, "response": {"content": msg.content}}}],
                    }
                )
            else:
                result.append({"role": msg.role, "parts": [{"text": msg.content}]})
        return result

    def to_tools(self, tools: dict[str, Any]) -> list[dict[str, Any]]:
        if not tools:
            return []

        return [
            {
                "functionDeclarations": [
                    {
                        "name": tool.name,
                        "description": tool.description,
                        "parameters": {
                            "type": "object",
                            "properties": tool.parameters,
                            "required": list(tool.parameters.keys()),
                        },
                    }
                    for tool in tools.values()
                ]
            }
        ]

    def to_payload(self, context: Any, *, max_output_tokens: int = 1024, tools: list | None = None) -> dict[str, Any]:
        return {
            "systemInstruction": {"parts": [{"text": context.system}]},
            "contents": self.to_messages(context.messages),
            "tools": tools if tools is not None else self.to_tools(context.tools),
            "generationConfig": {"maxOutputTokens": max_output_tokens},
        }

    def parse_response(self, response: dict[str, Any]) -> dict[str, Any]:
        parts = ((response.get("candidates") or [{}])[0].get("content") or {}).get("parts") or []
        content: list[dict[str, Any]] = []
        tool_used = False
        for part in parts:
            if "functionCall" in part:
                fc = part["functionCall"]
                content.append({"type": "tool_use", "id": fc["name"], "name": fc["name"], "input": fc.get("args") or {}})
                tool_used = True
            elif "text" in part:
                content.append({"type": "text", "text": part["text"]})
        return {"stop_reason": "tool_use" if tool_used else "end_turn", "content": content}

    def _assistant_parts(self, content: Any) -> list[dict[str, Any]]:
        blocks = content if isinstance(content, list) else [{"type": "text", "text": content}]
        parts: list[dict[str, Any]] = []
        for b in blocks:
            if b.get("type") == "tool_use":
                parts.append({"functionCall": {"name": b["name"], "args": b["input"]}})
            else:
                parts.append({"text": b.get("text", "")})
        return parts

    @property
    def headers(self) -> dict[str, str]:
        return {
            "Content-Type": "application/json",
            "x-goog-api-key": self._api_key,
        }

    @property
    def url(self) -> str:
        return f"{self.BASE_URL}/{self.model}:generateContent"
