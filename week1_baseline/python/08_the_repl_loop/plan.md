# The REPL Loop Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Port the Ruby `08_the_repl_loop` step to Python by adding `Repl`, `boukensha.repl()`, quiet-mode flags, persistent history, and `Logger.turn()` on top of the step 07 codebase.

**Architecture:** Step 08 is a thin layer over step 07 — the same `Agent`/`Context`/`Logger`/`Client` primitives, extended with: (1) a `Repl` class that reads stdin in a loop and feeds each turn to a fresh `Agent` sharing a persistent `Context`, and (2) a `boukensha.repl()` convenience function that wires the plumbing (identical to `boukensha.run()` minus the `task` argument). The only changes to existing primitives are `Agent.run()` persisting the final reply into context, `Context.clear_messages()`, and `Logger.turn()`.

**Tech Stack:** Python ≥ 3.11, `uv`, `pytest`, `pyyaml`, `python-dotenv`, `hatchling`. No new third-party dependencies.

## Global Constraints

- All source lives under `week1_baseline/python/08_the_repl_loop/` — never modify step 07.
- Package layout matches step 07: `src/boukensha/` with `pyproject.toml` + `uv`.
- Tests run with `pytest` from the step directory (activated venv or `uv run pytest`).
- No new third-party runtime dependencies (pyyaml and python-dotenv already in pyproject).
- Follow step 07 naming/style exactly: snake_case, `from __future__ import annotations`, type hints on all public APIs.
- `pyproject.toml` name field: `"boukensha-repl-loop"`, version `"0.1.0"`.

---

### Task 1: Scaffold step 08 from step 07

**Files:**
- Create: `week1_baseline/python/08_the_repl_loop/` (whole tree)
- Create: `week1_baseline/python/08_the_repl_loop/pyproject.toml`
- Create: `week1_baseline/python/08_the_repl_loop/src/boukensha/__init__.py`
- Create: `week1_baseline/python/08_the_repl_loop/src/boukensha/agent.py`
- Create: `week1_baseline/python/08_the_repl_loop/src/boukensha/client.py`
- Create: `week1_baseline/python/08_the_repl_loop/src/boukensha/config.py`
- Create: `week1_baseline/python/08_the_repl_loop/src/boukensha/context.py`
- Create: `week1_baseline/python/08_the_repl_loop/src/boukensha/errors.py`
- Create: `week1_baseline/python/08_the_repl_loop/src/boukensha/logger.py`
- Create: `week1_baseline/python/08_the_repl_loop/src/boukensha/message.py`
- Create: `week1_baseline/python/08_the_repl_loop/src/boukensha/prompt_builder.py`
- Create: `week1_baseline/python/08_the_repl_loop/src/boukensha/registry.py`
- Create: `week1_baseline/python/08_the_repl_loop/src/boukensha/run_dsl.py`
- Create: `week1_baseline/python/08_the_repl_loop/src/boukensha/tool.py`
- Create: `week1_baseline/python/08_the_repl_loop/src/boukensha/backends/__init__.py`
- Create: `week1_baseline/python/08_the_repl_loop/src/boukensha/backends/anthropic.py`
- Create: `week1_baseline/python/08_the_repl_loop/src/boukensha/backends/base.py`
- Create: `week1_baseline/python/08_the_repl_loop/src/boukensha/backends/gemini.py`
- Create: `week1_baseline/python/08_the_repl_loop/src/boukensha/backends/ollama.py`
- Create: `week1_baseline/python/08_the_repl_loop/src/boukensha/backends/ollama_cloud.py`
- Create: `week1_baseline/python/08_the_repl_loop/src/boukensha/backends/openai.py`
- Create: `week1_baseline/python/08_the_repl_loop/src/boukensha/tasks/__init__.py`
- Create: `week1_baseline/python/08_the_repl_loop/src/boukensha/tasks/base.py`
- Create: `week1_baseline/python/08_the_repl_loop/src/boukensha/tasks/player.py`
- Create: `week1_baseline/python/08_the_repl_loop/prompts/system.md`
- Create: `week1_baseline/python/08_the_repl_loop/tests/__init__.py`
- Create: `week1_baseline/python/08_the_repl_loop/tests/test_agent.py`
- Create: `week1_baseline/python/08_the_repl_loop/tests/test_logger.py`
- Create: `week1_baseline/python/08_the_repl_loop/tests/test_run_dsl.py`

**Interfaces:**
- Produces: a working copy of the step 07 package installed in its own venv at `week1_baseline/python/08_the_repl_loop/.venv/`

- [ ] **Step 1: Copy all source files from step 07 to step 08**

```bash
SRC=week1_baseline/python/07_the_run_dsl
DST=week1_baseline/python/08_the_repl_loop
cp -r "$SRC/src" "$DST/"
cp -r "$SRC/tests" "$DST/"
cp -r "$SRC/prompts" "$DST/"
cp "$SRC/pyproject.toml" "$DST/"
```

- [ ] **Step 2: Update `pyproject.toml` name**

Edit `week1_baseline/python/08_the_repl_loop/pyproject.toml` — change:
```toml
name = "boukensha-run-dsl"
description = "Boukensha run DSL (Step 7)"
```
to:
```toml
name = "boukensha-repl-loop"
description = "Boukensha REPL loop (Step 8)"
```

- [ ] **Step 3: Install the package and verify baseline tests pass**

```bash
cd week1_baseline/python/08_the_repl_loop
uv sync
uv run pytest tests/ -v
```

Expected: all existing tests pass (same count as step 07).

- [ ] **Step 4: Commit the scaffold**

```bash
git add week1_baseline/python/08_the_repl_loop/
git commit -m "feat: scaffold step 08 from step 07 baseline"
```

---

### Task 2: `Context.clear_messages()` method

**Files:**
- Modify: `week1_baseline/python/08_the_repl_loop/src/boukensha/context.py`
- Create: `week1_baseline/python/08_the_repl_loop/tests/test_context.py`

**Interfaces:**
- Consumes: `Context` from `context.py` (existing `__init__`, `add_message`, `register_tool`)
- Produces: `Context.clear_messages() -> None` — wipes `self.messages` but keeps `self.tools` intact

- [ ] **Step 1: Write the failing test**

Create `week1_baseline/python/08_the_repl_loop/tests/test_context.py`:

```python
from __future__ import annotations

from boukensha.context import Context
from boukensha.registry import Registry
from boukensha.run_dsl import RunDSL
from boukensha.tasks.player import Player


def _make_ctx() -> Context:
    return Context(task=Player, system="sys")


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
```

- [ ] **Step 2: Run test to confirm it fails**

```bash
cd week1_baseline/python/08_the_repl_loop
uv run pytest tests/test_context.py -v
```

Expected: `AttributeError: 'Context' object has no attribute 'clear_messages'`

- [ ] **Step 3: Add `clear_messages()` to `context.py`**

Open `src/boukensha/context.py` and add after the `add_message` method:

```python
    def clear_messages(self) -> None:
        self.messages = []
```

- [ ] **Step 4: Run tests to confirm they pass**

```bash
uv run pytest tests/test_context.py -v
```

Expected: all 3 tests PASS.

- [ ] **Step 5: Commit**

```bash
git add src/boukensha/context.py tests/test_context.py
git commit -m "feat: add Context.clear_messages() for REPL /clear command"
```

---

### Task 3: `Agent.run()` persists the final assistant reply into context

**Files:**
- Modify: `week1_baseline/python/08_the_repl_loop/src/boukensha/agent.py`
- Modify: `week1_baseline/python/08_the_repl_loop/tests/test_agent.py`

**Interfaces:**
- Consumes: `Context.add_message(role, content)` — already exists
- Produces: after `agent.run()` returns, the final assistant text is present in `context.messages` as a `Message(role="assistant", content=<text>)` entry. The `wrap_up` path also adds the assistant reply.

- [ ] **Step 1: Write the failing tests**

Add these tests to the bottom of `tests/test_agent.py`:

```python
def test_agent_run_adds_assistant_reply_to_context():
    """Final reply must be stored in context so subsequent REPL turns see it."""
    responses = [{"stop_reason": "end_turn", "content": [{"type": "text", "text": "Done!"}]}]
    agent, _, _ = _make_agent(responses)
    agent.run()
    last_msg = agent._context.messages[-1]
    assert last_msg.role == "assistant"
    assert last_msg.content == "Done!"


def test_agent_wrap_up_adds_assistant_reply_to_context():
    """Wrap-up reply must also be stored in context."""
    tool_response = {
        "stop_reason": "tool_use",
        "content": [{"type": "tool_use", "id": "tu_1", "name": "noop", "input": {}}],
    }
    wrap_up_response = {"stop_reason": "end_turn", "content": [{"type": "text", "text": "Wrapping up"}]}

    from unittest.mock import MagicMock
    from boukensha.agent import Agent
    from boukensha.context import Context
    from boukensha.registry import Registry
    from boukensha.tasks.player import Player

    ctx = Context(task=Player, system="sys")
    registry = Registry(ctx)
    registry.tool("noop", description="noop", parameters={}, block=lambda: "ok")

    mock_builder = MagicMock()
    mock_builder.parse_response.side_effect = [tool_response, wrap_up_response]
    mock_builder.to_api_payload.return_value = {}
    mock_builder.backend = None
    mock_client = MagicMock()
    mock_client.call.return_value = {}
    ctx.add_message("user", "go")

    agent = Agent(
        context=ctx,
        registry=registry,
        builder=mock_builder,
        client=mock_client,
        max_iterations=1,
    )
    agent.run()
    roles = [m.role for m in ctx.messages]
    assert roles[-1] == "assistant"
    assert ctx.messages[-1].content == "Wrapping up"
```

- [ ] **Step 2: Run tests to confirm they fail**

```bash
uv run pytest tests/test_agent.py::test_agent_run_adds_assistant_reply_to_context tests/test_agent.py::test_agent_wrap_up_adds_assistant_reply_to_context -v
```

Expected: both FAIL (final assistant message not in context).

- [ ] **Step 3: Update `agent.py` — normal `run()` path**

In `src/boukensha/agent.py`, inside the `run()` method, find the `else` branch that returns the final text:

```python
            else:
                text = self._extract_text(parsed["content"])
                self._log_response(text=text, response=response)
                if self._logger:
                    self._logger.turn_end(reason="completed", iterations=self._iteration)
                return text
```

Replace it with:

```python
            else:
                text = self._extract_text(parsed["content"])
                self._log_response(text=text, response=response)
                if self._logger:
                    self._logger.turn_end(reason="completed", iterations=self._iteration)
                self._context.add_message("assistant", text)
                return text
```

- [ ] **Step 4: Update `agent.py` — `_wrap_up()` path**

In `src/boukensha/agent.py`, find `_wrap_up`:

```python
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
```

Replace with:

```python
    def _wrap_up(self, reason: str) -> str:
        self._context.add_message("user", WRAP_UP_DIRECTIVE)
        try:
            response = self._client.call(tools=[], max_output_tokens=WRAP_UP_OUTPUT_TOKENS)
            text = self._extract_text(self._builder.parse_response(response)["content"])
            result = text.strip() or self._fallback_message(reason)
            self._log_response(text=result, response=response)
            if self._logger:
                self._logger.turn_end(reason=reason, iterations=self._iteration)
            self._context.add_message("assistant", result)
            return result
        except ApiError:
            msg = self._fallback_message(reason)
            if self._logger:
                self._logger.turn_end(reason=reason, iterations=self._iteration)
            self._context.add_message("assistant", msg)
            return msg
```

- [ ] **Step 5: Run all tests**

```bash
uv run pytest tests/ -v
```

Expected: all tests pass including the two new ones. The existing `test_agent_calls_tool_then_ends` will still pass — that test checks `roles == ["user", "assistant", "tool_result"]` (those are the mid-turn messages, the final assistant reply comes after).

- [ ] **Step 6: Commit**

```bash
git add src/boukensha/agent.py tests/test_agent.py
git commit -m "feat: persist final agent reply into context for multi-turn REPL history"
```

---

### Task 4: `Logger.turn()` method

**Files:**
- Modify: `week1_baseline/python/08_the_repl_loop/src/boukensha/logger.py`
- Modify: `week1_baseline/python/08_the_repl_loop/tests/test_logger.py`

**Interfaces:**
- Produces: `Logger.turn(*, n: int) -> None` — writes `{"phase": "turn", "n": <n>}` to the JSONL log

- [ ] **Step 1: Write the failing test**

Add to the bottom of `tests/test_logger.py`:

```python
def test_logger_turn_event():
    with tempfile.TemporaryDirectory() as d:
        lg = Logger(dir=d)
        lg.turn(n=1)
        lg.turn(n=2)
        lg.close()
        lines = _read_lines(lg.path)
        turn_lines = [l for l in lines if l["phase"] == "turn"]
        assert len(turn_lines) == 2
        assert turn_lines[0]["n"] == 1
        assert turn_lines[1]["n"] == 2
```

- [ ] **Step 2: Run test to confirm it fails**

```bash
uv run pytest tests/test_logger.py::test_logger_turn_event -v
```

Expected: `AttributeError: 'Logger' object has no attribute 'turn'`

- [ ] **Step 3: Add `turn()` to `logger.py`**

In `src/boukensha/logger.py`, add after `def iteration(...)`:

```python
    def turn(self, *, n: int) -> None:
        self._write_log({"phase": "turn", "n": n})
```

- [ ] **Step 4: Run all tests**

```bash
uv run pytest tests/ -v
```

Expected: all tests pass.

- [ ] **Step 5: Commit**

```bash
git add src/boukensha/logger.py tests/test_logger.py
git commit -m "feat: add Logger.turn(n) for REPL turn boundary logging"
```

---

### Task 5: Quiet mode in the `boukensha` module

**Files:**
- Modify: `week1_baseline/python/08_the_repl_loop/src/boukensha/__init__.py`
- Modify: `week1_baseline/python/08_the_repl_loop/src/boukensha/agent.py`
- Create: `week1_baseline/python/08_the_repl_loop/tests/test_quiet.py`

**Interfaces:**
- Produces:
  - `boukensha._quiet: bool` module-level flag (starts `False`)
  - `boukensha.enable_quiet() -> None` — sets `_quiet = True`
  - `boukensha.disable_quiet() -> None` — sets `_quiet = False`
  - `boukensha.is_quiet() -> bool` — returns `_quiet`
  - Agent's console `print()` calls are suppressed when `is_quiet()` is `True`

- [ ] **Step 1: Write failing tests**

Create `week1_baseline/python/08_the_repl_loop/tests/test_quiet.py`:

```python
from __future__ import annotations

import boukensha


def setup_function():
    boukensha._quiet = False


def teardown_function():
    boukensha._quiet = False


def test_quiet_starts_false():
    assert boukensha.is_quiet() is False


def test_enable_quiet():
    boukensha.enable_quiet()
    assert boukensha.is_quiet() is True


def test_disable_quiet():
    boukensha.enable_quiet()
    boukensha.disable_quiet()
    assert boukensha.is_quiet() is False


def test_agent_suppresses_prints_when_quiet(capsys):
    from unittest.mock import MagicMock
    from boukensha.agent import Agent
    from boukensha.context import Context
    from boukensha.registry import Registry
    from boukensha.tasks.player import Player

    boukensha.enable_quiet()

    ctx = Context(task=Player, system="sys")
    registry = Registry(ctx)
    mock_builder = MagicMock()
    mock_builder.parse_response.return_value = {
        "stop_reason": "end_turn",
        "content": [{"type": "text", "text": "ok"}],
    }
    mock_builder.to_api_payload.return_value = {}
    mock_builder.backend = None
    mock_client = MagicMock()
    mock_client.call.return_value = {}
    ctx.add_message("user", "hi")

    agent = Agent(context=ctx, registry=registry, builder=mock_builder, client=mock_client)
    agent.run()

    captured = capsys.readouterr()
    assert "[iteration" not in captured.out
```

- [ ] **Step 2: Run tests to confirm they fail**

```bash
uv run pytest tests/test_quiet.py -v
```

Expected: `AttributeError: module 'boukensha' has no attribute 'is_quiet'` (or similar).

- [ ] **Step 3: Add quiet state to `__init__.py`**

In `src/boukensha/__init__.py`, after the `_debug: bool = False` line and its two functions, add:

```python
_quiet: bool = False


def enable_quiet() -> None:
    global _quiet
    _quiet = True


def disable_quiet() -> None:
    global _quiet
    _quiet = False


def is_quiet() -> bool:
    return _quiet
```

Also add `"enable_quiet"`, `"disable_quiet"`, and `"is_quiet"` to `__all__`.

- [ ] **Step 4: Guard agent `print()` calls**

In `src/boukensha/agent.py`, at the top add:

```python
import boukensha
```

Replace the three `print()` calls:

```python
# Original line 61:
print(f"[iteration {self._iteration}/{self._max_iterations}]")
```
becomes:
```python
if not boukensha.is_quiet():
    print(f"[iteration {self._iteration}/{self._max_iterations}]")
```

```python
# Original line 165:
print(f"  tool call -> {name}({args})")
```
becomes:
```python
if not boukensha.is_quiet():
    print(f"  tool call -> {name}({args})")
```

```python
# Original line 166:
print(f"  tool result -> {str(result)[:61]}")
```
becomes:
```python
if not boukensha.is_quiet():
    print(f"  tool result -> {str(result)[:61]}")
```

- [ ] **Step 5: Run all tests**

```bash
uv run pytest tests/ -v
```

Expected: all tests pass.

- [ ] **Step 6: Commit**

```bash
git add src/boukensha/__init__.py src/boukensha/agent.py tests/test_quiet.py
git commit -m "feat: add quiet mode (enable_quiet/disable_quiet/is_quiet) for REPL /quiet and /loud commands"
```

---

### Task 6: `Repl` class

**Files:**
- Create: `week1_baseline/python/08_the_repl_loop/src/boukensha/repl.py`
- Create: `week1_baseline/python/08_the_repl_loop/tests/test_repl.py`

**Interfaces:**
- Consumes:
  - `Context(task, system)` with `add_message(role, content)` and `clear_messages()`
  - `Registry(ctx)`
  - `Agent(context, registry, builder, client, logger, task_settings, max_iterations, max_output_tokens)`
  - `boukensha.enable_quiet()`, `boukensha.disable_quiet()`
  - `Logger.turn(n=<int>)`
  - `LoopError`, `ApiError` from `boukensha.errors`
- Produces: `Repl` class with:
  - `__init__(context, registry, builder, client, logger, task_settings, max_iterations, max_output_tokens, config_dir, provider, model, version, api_key)` — all keyword arguments
  - `start() -> None` — reads stdin in a loop; returns on EOF, `/exit`, or `/quit`

- [ ] **Step 1: Write failing tests**

Create `week1_baseline/python/08_the_repl_loop/tests/test_repl.py`:

```python
from __future__ import annotations

import io
from unittest.mock import MagicMock, patch

import pytest

import boukensha
from boukensha.agent import Agent
from boukensha.context import Context
from boukensha.repl import Repl
from boukensha.registry import Registry
from boukensha.tasks.player import Player


def _make_repl(responses=None, **kwargs):
    ctx = Context(task=Player, system="sys")
    registry = Registry(ctx)

    mock_builder = MagicMock()
    if responses:
        mock_builder.parse_response.side_effect = responses
    else:
        mock_builder.parse_response.return_value = {
            "stop_reason": "end_turn",
            "content": [{"type": "text", "text": "ok"}],
        }
    mock_builder.to_api_payload.return_value = {}
    mock_builder.backend = None
    mock_client = MagicMock()
    mock_client.call.return_value = {}

    defaults = dict(
        context=ctx,
        registry=registry,
        builder=mock_builder,
        client=mock_client,
        logger=None,
        task_settings={},
        max_iterations=25,
        max_output_tokens=None,
        config_dir=None,
        provider="anthropic",
        model="claude-haiku-4-5",
        version="0.1.0",
        api_key="test-key",
    )
    defaults.update(kwargs)
    return Repl(**defaults), ctx


def _run_with_input(repl, lines):
    text = "\n".join(lines) + "\n"
    with patch("sys.stdin", io.StringIO(text)):
        repl.start()


def test_repl_exits_on_exit_command(capsys):
    repl, _ = _make_repl()
    _run_with_input(repl, ["/exit"])
    captured = capsys.readouterr()
    assert "Goodbye" in captured.out


def test_repl_exits_on_quit_command(capsys):
    repl, _ = _make_repl()
    _run_with_input(repl, ["/quit"])
    captured = capsys.readouterr()
    assert "Goodbye" in captured.out


def test_repl_exits_on_eof(capsys):
    repl, _ = _make_repl()
    with patch("sys.stdin", io.StringIO("")):
        repl.start()
    # no exception raised


def test_repl_help_command(capsys):
    repl, _ = _make_repl()
    _run_with_input(repl, ["/help", "/exit"])
    captured = capsys.readouterr()
    assert "/clear" in captured.out
    assert "/exit" in captured.out


def test_repl_clear_command_wipes_history(capsys):
    repl, ctx = _make_repl()
    ctx.add_message("user", "earlier")
    _run_with_input(repl, ["/clear", "/exit"])
    assert ctx.messages == []
    captured = capsys.readouterr()
    assert "cleared" in captured.out


def test_repl_quiet_command_enables_quiet(capsys):
    boukensha._quiet = False
    repl, _ = _make_repl()
    _run_with_input(repl, ["/quiet", "/exit"])
    assert boukensha.is_quiet() is True
    boukensha._quiet = False  # cleanup


def test_repl_loud_command_disables_quiet(capsys):
    boukensha._quiet = True
    repl, _ = _make_repl()
    _run_with_input(repl, ["/loud", "/exit"])
    assert boukensha.is_quiet() is False


def test_repl_runs_agent_for_normal_input(capsys):
    repl, ctx = _make_repl()
    _run_with_input(repl, ["hello world", "/exit"])
    # agent reply "ok" must appear in output
    captured = capsys.readouterr()
    assert "ok" in captured.out


def test_repl_history_accumulates_across_turns():
    repl, ctx = _make_repl()
    _run_with_input(repl, ["first turn", "second turn", "/exit"])
    roles = [m.role for m in ctx.messages]
    # user + assistant for each turn
    assert roles.count("user") == 2
    assert roles.count("assistant") == 2


def test_repl_skips_blank_lines():
    repl, ctx = _make_repl()
    _run_with_input(repl, ["", "   ", "/exit"])
    # No agent messages added for blank input
    user_msgs = [m for m in ctx.messages if m.role == "user"]
    assert user_msgs == []


def test_repl_banner_shows_provider(capsys):
    repl, _ = _make_repl(provider="anthropic", model="claude-haiku-4-5", api_key="key")
    _run_with_input(repl, ["/exit"])
    captured = capsys.readouterr()
    assert "anthropic" in captured.out
    assert "claude-haiku-4-5" in captured.out


def test_repl_api_key_status_in_banner(capsys):
    repl_with_key, _ = _make_repl(api_key="real-key")
    _run_with_input(repl_with_key, ["/exit"])
    out_with = capsys.readouterr().out
    assert "API key set" in out_with

    repl_no_key, _ = _make_repl(api_key=None)
    _run_with_input(repl_no_key, ["/exit"])
    out_without = capsys.readouterr().out
    assert "API key not set" in out_without
```

- [ ] **Step 2: Run tests to confirm they fail**

```bash
uv run pytest tests/test_repl.py -v
```

Expected: `ModuleNotFoundError: No module named 'boukensha.repl'`

- [ ] **Step 3: Create `repl.py`**

Create `src/boukensha/repl.py`:

```python
"""Boukensha::Repl port: interactive session loop.

Wraps the same primitives as a single boukensha.run() call but stays alive:
reads a task from stdin, runs the agent, prints the reply, and loops back.
The Context is shared across every turn so conversation history accumulates.
"""

from __future__ import annotations

import sys
from typing import TYPE_CHECKING, Any

import boukensha
from .agent import Agent
from .errors import ApiError, LoopError

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
        self._max_output_tokens = max_output_tokens
        self._config_dir = config_dir
        self._provider = provider
        self._model = model
        self._version = version
        self._api_key = api_key
        self._turn = 0

    def start(self) -> None:
        print(self._banner())

        for line in sys.stdin:
            text = line.rstrip("\n").strip()
            if not text:
                continue

            if text in ("/exit", "/quit"):
                print("Goodbye.")
                break
            elif text == "/help":
                print(HELP)
            elif text == "/quiet":
                boukensha.enable_quiet()
                print("(logging suppressed — type /loud to re-enable)")
            elif text == "/loud":
                boukensha.disable_quiet()
                print("(logging enabled)")
            elif text == "/clear":
                self._context.clear_messages()
                self._turn = 0
                print("(conversation history cleared)")
            else:
                self._run_turn(text)

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
            f"  /exit or /quit    leave the REPL\n"
        )

    def _run_turn(self, user_input: str) -> None:
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
            max_output_tokens=self._max_output_tokens,
        )
        try:
            result = agent.run()
            print()
            print(result)
        except LoopError as e:
            print(f"\n[error] {e}")
        except ApiError as e:
            print(f"\n[error] API call failed: {e}")
```

- [ ] **Step 4: Run all tests**

```bash
uv run pytest tests/ -v
```

Expected: all tests pass.

- [ ] **Step 5: Commit**

```bash
git add src/boukensha/repl.py tests/test_repl.py
git commit -m "feat: add Repl class — interactive REPL loop with /help, /clear, /quiet, /loud, /exit"
```

---

### Task 7: `boukensha.repl()` module-level function

**Files:**
- Modify: `week1_baseline/python/08_the_repl_loop/src/boukensha/__init__.py`
- Modify: `week1_baseline/python/08_the_repl_loop/tests/test_run_dsl.py`

**Interfaces:**
- Consumes: `Repl` from `repl.py`
- Produces: `boukensha.repl(*, system, model, backend, api_key, ollama_host, log, max_output_tokens, tool_registrar)` — identical plumbing to `boukensha.run()` but builds a `Repl` and calls `.start()` instead of running the agent once. `tool_registrar` optional callable `(RunDSL) -> None`.

- [ ] **Step 1: Write failing tests**

Add to the bottom of `tests/test_run_dsl.py`:

```python
def test_repl_is_callable():
    assert callable(boukensha.repl)


def test_repl_exported():
    from boukensha import Repl
    assert Repl is not None


def test_repl_starts_and_exits_immediately(monkeypatch):
    """boukensha.repl() must start the REPL and exit cleanly on EOF."""
    import io
    import tempfile
    import yaml
    from unittest.mock import MagicMock, patch

    with tempfile.TemporaryDirectory() as tmp:
        monkeypatch.setenv("BOUKENSHA_DIR", tmp)

        settings = {
            "tasks": {
                "player": {
                    "provider": "anthropic",
                    "model": "claude-haiku-4-5",
                }
            }
        }
        with open(f"{tmp}/settings.yaml", "w") as f:
            yaml.dump(settings, f)
        with open(f"{tmp}/.env", "w") as f:
            f.write("ANTHROPIC_API_KEY=test-key\n")

        with patch("sys.stdin", io.StringIO("")):
            boukensha.repl(log=f"{tmp}/test-repl.jsonl")
```

- [ ] **Step 2: Run tests to confirm they fail**

```bash
uv run pytest tests/test_run_dsl.py::test_repl_is_callable tests/test_run_dsl.py::test_repl_exported tests/test_run_dsl.py::test_repl_starts_and_exits_immediately -v
```

Expected: `AttributeError: module 'boukensha' has no attribute 'repl'`

- [ ] **Step 3: Add `repl()` and imports to `__init__.py`**

In `src/boukensha/__init__.py`, add `from .repl import Repl` in the imports block and add `"Repl"` and `"repl"` to `__all__`.

Then add the `repl()` function after `run()`:

```python
def repl(
    *,
    system: str | None = None,
    model: str | None = None,
    backend: str | None = None,
    api_key: str | None = None,
    ollama_host: str = "http://localhost:11434",
    log: str | None = None,
    max_output_tokens: int | None = None,
    tool_registrar: Callable[[RunDSL], None] | None = None,
) -> None:
    """Start the interactive REPL loop.

    Same plumbing as ``run()`` but stays alive across multiple turns, reading
    tasks from stdin and accumulating history in a shared Context. Exits on
    EOF, KeyboardInterrupt, or the ``/exit`` / ``/quit`` commands.
    """
    from .repl import Repl as _Repl

    cfg = Config()
    task_class = tasks.Player
    task_settings = cfg.tasks(task_class.task_name())

    resolved_system = system or task_class.system_prompt(
        task_settings,
        user_prompts_dir=cfg.user_prompts_dir,
        default_prompts_dir=Config.PROMPTS_DIR,
    )
    resolved_model = model or task_class.model(task_settings)
    resolved_backend = backend or task_class.provider(task_settings)

    resolved_api_key = api_key or {
        "anthropic": os.environ.get("ANTHROPIC_API_KEY"),
        "openai": os.environ.get("OPENAI_API_KEY"),
        "gemini": os.environ.get("GEMINI_API_KEY"),
        "ollama_cloud": os.environ.get("OLLAMA_API_KEY"),
    }.get(resolved_backend)

    ctx = Context(task=task_class, system=resolved_system)
    registry = Registry(ctx)

    if tool_registrar is not None:
        dsl = RunDSL(registry)
        tool_registrar(dsl)

    be: Any
    if resolved_backend == "anthropic":
        be = backends.Anthropic(api_key=resolved_api_key, model=resolved_model)
    elif resolved_backend == "openai":
        be = backends.OpenAI(api_key=resolved_api_key, model=resolved_model)
    elif resolved_backend == "gemini":
        be = backends.Gemini(api_key=resolved_api_key, model=resolved_model)
    elif resolved_backend == "ollama":
        be = backends.Ollama(host=ollama_host, model=resolved_model)
    elif resolved_backend == "ollama_cloud":
        be = backends.OllamaCloud(api_key=resolved_api_key, model=resolved_model)
    else:
        raise ValueError(
            f"Unknown backend {resolved_backend!r}. "
            "Use 'anthropic', 'openai', 'gemini', 'ollama', or 'ollama_cloud'."
        )

    builder = PromptBuilder(ctx, be)
    client = Client(builder)
    effective_max_iterations = task_class.max_iterations(task_settings)
    effective_max_output_tokens = max_output_tokens or task_class.max_output_tokens(task_settings)

    logger = Logger(
        log=log,
        snapshot={
            "task": task_class.task_name(),
            "max_iterations": effective_max_iterations,
            "max_output_tokens": effective_max_output_tokens,
            "model": resolved_model,
            "provider": resolved_backend,
        },
    )

    try:
        _Repl(
            context=ctx,
            registry=registry,
            builder=builder,
            client=client,
            logger=logger,
            task_settings=task_settings,
            max_iterations=effective_max_iterations,
            max_output_tokens=effective_max_output_tokens,
            config_dir=str(cfg.dir),
            provider=resolved_backend,
            model=resolved_model,
            version=__version__,
            api_key=resolved_api_key,
        ).start()
    except KeyboardInterrupt:
        print("\nInterrupted.")
    finally:
        logger.close()
```

- [ ] **Step 4: Run all tests**

```bash
uv run pytest tests/ -v
```

Expected: all tests pass.

- [ ] **Step 5: Commit**

```bash
git add src/boukensha/__init__.py tests/test_run_dsl.py
git commit -m "feat: add boukensha.repl() module-level function and export Repl"
```

---

### Task 8: Example script

**Files:**
- Create: `week1_baseline/python/08_the_repl_loop/examples/example.py`

**Interfaces:**
- Consumes: `boukensha.repl(tool_registrar=...)` with `read_file` and `list_directory` tools
- Produces: a runnable script that mirrors `ruby/08_the_repl_loop/examples/example.rb`

- [ ] **Step 1: Create the example**

Create `week1_baseline/python/08_the_repl_loop/examples/example.py`:

```python
import os
from pathlib import Path

os.environ.setdefault(
    "BOUKENSHA_DIR",
    str((Path(__file__).parent.parent.parent.parent.parent / ".boukensha").resolve()),
)

import boukensha
from boukensha import Config

# The step 07 folder makes a good playground — it already has source files.
base_dir = Path(__file__).parent.parent.parent.parent / "07_the_run_dsl"

print(f"Config: {Config()}")
print()


def register_tools(dsl):
    dsl.tool(
        "read_file",
        description="Read the contents of a file from disk",
        parameters={"path": {"type": "string", "description": "File path relative to the working directory"}},
        block=lambda path: (base_dir / path).read_text(),
    )
    dsl.tool(
        "list_directory",
        description="List the files in a directory",
        parameters={"path": {"type": "string", "description": "Directory path relative to the working directory, or '.' for root"}},
        block=lambda path: ", ".join(
            f for f in os.listdir(base_dir / path) if not f.startswith(".")
        ),
    )


boukensha.repl(tool_registrar=register_tools)
```

- [ ] **Step 2: Verify the example is importable (smoke test)**

```bash
cd week1_baseline/python/08_the_repl_loop
uv run python -c "import ast, pathlib; ast.parse(pathlib.Path('examples/example.py').read_text()); print('syntax OK')"
```

Expected: `syntax OK`

- [ ] **Step 3: Run the full test suite one final time**

```bash
uv run pytest tests/ -v
```

Expected: all tests pass.

- [ ] **Step 4: Commit**

```bash
git add examples/example.py
git commit -m "feat: add REPL example script (port of ruby/08_the_repl_loop/examples/example.rb)"
```

---

## Self-Review

### Spec coverage

| Requirement (from Ruby step 08 README / source) | Task |
|---|---|
| `Context.clear_messages()` | Task 2 |
| `Agent.run()` persists final reply into context | Task 3 |
| `Logger.turn(n)` | Task 4 |
| Quiet / loud mode (`enable_quiet`, `disable_quiet`, `is_quiet`) | Task 5 |
| `Repl` class with `/exit`, `/quit`, `/help`, `/quiet`, `/loud`, `/clear`, EOF | Task 6 |
| `boukensha.repl()` module function | Task 7 |
| Example script | Task 8 |
| Scaffold (copy step 07, rename package) | Task 1 |

All requirements covered.

### Type consistency

- `Context.clear_messages()` → used in `Repl._run_turn` and tests ✓
- `Logger.turn(*, n: int)` → called as `self._logger.turn(n=self._turn)` in `Repl._run_turn` ✓
- `boukensha.enable_quiet()` / `disable_quiet()` / `is_quiet()` → used in `Repl.start()` and `agent.py` ✓
- `Repl.__init__` keyword args match what `boukensha.repl()` passes ✓
- `Context.add_message("assistant", text)` in `agent.py` matches existing signature ✓
