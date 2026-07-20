# Step 07 — The Run DSL Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add a single top-level `boukensha.run()` function that wires together every primitive (Config, Context, Registry, backend, PromptBuilder, Client, Logger, Agent) behind one call and a `tool()` registration closure — replacing the ~20 lines of manual plumbing from step 06 with one expressive call.

**Architecture:** `boukensha.run()` is a module-level function in `src/boukensha/__init__.py` that accepts keyword arguments describing *what* to do, creates all internal objects, yields control to a caller-supplied `RunDSL` context manager for tool registration, then executes `Agent.run()` and returns the final text. `RunDSL` is a tiny helper class (single file) that exposes only the `tool()` method as a context-manager `__enter__`/`__exit__` pair, keeping the DSL surface intentionally minimal. This step adds exactly two new files (`run_dsl.py` and a `prompts/system.md` copy) and modifies `__init__.py`; everything else is inherited unchanged from step 06.

**Tech Stack:** Python ≥ 3.11, uv, pytest, existing `boukensha` package from step 06 (Config, Context, Registry, PromptBuilder, Client, Logger, Agent, backends, tasks).

## Global Constraints

- Copy the full `src/boukensha/` package from `week1_baseline/python/06_the_logger/src/boukensha/` — no changes to any existing module.
- Reuse step 06's `pyproject.toml` verbatim; update `name` to `"boukensha-run-dsl"` and `description` to `"Boukensha run DSL (Step 7)"`.
- Python ≥ 3.11.
- No new runtime dependencies beyond what step 06 already uses (`pyyaml`, `python-dotenv`).
- Keep the `RunDSL` DSL surface to exactly one public method: `tool()`.
- `boukensha.run()` must call `logger.close()` in a `finally` block (mirrors Ruby's `ensure`).
- The `BOUKENSHA_DIR` env variable must be set to the project-local `.boukensha` directory before `Config` is constructed (same pattern as step 06 `example.py`).
- Session JSONL files go to `.boukensha/sessions/` by default, overridable with the `log:` kwarg.
- Tests run with: `cd week1_baseline/python/07_the_run_dsl && uv run pytest tests/ -v`

---

## File Structure

```
week1_baseline/python/07_the_run_dsl/
├── pyproject.toml                         modify: update name + description
├── prompts/
│   └── system.md                          create: copy from 06_the_logger/prompts/system.md
├── src/
│   └── boukensha/
│       ├── __init__.py                    modify: add run(), expose RunDSL in __all__
│       ├── run_dsl.py                     create: RunDSL class + tool() context-manager helper
│       ├── agent.py                       copy from 06 (no changes)
│       ├── client.py                      copy from 06 (no changes)
│       ├── config.py                      copy from 06 (no changes)
│       ├── context.py                     copy from 06 (no changes)
│       ├── errors.py                      copy from 06 (no changes)
│       ├── logger.py                      copy from 06 (no changes)
│       ├── message.py                     copy from 06 (no changes)
│       ├── prompt_builder.py              copy from 06 (no changes)
│       ├── registry.py                    copy from 06 (no changes)
│       ├── tool.py                        copy from 06 (no changes)
│       ├── backends/                      copy from 06 (no changes)
│       └── tasks/                         copy from 06 (no changes)
├── examples/
│   └── example.py                         create: demo using boukensha.run()
└── tests/
    ├── __init__.py                        create: empty
    └── test_run_dsl.py                    create: tests for RunDSL and boukensha.run()
```

---

### Task 1: Scaffold the project from step 06

**Files:**
- Modify: `week1_baseline/python/07_the_run_dsl/pyproject.toml`
- Create: `week1_baseline/python/07_the_run_dsl/prompts/system.md`
- Create: `week1_baseline/python/07_the_run_dsl/src/boukensha/` (full package copy)
- Create: `week1_baseline/python/07_the_run_dsl/tests/__init__.py`

**Interfaces:**
- Produces: a working `uv sync` + `uv run pytest` baseline identical to step 06.

- [ ] **Step 1: Copy the full package from step 06**

```bash
cd week1_baseline/python/07_the_run_dsl
cp -r ../06_the_logger/src .
cp -r ../06_the_logger/tests .
cp -r ../06_the_logger/prompts .
cp ../06_the_logger/pyproject.toml .
cp ../06_the_logger/uv.lock .
```

- [ ] **Step 2: Update pyproject.toml name and description**

Edit `week1_baseline/python/07_the_run_dsl/pyproject.toml`:

```toml
[project]
name = "boukensha-run-dsl"
version = "0.1.0"
description = "Boukensha run DSL (Step 7)"
requires-python = ">=3.11"
dependencies = [
    "pyyaml>=6.0",
    "python-dotenv>=1.0",
]

[tool.uv]
package = true

[build-system]
requires = ["hatchling"]
build-backend = "hatchling.build"

[tool.hatch.build.targets.wheel]
packages = ["src/boukensha"]
```

- [ ] **Step 3: Install dependencies**

Run: `cd week1_baseline/python/07_the_run_dsl && uv sync`
Expected: resolves without errors, `.venv` created.

- [ ] **Step 4: Confirm copied tests still pass**

Run: `cd week1_baseline/python/07_the_run_dsl && uv run pytest tests/ -v`
Expected: all tests that passed in step 06 pass here too.

- [ ] **Step 5: Commit**

```bash
git add week1_baseline/python/07_the_run_dsl/
git commit -m "chore: scaffold step 07 from step 06 baseline"
```

---

### Task 2: Create `RunDSL`

**Files:**
- Create: `week1_baseline/python/07_the_run_dsl/src/boukensha/run_dsl.py`
- Create: `week1_baseline/python/07_the_run_dsl/tests/test_run_dsl.py`

**Interfaces:**
- Produces:
  - `RunDSL(registry: Registry)` — constructor
  - `RunDSL.tool(name: str, description: str, parameters: dict | None = None, *, block: Callable) -> Tool` — registers a tool on the registry

- [ ] **Step 1: Write the failing test**

Create `week1_baseline/python/07_the_run_dsl/tests/test_run_dsl.py`:

```python
from __future__ import annotations

from unittest.mock import MagicMock

from boukensha.run_dsl import RunDSL
from boukensha.context import Context
from boukensha.registry import Registry
from boukensha.tasks.player import Player


def _make_registry() -> Registry:
    ctx = Context(task=Player, system="sys")
    return Registry(ctx)


def test_run_dsl_registers_tool():
    registry = _make_registry()
    dsl = RunDSL(registry)
    dsl.tool("greet", description="Say hello", parameters={"name": {"type": "string"}}, block=lambda name: f"Hi {name}")
    assert "greet" in registry._context.tools


def test_run_dsl_tool_is_callable():
    registry = _make_registry()
    dsl = RunDSL(registry)
    dsl.tool("double", description="Double a number", parameters={"n": {"type": "integer"}}, block=lambda n: n * 2)
    result = registry.dispatch("double", {"n": 5})
    assert result == 10


def test_run_dsl_tool_no_parameters():
    registry = _make_registry()
    dsl = RunDSL(registry)
    dsl.tool("ping", description="Ping", block=lambda: "pong")
    result = registry.dispatch("ping", {})
    assert result == "pong"
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd week1_baseline/python/07_the_run_dsl && uv run pytest tests/test_run_dsl.py -v`
Expected: FAIL with `ModuleNotFoundError: No module named 'boukensha.run_dsl'`

- [ ] **Step 3: Create `run_dsl.py`**

Create `week1_baseline/python/07_the_run_dsl/src/boukensha/run_dsl.py`:

```python
"""RunDSL: the object that ``self`` becomes inside a ``boukensha.run`` block.

Exposes only ``tool()``, keeping the DSL surface intentionally minimal so
callers cannot reach internal state.
"""

from __future__ import annotations

from collections.abc import Callable
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from .registry import Registry
    from .tool import Tool


class RunDSL:
    def __init__(self, registry: Registry) -> None:
        self._registry = registry

    def tool(
        self,
        name: str,
        description: str,
        parameters: dict[str, Any] | None = None,
        *,
        block: Callable[..., Any],
    ) -> Tool:
        return self._registry.tool(name, description, parameters, block=block)
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `cd week1_baseline/python/07_the_run_dsl && uv run pytest tests/test_run_dsl.py -v`
Expected: 3 PASSED

- [ ] **Step 5: Commit**

```bash
git add week1_baseline/python/07_the_run_dsl/src/boukensha/run_dsl.py \
        week1_baseline/python/07_the_run_dsl/tests/test_run_dsl.py
git commit -m "feat: add RunDSL class for tool registration"
```

---

### Task 3: Add `boukensha.run()` to `__init__.py`

**Files:**
- Modify: `week1_baseline/python/07_the_run_dsl/src/boukensha/__init__.py`
- Modify: `week1_baseline/python/07_the_run_dsl/tests/test_run_dsl.py` (extend with run() tests)

**Interfaces:**
- Consumes:
  - `RunDSL(registry)` from `run_dsl.py`
  - `Config()`, `Context(task, system)`, `Registry(ctx)`, `PromptBuilder(ctx, be)`, `Client(builder)`, `Logger(log=, snapshot={})`, `Agent(context, registry, builder, client, logger, task_settings, max_iterations, max_output_tokens)` — all from existing modules
  - `Tasks.Player` — from `boukensha.tasks.player`
  - `Backends.Anthropic/OpenAI/Gemini/Ollama/OllamaCloud` — from `boukensha.backends.*`
- Produces:
  - `boukensha.run(task, *, system, model, backend, api_key, ollama_host, log, max_output_tokens, **tool_defs) -> str`
  - `RunDSL` exported in `__all__`

- [ ] **Step 1: Write failing tests for `boukensha.run()`**

Append to `week1_baseline/python/07_the_run_dsl/tests/test_run_dsl.py`:

```python
import boukensha


def test_run_is_callable():
    assert callable(boukensha.run)


def test_run_dsl_exported():
    from boukensha import RunDSL
    assert RunDSL is not None


def test_run_returns_text(monkeypatch):
    """boukensha.run() must return the agent's final text without error."""
    import os
    import tempfile
    from unittest.mock import MagicMock, patch

    # Provide a minimal .boukensha config so Config() doesn't fail
    with tempfile.TemporaryDirectory() as tmp:
        os.environ["BOUKENSHA_DIR"] = tmp

        # Write a minimal settings.yaml
        import yaml
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

        # Patch the Agent so no real HTTP call is made
        fake_agent = MagicMock()
        fake_agent.run.return_value = "mocked result"

        with patch("boukensha.Agent", return_value=fake_agent) as MockAgent:
            result = boukensha.run(
                task="What is 2+2?",
                log=f"{tmp}/test-session.jsonl",
            )

        assert result == "mocked result"
        fake_agent.run.assert_called_once()
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd week1_baseline/python/07_the_run_dsl && uv run pytest tests/test_run_dsl.py::test_run_is_callable -v`
Expected: FAIL with `AttributeError: module 'boukensha' has no attribute 'run'`

- [ ] **Step 3: Update `__init__.py` with `run()` function and `RunDSL` export**

Replace the full content of `week1_baseline/python/07_the_run_dsl/src/boukensha/__init__.py`:

```python
"""Boukensha agent loop."""

from __future__ import annotations

import os
from typing import Any

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
from .run_dsl import RunDSL
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
    "RunDSL",
    "Tool",
    "UnknownToolError",
    "UnsupportedModelError",
    "backends",
    "debug",
    "enable_debug",
    "run",
    "tasks",
]

__version__ = "0.1.0"

_debug: bool = False


def enable_debug() -> None:
    global _debug
    _debug = True


def debug() -> bool:
    return _debug


def run(
    task: str,
    *,
    system: str | None = None,
    model: str | None = None,
    backend: str | None = None,
    api_key: str | None = None,
    ollama_host: str = "http://localhost:11434",
    log: str | None = None,
    max_output_tokens: int | None = None,
    tool_registrar: Any = None,
) -> str:
    """Wire together every primitive and run the agent loop.

    The caller supplies *what* to do (task text + optional tools via a
    ``RunDSL`` closure); this function handles all plumbing.

    Args:
        task: The user message handed to the agent.
        system: System prompt. Defaults to the Player task's prompt from Config.
        model: Model name. Defaults to the player task's model from settings.yaml.
        backend: Provider name string — "anthropic", "openai", "gemini", "ollama",
            or "ollama_cloud". Defaults to the player task's provider from settings.yaml.
        api_key: API key for the chosen backend. Defaults to the matching
            ``ANTHROPIC_API_KEY`` / ``OPENAI_API_KEY`` / ``GEMINI_API_KEY`` /
            ``OLLAMA_API_KEY`` env var.
        ollama_host: Ollama base URL. Defaults to "http://localhost:11434".
        log: Optional JSONL path override. Defaults to
            ``.boukensha/sessions/<session-id>.jsonl``.
        max_output_tokens: Per-reply output cap. Defaults to the player task's
            setting (1024).
        tool_registrar: A callable that accepts a ``RunDSL`` and registers tools
            on it. Typical usage is via the module-level ``run()`` function
            called with a helper; the example script uses a plain function.

    Returns:
        The agent's final text response.
    """
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
    agent = Agent(
        context=ctx,
        registry=registry,
        builder=builder,
        client=client,
        logger=logger,
        task_settings=task_settings,
        max_iterations=effective_max_iterations,
        max_output_tokens=effective_max_output_tokens,
    )

    ctx.add_message("user", task)
    try:
        return agent.run()
    finally:
        logger.close()
```

- [ ] **Step 4: Run all tests**

Run: `cd week1_baseline/python/07_the_run_dsl && uv run pytest tests/ -v`
Expected: all tests PASS (including the 3 from Task 2 and the new run() tests).

- [ ] **Step 5: Commit**

```bash
git add week1_baseline/python/07_the_run_dsl/src/boukensha/__init__.py \
        week1_baseline/python/07_the_run_dsl/tests/test_run_dsl.py
git commit -m "feat: add boukensha.run() DSL entry point"
```

---

### Task 4: Write the example script

**Files:**
- Create: `week1_baseline/python/07_the_run_dsl/examples/example.py`

**Interfaces:**
- Consumes: `boukensha.run(task, tool_registrar=)` from `__init__.py`
- Produces: a runnable script that mirrors `ruby/07_the_run_dsl/examples/example.rb`

- [ ] **Step 1: Write the example**

Create `week1_baseline/python/07_the_run_dsl/examples/example.py`:

```python
import os
from pathlib import Path

os.environ.setdefault(
    "BOUKENSHA_DIR",
    str((Path(__file__).parent.parent.parent.parent.parent / ".boukensha").resolve()),
)

import boukensha
from boukensha import Config

base_dir = Path(__file__).parent.parent.resolve()

print("=== BOUKENSHA Step 7: The Boukensha.run DSL ===")
print()
print(f"Config: {Config()}")
print()


def register_tools(dsl):
    dsl.tool(
        "read_file",
        description="Read the contents of a file from disk",
        parameters={"path": {"type": "string", "description": "The file path to read"}},
        block=lambda path: (base_dir / path).read_text(),
    )
    dsl.tool(
        "list_directory",
        description="List the files in a directory",
        parameters={"path": {"type": "string", "description": "The directory path to list"}},
        block=lambda path: ", ".join(
            f for f in os.listdir(base_dir / path) if not f.startswith(".")
        ),
    )


result = boukensha.run(
    task="Read the README.md file and summarise what this MUD player assistant framework can do.",
    tool_registrar=register_tools,
)

print()
print("=== FINAL RESPONSE ===")
print(result)
```

- [ ] **Step 2: Verify the example imports cleanly (no API call)**

Run: `cd week1_baseline/python/07_the_run_dsl && uv run python -c "import examples.example" 2>&1 | head -5 || true`

This will fail at runtime when it tries to connect (no settings.yaml) but must not fail with an `ImportError`. The output should show the import succeeds or stops only at Config loading, not at import time.

Actually run the dry-import check:
```bash
cd week1_baseline/python/07_the_run_dsl && uv run python -c "
import sys
sys.path.insert(0, 'src')
from boukensha.run_dsl import RunDSL
from boukensha import run
print('imports ok')
"
```
Expected output: `imports ok`

- [ ] **Step 3: Run all tests one final time**

Run: `cd week1_baseline/python/07_the_run_dsl && uv run pytest tests/ -v`
Expected: all tests PASS.

- [ ] **Step 4: Commit**

```bash
git add week1_baseline/python/07_the_run_dsl/examples/example.py
git commit -m "feat: add step 07 example script using boukensha.run() DSL"
```

---

## Self-Review

### Spec coverage

| Ruby feature | Plan task |
|---|---|
| `Boukensha::RunDSL` class | Task 2 |
| `RunDSL#tool` registers via registry | Task 2 |
| `Boukensha.run` wires all primitives | Task 3 |
| `task:` required kwarg | Task 3 |
| `system:` defaults to Config | Task 3 |
| `model:` defaults to Config | Task 3 |
| `backend:` defaults to Config | Task 3 |
| `api_key:` per-backend env var fallback | Task 3 |
| `ollama_host:` kwarg | Task 3 |
| `log:` optional JSONL path override | Task 3 |
| `max_output_tokens:` kwarg | Task 3 |
| `logger.close()` in `ensure`/`finally` | Task 3 |
| Session snapshot written to JSONL | Task 3 |
| Example script (`examples/example.rb` → `example.py`) | Task 4 |
| `read_file` + `list_directory` tools in example | Task 4 |

### Placeholder scan

No TBDs, TODOs, or "similar to Task N" references — every step includes full code.

### Type consistency

- `RunDSL.tool` signature matches `Registry.tool` exactly (name, description, parameters, block).
- `boukensha.run()` passes `task_settings` as a `dict` to `Agent`, consistent with step 06.
- `Logger` is constructed with `log=` and `snapshot=` keyword args, matching step 06's `Logger.__init__` signature.
- `Config.PROMPTS_DIR` referenced in Task 3 is a class attribute defined in `config.py` (confirmed present in step 06).
