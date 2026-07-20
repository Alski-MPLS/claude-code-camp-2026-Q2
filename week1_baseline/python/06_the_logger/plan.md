# 06 The Logger — Python Port Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Port `Boukensha::Logger` from Ruby `week1_baseline/ruby/06_the_logger` to Python as a drop-in addition to the existing `week1_baseline/python/05_agent_loop` codebase.

**Architecture:** Copy the full `05_agent_loop` tree into a new `06_the_logger` directory, add a `Logger` class that writes structured JSONL session files, wire it into `Agent`, add `debug!`/`debug?` to the module level, and update the example script. All existing files are copied unchanged except `agent.py`, `__init__.py`, and the example.

**Tech Stack:** Python 3.11+, `uv`, `pytest`, standard-library `json`, `pathlib`, `uuid`, `datetime` — no new third-party dependencies.

## Global Constraints

- Python 3.11+ (`requires-python = ">=3.11"` in pyproject.toml)
- Package managed with `uv` + `hatchling`; run tests with `uv run pytest`
- No new third-party dependencies — use only the stdlib (`json`, `pathlib`, `uuid`, `datetime`) plus what is already in `pyproject.toml`
- All source lives under `src/boukensha/`; tests under `tests/`
- Follow existing conventions: `from __future__ import annotations`, `_private` names, keyword-only constructor args with `*`
- Logger is a **file logger only** — it writes JSONL; it is not user-facing display output
- Every log line must contain `session_id` and `at` (ISO-8601) fields in addition to phase-specific data
- `raw()` must be a no-op unless `boukensha.debug()` returns `True`
- Session files default to `<boukensha_dir>/sessions/<session_id>.jsonl`
- `session_id` format: `YYYYMMDDTHHMMSSZ-<8 hex chars>` (UTC)
- Agent gets a default `Logger()` if none provided; existing behavior is unchanged when no logger is given (i.e. the print statements stay, they are not replaced)

---

## File Structure

| Path (relative to `week1_baseline/python/06_the_logger/`) | Action | Responsibility |
|---|---|---|
| `src/boukensha/logger.py` | **Create** | `Logger` class — JSONL session writer |
| `src/boukensha/__init__.py` | **Modify** | add `Logger`, `debug()`, `enable_debug()` exports; add module-level debug flag |
| `src/boukensha/agent.py` | **Modify** | accept optional `logger:` kwarg; call logger methods at each lifecycle point |
| `examples/example.py` | **Modify** | construct `Logger`, pass to `Agent`, print session path, update banner |
| `tests/test_logger.py` | **Create** | unit tests for `Logger` |
| `tests/test_agent.py` | **Modify** | extend existing agent tests to cover logger call sites |

Everything else (`backends/`, `client.py`, `config.py`, `context.py`, `errors.py`, `message.py`, `prompt_builder.py`, `registry.py`, `tasks/`, `tool.py`, `pyproject.toml`, `prompts/`) is copied verbatim from `05_agent_loop` — no changes.

---

## Task 1: Scaffold the 06_the_logger directory

Copy the entire `05_agent_loop` tree into `06_the_logger` and adjust the pyproject description/name. The copy is the baseline; every subsequent task modifies files inside `06_the_logger`.

**Files:**
- Create: `week1_baseline/python/06_the_logger/` (directory tree)
- Modify: `week1_baseline/python/06_the_logger/pyproject.toml`

**Interfaces:**
- Produces: a runnable Python package at `week1_baseline/python/06_the_logger/` with all `05_agent_loop` tests passing

- [x] **Step 1: Copy the tree**

```bash
cp -r week1_baseline/python/05_agent_loop/. week1_baseline/python/06_the_logger/
```

- [x] **Step 2: Re-write plan.md with the current file content**

- [x] **Step 3: Update pyproject.toml description**

In `week1_baseline/python/06_the_logger/pyproject.toml`, change:

```toml
description = "Boukensha agent loop (Step 5)"
```

to:

```toml
description = "Boukensha logger (Step 6)"
```

- [x] **Step 4: Install dependencies and run existing tests**

```bash
cd week1_baseline/python/06_the_logger
uv sync
uv run pytest tests/ -v
```

Expected: all existing `05_agent_loop` tests pass (green). If any fail, investigate before continuing.

- [x] **Step 5: Commit**

```bash
git add week1_baseline/python/06_the_logger/
git commit -m "feat: scaffold 06_the_logger from 05_agent_loop"
```

---

## Task 2: Add module-level debug flag to `__init__.py`

Ruby's `Boukensha.debug!` / `Boukensha.debug?` become `boukensha.enable_debug()` and `boukensha.debug()` at the package level.

**Files:**
- Modify: `week1_baseline/python/06_the_logger/src/boukensha/__init__.py`

**Interfaces:**
- Produces:
  - `boukensha.enable_debug() -> None` — sets the debug flag to `True`
  - `boukensha.debug() -> bool` — returns current debug flag state
  - The flag is a module-level variable `_debug: bool = False`

- [ ] **Step 1: Write the failing test in `tests/test_logger.py`**

Create `week1_baseline/python/06_the_logger/tests/test_logger.py`:

```python
from __future__ import annotations

import boukensha


def test_debug_flag_starts_false():
    # Reset in case another test mutated it
    boukensha._debug = False
    assert boukensha.debug() is False


def test_enable_debug_sets_flag():
    boukensha._debug = False
    boukensha.enable_debug()
    assert boukensha.debug() is True
    boukensha._debug = False  # cleanup
```

- [ ] **Step 2: Run test to verify it fails**

```bash
cd week1_baseline/python/06_the_logger
uv run pytest tests/test_logger.py::test_debug_flag_starts_false -v
```

Expected: FAIL — `AttributeError: module 'boukensha' has no attribute '_debug'`

- [ ] **Step 3: Add the debug flag to `__init__.py`**

Open `src/boukensha/__init__.py`. It currently ends with `__version__ = "0.1.0"`. Replace the entire file with:

```python
"""Boukensha agent loop."""

from __future__ import annotations

from . import backends, tasks
from .agent import Agent
from .client import Client
from .config import Config
from .context import Context
from .errors import ApiError, LoopError, UnknownToolError, UnsupportedModelError
from .logger import Logger
from .message import Message
from .prompt_builder import PromptBuilder
from .registry import Registry
from .tool import Tool

__all__ = [
    "Agent",
    "ApiError",
    "Client",
    "Config",
    "Context",
    "Logger",
    "LoopError",
    "Message",
    "PromptBuilder",
    "Registry",
    "Tool",
    "UnknownToolError",
    "UnsupportedModelError",
    "backends",
    "debug",
    "enable_debug",
    "tasks",
]

__version__ = "0.1.0"

_debug: bool = False


def enable_debug() -> None:
    global _debug
    _debug = True


def debug() -> bool:
    return _debug
```

> Note: `from .logger import Logger` will fail until Task 3 creates `logger.py`. That's expected — the test for the debug flag doesn't import `Logger`, so the tests in Task 2 will pass if `logger.py` exists as a stub. Create a minimal stub now:

```python
# src/boukensha/logger.py  (stub — replaced in Task 3)
class Logger:
    pass
```

- [ ] **Step 4: Run tests**

```bash
cd week1_baseline/python/06_the_logger
uv run pytest tests/test_logger.py -v
```

Expected: PASS for both debug tests.

- [ ] **Step 5: Run all tests to confirm no regressions**

```bash
uv run pytest tests/ -v
```

Expected: all tests pass.

- [ ] **Step 6: Commit**

```bash
git add src/boukensha/__init__.py src/boukensha/logger.py tests/test_logger.py
git commit -m "feat: add module-level debug flag and Logger stub"
```

---

## Task 3: Implement `Logger`

The `Logger` class writes one JSONL file per session under `<config.dir>/sessions/`. Every `write_log` call appends one JSON line with `session_id`, `at`, and phase data.

**Files:**
- Modify: `week1_baseline/python/06_the_logger/src/boukensha/logger.py`
- Modify: `week1_baseline/python/06_the_logger/tests/test_logger.py`

**Interfaces:**
- Consumes:
  - `boukensha.debug() -> bool` (from Task 2)
  - `boukensha.Config` — `config.dir: str`
  - `boukensha.Message` — `.role: str`, `.content: Any`
- Produces:
  - `Logger(*, session_id=None, dir=None, log=None, snapshot={})` — constructor
  - `logger.session_id: str`
  - `logger.path: str`
  - `logger.iteration(*, n: int, max: int) -> None`
  - `logger.limit_reached(*, kind: str, n: int, max: int) -> None`
  - `logger.turn_end(*, reason: str, iterations: int, tokens=None) -> None`
  - `logger.prompt(*, messages: list, tools: dict) -> None`
  - `logger.tool_call(*, name: str, args: dict) -> None`
  - `logger.tool_result(*, name: str, result: Any, ok: bool = True, error=None) -> None`
  - `logger.response(*, text: str, usage=None, stop_reason=None, task=None, backend=None) -> None`
  - `logger.raw(*, data: Any) -> None`
  - `logger.close() -> None`

- [ ] **Step 1: Write the failing tests** (append to `tests/test_logger.py`)

```python
import json
import tempfile
from pathlib import Path

from boukensha.logger import Logger


def _read_lines(path: str) -> list[dict]:
    return [json.loads(line) for line in Path(path).read_text().splitlines() if line.strip()]


def test_logger_creates_file_on_init():
    with tempfile.TemporaryDirectory() as d:
        lg = Logger(dir=d)
        assert Path(lg.path).exists()
        lg.close()


def test_logger_session_start_line_written():
    with tempfile.TemporaryDirectory() as d:
        lg = Logger(dir=d)
        lg.close()
        lines = _read_lines(lg.path)
        assert lines[0]["phase"] == "session_start"
        assert "session_id" in lines[0]
        assert "at" in lines[0]


def test_logger_custom_session_id():
    with tempfile.TemporaryDirectory() as d:
        lg = Logger(dir=d, session_id="my-session")
        lg.close()
        lines = _read_lines(lg.path)
        assert lines[0]["session_id"] == "my-session"


def test_logger_snapshot_merged_into_session_start():
    with tempfile.TemporaryDirectory() as d:
        lg = Logger(dir=d, snapshot={"model": "claude-haiku-4-5"})
        lg.close()
        lines = _read_lines(lg.path)
        assert lines[0]["model"] == "claude-haiku-4-5"


def test_logger_explicit_log_path():
    with tempfile.TemporaryDirectory() as d:
        log_path = str(Path(d) / "custom.jsonl")
        lg = Logger(log=log_path)
        lg.close()
        assert Path(log_path).exists()


def test_logger_iteration():
    with tempfile.TemporaryDirectory() as d:
        lg = Logger(dir=d)
        lg.iteration(n=1, max=25)
        lg.close()
        lines = _read_lines(lg.path)
        iter_line = next(l for l in lines if l["phase"] == "iteration")
        assert iter_line["n"] == 1
        assert iter_line["max"] == 25


def test_logger_limit_reached():
    with tempfile.TemporaryDirectory() as d:
        lg = Logger(dir=d)
        lg.limit_reached(kind="max_iterations", n=25, max=25)
        lg.close()
        lines = _read_lines(lg.path)
        lr = next(l for l in lines if l["phase"] == "limit_reached")
        assert lr["kind"] == "max_iterations"
        assert lr["n"] == 25


def test_logger_turn_end():
    with tempfile.TemporaryDirectory() as d:
        lg = Logger(dir=d)
        lg.turn_end(reason="completed", iterations=3)
        lg.close()
        lines = _read_lines(lg.path)
        te = next(l for l in lines if l["phase"] == "turn_end")
        assert te["reason"] == "completed"
        assert te["iterations"] == 3


def test_logger_prompt():
    from boukensha.message import Message
    with tempfile.TemporaryDirectory() as d:
        lg = Logger(dir=d)
        msgs = [Message(role="user", content="hello")]
        tools = {"read_file": object()}
        lg.prompt(messages=msgs, tools=tools)
        lg.close()
        lines = _read_lines(lg.path)
        p = next(l for l in lines if l["phase"] == "prompt")
        assert p["message_count"] == 1
        assert p["tool_count"] == 1
        assert p["messages"][0]["role"] == "user"
        assert p["tools"] == ["read_file"]


def test_logger_tool_call():
    with tempfile.TemporaryDirectory() as d:
        lg = Logger(dir=d)
        lg.tool_call(name="read_file", args={"path": "f.txt"})
        lg.close()
        lines = _read_lines(lg.path)
        tc = next(l for l in lines if l["phase"] == "tool_call")
        assert tc["name"] == "read_file"
        assert tc["args"] == {"path": "f.txt"}


def test_logger_tool_result_ok():
    with tempfile.TemporaryDirectory() as d:
        lg = Logger(dir=d)
        lg.tool_result(name="read_file", result="contents", ok=True)
        lg.close()
        lines = _read_lines(lg.path)
        tr = next(l for l in lines if l["phase"] == "tool_result")
        assert tr["ok"] is True
        assert tr["result"] == "contents"


def test_logger_tool_result_error():
    with tempfile.TemporaryDirectory() as d:
        lg = Logger(dir=d)
        lg.tool_result(name="read_file", result="ERROR: FileNotFoundError: f.txt", ok=False, error="f.txt")
        lg.close()
        lines = _read_lines(lg.path)
        tr = next(l for l in lines if l["phase"] == "tool_result")
        assert tr["ok"] is False
        assert tr["error"] == "f.txt"


def test_logger_response_basic():
    with tempfile.TemporaryDirectory() as d:
        lg = Logger(dir=d)
        lg.response(text="Done!", usage=None, stop_reason="end_turn")
        lg.close()
        lines = _read_lines(lg.path)
        r = next(l for l in lines if l["phase"] == "response")
        assert r["text"] == "Done!"
        assert r["stop_reason"] == "end_turn"


def test_logger_response_with_anthropic_usage():
    from boukensha.backends.anthropic import Anthropic
    backend = Anthropic(api_key="k", model="claude-haiku-4-5")
    with tempfile.TemporaryDirectory() as d:
        lg = Logger(dir=d)
        lg.response(
            text="hi",
            usage={"input_tokens": 100, "output_tokens": 50},
            stop_reason="end_turn",
            backend=backend,
        )
        lg.close()
        lines = _read_lines(lg.path)
        r = next(l for l in lines if l["phase"] == "response")
        assert r["input_tokens"] == 100
        assert r["output_tokens"] == 50
        assert r["provider"] == "anthropic"
        assert r["model"] == "claude-haiku-4-5"
        assert isinstance(r["cost_usd"], float)


def test_logger_raw_no_op_when_debug_false():
    import boukensha
    boukensha._debug = False
    with tempfile.TemporaryDirectory() as d:
        lg = Logger(dir=d)
        lg.raw(data={"some": "data"})
        lg.close()
        lines = _read_lines(lg.path)
        assert not any(l["phase"] == "raw" for l in lines)


def test_logger_raw_written_when_debug_true():
    import boukensha
    boukensha._debug = False
    boukensha.enable_debug()
    with tempfile.TemporaryDirectory() as d:
        lg = Logger(dir=d)
        lg.raw(data={"some": "data"})
        lg.close()
        lines = _read_lines(lg.path)
        raw_line = next((l for l in lines if l["phase"] == "raw"), None)
        assert raw_line is not None
        assert raw_line["data"] == {"some": "data"}
    boukensha._debug = False  # cleanup


def test_logger_session_id_format():
    import re
    with tempfile.TemporaryDirectory() as d:
        lg = Logger(dir=d)
        lg.close()
        # Format: YYYYMMDDTHHMMSSZ-<8 hex chars>
        assert re.match(r"^\d{8}T\d{6}Z-[0-9a-f]{8}$", lg.session_id)
```

- [ ] **Step 2: Run tests to verify they fail**

```bash
cd week1_baseline/python/06_the_logger
uv run pytest tests/test_logger.py -v
```

Expected: All new logger tests FAIL (stub `Logger` has no methods).

- [ ] **Step 3: Implement `logger.py`**

Replace the stub `src/boukensha/logger.py` with:

```python
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
```

- [ ] **Step 4: Run logger tests**

```bash
cd week1_baseline/python/06_the_logger
uv run pytest tests/test_logger.py -v
```

Expected: all logger tests PASS.

- [ ] **Step 5: Run all tests**

```bash
uv run pytest tests/ -v
```

Expected: all tests PASS.

- [ ] **Step 6: Commit**

```bash
git add src/boukensha/logger.py tests/test_logger.py
git commit -m "feat: implement Logger JSONL session writer"
```

---

## Task 4: Wire `Logger` into `Agent`

The Ruby `Agent` accepts `logger:` and calls it at every lifecycle point. The Python `Agent` currently has inline `print()` calls instead. This task adds `logger:` support while keeping the `print()` calls as-is (the logger is additive, not a replacement for stdout feedback in this step).

**Files:**
- Modify: `week1_baseline/python/06_the_logger/src/boukensha/agent.py`
- Modify: `week1_baseline/python/06_the_logger/tests/test_agent.py`

**Interfaces:**
- Consumes:
  - `Logger.iteration(n, max)`, `Logger.limit_reached(kind, n, max)`, `Logger.turn_end(reason, iterations)`, `Logger.prompt(messages, tools)`, `Logger.tool_call(name, args)`, `Logger.tool_result(name, result, ok, error)`, `Logger.response(text, usage, stop_reason, task, backend)`, `Logger.raw(data)` — all from Task 3
- Produces:
  - `Agent(*, ..., logger: Logger | None = None)` — new optional kwarg
  - When `logger` is `None`, all logger calls are silently skipped (no attribute errors)

- [ ] **Step 1: Write the failing tests** (append to `tests/test_agent.py`)

```python
# -- Logger integration tests ------------------------------------------------

import tempfile
from pathlib import Path
import json as _json

from boukensha.logger import Logger


def _make_agent_with_logger(responses, tmp_dir, max_iterations=25):
    """Build an Agent with a real Logger writing to tmp_dir."""
    from unittest.mock import MagicMock
    from boukensha.agent import Agent
    from boukensha.context import Context
    from boukensha.registry import Registry
    from boukensha.tasks.player import Player

    ctx = Context(task=Player, system="sys")
    registry = Registry(ctx)

    mock_builder = MagicMock()
    mock_builder.parse_response.side_effect = responses
    mock_builder.to_api_payload.return_value = {}
    mock_builder.backend = None

    mock_client = MagicMock()
    mock_client.call.return_value = {}

    ctx.add_message("user", "hello")
    logger = Logger(dir=tmp_dir)
    agent = Agent(
        context=ctx,
        registry=registry,
        builder=mock_builder,
        client=mock_client,
        max_iterations=max_iterations,
        logger=logger,
    )
    return agent, logger


def _read_phases(path: str) -> list[str]:
    return [_json.loads(l)["phase"] for l in Path(path).read_text().splitlines() if l.strip()]


def test_logger_receives_iteration_events():
    responses = [{"stop_reason": "end_turn", "content": [{"type": "text", "text": "Done"}]}]
    with tempfile.TemporaryDirectory() as d:
        agent, logger = _make_agent_with_logger(responses, d)
        agent.run()
        logger.close()
        phases = _read_phases(logger.path)
        assert "session_start" in phases
        assert "iteration" in phases
        assert "prompt" in phases
        assert "response" in phases
        assert "turn_end" in phases


def test_logger_records_tool_call_and_result():
    from unittest.mock import MagicMock
    from boukensha.agent import Agent
    from boukensha.context import Context
    from boukensha.registry import Registry
    from boukensha.tasks.player import Player

    tool_responses = [
        {
            "stop_reason": "tool_use",
            "content": [{"type": "tool_use", "id": "tu_1", "name": "echo", "input": {"msg": "hi"}}],
        },
        {"stop_reason": "end_turn", "content": [{"type": "text", "text": "Done"}]},
    ]

    ctx = Context(task=Player, system="sys")
    registry = Registry(ctx)
    registry.tool("echo", description="echo", parameters={"msg": {"type": "string"}}, block=lambda msg: f"echo:{msg}")

    mock_builder = MagicMock()
    mock_builder.parse_response.side_effect = tool_responses
    mock_builder.to_api_payload.return_value = {}
    mock_builder.backend = None

    mock_client = MagicMock()
    mock_client.call.return_value = {}
    ctx.add_message("user", "hello")

    with tempfile.TemporaryDirectory() as d:
        logger = Logger(dir=d)
        agent = Agent(
            context=ctx,
            registry=registry,
            builder=mock_builder,
            client=mock_client,
            logger=logger,
        )
        agent.run()
        logger.close()
        phases = _read_phases(logger.path)
        assert "tool_call" in phases
        assert "tool_result" in phases


def test_agent_works_without_logger():
    """Passing no logger= must not raise."""
    from unittest.mock import MagicMock
    from boukensha.agent import Agent
    from boukensha.context import Context
    from boukensha.registry import Registry
    from boukensha.tasks.player import Player

    ctx = Context(task=Player, system="sys")
    registry = Registry(ctx)
    mock_builder = MagicMock()
    mock_builder.parse_response.return_value = {"stop_reason": "end_turn", "content": [{"type": "text", "text": "ok"}]}
    mock_builder.to_api_payload.return_value = {}
    mock_builder.backend = None
    mock_client = MagicMock()
    mock_client.call.return_value = {}
    ctx.add_message("user", "hi")

    agent = Agent(context=ctx, registry=registry, builder=mock_builder, client=mock_client)
    result = agent.run()
    assert result == "ok"


def test_logger_limit_reached_event():
    tool_response = {
        "stop_reason": "tool_use",
        "content": [{"type": "tool_use", "id": "tu_1", "name": "noop", "input": {}}],
    }
    wrap_up = {"stop_reason": "end_turn", "content": [{"type": "text", "text": "Wrapping up"}]}

    from unittest.mock import MagicMock
    from boukensha.agent import Agent
    from boukensha.context import Context
    from boukensha.registry import Registry
    from boukensha.tasks.player import Player

    ctx = Context(task=Player, system="sys")
    registry = Registry(ctx)
    registry.tool("noop", description="noop", parameters={}, block=lambda: "ok")

    mock_builder = MagicMock()
    mock_builder.parse_response.side_effect = [tool_response, tool_response, wrap_up]
    mock_builder.to_api_payload.return_value = {}
    mock_builder.backend = None
    mock_client = MagicMock()
    mock_client.call.return_value = {}
    ctx.add_message("user", "go")

    with tempfile.TemporaryDirectory() as d:
        logger = Logger(dir=d)
        agent = Agent(
            context=ctx,
            registry=registry,
            builder=mock_builder,
            client=mock_client,
            max_iterations=2,
            logger=logger,
        )
        agent.run()
        logger.close()
        phases = _read_phases(logger.path)
        assert "limit_reached" in phases
        assert "turn_end" in phases
```

- [ ] **Step 2: Run tests to verify they fail**

```bash
cd week1_baseline/python/06_the_logger
uv run pytest tests/test_agent.py::test_logger_receives_iteration_events -v
```

Expected: FAIL — `Agent.__init__() got an unexpected keyword argument 'logger'`

- [ ] **Step 3: Update `agent.py`**

Replace the entire `src/boukensha/agent.py` with:

```python
"""Boukensha::Agent port: drives the tool-call loop until the model signals
done or the iteration ceiling is reached.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

from .errors import ApiError

if TYPE_CHECKING:
    from .logger import Logger

MAX_ITERATIONS = 25
WRAP_UP_OUTPUT_TOKENS = 400
WRAP_UP_DIRECTIVE = (
    "You have reached your action limit for this turn. Do not call any more tools.\n"
    "Briefly summarize what you accomplished, what is still unfinished, and the\n"
    "single next action you would take."
)


class Agent:
    def __init__(
        self,
        *,
        context: Any,
        registry: Any,
        builder: Any,
        client: Any,
        logger: Logger | None = None,
        task_settings: dict[str, Any] | None = None,
        max_iterations: int | None = None,
        max_output_tokens: int | None = None,
    ) -> None:
        self._context = context
        self._registry = registry
        self._builder = builder
        self._client = client
        self._logger = logger
        self._max_iterations = self._resolve_max_iterations(task_settings, max_iterations)
        self._max_output_tokens = self._resolve_max_output_tokens(task_settings, max_output_tokens)
        self._iteration = 0

    def run(self) -> str:
        while True:
            if self._iteration_limit_reached():
                if self._logger:
                    self._logger.limit_reached(
                        kind="max_iterations", n=self._iteration, max=self._max_iterations
                    )
                return self._wrap_up("max_iterations")

            self._iteration += 1
            if self._logger:
                self._logger.iteration(n=self._iteration, max=self._max_iterations)
                self._logger.prompt(messages=self._context.messages, tools=self._context.tools)
            print(f"[iteration {self._iteration}/{self._max_iterations}]")

            response = self._client.call(**self._call_opts())
            if self._logger:
                self._logger.raw(data=response)
            parsed = self._builder.parse_response(response)

            if parsed["stop_reason"] == "tool_use":
                self._handle_tool_calls(parsed["content"], response)
            else:
                text = self._extract_text(parsed["content"])
                self._log_response(text=text, response=response)
                if self._logger:
                    self._logger.turn_end(reason="completed", iterations=self._iteration)
                return text

    # ---------- private -----------------------------------------------------

    def _resolve_max_iterations(
        self, task_settings: dict[str, Any] | None, explicit: int | None
    ) -> int:
        if explicit is not None:
            return int(explicit)
        if task_settings is not None and hasattr(self._context.task, "max_iterations"):
            return self._context.task.max_iterations(task_settings)
        return MAX_ITERATIONS

    def _resolve_max_output_tokens(
        self, task_settings: dict[str, Any] | None, explicit: int | None
    ) -> int | None:
        if explicit is not None:
            return explicit
        if task_settings is not None and hasattr(self._context.task, "max_output_tokens"):
            return self._context.task.max_output_tokens(task_settings)
        return None

    def _iteration_limit_reached(self) -> bool:
        return self._max_iterations > 0 and self._iteration >= self._max_iterations

    def _call_opts(self) -> dict[str, Any]:
        if self._max_output_tokens is not None:
            return {"max_output_tokens": self._max_output_tokens}
        return {}

    def _wrap_up(self, reason: str) -> str:
        self._context.add_message("user", WRAP_UP_DIRECTIVE)
        try:
            response = self._client.call(tools=[], max_output_tokens=WRAP_UP_OUTPUT_TOKENS)
            text = self._extract_text(self._builder.parse_response(response)["content"])
            result = text.strip() or self._fallback_message(reason)
            self._log_response(text=result, response=response)
            if self._logger:
                self._logger.turn_end(reason=reason, iterations=self._iteration)
            return result
        except ApiError:
            msg = self._fallback_message(reason)
            if self._logger:
                self._logger.turn_end(reason=reason, iterations=self._iteration)
            return msg

    def _fallback_message(self, reason: str) -> str:
        return (
            f"I reached my {self._max_iterations}-action limit for this turn before finishing "
            f"({reason}). Ask me to continue and I'll pick up from here."
        )

    def _extract_text(self, content: list[dict[str, Any]]) -> str:
        return "".join(b["text"] for b in content if b.get("type") == "text")

    def _log_response(self, *, text: str, response: Any) -> None:
        if not self._logger:
            return
        self._logger.response(
            text=text,
            usage=_normalized_usage(response),
            stop_reason=response.get("stop_reason") if isinstance(response, dict) else None,
            task=self._context.task,
            backend=self._builder.backend,
        )

    def _handle_tool_calls(self, content: list[dict[str, Any]], response: Any) -> None:
        reasoning = self._extract_text(content)
        tool_calls = [b for b in content if b.get("type") == "tool_use"]
        display = reasoning.strip() or f"(tool use — {len(tool_calls)} call{'s' if len(tool_calls) != 1 else ''})"
        self._log_response(text=display, response=response)

        self._context.add_message("assistant", content)

        for block in tool_calls:
            name = block["name"]
            args = block["input"]
            use_id = block["id"]

            if self._logger:
                self._logger.tool_call(name=name, args=args)
            print(f"  tool call -> {name}({args})")
            try:
                result = self._registry.dispatch(name, args)
                if self._logger:
                    self._logger.tool_result(name=name, result=result, ok=True)
            except Exception as e:
                result = f"ERROR: {type(e).__name__}: {e}"
                if self._logger:
                    self._logger.tool_result(name=name, result=result, ok=False, error=str(e))
            print(f"  tool result -> {str(result)[:61]}")

            self._context.add_message("tool_result", str(result), tool_use_id=use_id)


def _normalized_usage(response: Any) -> dict[str, Any] | None:
    if not isinstance(response, dict):
        return None
    if "usage" in response:
        return response["usage"]
    if "usageMetadata" in response:
        return response["usageMetadata"]
    usage = {k: response[k] for k in ("prompt_eval_count", "eval_count") if k in response}
    return usage or None
```

- [ ] **Step 4: Run all agent tests**

```bash
cd week1_baseline/python/06_the_logger
uv run pytest tests/test_agent.py -v
```

Expected: all tests PASS, including the new logger integration tests and all original agent tests.

- [ ] **Step 5: Run full test suite**

```bash
uv run pytest tests/ -v
```

Expected: all tests PASS.

- [ ] **Step 6: Commit**

```bash
git add src/boukensha/agent.py tests/test_agent.py
git commit -m "feat: wire Logger into Agent lifecycle"
```

---

## Task 5: Update the example script

Wire the `Logger` into `examples/example.py` and print the session path. Update the banner to say "Step 6: The Logger".

**Files:**
- Modify: `week1_baseline/python/06_the_logger/examples/example.py`

**Interfaces:**
- Consumes: `Logger(dir=None)` → default sessions dir, `.path: str`, `.session_id: str`
- Produces: a runnable example that prints the session file path and writes a full JSONL log

- [ ] **Step 1: Replace `examples/example.py`**

```python
import os
from pathlib import Path

os.environ.setdefault(
    "BOUKENSHA_DIR",
    str((Path(__file__).parent.parent.parent.parent.parent / ".boukensha").resolve()),
)

from boukensha import Agent, Client, Config, Context, Logger, PromptBuilder, Registry
from boukensha.backends import Anthropic, Gemini, Ollama, OllamaCloud, OpenAI
from boukensha.tasks import Player

config = Config()
player_settings = config.tasks("player")
system_prompt = Player.system_prompt(
    player_settings,
    user_prompts_dir=config.user_prompts_dir,
    default_prompts_dir=Config.PROMPTS_DIR,
)

base_dir = Path(__file__).parent.parent.resolve()

ctx = Context(task=Player, system=system_prompt)
registry = Registry(ctx)

provider = Player.provider(player_settings)
model = Player.model(player_settings)

if provider == "anthropic":
    backend = Anthropic(api_key=os.environ["ANTHROPIC_API_KEY"], model=model)
elif provider == "openai":
    backend = OpenAI(api_key=os.environ["OPENAI_API_KEY"], model=model)
elif provider == "gemini":
    backend = Gemini(api_key=os.environ["GEMINI_API_KEY"], model=model)
elif provider == "ollama":
    backend = Ollama(model=model)
elif provider == "ollama_cloud":
    backend = OllamaCloud(api_key=os.environ["OLLAMA_API_KEY"], model=model)
else:
    raise ValueError(f"Unsupported provider for player task: {provider}")

builder = PromptBuilder(ctx, backend)
client = Client(builder)
# Writes structured JSONL events to .boukensha/sessions/<session-id>.jsonl.
# Call boukensha.enable_debug() before this line to include raw API responses.
logger = Logger()
agent = Agent(
    context=ctx,
    registry=registry,
    builder=builder,
    client=client,
    logger=logger,
    task_settings=player_settings,
)

registry.tool(
    "read_file",
    description="Read the contents of a file from disk",
    parameters={"path": {"type": "string", "description": "The file path to read"}},
    block=lambda path: (base_dir / path).read_text(),
)

registry.tool(
    "list_directory",
    description="List the files in a directory",
    parameters={"path": {"type": "string", "description": "The directory path to list"}},
    block=lambda path: ", ".join(
        f for f in os.listdir(base_dir / path) if not f.startswith(".")
    ),
)

ctx.add_message("user", "Read the README.md file and summarise what this MUD player assistant framework can do.")

print("=== BOUKENSHA Step 6: The Logger ===")
print()
print(f"Config: {config}")
print(f"Provider: {provider}")
print(f"Model: {model}")
print(f"Max iterations: {Player.max_iterations(player_settings)}")
print(f"Max output tokens: {Player.max_output_tokens(player_settings)}")
print(f"Session log: {logger.path}")
print()

result = agent.run()

logger.close()

print()
print("=== FINAL RESPONSE ===")
print(result)
print()
print(f"Session log written to: {logger.path}")
```

- [ ] **Step 2: Run all tests to confirm nothing broken**

```bash
cd week1_baseline/python/06_the_logger
uv run pytest tests/ -v
```

Expected: all tests PASS.

- [ ] **Step 3: Commit**

```bash
git add examples/example.py
git commit -m "feat: update example to use Logger for step 6"
```

---

## Self-Review

**Spec coverage check:**

| Ruby feature | Covered by task |
|---|---|
| `Logger` class with all phase methods | Task 3 |
| `session_id` generated as `YYYYMMDDTHHMMSSZ-<hex>` | Task 3 |
| Default path `<dir>/sessions/<session_id>.jsonl` | Task 3 |
| `log:` override for explicit path | Task 3 |
| `dir:` override for session directory | Task 3 |
| `session_id:` override | Task 3 |
| `snapshot:` merged into `session_start` | Task 3 |
| `raw()` guarded by `debug?` | Tasks 2 + 3 |
| `Boukensha.debug!` / `debug?` → `enable_debug()` / `debug()` | Task 2 |
| Agent wired: `iteration`, `limit_reached`, `turn_end`, `prompt`, `tool_call`, `tool_result`, `response`, `raw` | Task 4 |
| `execution_metadata` with provider/model/tokens/cost_usd | Task 3 |
| `_usage_tokens` normalizing all 4 provider key variants | Task 3 |
| Example script with `Logger` and session path output | Task 5 |
| All 05 tests still pass in 06 | Task 1 |

**Placeholder scan:** No TBDs, no "similar to Task N", all code blocks complete.

**Type consistency:**
- `Logger` constructor: `session_id`, `dir`, `log`, `snapshot` — used consistently in tests and example
- `Agent` constructor new kwarg: `logger: Logger | None = None` — matched in all test helpers
- `logger.response(text=, usage=, stop_reason=, task=, backend=)` — matches `_log_response` call site in `agent.py`
- `logger.tool_result(name=, result=, ok=, error=)` — matched in test assertions and agent call
