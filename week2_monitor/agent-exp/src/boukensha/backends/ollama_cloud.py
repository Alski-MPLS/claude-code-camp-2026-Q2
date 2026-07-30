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
            elif msg.role == "assistant":
                conversation.append(self._assistant_message(msg.content))
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

    def to_payload(self, context: Any, *, max_output_tokens: int = 1024, tools: list | None = None) -> dict[str, Any]:
        return {
            "model": self.model,
            "stream": False,
            "messages": self.to_messages(context.system, context.messages),
            "tools": tools if tools is not None else self.to_tools(context.tools),
        }

    def parse_response(self, response: dict[str, Any]) -> dict[str, Any]:
        message = response.get("message") or {}
        tool_calls = message.get("tool_calls") or []
        content: list[dict[str, Any]] = []
        if message.get("content"):
            content.append({"type": "text", "text": message["content"]})
        for tc in tool_calls:
            fn = tc.get("function") or {}
            content.append({"type": "tool_use", "id": fn.get("name"), "name": fn.get("name"), "input": fn.get("arguments") or {}})
        return {"stop_reason": "tool_use" if tool_calls else "end_turn", "content": content}

    def _assistant_message(self, content: Any) -> dict[str, Any]:
        blocks = content if isinstance(content, list) else [{"type": "text", "text": content}]
        text_blocks = [b for b in blocks if b.get("type") == "text"]
        tool_blocks = [b for b in blocks if b.get("type") == "tool_use"]
        message: dict[str, Any] = {"role": "assistant", "content": "".join(b["text"] for b in text_blocks)}
        if tool_blocks:
            message["tool_calls"] = [{"function": {"name": b["name"], "arguments": b["input"]}} for b in tool_blocks]
        return message

    @property
    def headers(self) -> dict[str, str]:
        return {
            "Content-Type": "application/json",
            "Authorization": f"Bearer {self._api_key}",
        }

    @property
    def url(self) -> str:
        return f"{self.BASE_URL}/api/chat"
