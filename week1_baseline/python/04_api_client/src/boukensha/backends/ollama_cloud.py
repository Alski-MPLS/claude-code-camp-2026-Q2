"""Boukensha::Backends::OllamaCloud port: serializes context into the
Ollama Cloud chat API format (https://ollama.com/api/chat).
"""

from __future__ import annotations

from typing import Any

from .base import Base


class OllamaCloud(Base):
    BASE_URL = "https://ollama.com"
    MODELS: dict[str, dict[str, Any]] = {
        "gemma4:31b-cloud": {
            "context_window": 256_000,
            "cost_per_million": {"input": None, "output": None},
            "usage_unit": "ollama_cloud_usage",
            "usage_level": "medium",
        },
        "minimax-m3:cloud": {
            "context_window": 512_000,
            "advertised_context_window": 1_000_000,
            "cost_per_million": {"input": None, "output": None},
            "usage_unit": "ollama_cloud_usage",
            "usage_level": "high",
        },
        "kimi-k2.5:cloud": {
            "context_window": 256_000,
            "cost_per_million": {"input": None, "output": None},
            "usage_unit": "ollama_cloud_usage",
            "usage_level": "high",
        },
    }

    def __init__(self, *, api_key: str, model: str) -> None:
        self._api_key = api_key
        self._configure_model(model)

    def to_messages(self, system: str | None, messages: list[Any]) -> list[dict[str, Any]]:
        system_message = [{"role": "system", "content": system}]
        conversation: list[dict[str, Any]] = []
        for msg in messages:
            if msg.role == "tool_result":
                conversation.append({"role": "tool", "tool_name": msg.tool_use_id, "content": msg.content})
            else:
                conversation.append({"role": msg.role, "content": msg.content})
        return system_message + conversation

    def to_tools(self, tools: dict[str, Any]) -> list[dict[str, Any]]:
        return [
            {
                "type": "function",
                "function": {
                    "name": tool.name,
                    "description": tool.description,
                    "parameters": {
                        "type": "object",
                        "properties": tool.parameters,
                        "required": list(tool.parameters.keys()),
                    },
                },
            }
            for tool in tools.values()
        ]

    def to_payload(self, context: Any, *, max_output_tokens: int = 1024) -> dict[str, Any]:
        return {
            "model": self.model,
            "stream": False,
            "messages": self.to_messages(context.system, context.messages),
            "tools": self.to_tools(context.tools),
        }

    @property
    def headers(self) -> dict[str, str]:
        return {
            "Content-Type": "application/json",
            "Authorization": f"Bearer {self._api_key}",
        }

    @property
    def url(self) -> str:
        return f"{self.BASE_URL}/api/chat"
