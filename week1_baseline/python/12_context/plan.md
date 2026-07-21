# Boukensha Python TUI (Step 11) Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Port the Ruby `11_tui` step to Python — replace the plain `Repl`'s `print`/`input` I/O with a structured four-zone Textual terminal UI while keeping the plain REPL available via `tui=False`.

**Architecture:** `Tui` is a `textual.app.App` subclass wrapping the existing `Repl`. The agent runs in a thread pool executor so the Textual event loop stays unblocked. Logger events are broadcast to subscribers and forwarded to the UI via `call_from_thread`. `Repl` is refactored to expose `on_output`/`handle_command`/`run_turn` so any front-end can drive it.

**Tech Stack:** Python ≥ 3.11, `uv`, `hatchling`, `pytest`, `textual>=0.80`, `pyyaml`, `python-dotenv`.

## Global Constraints

- All source lives under `week1_baseline/python/11_tui/` — never modify step 10.
- Package layout: `src/boukensha/` (step 10 baseline) + new `src/boukensha/tui.py`.
- `pyproject.toml` name: `"boukensha-tui"`, version stays `"0.1.0"`.
- New runtime dependency: `textual>=0.80` — add to `[project.dependencies]`.
- `tui=False` must fall back to the existing plain `Repl.start()` with no Textual import.
- Agent runs in `loop.run_in_executor(None, repl.run_turn, text)` — never `asyncio.create_task` with a blocking call.
- All paths use `from __future__ import annotations`, snake_case, type hints on all public APIs.
- Tests run with `uv run pytest tests/ -v` from the step directory.
- Follow step 10 style throughout.

---

## File Map

| File | Action | Responsibility |
|---|---|---|
| `src/boukensha/logger.py` | Modify | Add `subscribe(callback)` |
| `src/boukensha/repl.py` | Modify | Expose `on_output`, `handle_command`, `run_turn`, properties |
| `src/boukensha/tui.py` | Create | `Tui` Textual App — four-zone layout, spinner, event bridging |
| `src/boukensha/__init__.py` | Modify | Add `tui: bool = True` to `repl()`, export `Tui` |
| `pyproject.toml` | Modify | Add `textual>=0.80` dependency, update name/description |
| `tests/test_logger.py` | Modify | Add `subscribe` tests |
| `tests/test_repl.py` | Modify | Add `on_output`, `handle_command`, `run_turn` tests |
| `examples/example.py` | Modify | Update to demonstrate TUI launch |
| `README.md` | Modify | Document new TUI and `tui=` kwarg |

---

### Task 1: Scaffold step 11 from step 10

**Files:**
- Create: `week1_baseline/python/11_tui/` (full tree from step 10)
- Modify: `week1_baseline/python/11_tui/pyproject.toml`

**Interfaces:**
- Produces: a working copy of the step 10 package installed in its own venv, with all existing tests passing before any new code is added.

- [ ] **Step 1: Copy all source files from step 10 to step 11**

```bash
SRC=week1_baseline/python/10_standard_tool_library
DST=week1_baseline/python/11_tui
cp -r "$SRC/src" "$DST/"
cp -r "$SRC/tests" "$DST/"
cp -r "$SRC/prompts" "$DST/"
cp -r "$SRC/examples" "$DST/"
cp "$SRC/pyproject.toml" "$DST/"
cp "$SRC/README.md" "$DST/"
find "$DST" -name "__pycache__" -type d -exec rm -rf {} + 2>/dev/null || true
find "$DST" -name "*.pyc" -delete 2>/dev/null || true
```

- [ ] **Step 2: Update `pyproject.toml` name, description, and add Textual dependency**

Edit `week1_baseline/python/11_tui/pyproject.toml` so it reads:

```toml
[project]
name = "boukensha-tui"
version = "0.1.0"
description = "Boukensha TUI (Step 11)"
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

- [ ] **Step 3: Install and verify baseline tests pass**

```bash
cd week1_baseline/python/11_tui
uv sync
uv run pytest tests/ -v
```

Expected: all step 10 tests pass.

- [ ] **Step 4: Commit the scaffold**

```bash
git add week1_baseline/python/11_tui/
git commit -m "feat: scaffold step 11 TUI from step 10 baseline"
```

---

### Task 2: Add `Logger.subscribe()`

**Files:**
- Modify: `week1_baseline/python/11_tui/src/boukensha/logger.py`
- Modify: `week1_baseline/python/11_tui/tests/test_logger.py`

**Interfaces:**
- Produces:
  - `Logger.subscribe(callback: Callable[[dict], None]) -> None` — registers a callback. Every subsequent `_write_log()` call invokes all registered callbacks with the raw event dict (same object written to JSONL, including `session_id` and `at` keys).
  - Callbacks are called synchronously inside `_write_log`, before the method returns.

- [ ] **Step 1: Write the failing tests**

Append to the bottom of `week1_baseline/python/11_tui/tests/test_logger.py`:

```python
def test_logger_subscribe_receives_events():
    received = []
    with tempfile.TemporaryDirectory() as d:
        lg = Logger(dir=d)
        lg.subscribe(received.append)
        lg.tool_call(name="read_file", args={"path": "f.txt"})
        lg.close()
    phases = [e["phase"] for e in received]
    assert "tool_call" in phases


def test_logger_subscribe_multiple_callbacks():
    received_a = []
    received_b = []
    with tempfile.TemporaryDirectory() as d:
        lg = Logger(dir=d)
        lg.subscribe(received_a.append)
        lg.subscribe(received_b.append)
        lg.iteration(n=1, max=10)
        lg.close()
    assert any(e["phase"] == "iteration" for e in received_a)
    assert any(e["phase"] == "iteration" for e in received_b)


def test_logger_subscribe_receives_session_start():
    received = []
    with tempfile.TemporaryDirectory() as d:
        lg = Logger(dir=d)
        lg.subscribe(received.append)
        lg.close()
    # session_start is written in __init__ before subscribe is called,
    # but close() triggers no extra write — received should be empty here
    assert received == []


def test_logger_subscribe_event_has_session_id():
    received = []
    with tempfile.TemporaryDirectory() as d:
        lg = Logger(dir=d)
        lg.subscribe(received.append)
        lg.turn(n=1)
        lg.close()
    turn_events = [e for e in received if e["phase"] == "turn"]
    assert len(turn_events) == 1
    assert "session_id" in turn_events[0]
```

- [ ] **Step 2: Run tests to verify they fail**

```bash
cd week1_baseline/python/11_tui
uv run pytest tests/test_logger.py -v -k "subscribe"
```

Expected: `AttributeError: 'Logger' object has no attribute 'subscribe'`

- [ ] **Step 3: Update `src/boukensha/logger.py`**

Add `self._subscribers: list[Callable[[dict[str, Any]], None]] = []` to `__init__` after the last existing assignment:

```python
# inside __init__, after self._write_log({"phase": "session_start", ...})
self._subscribers: list = []
```

Add the `subscribe` method after `close()`:

```python
def subscribe(self, callback) -> None:
    self._subscribers.append(callback)
```

Update `_write_log` to broadcast after writing:

```python
def _write_log(self, event: dict[str, Any]) -> None:
    full = {**event, "session_id": self.session_id, "at": _now_iso()}
    line = json.dumps(full)
    self._log_io.write(line + "\n")
    self._log_io.flush()
    for cb in self._subscribers:
        cb(full)
```

Also add `Callable` to the import at the top of the file:

```python
from collections.abc import Callable
```

- [ ] **Step 4: Run tests to verify they pass**

```bash
uv run pytest tests/test_logger.py -v
```

Expected: all logger tests PASS.

- [ ] **Step 5: Commit**

```bash
git add src/boukensha/logger.py tests/test_logger.py
git commit -m "feat: add Logger.subscribe() for live event broadcast"
```

---

### Task 3: Refactor `Repl` for composability

**Files:**
- Modify: `week1_baseline/python/11_tui/src/boukensha/repl.py`
- Modify: `week1_baseline/python/11_tui/tests/test_repl.py`

**Interfaces:**
- Produces:
  - `Repl.on_output(callback: Callable[[str], None]) -> None` — registers a callback. When set, all `print()` calls in `Repl` are replaced by `callback(str)`. Only one callback at a time; calling again replaces the previous.
  - `Repl.handle_command(text: str) -> str | None` — processes a slash command. Returns `"quit"` for `/exit`/`/quit`, `"command"` for `/help`/`/clear`/`/quiet`/`/loud`, `None` if `text` is not a slash command. Output goes through the registered `on_output` callback (or `print` if none).
  - `Repl.run_turn(text: str) -> None` — runs one agent turn for `text`. Output (agent reply + blank line) goes through the registered `on_output` callback (or `print` if none).
  - `Repl.banner` — property returning the banner string (no side effects, no printing).
  - `Repl.model` — property returning `self._model`.
  - `Repl.version` — property returning `self._version`.
  - `Repl.context` — property returning `self._context`.
  - `Repl.logger` — property returning `self._logger`.
  - `Repl.start()` — unchanged public API; internally calls `handle_command` and `run_turn`.

- [ ] **Step 1: Write the failing tests**

Append to the bottom of `week1_baseline/python/11_tui/tests/test_repl.py`:

```python
def test_repl_on_output_routes_banner():
    repl, _, logger = _make_repl()
    received = []
    repl.on_output(received.append)
    try:
        import io
        with patch("sys.stdin", io.StringIO("/exit\n")):
            repl.start()
    finally:
        logger.close()
    all_output = "\n".join(received)
    assert "BOUKENSHA" in all_output


def test_repl_on_output_routes_agent_reply():
    repl, _, logger = _make_repl()
    received = []
    repl.on_output(received.append)
    try:
        import io
        with patch("sys.stdin", io.StringIO("hello\n/exit\n")):
            repl.start()
    finally:
        logger.close()
    all_output = "\n".join(received)
    assert "ok" in all_output


def test_repl_handle_command_exit_returns_quit():
    repl, _, logger = _make_repl()
    try:
        result = repl.handle_command("/exit")
    finally:
        logger.close()
    assert result == "quit"


def test_repl_handle_command_quit_returns_quit():
    repl, _, logger = _make_repl()
    try:
        result = repl.handle_command("/quit")
    finally:
        logger.close()
    assert result == "quit"


def test_repl_handle_command_clear_wipes_history():
    repl, ctx, logger = _make_repl()
    ctx.add_message("user", "earlier message")
    try:
        result = repl.handle_command("/clear")
    finally:
        logger.close()
    assert result == "command"
    assert ctx.messages == []


def test_repl_handle_command_help_returns_command():
    repl, _, logger = _make_repl()
    try:
        result = repl.handle_command("/help")
    finally:
        logger.close()
    assert result == "command"


def test_repl_handle_command_none_for_non_command():
    repl, _, logger = _make_repl()
    try:
        result = repl.handle_command("hello world")
    finally:
        logger.close()
    assert result is None


def test_repl_run_turn_calls_agent_and_routes_output():
    repl, _, logger = _make_repl()
    received = []
    repl.on_output(received.append)
    try:
        repl.run_turn("say hello")
    finally:
        logger.close()
    all_output = "\n".join(received)
    assert "ok" in all_output


def test_repl_properties_exposed():
    repl, ctx, logger = _make_repl(model="claude-haiku-4-5", version="0.1.0")
    try:
        assert repl.model == "claude-haiku-4-5"
        assert repl.version == "0.1.0"
        assert repl.context is ctx
        assert repl.logger is logger
        assert "BOUKENSHA" in repl.banner
    finally:
        logger.close()
```

- [ ] **Step 2: Run tests to verify they fail**

```bash
cd week1_baseline/python/11_tui
uv run pytest tests/test_repl.py -v -k "on_output or handle_command or run_turn or properties"
```

Expected: `AttributeError: 'Repl' object has no attribute 'on_output'` (and similar failures).

- [ ] **Step 3: Update `src/boukensha/repl.py`**

Replace the entire file with:

```python
"""Boukensha::Repl port: interactive session loop.

Wraps the same primitives as a single boukensha.run() call but stays alive:
reads a task from stdin, runs the agent, prints the reply, and loops back.
The Context is shared across every turn so conversation history accumulates.
"""

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
            f"  /exit or /quit    leave the REPL\n"
        )
```

- [ ] **Step 4: Run all tests to verify they pass**

```bash
uv run pytest tests/ -v
```

Expected: all tests PASS (including all pre-existing repl tests).

- [ ] **Step 5: Commit**

```bash
git add src/boukensha/repl.py tests/test_repl.py
git commit -m "feat: refactor Repl to expose on_output/handle_command/run_turn and public properties"
```

---

### Task 4: Create `boukensha/tui.py` — Textual App

**Files:**
- Create: `week1_baseline/python/11_tui/src/boukensha/tui.py`

**Interfaces:**
- Consumes:
  - `Repl.on_output(cb)`, `Repl.handle_command(text) -> str | None`, `Repl.run_turn(text) -> None`
  - `Repl.banner: str`, `Repl.model: str | None`, `Repl.version: str | None`, `Repl.context` (has `.tool_count` and `.working_dir`)
  - `Repl.logger` (has `.subscribe(cb)`)
  - `Logger.subscribe(callback: Callable[[dict], None]) -> None`
- Produces:
  - `Tui(repl: Repl)` — a `textual.app.App` subclass. Call `Tui(repl).run()` to launch.
  - Four-zone layout: scrollable `RichLog` (conversation), `Label#progress` (spinner/idle), `Input#input` (prompt), `Label#status` (always-on bar).
  - Spinner: `⠋ ⠙ ⠹ ⠸ ⠼ ⠴ ⠦ ⠧ ⠇ ⠏`, advancing every 60ms via `set_interval`.
  - `Escape` cancels the running agent future (raises `CancelledError` in the thread).
  - `Ctrl+L` calls `repl.handle_command("/clear")` and resets turn count.
  - `Page Up` / `Page Down` scroll the `RichLog`.
  - `Ctrl+C` / `Ctrl+D` exits the app.

Note: `Tui` is not unit-tested (requires a running Textual event loop). Verify manually by running the example.

- [ ] **Step 1: Create `src/boukensha/tui.py`**

Create `week1_baseline/python/11_tui/src/boukensha/tui.py`:

```python
"""Boukensha TUI — Textual four-zone terminal UI wrapping Repl."""

from __future__ import annotations

import asyncio
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
        self._session_input_tokens = 0
        self._session_output_tokens = 0
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
        loop = asyncio.get_event_loop()
        self._future = loop.run_in_executor(None, self._run_turn_sync, text)

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
            self._session_input_tokens += itu
            self._session_output_tokens += otu

    def _on_repl_output(self, text: str) -> None:
        self.call_from_thread(self._append_to_log, text)

    def _append_to_log(self, text: str) -> None:
        self.query_one("#log", RichLog).write(text)

    def _on_turn_complete(self) -> None:
        self._live = self._idle_state()
        self._turn_count += 1

    def _on_turn_error(self, message: str) -> None:
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
            label.update(
                f"{frame} {action}  "
                f"(iter {iteration}/{MAX_ITERATIONS} · {elapsed}s · "
                f"↑ {itok} · ↓ {otok} · {calls} calls)"
            )
            label.add_class("active")
        else:
            used = _fmt_tokens(self._session_input_tokens)
            label.update(f"  [ready]   ctx {used}   {self._turn_count} turns")
            label.remove_class("active")

    def _refresh_status(self) -> None:
        import datetime

        label = self.query_one("#status", Label)
        ver = self._repl.version or "?.?.?"
        model = self._repl.model or "(model)"
        used = _fmt_tokens(self._session_input_tokens)
        tool_count = len(self._repl.context.tools)
        clock = datetime.datetime.now().strftime("%H:%M:%S")
        label.update(
            f" boukensha v{ver} · {model}  ·  ctx {used}  ·  {tool_count} tools  ·  {clock} "
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

- [ ] **Step 2: Verify the module imports cleanly**

```bash
cd week1_baseline/python/11_tui
uv run python -c "from boukensha.tui import Tui; print('ok')"
```

Expected: `ok`

- [ ] **Step 3: Run the full test suite (no regressions)**

```bash
uv run pytest tests/ -v
```

Expected: all tests PASS.

- [ ] **Step 4: Commit**

```bash
git add src/boukensha/tui.py
git commit -m "feat: add Tui Textual App with four-zone layout and live progress"
```

---

### Task 5: Wire `tui=True` into `boukensha.repl()` and export `Tui`

**Files:**
- Modify: `week1_baseline/python/11_tui/src/boukensha/__init__.py`
- Modify: `week1_baseline/python/11_tui/tests/test_run_dsl.py`

**Interfaces:**
- Consumes: `Tui(repl: Repl)` from `boukensha.tui` (Task 4)
- Produces:
  - `boukensha.repl(*, tui: bool = True, ...)` — when `tui=True`, wraps the constructed `Repl` in `Tui` and calls `Tui(repl).run()`. When `tui=False`, calls `repl.start()` as before.
  - `boukensha.Tui` is importable and in `__all__`.

- [ ] **Step 1: Write the failing tests**

Append to the bottom of `week1_baseline/python/11_tui/tests/test_run_dsl.py`:

```python
def test_tui_exported():
    import boukensha
    assert hasattr(boukensha, "Tui")
    from boukensha.tui import Tui
    assert boukensha.Tui is Tui


def test_repl_tui_false_calls_repl_start(monkeypatch, tmp_path):
    import yaml, os
    bdir = tmp_path / "bdir"
    bdir.mkdir()
    settings = {"tasks": {"player": {"provider": "anthropic", "model": "claude-haiku-4-5"}}}
    (bdir / "settings.yaml").write_text(yaml.dump(settings))
    (bdir / ".env").write_text("ANTHROPIC_API_KEY=test-key\n")
    monkeypatch.setenv("BOUKENSHA_DIR", str(bdir))

    started = []

    import boukensha
    from boukensha.repl import Repl as _Repl
    original_start = _Repl.start

    def fake_start(self):
        started.append(True)

    monkeypatch.setattr(_Repl, "start", fake_start)
    try:
        boukensha.repl(tui=False)
    except Exception:
        pass

    assert started, "Repl.start() was not called when tui=False"
```

- [ ] **Step 2: Run tests to verify they fail**

```bash
cd week1_baseline/python/11_tui
uv run pytest tests/test_run_dsl.py -v -k "tui_exported or tui_false"
```

Expected: `AttributeError: module 'boukensha' has no attribute 'Tui'`

- [ ] **Step 3: Update `src/boukensha/__init__.py`**

Add the `Tui` import near the top imports block (after existing imports):

```python
from .tui import Tui
```

Add `"Tui"` to `__all__`.

Find the `repl()` function signature and add the `tui` parameter:

```python
def repl(
    *,
    tui: bool = True,
    system: str | None = None,
    model: str | None = None,
    backend: str | None = None,
    api_key: str | None = None,
    ollama_host: str = "http://localhost:11434",
    log: str | None = None,
    max_output_tokens: int | None = None,
    working_dir: str | bool | None = None,
    allowed_commands: list[str] | None = None,
    shell_timeout: int = 30,
    tool_registrar: Callable[[RunDSL], None] | None = None,
) -> None:
```

Find the end of `repl()` where `_Repl(...).start()` is called. Replace:

```python
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

with:

```python
    repl_instance = _Repl(
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
    )
    try:
        if tui:
            Tui(repl_instance).run()
        else:
            repl_instance.start()
    except KeyboardInterrupt:
        print("\nInterrupted.")
    finally:
        logger.close()
```

- [ ] **Step 4: Run the full test suite**

```bash
uv run pytest tests/ -v
```

Expected: all tests PASS.

- [ ] **Step 5: Commit**

```bash
git add src/boukensha/__init__.py tests/test_run_dsl.py
git commit -m "feat: wire tui=True into boukensha.repl() and export Tui"
```

---

### Task 6: README, example script, and final verification

**Files:**
- Modify: `week1_baseline/python/11_tui/README.md`
- Modify: `week1_baseline/python/11_tui/examples/example.py`

**Interfaces:**
- Produces: documentation and an example that demonstrates TUI launch.

- [ ] **Step 1: Replace README.md**

Replace `week1_baseline/python/11_tui/README.md` with:

```markdown
# Step 11 — A Terminal UI

Boukensha now ships a full terminal UI (TUI) built on [Textual](https://github.com/Textualize/textual). The plain REPL from step 10 is still available with `tui=False`.

## What's new

### `boukensha.Tui`

New class. Wraps a `Repl` instance and replaces its raw `print`/`input` I/O with a structured four-zone display:

```
┌──────────────────────────────────────────────┐
│  conversation viewport (scrollable)           │
├──────────────────────────────────────────────┤
│  ⟳ live progress line (idle when not running) │
├──────────────────────────────────────────────┤
│  boukensha> input box                         │
├──────────────────────────────────────────────┤
│  status line (always-on)                      │
└──────────────────────────────────────────────┘
```

The **progress line** shows a spinner, current action, iteration counter (`n/MAX`), elapsed seconds, token counts (↑ in / ↓ out), and tool call count while the agent is running. When idle it shows context usage and turn count.

The **status line** always shows: version · model · context tokens used · registered tool count · wall-clock time.

**Keyboard shortcuts:**

| Key | Action |
|-----|--------|
| `Enter` | Submit input or slash command |
| `Esc` | Interrupt the running agent turn |
| `Ctrl+L` | Clear conversation history |
| `PgUp` / `PgDn` | Scroll conversation viewport |
| `Ctrl+C` / `Ctrl+D` | Quit |

### `boukensha.repl()` — new `tui:` keyword

```python
boukensha.repl(tui=True)   # default — launches Textual TUI
boukensha.repl(tui=False)  # falls back to plain terminal REPL
```

### `Repl` refactored for composability

`Repl` now exposes three methods so `Tui` (or any other front-end) can drive it:

| Method | Purpose |
|--------|---------|
| `on_output(callback)` | Route all REPL output through a callback instead of stdout |
| `handle_command(text)` | Process a slash command; returns `"quit"`, `"command"`, or `None` |
| `run_turn(text)` | Run one agent turn and route the result through `on_output` |

`banner`, `logger`, `context`, `model`, and `version` are also exposed as properties.

### `Logger.subscribe()`

```python
logger.subscribe(lambda event: ...)
```

Every structured log event is now broadcast to all registered subscribers. `Tui` uses this to update the live progress line in real time.

## Run

```sh
cd week1_baseline/python/11_tui
uv sync

# TUI (default):
uv run python examples/example.py

# Plain REPL:
uv run python examples/example.py --no-tui
```

## Tests

```sh
uv run pytest tests/ -v
```
```

- [ ] **Step 2: Replace the example script**

Replace `week1_baseline/python/11_tui/examples/example.py` with:

```python
#!/usr/bin/env python
"""Step 11 — TUI demo.

Launches the Textual TUI by default.  Pass --no-tui for the plain REPL.
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
)
```

- [ ] **Step 3: Run the full test suite one final time**

```bash
cd week1_baseline/python/11_tui
uv run pytest tests/ -v
```

Expected: all tests PASS.

- [ ] **Step 4: Commit**

```bash
git add README.md examples/example.py
git commit -m "docs: add step 11 README and TUI example script"
```

---

## Self-Review

### Spec coverage

| Requirement (from design spec) | Task | Status |
|---|---|---|
| Four-zone Textual layout: RichLog, progress Label, Input, status Label | Task 4 | ✓ |
| Spinner cycling every 60ms | Task 4 (`set_interval(TICK_S, ...)`) | ✓ |
| Agent runs in thread pool executor | Task 4 (`run_in_executor`) | ✓ |
| `Logger.subscribe(callback)` for live events | Task 2 | ✓ |
| `call_from_thread` for safe UI updates from agent thread | Task 4 | ✓ |
| `Repl.on_output`, `handle_command`, `run_turn` | Task 3 | ✓ |
| `Repl.banner`, `model`, `version`, `context`, `logger` as properties | Task 3 | ✓ |
| `boukensha.repl(tui=True)` launches TUI; `tui=False` uses plain REPL | Task 5 | ✓ |
| `Tui` exported from `boukensha` | Task 5 | ✓ |
| `textual>=0.80` added to dependencies | Task 1 | ✓ |
| Keyboard: Enter, Esc, Ctrl+L, PgUp/Dn, Ctrl+C/D | Task 4 (BINDINGS) | ✓ |
| Progress line: spinner + action + iter/elapsed/tokens/calls | Task 4 (`_refresh_progress`) | ✓ |
| Status bar: version · model · ctx · tools · clock | Task 4 (`_refresh_status`) | ✓ |
| Idle progress line: `[ready] ctx N turns` | Task 4 | ✓ |
| All step 10 tests continue passing | Every task's final pytest run | ✓ |
| `tui=False` fallback — no Textual import exercised | Task 5 (lazy import path) | ✓ |

### Placeholder scan

No "TBD", "TODO", "similar to Task N", or incomplete steps — every step contains runnable commands or complete code.

### Type consistency

- `Logger.subscribe(callback)` defined in Task 2; called in `Tui.__init__` as `self._repl.logger.subscribe(self._on_logger_event_from_thread)` in Task 4 ✓
- `Repl.on_output(cb)` defined in Task 3; called in `Tui.on_mount` as `self._repl.on_output(self._on_repl_output)` in Task 4 ✓
- `Repl.handle_command(text)` returns `"quit" | "command" | None` in Task 3; checked with `== "quit"` and `== "command"` in Task 4 ✓
- `Repl.run_turn(text)` defined in Task 3; called as `self._repl.run_turn(text)` in `_run_turn_sync` in Task 4 ✓
- `Tui(repl_instance).run()` in Task 5 matches `Tui.__init__(self, repl: Repl)` in Task 4 ✓
