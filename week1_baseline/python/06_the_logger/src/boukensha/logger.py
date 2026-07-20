"""Boukensha::Logger port: writes structured JSONL session files."""

from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any
from uuid import uuid4

DEFAULT_SESSION_DIR = "sessions"


class Logger:
    def __init__(
        self,
        *,
        session_id: str | None = None,
        dir: str | None = None,
        log: str | None = None,
        snapshot: dict[str, Any] | None = None,
    ) -> None:
        self.session_id = session_id or _generate_session_id()
        self.path = log or str(Path(dir or _default_dir()) / f"{self.session_id}.jsonl")
        Path(self.path).parent.mkdir(parents=True, exist_ok=True)
        self._log_io = open(self.path, "a", encoding="utf-8")  # noqa: WPS515
        self._write_log({"phase": "session_start", **(snapshot or {})})

    def iteration(self, *, n: int, max: int) -> None:
        self._write_log({"phase": "iteration", "n": n, "max": max})

    def limit_reached(self, *, kind: str, n: int, max: int) -> None:
        self._write_log({"phase": "limit_reached", "kind": kind, "n": n, "max": max})

    def turn_end(self, *, reason: str, iterations: int, tokens: Any = None) -> None:
        self._write_log({"phase": "turn_end", "reason": reason, "iterations": iterations, "tokens": tokens})

    def prompt(self, *, messages: list[Any], tools: dict[str, Any]) -> None:
        self._write_log({
            "phase": "prompt",
            "message_count": len(messages),
            "messages": [{"role": m.role, "content": m.content} for m in messages],
            "tool_count": len(tools),
            "tools": list(tools.keys()),
        })

    def tool_call(self, *, name: str, args: dict[str, Any]) -> None:
        self._write_log({"phase": "tool_call", "name": name, "args": args})

    def tool_result(self, *, name: str, result: Any, ok: bool = True, error: str | None = None) -> None:
        self._write_log({"phase": "tool_result", "name": name, "result": str(result), "ok": ok, "error": error})

    def response(
        self,
        *,
        text: str,
        usage: dict[str, Any] | None = None,
        stop_reason: str | None = None,
        task: Any = None,
        backend: Any = None,
    ) -> None:
        event: dict[str, Any] = {
            "phase": "response",
            "text": str(text).strip(),
            "usage": usage,
            "stop_reason": stop_reason,
        }
        event.update(_execution_metadata(task=task, backend=backend, usage=usage))
        self._write_log(event)

    def raw(self, *, data: Any) -> None:
        import boukensha
        if not boukensha.debug():
            return
        self._write_log({"phase": "raw", "data": data})

    def close(self) -> None:
        if self._log_io:
            self._log_io.close()

    # ---------- private -----------------------------------------------------

    def _write_log(self, event: dict[str, Any]) -> None:
        line = json.dumps({**event, "session_id": self.session_id, "at": _now_iso()})
        self._log_io.write(line + "\n")
        self._log_io.flush()


# ---------- module helpers --------------------------------------------------

def _generate_session_id() -> str:
    ts = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    return f"{ts}-{uuid4().hex[:8]}"


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def _default_dir() -> str:
    import boukensha
    return str(Path(boukensha.Config().dir) / DEFAULT_SESSION_DIR)


def _execution_metadata(*, task: Any, backend: Any, usage: Any) -> dict[str, Any]:
    if task is None and backend is None and usage is None:
        return {}
    tokens = _usage_tokens(usage)
    metadata: dict[str, Any] = {
        "task": _task_name(task),
        "provider": _provider_name(backend),
        "model": getattr(backend, "model", None),
        "usage_unit": getattr(backend, "usage_unit", None) if backend and hasattr(backend, "usage_unit") else None,
        "usage_level": getattr(backend, "usage_level", None) if backend and hasattr(backend, "usage_level") else None,
        "input_tokens": tokens["input"],
        "output_tokens": tokens["output"],
        "cost_usd": _estimate_cost(backend, tokens),
    }
    return {k: v for k, v in metadata.items() if v is not None}


def _task_name(task: Any) -> str | None:
    if task is None:
        return None
    if hasattr(task, "task_name"):
        return task.task_name()
    return str(task)


def _provider_name(backend: Any) -> str | None:
    if backend is None:
        return None
    import re
    name = type(backend).__name__
    # CamelCase -> snake_case
    return re.sub(r"([a-z\d])([A-Z])", r"\1_\2", name).lower()


def _usage_tokens(usage: Any) -> dict[str, int | None]:
    if not isinstance(usage, dict):
        return {"input": None, "output": None}
    input_keys = ("input_tokens", "prompt_tokens", "promptTokenCount", "prompt_eval_count")
    output_keys = ("output_tokens", "completion_tokens", "candidatesTokenCount", "eval_count")
    return {
        "input": _first_int(usage, input_keys),
        "output": _first_int(usage, output_keys),
    }


def _first_int(d: dict[str, Any], keys: tuple[str, ...]) -> int | None:
    for key in keys:
        val = d.get(key)
        if val is not None:
            try:
                return int(val)
            except (TypeError, ValueError):
                pass
    return None


def _estimate_cost(backend: Any, tokens: dict[str, int | None]) -> float | None:
    if backend is None or not hasattr(backend, "estimate_cost"):
        return None
    if tokens["input"] is None or tokens["output"] is None:
        return None
    return backend.estimate_cost(input_tokens=tokens["input"], output_tokens=tokens["output"])
