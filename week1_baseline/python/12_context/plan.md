# Step 12 — Context Management Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Port Ruby's step 12 context-management features to Python: accurate token tracking per API call, context-window usage percentage, colour-coded TUI indicators, auto-compaction at configurable thresholds, and a `/compact` REPL command.

**Architecture:** Step 12 is a self-contained snapshot forked from step 11 (same pattern as every prior step). All source files in `src/boukensha/` and test files in `tests/` are copied verbatim from step 11 as a baseline, then the specific files listed below are modified. The Context class grows token-tracking state, Agent drives it (record usage, compact if needed), Logger gains two new event methods, Repl gains `/compact`, and Tui gets context-aware colour display.

**Tech Stack:** Python ≥ 3.11, uv, pytest, textual ≥ 0.80, pyyaml, python-dotenv

## Global Constraints

- Each step is a self-contained snapshot — do NOT import from step 11 or any sibling directory; copy code wholesale.
- Step 12 directory: `week1_baseline/python/12_context/`
- Package name: `boukensha-context`, version `0.12.0`
- Python package lives under `src/boukensha/` — same layout as step 11.
- All tests in `tests/` — run with `cd week1_baseline/python/12_context && uv run pytest tests/ -v`.
- `uv` manages the virtualenv (`.venv/`). Install with `uv sync`.
- `compaction_threshold` default: `0.85` (85 %).
- `context_window` default: `200_000`.
- `CTX_WARN_PCT = 70`, `CTX_ALERT_PCT = 85` for TUI colour coding.
- Token counts sourced from `response["usage"]["input_tokens"]` / `"output_tokens"]` — same normalisation as existing `_normalized_usage()` in agent.py.

---

### Task 1: Scaffold step 12 from step 11

**Files:**
- Create: all of `week1_baseline/python/12_context/` — copied from step 11
- Modify: `week1_baseline/python/12_context/pyproject.toml`
- Modify: `week1_baseline/python/12_context/examples/example.py`

**Interfaces:**
- Produces: a working copy of step 11 under `12_context/` with tests passing and correct package metadata.

- [x] **Step 1: Copy step 11 tree into step 12**

```bash
cd week1_baseline/python
# Copy step 11 into 12_context — plan.md already exists there, skip it
cp -r 11_tui/. 12_context/
# Remove stale pytest cache and venv so we start clean
rm -rf 12_context/.pytest_cache 12_context/.venv
```

- [x] **Step 2: Update pyproject.toml**

Edit `week1_baseline/python/12_context/pyproject.toml` — change `name` and `version`:

```toml
[project]
name = "boukensha-context"
version = "0.12.0"
description = "Boukensha Context Management (Step 12)"
requires-python = ">=3.11"
dependencies = [
    "pyyaml>=6.0",
    "python-dotenv>=1.0",
    "textual>=0.80",
]

[dependency-groups]
dev = ["pytest>=7.0"]

[tool.uv]
package = true

[build-system]
requires = ["hatchling"]
build-backend = "hatchling.build"

[project.scripts]
boukensha = "boukensha_loader:main"

[tool.hatch.build.targets.wheel]
sources = ["src"]
include = ["src/boukensha/**", "src/boukensha_loader.py"]
```

- [x] **Step 3: Install dependencies and run existing tests**

```bash
cd week1_baseline/python/12_context
uv sync
uv run pytest tests/ -v
```

Expected: all tests from step 11 pass (or the same set that passed in step 11 pass here).

- [x] **Step 4: Commit scaffold**

```bash
git add week1_baseline/python/12_context/
git commit -m "feat(12): scaffold step 12 from step 11 baseline"
```

---

### Task 2: Add token tracking to Context

**Files:**
- Modify: `week1_baseline/python/12_context/src/boukensha/context.py`
- Modify: `week1_baseline/python/12_context/tests/test_context.py`

**Interfaces:**
- Produces:
  - `Context(task, system, working_dir, context_window=200_000, compaction_threshold=0.85)`
  - `context.update_tokens(n: int) -> None`
  - `context.reset_turn_tokens() -> None`
  - `context.add_turn_tokens(input_tokens: int, output_tokens: int) -> None`
  - `context.usage_fraction -> float`  (0.0–1.0)
  - `context.usage_pct -> int`  (0–100)
  - `context.needs_compaction(threshold: float | None = None) -> bool`
  - `context.compact_messages(target_fraction: float = 0.60) -> int`  — returns dropped count
  - `context.clear_messages() -> None`  — also resets `current_tokens` to 0
  - `context.current_tokens: int`
  - `context.turn_tokens: int`
  - `context.context_window: int`
  - `context.compaction_threshold: float`

- [ ] **Step 1: Write failing tests for new Context token methods**

Replace the contents of `tests/test_context.py` with:

```python
from __future__ import annotations

from pathlib import Path

from boukensha.context import Context
from boukensha.registry import Registry
from boukensha.run_dsl import RunDSL
from boukensha.tasks.player import Player


def _make_ctx(**kw) -> Context:
    return Context(task=Player, system="sys", **kw)


# ── existing tests (keep) ────────────────────────────────────────────────────

def test_clear_messages_wipes_history():
    ctx = _make_ctx()
    ctx.add_message("user", "hello")
    ctx.add_message("assistant", "hi")
    ctx.clear_messages()
    assert ctx.messages == []


def test_clear_messages_keeps_tools():
    ctx = _make_ctx()
    registry = Registry(ctx)
    dsl = RunDSL(registry)
    dsl.tool("ping", description="Ping", block=lambda: "pong")
    ctx.add_message("user", "hello")
    ctx.clear_messages()
    assert "ping" in ctx.tools
    assert ctx.messages == []


def test_clear_messages_resets_turn_count():
    ctx = _make_ctx()
    ctx.add_message("user", "one")
    ctx.add_message("user", "two")
    ctx.clear_messages()
    assert ctx.turn_count == 0


def test_context_working_dir_resolves_path(tmp_path):
    ctx = Context(task=Player, system="sys", working_dir=str(tmp_path))
    assert ctx.working_dir == str(tmp_path.resolve())


def test_context_working_dir_none_by_default():
    ctx = Context(task=Player, system="sys")
    assert ctx.working_dir is None


def test_context_working_dir_expands_tilde(monkeypatch, tmp_path):
    monkeypatch.setenv("HOME", str(tmp_path))
    ctx = Context(task=Player, system="sys", working_dir="~")
    assert ctx.working_dir == str(tmp_path.resolve())


# ── new token-tracking tests ─────────────────────────────────────────────────

def test_context_default_context_window():
    ctx = _make_ctx()
    assert ctx.context_window == 200_000


def test_context_custom_context_window():
    ctx = _make_ctx(context_window=128_000)
    assert ctx.context_window == 128_000


def test_context_current_tokens_starts_zero():
    ctx = _make_ctx()
    assert ctx.current_tokens == 0


def test_context_turn_tokens_starts_zero():
    ctx = _make_ctx()
    assert ctx.turn_tokens == 0


def test_context_update_tokens():
    ctx = _make_ctx()
    ctx.update_tokens(5000)
    assert ctx.current_tokens == 5000


def test_context_update_tokens_accepts_string():
    ctx = _make_ctx()
    ctx.update_tokens("3000")
    assert ctx.current_tokens == 3000


def test_context_reset_turn_tokens():
    ctx = _make_ctx()
    ctx.add_turn_tokens(100, 50)
    ctx.reset_turn_tokens()
    assert ctx.turn_tokens == 0


def test_context_add_turn_tokens_accumulates():
    ctx = _make_ctx()
    ctx.add_turn_tokens(100, 50)
    ctx.add_turn_tokens(200, 75)
    assert ctx.turn_tokens == 425


def test_context_usage_fraction_zero_when_no_tokens():
    ctx = _make_ctx()
    assert ctx.usage_fraction == 0.0


def test_context_usage_fraction():
    ctx = _make_ctx(context_window=200_000)
    ctx.update_tokens(100_000)
    assert ctx.usage_fraction == 0.5


def test_context_usage_pct():
    ctx = _make_ctx(context_window=200_000)
    ctx.update_tokens(170_000)
    assert ctx.usage_pct == 85


def test_context_usage_fraction_zero_when_context_window_zero():
    ctx = _make_ctx(context_window=0)
    assert ctx.usage_fraction == 0.0


def test_context_needs_compaction_false_below_threshold():
    ctx = _make_ctx(context_window=200_000)
    ctx.update_tokens(100_000)  # 50 %
    assert ctx.needs_compaction() is False


def test_context_needs_compaction_true_at_threshold():
    ctx = _make_ctx(context_window=200_000, compaction_threshold=0.85)
    ctx.update_tokens(170_000)  # exactly 85 %
    assert ctx.needs_compaction() is True


def test_context_needs_compaction_custom_threshold():
    ctx = _make_ctx(context_window=200_000)
    ctx.update_tokens(140_000)  # 70 %
    assert ctx.needs_compaction(threshold=0.70) is True
    assert ctx.needs_compaction(threshold=0.71) is False


def test_context_compact_messages_drops_oldest_40_pct():
    ctx = _make_ctx()
    for i in range(10):
        ctx.add_message("user", f"msg {i}")
    dropped = ctx.compact_messages()
    # ceil(10 * 0.40) = 4 dropped
    assert dropped == 4
    assert len(ctx.messages) == 6


def test_context_compact_messages_keeps_at_least_2():
    ctx = _make_ctx()
    ctx.add_message("user", "a")
    ctx.add_message("user", "b")
    ctx.add_message("user", "c")
    # ceil(3 * 0.40) = 2, but that would leave only 1 — capped to keep 2
    dropped = ctx.compact_messages()
    assert len(ctx.messages) >= 2


def test_context_compact_messages_resets_current_tokens():
    ctx = _make_ctx()
    ctx.update_tokens(170_000)
    for i in range(5):
        ctx.add_message("user", f"msg {i}")
    ctx.compact_messages()
    assert ctx.current_tokens == 0


def test_context_compact_messages_returns_zero_for_empty():
    ctx = _make_ctx()
    dropped = ctx.compact_messages()
    assert dropped == 0


def test_context_clear_messages_resets_current_tokens():
    ctx = _make_ctx()
    ctx.update_tokens(5000)
    ctx.add_message("user", "hi")
    ctx.clear_messages()
    assert ctx.current_tokens == 0
    assert ctx.messages == []
```

- [ ] **Step 2: Run tests to verify they fail**

```bash
cd week1_baseline/python/12_context
uv run pytest tests/test_context.py -v
```

Expected: failures on all new token-tracking tests (`AttributeError: 'Context' object has no attribute 'context_window'`).

- [ ] **Step 3: Implement token tracking in Context**

Replace `week1_baseline/python/12_context/src/boukensha/context.py` with:

```python
"""Boukensha::Context port: holds everything needed to make an API call."""

from __future__ import annotations

import math
from pathlib import Path
from typing import Any

from .message import Message
from .tasks.base import Base
from .tool import Tool


class Context:
    def __init__(
        self,
        task: type[Base],
        system: str | None = None,
        working_dir: str | None = None,
        context_window: int = 200_000,
        compaction_threshold: float = 0.85,
    ) -> None:
        self.task = task
        self.system = system
        self.working_dir = str(Path(working_dir).expanduser().resolve()) if working_dir else None
        self.context_window = context_window
        self.compaction_threshold = compaction_threshold
        self.messages: list[Message] = []
        self.tools: dict[str, Tool] = {}
        self.current_tokens: int = 0
        self.turn_tokens: int = 0

    def register_tool(self, tool: Tool) -> None:
        self.tools[tool.name] = tool

    def add_message(self, role: str, content: Any, tool_use_id: str | None = None) -> None:
        self.messages.append(Message(role, content, tool_use_id))

    def update_tokens(self, n: int | str) -> None:
        self.current_tokens = int(n)

    def reset_turn_tokens(self) -> None:
        self.turn_tokens = 0

    def add_turn_tokens(self, input_tokens: int | str, output_tokens: int | str) -> None:
        self.turn_tokens += int(input_tokens) + int(output_tokens)

    @property
    def usage_fraction(self) -> float:
        if self.context_window <= 0:
            return 0.0
        return self.current_tokens / self.context_window

    @property
    def usage_pct(self) -> int:
        return round(self.usage_fraction * 100)

    def needs_compaction(self, threshold: float | None = None) -> bool:
        t = threshold if threshold is not None else self.compaction_threshold
        return self.usage_fraction >= t

    def compact_messages(self, target_fraction: float = 0.60) -> int:
        if not self.messages:
            return 0
        drop_count = math.ceil(len(self.messages) * 0.40)
        drop_count = min(drop_count, len(self.messages) - 2)
        drop_count = max(drop_count, 0)
        self.messages = self.messages[drop_count:]
        self.current_tokens = 0
        return drop_count

    def clear_messages(self) -> None:
        self.messages = []
        self.current_tokens = 0

    @property
    def tool_count(self) -> int:
        return len(self.tools)

    @property
    def turn_count(self) -> int:
        return len(self.messages)

    def __str__(self) -> str:
        task_name = self.task.task_name() if self.task is not None else None
        return (
            f"#<Context task={task_name} turns={self.turn_count} "
            f"tools={self.tool_count} window={self.context_window} "
            f"current={self.current_tokens}>"
        )
```

- [ ] **Step 4: Run tests to verify they pass**

```bash
cd week1_baseline/python/12_context
uv run pytest tests/test_context.py -v
```

Expected: all tests PASS.

- [ ] **Step 5: Commit**

```bash
git add week1_baseline/python/12_context/src/boukensha/context.py \
        week1_baseline/python/12_context/tests/test_context.py
git commit -m "feat(12): add token tracking and compaction to Context"
```

---

### Task 3: Add compaction and reasoning events to Logger

**Files:**
- Modify: `week1_baseline/python/12_context/src/boukensha/logger.py`
- Modify: `week1_baseline/python/12_context/tests/test_logger.py`

**Interfaces:**
- Consumes: `Context.context_window: int`
- Produces:
  - `logger.compaction(before: int, dropped: int, context_window: int) -> None`
  - `logger.reasoning(text: str, redacted: bool = False) -> None`
  - `logger.prompt(messages, tools, context_window: int)` — adds `context_window` to the event

- [ ] **Step 1: Write failing tests for new Logger methods**

Add these tests to the bottom of `tests/test_logger.py`:

```python
def test_logger_compaction_event():
    with tempfile.TemporaryDirectory() as d:
        lg = Logger(dir=d)
        lg.compaction(before=170_000, dropped=4, context_window=200_000)
        lg.close()
        lines = _read_lines(lg.path)
        evt = next(l for l in lines if l["phase"] == "compaction")
        assert evt["before"] == 170_000
        assert evt["dropped"] == 4
        assert evt["context_window"] == 200_000


def test_logger_reasoning_event():
    with tempfile.TemporaryDirectory() as d:
        lg = Logger(dir=d)
        lg.reasoning(text="I should look at the inventory.", redacted=False)
        lg.close()
        lines = _read_lines(lg.path)
        evt = next(l for l in lines if l["phase"] == "reasoning")
        assert evt["text"] == "I should look at the inventory."
        assert evt["redacted"] is False


def test_logger_reasoning_event_redacted():
    with tempfile.TemporaryDirectory() as d:
        lg = Logger(dir=d)
        lg.reasoning(text="", redacted=True)
        lg.close()
        lines = _read_lines(lg.path)
        evt = next(l for l in lines if l["phase"] == "reasoning")
        assert evt["redacted"] is True


def test_logger_prompt_includes_context_window():
    from boukensha.message import Message
    with tempfile.TemporaryDirectory() as d:
        lg = Logger(dir=d)
        msgs = [Message(role="user", content="hello")]
        tools = {"read_file": object()}
        lg.prompt(messages=msgs, tools=tools, context_window=200_000)
        lg.close()
        lines = _read_lines(lg.path)
        p = next(l for l in lines if l["phase"] == "prompt")
        assert p["context_window"] == 200_000
```

- [ ] **Step 2: Run tests to verify they fail**

```bash
cd week1_baseline/python/12_context
uv run pytest tests/test_logger.py::test_logger_compaction_event \
              tests/test_logger.py::test_logger_reasoning_event \
              tests/test_logger.py::test_logger_reasoning_event_redacted \
              tests/test_logger.py::test_logger_prompt_includes_context_window -v
```

Expected: FAIL with `TypeError` (unexpected keyword argument) or `StopIteration` (phase not found).

- [ ] **Step 3: Add compaction, reasoning, and updated prompt to Logger**

In `week1_baseline/python/12_context/src/boukensha/logger.py`:

1. Update the `prompt` method signature to accept `context_window`:

```python
def prompt(self, *, messages: list[Any], tools: dict[str, Any], context_window: int = 0) -> None:
    self._write_log({
        "phase": "prompt",
        "message_count": len(messages),
        "messages": [{"role": m.role, "content": m.content} for m in messages],
        "tool_count": len(tools),
        "tools": list(tools.keys()),
        "context_window": context_window,
    })
```

2. Add `compaction` method after `prompt`:

```python
def compaction(self, *, before: int, dropped: int, context_window: int) -> None:
    self._write_log({"phase": "compaction", "before": before, "dropped": dropped, "context_window": context_window})
```

3. Add `reasoning` method after `compaction`:

```python
def reasoning(self, *, text: str, redacted: bool = False) -> None:
    self._write_log({"phase": "reasoning", "text": str(text), "redacted": redacted})
```

- [ ] **Step 4: Run tests to verify they pass**

```bash
cd week1_baseline/python/12_context
uv run pytest tests/test_logger.py -v
```

Expected: all PASS.

- [ ] **Step 5: Commit**

```bash
git add week1_baseline/python/12_context/src/boukensha/logger.py \
        week1_baseline/python/12_context/tests/test_logger.py
git commit -m "feat(12): add compaction and reasoning events to Logger"
```

---

### Task 4: Update Agent with token tracking, compaction, and reasoning logging

**Files:**
- Modify: `week1_baseline/python/12_context/src/boukensha/agent.py`
- Modify: `week1_baseline/python/12_context/tests/test_agent.py`

**Interfaces:**
- Consumes:
  - `Context.reset_turn_tokens() -> None`
  - `Context.add_turn_tokens(input, output) -> None`
  - `Context.update_tokens(n) -> None`
  - `Context.needs_compaction() -> bool`
  - `Context.compact_messages() -> int`
  - `Context.current_tokens: int`
  - `Context.turn_tokens: int`
  - `Context.context_window: int`
  - `Logger.compaction(before, dropped, context_window) -> None`
  - `Logger.reasoning(text, redacted) -> None`
  - `Logger.prompt(messages, tools, context_window) -> None`
- Produces:
  - `Agent(..., max_turn_tokens: int | None = None)` — new constructor param; 0 or None = disabled
  - `agent.run() -> str` — now calls `context.reset_turn_tokens()` and `compact_if_needed()` before the loop, records usage after every API call, checks token ceiling, logs reasoning blocks
  - `turn_end` logger events now include `tokens=context.turn_tokens`

- [ ] **Step 1: Write failing tests for Agent token/compaction behavior**

Add the following tests to `tests/test_agent.py` (append to the bottom of the file):

```python
# ── Step 12: token tracking and compaction tests ─────────────────────────────

from boukensha.context import Context
from boukensha.registry import Registry
from boukensha.tasks.player import Player


def _make_agent_12(responses, max_iterations=25, max_turn_tokens=None, context_window=200_000):
    """Build Agent with token-tracking context and mock builder/client."""
    from unittest.mock import MagicMock
    from boukensha.agent import Agent

    ctx = Context(task=Player, system="sys", context_window=context_window)
    registry = Registry(ctx)

    mock_builder = MagicMock()
    mock_builder.parse_response.side_effect = responses
    mock_builder.to_api_payload.return_value = {}
    mock_builder.backend = None

    mock_client = MagicMock()
    # Each call returns a response dict with usage
    mock_client.call.return_value = {
        "usage": {"input_tokens": 1000, "output_tokens": 100}
    }
    # Override for each response when usage varies
    mock_builder.parse_response.side_effect = responses

    ctx.add_message("user", "hello")
    agent = Agent(
        context=ctx,
        registry=registry,
        builder=mock_builder,
        client=mock_client,
        max_iterations=max_iterations,
        max_turn_tokens=max_turn_tokens,
    )
    return agent, ctx, mock_client, mock_builder


def test_agent_records_usage_in_context():
    responses = [{"stop_reason": "end_turn", "content": [{"type": "text", "text": "Done"}]}]
    agent, ctx, mock_client, _ = _make_agent_12(responses)
    mock_client.call.return_value = {"usage": {"input_tokens": 5000, "output_tokens": 200}}
    agent.run()
    # current_tokens updated from input_tokens of last API call
    assert ctx.current_tokens == 5000


def test_agent_resets_turn_tokens_at_start():
    responses = [{"stop_reason": "end_turn", "content": [{"type": "text", "text": "Done"}]}]
    agent, ctx, mock_client, _ = _make_agent_12(responses)
    # Pre-load stale turn_tokens
    ctx.add_turn_tokens(99_999, 0)
    mock_client.call.return_value = {"usage": {"input_tokens": 100, "output_tokens": 50}}
    agent.run()
    # After run, turn_tokens = 100+50 = 150 (stale value was reset)
    assert ctx.turn_tokens == 150


def test_agent_stops_at_max_turn_tokens():
    """Agent should trigger wrap-up when turn tokens exceed max_turn_tokens."""
    from unittest.mock import MagicMock
    from boukensha.agent import Agent

    ctx = Context(task=Player, system="sys", context_window=200_000)
    registry = Registry(ctx)
    registry.tool("noop", description="noop", parameters={}, block=lambda: "ok")

    tool_response = {
        "stop_reason": "tool_use",
        "content": [{"type": "tool_use", "id": "tu_1", "name": "noop", "input": {}}],
    }
    wrap_up_response = {"stop_reason": "end_turn", "content": [{"type": "text", "text": "Token limit hit"}]}

    mock_builder = MagicMock()
    mock_builder.parse_response.side_effect = [tool_response, wrap_up_response]
    mock_builder.to_api_payload.return_value = {}
    mock_builder.backend = None

    mock_client = MagicMock()
    # Each call consumes 600 tokens; max_turn_tokens=500 so first call already exceeds it
    mock_client.call.return_value = {"usage": {"input_tokens": 400, "output_tokens": 200}}

    ctx.add_message("user", "go")
    agent = Agent(
        context=ctx,
        registry=registry,
        builder=mock_builder,
        client=mock_client,
        max_iterations=25,
        max_turn_tokens=500,
    )
    result = agent.run()
    assert result == "Token limit hit"


def test_agent_compact_if_needed_runs_before_loop():
    """When context is at threshold, compact_messages is called before the first iteration."""
    import tempfile
    from unittest.mock import MagicMock
    from boukensha.agent import Agent
    from boukensha.logger import Logger

    ctx = Context(task=Player, system="sys", context_window=200_000)
    # Fill context to 90% — above 85% threshold
    ctx.update_tokens(180_000)
    for i in range(10):
        ctx.add_message("user", f"msg {i}")

    registry = Registry(ctx)
    mock_builder = MagicMock()
    mock_builder.parse_response.return_value = {
        "stop_reason": "end_turn",
        "content": [{"type": "text", "text": "ok"}],
    }
    mock_builder.to_api_payload.return_value = {}
    mock_builder.backend = None
    mock_client = MagicMock()
    mock_client.call.return_value = {"usage": {"input_tokens": 0, "output_tokens": 0}}

    msg_count_before = len(ctx.messages)

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
        import json
        from pathlib import Path
        lines = [json.loads(l) for l in Path(logger.path).read_text().splitlines() if l.strip()]
        phases = [l["phase"] for l in lines]
        assert "compaction" in phases
    # Messages were reduced
    assert len(ctx.messages) < msg_count_before


def test_agent_reasoning_blocks_logged():
    """Reasoning blocks in the response content are forwarded to logger.reasoning()."""
    import tempfile
    from unittest.mock import MagicMock, call
    from boukensha.agent import Agent
    from boukensha.logger import Logger

    ctx = Context(task=Player, system="sys")
    registry = Registry(ctx)

    reasoning_block = {"type": "reasoning", "text": "Let me think about this.", "redacted": False}
    text_block = {"type": "text", "text": "Done"}

    mock_builder = MagicMock()
    mock_builder.parse_response.return_value = {
        "stop_reason": "end_turn",
        "content": [reasoning_block, text_block],
    }
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
        import json
        from pathlib import Path
        lines = [json.loads(l) for l in Path(logger.path).read_text().splitlines() if l.strip()]
        reasoning_events = [l for l in lines if l["phase"] == "reasoning"]
        assert len(reasoning_events) == 1
        assert reasoning_events[0]["text"] == "Let me think about this."
        assert reasoning_events[0]["redacted"] is False
```

- [ ] **Step 2: Run tests to verify they fail**

```bash
cd week1_baseline/python/12_context
uv run pytest tests/test_agent.py::test_agent_records_usage_in_context \
              tests/test_agent.py::test_agent_resets_turn_tokens_at_start \
              tests/test_agent.py::test_agent_stops_at_max_turn_tokens \
              tests/test_agent.py::test_agent_compact_if_needed_runs_before_loop \
              tests/test_agent.py::test_agent_reasoning_blocks_logged -v
```

Expected: FAIL (attribute errors, assertion errors, TypeError on prompt() call).

- [ ] **Step 3: Rewrite Agent with full token tracking, compaction, and reasoning**

Replace `week1_baseline/python/12_context/src/boukensha/agent.py` with:

```python
"""Boukensha::Agent port: drives the tool-call loop until the model signals
done or an iteration/token ceiling is reached.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

import boukensha

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
        max_turn_tokens: int | None = None,
        max_output_tokens: int | None = None,
    ) -> None:
        self._context = context
        self._registry = registry
        self._builder = builder
        self._client = client
        if logger is None:
            from .logger import Logger as _Logger
            logger = _Logger()
        self._logger = logger
        self._max_iterations = self._resolve_max_iterations(task_settings, max_iterations)
        self._max_turn_tokens = int(max_turn_tokens or 0)
        self._max_output_tokens = self._resolve_max_output_tokens(task_settings, max_output_tokens)
        self._iteration = 0

    def run(self) -> str:
        self._context.reset_turn_tokens()
        self._compact_if_needed()

        while True:
            if self._iteration_limit_reached():
                if self._logger:
                    self._logger.limit_reached(
                        kind="max_iterations", n=self._iteration, max=self._max_iterations
                    )
                return self._wrap_up("max_iterations")

            if self._token_limit_reached():
                if self._logger:
                    self._logger.limit_reached(
                        kind="max_tokens",
                        n=self._context.turn_tokens,
                        max=self._max_turn_tokens,
                    )
                return self._wrap_up("max_tokens")

            self._iteration += 1
            if self._logger:
                self._logger.iteration(n=self._iteration, max=self._max_iterations)
                self._logger.prompt(
                    messages=self._context.messages,
                    tools=self._context.tools,
                    context_window=self._context.context_window,
                )
            if not boukensha.is_quiet():
                print(f"[iteration {self._iteration}/{self._max_iterations}]")

            response = self._client.call(**self._call_opts())
            if self._logger:
                self._logger.raw(data=response)
            parsed = self._builder.parse_response(response)
            self._record_usage(response)
            self._log_reasoning(parsed["content"])

            if parsed["stop_reason"] == "tool_use":
                self._handle_tool_calls(parsed["content"], response)
            else:
                text = self._extract_text(parsed["content"])
                self._log_response(text=text, response=response)
                if self._logger:
                    self._logger.turn_end(
                        reason="completed",
                        iterations=self._iteration,
                        tokens=self._context.turn_tokens,
                    )
                self._context.add_message("assistant", text)
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

    def _token_limit_reached(self) -> bool:
        return self._max_turn_tokens > 0 and self._context.turn_tokens >= self._max_turn_tokens

    def _call_opts(self) -> dict[str, Any]:
        if self._max_output_tokens is not None:
            return {"max_output_tokens": self._max_output_tokens}
        return {}

    def _record_usage(self, response: Any) -> None:
        usage = response.get("usage", {}) if isinstance(response, dict) else {}
        input_tok = int(usage.get("input_tokens", 0))
        output_tok = int(usage.get("output_tokens", 0))
        self._context.add_turn_tokens(input_tok, output_tok)
        self._context.update_tokens(input_tok)

    def _compact_if_needed(self) -> None:
        if not self._context.needs_compaction():
            return
        before = self._context.current_tokens
        dropped = self._context.compact_messages()
        if self._logger:
            self._logger.compaction(
                before=before,
                dropped=dropped,
                context_window=self._context.context_window,
            )

    def _wrap_up(self, reason: str) -> str:
        self._context.add_message("user", WRAP_UP_DIRECTIVE)
        try:
            response = self._client.call(tools=[], max_output_tokens=WRAP_UP_OUTPUT_TOKENS)
            parsed = self._builder.parse_response(response)
            text = self._extract_text(parsed["content"])
            result = text.strip() or self._fallback_message(reason)
            self._record_usage(response)
            self._log_response(text=result, response=response)
            if self._logger:
                self._logger.turn_end(
                    reason=reason,
                    iterations=self._iteration,
                    tokens=self._context.turn_tokens,
                )
            self._context.add_message("assistant", result)
            return result
        except ApiError:
            msg = self._fallback_message(reason)
            if self._logger:
                self._logger.turn_end(
                    reason=reason,
                    iterations=self._iteration,
                    tokens=self._context.turn_tokens,
                )
            self._context.add_message("assistant", msg)
            return msg

    def _fallback_message(self, reason: str) -> str:
        return (
            f"I reached my {self._max_iterations}-action limit for this turn before finishing "
            f"({reason}). Ask me to continue and I'll pick up from here."
        )

    def _extract_text(self, content: list[dict[str, Any]]) -> str:
        return "".join(b["text"] for b in content if b.get("type") == "text")

    def _log_reasoning(self, content: list[dict[str, Any]]) -> None:
        if not self._logger:
            return
        for block in content:
            if block.get("type") != "reasoning":
                continue
            redacted = block.get("redacted") is True
            text = str(block.get("text", ""))
            if not text.strip() and not redacted:
                continue
            self._logger.reasoning(text=text, redacted=redacted)

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
            if not boukensha.is_quiet():
                print(f"  tool call -> {name}({args})")
            try:
                result = self._registry.dispatch(name, args)
                if self._logger:
                    self._logger.tool_result(name=name, result=result, ok=True)
            except Exception as e:
                result = f"ERROR: {type(e).__name__}: {e}"
                if self._logger:
                    self._logger.tool_result(name=name, result=result, ok=False, error=str(e))
            if not boukensha.is_quiet():
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

- [ ] **Step 4: Run all agent and logger tests**

```bash
cd week1_baseline/python/12_context
uv run pytest tests/test_agent.py tests/test_logger.py -v
```

Expected: all PASS.

- [ ] **Step 5: Commit**

```bash
git add week1_baseline/python/12_context/src/boukensha/agent.py \
        week1_baseline/python/12_context/tests/test_agent.py
git commit -m "feat(12): add token tracking, compaction, and reasoning logging to Agent"
```

---

### Task 5: Add `/compact` command to Repl

**Files:**
- Modify: `week1_baseline/python/12_context/src/boukensha/repl.py`
- Modify: `week1_baseline/python/12_context/tests/test_repl.py`

**Interfaces:**
- Consumes:
  - `Context.compact_messages() -> int`
  - `Agent(max_turn_tokens=...)` — new kwarg forwarded from Repl
- Produces:
  - `Repl(..., max_turn_tokens: int | None = None)` — new constructor param
  - `handle_command("/compact") -> "command"` — drops oldest 40 % of messages, prints dropped count
  - `/compact` in `HELP` text and banner

- [ ] **Step 1: Write failing tests for /compact**

Add the following to `tests/test_repl.py` (append to bottom):

```python
# ── Step 12: /compact command ────────────────────────────────────────────────

def test_repl_compact_command_drops_messages(capsys):
    repl, ctx, logger = _make_repl()
    # Pre-load 10 messages
    for i in range(10):
        ctx.add_message("user", f"msg {i}")
    count_before = len(ctx.messages)
    try:
        result = repl.handle_command("/compact")
    finally:
        logger.close()
    assert result == "command"
    assert len(ctx.messages) < count_before


def test_repl_compact_command_prints_dropped_count(capsys):
    repl, ctx, logger = _make_repl()
    for i in range(10):
        ctx.add_message("user", f"msg {i}")
    try:
        repl.handle_command("/compact")
    finally:
        logger.close()
    captured = capsys.readouterr()
    assert "compacted" in captured.out
    assert "dropped" in captured.out


def test_repl_compact_in_help_text(capsys):
    repl, _, logger = _make_repl()
    try:
        _run_with_input(repl, ["/help", "/exit"])
    finally:
        logger.close()
    captured = capsys.readouterr()
    assert "/compact" in captured.out


def test_repl_compact_via_start(capsys):
    repl, ctx, logger = _make_repl()
    for i in range(6):
        ctx.add_message("user", f"msg {i}")
    try:
        _run_with_input(repl, ["/compact", "/exit"])
    finally:
        logger.close()
    captured = capsys.readouterr()
    assert "compacted" in captured.out
```

- [ ] **Step 2: Run tests to verify they fail**

```bash
cd week1_baseline/python/12_context
uv run pytest tests/test_repl.py::test_repl_compact_command_drops_messages \
              tests/test_repl.py::test_repl_compact_command_prints_dropped_count \
              tests/test_repl.py::test_repl_compact_in_help_text \
              tests/test_repl.py::test_repl_compact_via_start -v
```

Expected: FAIL.

- [ ] **Step 3: Update Repl with /compact support**

Replace `week1_baseline/python/12_context/src/boukensha/repl.py` with:

```python
"""Boukensha::Repl port: interactive session loop."""

from __future__ import annotations

import sys
from collections.abc import Callable
from typing import TYPE_CHECKING, Any

import boukensha
from .agent import Agent
from .errors import ApiError

if TYPE_CHECKING:
    from .context import Context
    from .logger import Logger
    from .registry import Registry

PROMPT = "boukensha> "

HELP = """\
Commands:
  /quiet   suppress logging output
  /loud    re-enable logging output
  /clear   wipe conversation history (tools stay)
  /compact drop oldest 40% of messages to free context
  /exit    leave the REPL
  /help    show this message"""


class Repl:
    def __init__(
        self,
        *,
        context: Context,
        registry: Registry,
        builder: Any,
        client: Any,
        logger: Logger | None,
        task_settings: dict[str, Any] | None,
        max_iterations: int | None,
        max_turn_tokens: int | None,
        max_output_tokens: int | None,
        config_dir: str | None,
        provider: str | None,
        model: str | None,
        version: str | None,
        api_key: str | None,
    ) -> None:
        self._context = context
        self._registry = registry
        self._builder = builder
        self._client = client
        self._logger = logger
        self._task_settings = task_settings
        self._max_iterations = max_iterations
        self._max_turn_tokens = max_turn_tokens
        self._max_output_tokens = max_output_tokens
        self._config_dir = config_dir
        self._provider = provider
        self._model = model
        self._version = version
        self._api_key = api_key
        self._turn = 0
        self._output_cb: Callable[[str], None] | None = None

    # ── public properties ──────────────────────────────────────────────────

    @property
    def banner(self) -> str:
        return self._banner()

    @property
    def model(self) -> str | None:
        return self._model

    @property
    def version(self) -> str | None:
        return self._version

    @property
    def context(self) -> Context:
        return self._context

    @property
    def logger(self) -> Logger | None:
        return self._logger

    # ── composability API (used by Tui) ───────────────────────────────────

    def on_output(self, callback: Callable[[str], None]) -> None:
        """Route all output through *callback* instead of print()."""
        self._output_cb = callback

    def handle_command(self, text: str) -> str | None:
        """Process a slash command.

        Returns:
            "quit"    — caller should exit
            "command" — handled, no agent turn needed
            None      — not a slash command
        """
        if text in ("/exit", "/quit"):
            self._output("Goodbye.")
            return "quit"
        if text == "/help":
            self._output(HELP)
            return "command"
        if text == "/quiet":
            boukensha.enable_quiet()
            self._output("(logging suppressed — type /loud to re-enable)")
            return "command"
        if text == "/loud":
            boukensha.disable_quiet()
            self._output("(logging enabled)")
            return "command"
        if text == "/clear":
            self._context.clear_messages()
            self._turn = 0
            self._output("(conversation history cleared)")
            return "command"
        if text == "/compact":
            dropped = self._context.compact_messages()
            self._output(f"(compacted context — {dropped} messages dropped)")
            return "command"
        return None

    def run_turn(self, user_input: str) -> None:
        """Run one agent turn; output goes through on_output callback (or print)."""
        self._turn += 1
        if self._logger:
            self._logger.turn(n=self._turn)

        self._context.add_message("user", user_input)

        agent = Agent(
            context=self._context,
            registry=self._registry,
            builder=self._builder,
            client=self._client,
            logger=self._logger,
            task_settings=self._task_settings,
            max_iterations=self._max_iterations,
            max_turn_tokens=self._max_turn_tokens,
            max_output_tokens=self._max_output_tokens,
        )
        try:
            result = agent.run()
            self._output("")
            self._output(result)
        except ApiError as e:
            self._output(f"\n[error] API call failed: {e}")

    # ── plain REPL entry point ─────────────────────────────────────────────

    def start(self) -> None:
        self._output(self._banner())

        while True:
            if not self._output_cb:
                print(PROMPT, end="", flush=True)
            line = sys.stdin.readline()
            if not line:
                break
            text = line.rstrip("\n").strip()
            if not text:
                continue

            result = self.handle_command(text)
            if result == "quit":
                break
            if result == "command":
                continue

            self.run_turn(text)

    # ── private ────────────────────────────────────────────────────────────

    def _output(self, text: str) -> None:
        if self._output_cb:
            self._output_cb(text)
        else:
            print(text)

    def _banner(self) -> str:
        ver = self._version or "?.?.?"
        key_status = (
            "API key set"
            if self._api_key and self._api_key.strip()
            else "API key not set"
        )
        provider_line = f"{self._provider or 'default'} ({self._model or 'default'})  {key_status}"
        config_line = self._config_dir or "(default)"

        pad = max(0, 9 - len(ver))
        return (
            f"\n"
            f"╔══════════════════════════════════════╗\n"
            f"║  BOUKENSHA MUD Assistant (v{ver}){' ' * pad}║\n"
            f"╚══════════════════════════════════════╝\n"
            f"  config:    {config_line}\n"
            f"  provider:  {provider_line}\n"
            f"\n"
            f"  /quiet or /loud   toggle logging\n"
            f"  /clear           reset conversation history\n"
            f"  /compact         free context (drop oldest messages)\n"
            f"  /exit or /quit    leave the REPL\n"
        )
```

- [ ] **Step 4: Update `_make_repl` helper in test_repl.py to add `max_turn_tokens`**

Find the `defaults = dict(...)` block in `tests/test_repl.py::_make_repl` and add `max_turn_tokens=None` to it:

```python
    defaults = dict(
        context=ctx,
        registry=registry,
        builder=mock_builder,
        client=mock_client,
        logger=_logger,
        task_settings={},
        max_iterations=25,
        max_turn_tokens=None,
        max_output_tokens=None,
        config_dir=None,
        provider="anthropic",
        model="claude-haiku-4-5",
        version="0.1.0",
        api_key="test-key",
    )
```

- [ ] **Step 5: Run all repl tests**

```bash
cd week1_baseline/python/12_context
uv run pytest tests/test_repl.py -v
```

Expected: all PASS.

- [ ] **Step 6: Commit**

```bash
git add week1_baseline/python/12_context/src/boukensha/repl.py \
        week1_baseline/python/12_context/tests/test_repl.py
git commit -m "feat(12): add /compact command and max_turn_tokens to Repl"
```

---

### Task 6: Update TUI for context-aware display and compaction events

**Files:**
- Modify: `week1_baseline/python/12_context/src/boukensha/tui.py`

**Interfaces:**
- Consumes:
  - `Context.current_tokens: int`
  - `Context.context_window: int`
  - `Context.usage_pct: int`
  - Logger `compaction` event: `{"phase": "compaction", "dropped": int}`
- Produces:
  - Idle progress line: `[ready]   ctx {used}/{max} ({pct}%)   {turns} turns` (colour-coded)
  - Status bar: `ctx {used}/{max} ({pct}%)[⚠ if ≥85%]`
  - `compaction` event appended to RichLog as `[context compacted — N messages dropped to free space]`
  - CSS classes `ctx-warn` (≥70 %) and `ctx-alert` (≥85 %) on the `#progress` label

**Note:** Textual `Label` does not natively support inline ANSI colours via class-based CSS colour changes to a `Label` update. We use Textual's CSS reactive classes approach — add/remove CSS classes on the label widget. The CSS defines colour rules per class.

- [ ] **Step 1: Update tui.py**

Replace `week1_baseline/python/12_context/src/boukensha/tui.py` with:

```python
"""Boukensha TUI — Textual four-zone terminal UI wrapping Repl."""

from __future__ import annotations

import asyncio
import datetime
import time
from concurrent.futures import Future
from typing import TYPE_CHECKING, Any

from textual.app import App, ComposeResult
from textual.widgets import Input, Label, RichLog
from textual.binding import Binding

if TYPE_CHECKING:
    from .repl import Repl

SPINNER_FRAMES = ["⠋", "⠙", "⠹", "⠸", "⠼", "⠴", "⠦", "⠧", "⠇", "⠏"]
TICK_S = 0.06
MAX_ITERATIONS = 25

CTX_WARN_PCT = 70
CTX_ALERT_PCT = 85

CSS = """
Screen {
    layout: vertical;
}

RichLog {
    height: 1fr;
    border: none;
    scrollbar-gutter: stable;
}

#progress {
    height: 1;
    padding: 0 1;
    color: $text-muted;
}

#progress.active {
    color: cyan;
}

#progress.ctx-warn {
    color: yellow;
}

#progress.ctx-alert {
    color: red;
}

Input {
    height: 3;
    border: none;
    padding: 0 0;
}

#status {
    height: 1;
    background: $surface;
    color: $text;
    padding: 0 1;
}
"""


class Tui(App):
    BINDINGS = [
        Binding("ctrl+c", "quit", "Quit", show=False),
        Binding("ctrl+d", "quit", "Quit", show=False),
        Binding("ctrl+l", "clear_history", "Clear", show=False),
        Binding("escape", "interrupt_turn", "Interrupt", show=False),
        Binding("pageup", "scroll_up", "Scroll Up", show=False),
        Binding("pagedown", "scroll_down", "Scroll Down", show=False),
    ]

    CSS = CSS

    def __init__(self, repl: Repl) -> None:
        super().__init__()
        self._repl = repl
        self._turn_count = 0
        self._live: dict[str, Any] = self._idle_state()
        self._spinner_idx = 0
        self._future: Future | None = None

    # ── layout ────────────────────────────────────────────────────────────

    def compose(self) -> ComposeResult:
        yield RichLog(highlight=False, markup=False, wrap=True, id="log")
        yield Label("", id="progress")
        yield Input(placeholder="Type a message…", id="input")
        yield Label("", id="status")

    def on_mount(self) -> None:
        self._repl.on_output(self._on_repl_output)
        if self._repl.logger:
            self._repl.logger.subscribe(self._on_logger_event_from_thread)

        log = self.query_one("#log", RichLog)
        log.write(self._repl.banner)

        self.query_one("#input", Input).focus()
        self.set_interval(TICK_S, self._tick)

    # ── input submission ──────────────────────────────────────────────────

    def on_input_submitted(self, event: Input.Submitted) -> None:
        text = event.value.strip()
        event.input.clear()
        if not text:
            return

        result = self._repl.handle_command(text)
        if result == "quit":
            self.exit()
            return
        if result == "command":
            if text == "/clear":
                self._turn_count = 0
            return

        log = self.query_one("#log", RichLog)
        log.write(f"> {text}")
        self._launch_turn(text)

    # ── keyboard actions ──────────────────────────────────────────────────

    def action_quit(self) -> None:
        self.exit()

    def action_clear_history(self) -> None:
        self._repl.handle_command("/clear")
        self._turn_count = 0

    def action_interrupt_turn(self) -> None:
        if self._future and not self._future.done():
            self._future.cancel()

    def action_scroll_up(self) -> None:
        self.query_one("#log", RichLog).scroll_up(5)

    def action_scroll_down(self) -> None:
        self.query_one("#log", RichLog).scroll_down(5)

    # ── agent thread ──────────────────────────────────────────────────────

    def _launch_turn(self, text: str) -> None:
        self._live = {
            "active": True,
            "start_time": time.monotonic(),
            "elapsed": 0,
            "current_action": "Thinking…",
            "iteration": 0,
            "tool_call_count": 0,
            "turn_input_tokens": 0,
            "turn_output_tokens": 0,
        }
        loop = asyncio.get_running_loop()
        self._future = loop.run_in_executor(None, self._run_turn_sync, text)
        self.query_one("#input", Input).disabled = True

    def _run_turn_sync(self, text: str) -> None:
        try:
            self._repl.run_turn(text)
        except Exception as e:
            self.call_from_thread(self._on_turn_error, str(e))
        finally:
            self.call_from_thread(self._on_turn_complete)

    # ── event callbacks (called from logger subscriber, thread-safe) ───────

    def _on_logger_event_from_thread(self, event: dict[str, Any]) -> None:
        self.call_from_thread(self._handle_live_event, event)

    def _handle_live_event(self, event: dict[str, Any]) -> None:
        phase = event.get("phase", "")
        if phase == "iteration":
            self._live["iteration"] = int(event.get("n", 0))
            self._live["max_iterations"] = int(event.get("max", MAX_ITERATIONS))
            self._live["current_action"] = "Thinking…"
        elif phase == "tool_call":
            self._live["current_action"] = f"Calling tool: {event.get('name', '')}"
            self._live["tool_call_count"] = self._live.get("tool_call_count", 0) + 1
        elif phase == "tool_result":
            self._live["current_action"] = "Awaiting result…"
        elif phase == "response":
            usage = event.get("usage") or {}
            itu = int(usage.get("input_tokens", 0))
            otu = int(usage.get("output_tokens", 0))
            self._live["turn_input_tokens"] = self._live.get("turn_input_tokens", 0) + itu
            self._live["turn_output_tokens"] = self._live.get("turn_output_tokens", 0) + otu
        elif phase == "compaction":
            dropped = event.get("dropped", 0)
            log = self.query_one("#log", RichLog)
            log.write(f"[context compacted — {dropped} messages dropped to free space]")

    def _on_repl_output(self, text: str) -> None:
        self.call_from_thread(self._append_to_log, text)

    def _append_to_log(self, text: str) -> None:
        self.query_one("#log", RichLog).write(text)

    def _on_turn_complete(self) -> None:
        self.query_one("#input", Input).disabled = False
        self._live = self._idle_state()
        self._turn_count += 1

    def _on_turn_error(self, message: str) -> None:
        self.query_one("#input", Input).disabled = False
        self._live = self._idle_state()
        self.query_one("#log", RichLog).write(f"[error] {message}")

    # ── periodic tick (spinner + status refresh) ──────────────────────────

    def _tick(self) -> None:
        self._spinner_idx = (self._spinner_idx + 1) % len(SPINNER_FRAMES)
        if self._live.get("active") and self._live.get("start_time"):
            self._live["elapsed"] = time.monotonic() - self._live["start_time"]
        self._refresh_progress()
        self._refresh_status()

    def _refresh_progress(self) -> None:
        label = self.query_one("#progress", Label)
        if self._live.get("active"):
            frame = SPINNER_FRAMES[self._spinner_idx]
            action = self._live.get("current_action", "")
            iteration = self._live.get("iteration", 0)
            elapsed = int(self._live.get("elapsed", 0))
            itok = _fmt_tokens(self._live.get("turn_input_tokens", 0))
            otok = _fmt_tokens(self._live.get("turn_output_tokens", 0))
            calls = self._live.get("tool_call_count", 0)
            max_iter = self._live.get("max_iterations", MAX_ITERATIONS)
            label.update(
                f"{frame} {action}  "
                f"(iter {iteration}/{max_iter} · {elapsed}s · "
                f"↑ {itok} · ↓ {otok} · {calls} calls)"
            )
            label.add_class("active")
            label.remove_class("ctx-warn", "ctx-alert")
        else:
            ctx = self._repl.context
            pct = ctx.usage_pct
            used = _fmt_tokens(ctx.current_tokens)
            max_tok = _fmt_tokens(ctx.context_window)
            label.update(
                f"  [ready]   ctx {used} / {max_tok} ({pct}%)   {self._turn_count} turns"
            )
            label.remove_class("active")
            # Apply colour class based on context pressure
            if pct >= CTX_ALERT_PCT:
                label.add_class("ctx-alert")
                label.remove_class("ctx-warn")
            elif pct >= CTX_WARN_PCT:
                label.add_class("ctx-warn")
                label.remove_class("ctx-alert")
            else:
                label.remove_class("ctx-warn", "ctx-alert")

    def _refresh_status(self) -> None:
        label = self.query_one("#status", Label)
        ctx = self._repl.context
        ver = self._repl.version or "?.?.?"
        model = self._repl.model or "(model)"
        pct = ctx.usage_pct
        used = _fmt_tokens(ctx.current_tokens)
        max_tok = _fmt_tokens(ctx.context_window)
        tool_count = len(ctx.tools)
        clock = datetime.datetime.now().strftime("%H:%M:%S")
        ctx_indicator = " ⚠ " if pct >= CTX_ALERT_PCT else " "
        label.update(
            f" boukensha v{ver} · {model}  ·  "
            f"ctx {used}/{max_tok} ({pct}%){ctx_indicator}·  "
            f"{tool_count} tools  ·  {clock} "
        )

    # ── helpers ───────────────────────────────────────────────────────────

    @staticmethod
    def _idle_state() -> dict[str, Any]:
        return {
            "active": False,
            "start_time": None,
            "elapsed": 0,
            "current_action": "idle",
            "iteration": 0,
            "tool_call_count": 0,
            "turn_input_tokens": 0,
            "turn_output_tokens": 0,
        }


def _fmt_tokens(n: int) -> str:
    n = int(n)
    return f"{n / 1000:.1f}k" if n >= 1000 else str(n)
```

- [ ] **Step 2: Run full test suite (TUI has no unit tests — verify no regressions)**

```bash
cd week1_baseline/python/12_context
uv run pytest tests/ -v
```

Expected: all tests PASS. (TUI tests require a running terminal and are not covered by unit tests — manual verification done in Task 9.)

- [ ] **Step 3: Commit**

```bash
git add week1_baseline/python/12_context/src/boukensha/tui.py
git commit -m "feat(12): update TUI with context-aware colour display and compaction events"
```

---

### Task 7: Wire context_window and max_turn_tokens into __init__.py

**Files:**
- Modify: `week1_baseline/python/12_context/src/boukensha/__init__.py`

**Interfaces:**
- Consumes:
  - `Context(task, system, working_dir, context_window=200_000)` — new kwarg
  - `Repl(..., max_turn_tokens=...)` — new kwarg
  - `Agent(..., max_turn_tokens=...)` — new kwarg
- Produces:
  - `boukensha.run(..., context_window: int = 200_000, max_turn_tokens: int | None = None) -> str`
  - `boukensha.repl(..., context_window: int = 200_000, max_turn_tokens: int | None = None) -> None`

- [ ] **Step 1: Update `__init__.py`**

In `week1_baseline/python/12_context/src/boukensha/__init__.py`:

1. Add `context_window: int = 200_000` and `max_turn_tokens: int | None = None` parameters to both `run()` and `repl()`.

2. Pass `context_window=context_window` to every `Context(...)` call.

3. Pass `max_turn_tokens=max_turn_tokens` to `Agent(...)` in `run()`.

4. Pass `max_turn_tokens=max_turn_tokens` to `Repl(...)` in `repl()`.

5. Update `__version__` to `"0.12.0"`.

The updated signatures look like:

```python
__version__ = "0.12.0"

def run(
    task: str,
    *,
    system: str | None = None,
    model: str | None = None,
    backend: str | None = None,
    api_key: str | None = None,
    ollama_host: str = "http://localhost:11434",
    log: str | None = None,
    context_window: int = 200_000,
    max_turn_tokens: int | None = None,
    max_output_tokens: int | None = None,
    working_dir: str | bool | None = None,
    allowed_commands: list[str] | None = None,
    shell_timeout: int = 30,
    tool_registrar: Callable[[RunDSL], None] | None = None,
) -> str:
    ...
    ctx = Context(task=task_class, system=resolved_system, working_dir=resolved_wd, context_window=context_window)
    ...
    agent = Agent(
        ...
        max_turn_tokens=max_turn_tokens,
        ...
    )


def repl(
    *,
    tui: bool = True,
    system: str | None = None,
    model: str | None = None,
    backend: str | None = None,
    api_key: str | None = None,
    ollama_host: str = "http://localhost:11434",
    log: str | None = None,
    context_window: int = 200_000,
    max_turn_tokens: int | None = None,
    max_output_tokens: int | None = None,
    working_dir: str | bool | None = None,
    allowed_commands: list[str] | None = None,
    shell_timeout: int = 30,
    tool_registrar: Callable[[RunDSL], None] | None = None,
) -> None:
    ...
    ctx = Context(task=task_class, system=resolved_system, working_dir=resolved_wd, context_window=context_window)
    ...
    repl_instance = _Repl(
        ...
        max_turn_tokens=max_turn_tokens,
        ...
    )
```

Apply these changes to the full file without altering any other logic.

- [ ] **Step 2: Run full test suite**

```bash
cd week1_baseline/python/12_context
uv run pytest tests/ -v
```

Expected: all tests PASS. No test should fail due to the `context_window` parameter addition (existing `Context(task=Player, system="sys")` calls use default).

- [ ] **Step 3: Commit**

```bash
git add week1_baseline/python/12_context/src/boukensha/__init__.py
git commit -m "feat(12): wire context_window and max_turn_tokens into run() and repl()"
```

---

### Task 8: Update the example script and write README

**Files:**
- Modify: `week1_baseline/python/12_context/examples/example.py`
- Create: `week1_baseline/python/12_context/README.md`

**Interfaces:**
- Produces: runnable example that demonstrates `context_window=` parameter

- [ ] **Step 1: Update example.py**

Replace `week1_baseline/python/12_context/examples/example.py` with:

```python
#!/usr/bin/env python
"""Step 12 — Context Management demo.

Launches the Textual TUI by default.  Pass --no-tui for the plain REPL.
The context_window= parameter controls how many tokens trigger compaction.
"""

from __future__ import annotations

import os
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

os.environ.setdefault(
    "BOUKENSHA_DIR",
    str(Path(__file__).parent.parent.parent.parent.parent / ".boukensha"),
)

import boukensha

use_tui = "--no-tui" not in sys.argv

boukensha.repl(
    tui=use_tui,
    working_dir=str(Path(__file__).parent),
    context_window=200_000,
)
```

- [ ] **Step 2: Write README.md**

Create `week1_baseline/python/12_context/README.md` that mirrors the Ruby README — document the new features (context tracking, colour coding, auto-compaction, `/compact` command, `context_window=` parameter) and how to run the demo.

- [ ] **Step 3: Run final test suite**

```bash
cd week1_baseline/python/12_context
uv run pytest tests/ -v
```

Expected: all tests PASS.

- [ ] **Step 4: Commit**

```bash
git add week1_baseline/python/12_context/examples/example.py \
        week1_baseline/python/12_context/README.md
git commit -m "feat(12): add example script and README for step 12 context management"
```

---

### Task 9: Final verification

**Files:** none (read-only verification)

- [ ] **Step 1: Run complete test suite**

```bash
cd week1_baseline/python/12_context
uv run pytest tests/ -v --tb=short
```

Expected: all tests pass. Zero failures.

- [ ] **Step 2: Spot-check boukensha_loader integration**

```bash
cd week1_baseline/python/12_context
uv run python -c "
import sys; sys.path.insert(0, 'src')
from boukensha.context import Context
from boukensha.tasks.player import Player
ctx = Context(task=Player, system='s', context_window=200_000)
ctx.update_tokens(170_000)
print('usage_pct:', ctx.usage_pct)
print('needs_compaction:', ctx.needs_compaction())
for i in range(10): ctx.add_message('user', f'msg {i}')
dropped = ctx.compact_messages()
print('dropped:', dropped, 'remaining:', len(ctx.messages))
print('current_tokens after compact:', ctx.current_tokens)
"
```

Expected output:
```
usage_pct: 85
needs_compaction: True
dropped: 4
remaining: 6
current_tokens after compact: 0
```

- [ ] **Step 3: Commit final verification note**

No code changes required — if all tests pass, the step is complete.

```bash
git log --oneline -6
```

Expected: 6+ commits for step 12 tasks all present.
