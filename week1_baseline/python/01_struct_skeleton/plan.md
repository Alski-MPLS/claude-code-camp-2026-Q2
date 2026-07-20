# 01 · Struct Skeleton (Python) Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Port `ruby/01_struct_skeleton` to Python as `python/01_struct_skeleton` — a
standalone `uv` package that carries `Config`/`Base`/`Player` forward from
`python/00_config` unchanged (minus one dropped constant) and adds three new
data structures: `Tool`, `Message`, `Context`.

**Architecture:** Each numbered step under `week1_baseline/python/` is a
self-contained `uv` project — it does not import from sibling step
directories. Step 01 therefore re-creates (copies forward) the `Config`,
`Base`, and `Player` files from `00_config` verbatim, then adds the new
struct-equivalents. This mirrors the Ruby original, where `01_struct_skeleton`
has its own `Gemfile` and its own copy of `lib/boukensha/config.rb`.

**Tech Stack:** Python 3.11+, `uv` for dependency management, `pyyaml` +
`python-dotenv` (same two deps as `00_config` — no new dependencies needed for
this step; `dataclasses` and `pathlib` are stdlib).

## Global Constraints

- Python 3.11+, dependency-managed via `uv` (`pyproject.toml`, `uv sync`) — exact same toolchain decision as `00_config`.
- Dependencies stay at exactly `pyyaml>=6.0` and `python-dotenv>=1.0` — no new third-party packages are needed for structs.
- No automated test suite. The Ruby original has none, and `00_config`'s plan explicitly matched that scope (`plan.md` line: "Ruby version has no test suite; match that scope for the port"). Verification here is a manual run of `examples/example.py`, diffed against the Ruby example's output. If a future step adds `pytest`, add it there — not retroactively here.
- Ruby `Struct.new(...)` → Python `@dataclass`. This is the direct idiomatic equivalent: both are lightweight, positional-or-keyword field containers with auto-generated `__init__`/equality. Use plain (non-frozen) dataclasses since Ruby `Struct` instances are mutable.
- Ruby's `#to_s` override → Python's `__str__` override (not `__repr__`), because every one of the Ruby classes is only ever interpolated with `#{obj}` / `puts obj`, which calls `to_s`. Python's `str(obj)` / f-string `{obj}` calls `__str__` the same way.
- `Context` stays a plain class with `__init__`, not a dataclass — it has behavior (`register_tool`, `add_message`) and derived properties (`tool_count`, `turn_count`), matching the precedent set by `Config` in `00_config` (stateful classes stay hand-written classes; only pure data holders become dataclasses/Structs).
- `python/01_struct_skeleton` does not have a `prompts/` directory of its own, and `Config` in this step drops the `PROMPTS_DIR` class attribute. This matches the Ruby original exactly — `diff ruby/00_config/lib/boukensha/config.rb ruby/01_struct_skeleton/lib/boukensha/config.rb` shows only the `PROMPTS_DIR` constant removed, nothing else changed. `examples/example.py` in this step calls `system_prompt` without a `default_prompts_dir`, so it will print `None` unless a user-level prompt override file exists — matching the Ruby example.
- Truncation lengths must match Ruby's inclusive-range slicing exactly: `description.to_s[0..40]` (41 chars) → Python `description[:41]`; `content.to_s[0..60]` (61 chars) → Python `content[:61]`.

## File Structure

```
python/01_struct_skeleton/
  pyproject.toml            # project metadata + deps, copied from 00_config, description bumped
  README.md                 # usage docs for this step
  plan.md                   # this file
  prompts/                  # intentionally absent — matches Ruby 01_struct_skeleton
  src/boukensha/
    __init__.py              # re-exports Config, Context, Message, Tool, tasks
    config.py                 # Config class, copied from 00_config minus PROMPTS_DIR
    tool.py                    # Tool dataclass (new)
    message.py                 # Message dataclass (new)
    context.py                 # Context class (new)
    tasks/
      __init__.py
      base.py                  # Base task class, copied from 00_config unchanged
      player.py                # Player(Base), copied from 00_config unchanged
  examples/
    example.py                # runnable smoke-test, ported from ruby examples/example.rb
```

---

### Task 1: Scaffold the `uv` project

**Files:**
- Create: `python/01_struct_skeleton/pyproject.toml`
- Create: `python/01_struct_skeleton/src/boukensha/__init__.py` (placeholder, filled in Task 6)
- Create: `python/01_struct_skeleton/examples/` (empty dir, populated in Task 7)

**Interfaces:**
- Produces: an importable `boukensha` package installed editable via `uv sync`, ready for Tasks 2–7 to add modules into `src/boukensha/`.

- [ ] **Step 1: Create `pyproject.toml`**

```toml
[project]
name = "boukensha"
version = "0.1.0"
description = "Boukensha struct skeleton (Step 1)"
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

- [ ] **Step 2: Create an empty package placeholder**

Create `python/01_struct_skeleton/src/boukensha/__init__.py` with just:

```python
```

(empty file — real content added in Task 6, once `Config`, `Context`, `Message`, `Tool` exist to export)

- [ ] **Step 3: Run `uv sync` and verify the environment builds**

Run: `cd python/01_struct_skeleton && uv sync`
Expected: creates `.venv/`, installs `pyyaml` and `python-dotenv`, no errors.

- [ ] **Step 4: Commit**

```bash
git add python/01_struct_skeleton/pyproject.toml python/01_struct_skeleton/src/boukensha/__init__.py
git commit -m "chore: scaffold python/01_struct_skeleton uv project"
```

---

### Task 2: Port `Config` and the task classes forward

**Files:**
- Create: `python/01_struct_skeleton/src/boukensha/config.py`
- Create: `python/01_struct_skeleton/src/boukensha/tasks/__init__.py`
- Create: `python/01_struct_skeleton/src/boukensha/tasks/base.py`
- Create: `python/01_struct_skeleton/src/boukensha/tasks/player.py`

**Interfaces:**
- Consumes: nothing (self-contained copy-forward from `00_config`).
- Produces: `Config` (class, no `PROMPTS_DIR` attribute), `Base` (abstract task base), `Player(Base)` with `TASK_NAME = "player"`. These are used by `Context` (Task 5) and `examples/example.py` (Task 7).

- [ ] **Step 1: Write `config.py`, identical to `00_config`'s but without `PROMPTS_DIR`**

```python
"""Boukensha::Config port: resolves the ``.boukensha`` config directory and
loads its ``.env`` and ``settings.yaml`` files.
"""

from __future__ import annotations

import os
from pathlib import Path
from typing import Any

import yaml
from dotenv import load_dotenv


class Config:
    # The .boukensha config directory is resolved in this order:
    #   1. BOUKENSHA_DIR environment variable (set before loading .env)
    #   2. ~/.boukensha (default)
    DEFAULT_DIR = str(Path.home() / ".boukensha")

    def __init__(self) -> None:
        self.dir = self._resolve_dir()
        self._load_env()
        self.settings: dict[str, Any] = self._load_settings()

    # ---------- tasks -----------------------------------------------------

    def tasks(self, name: str | None = None) -> dict[str, Any]:
        """With no argument: returns the full tasks dict from settings.yaml.
        With a name: returns that task's settings dict, e.g. tasks("player").
        """
        all_tasks = self.dig("tasks") or {}
        return (all_tasks.get(name) or {}) if name else all_tasks

    @property
    def user_prompts_dir(self) -> str:
        """The user's prompts directory for task prompt overrides."""
        return str(Path(self.dir) / "prompts")

    # ---------- MUD connection ----------------------------------------------

    @property
    def mud_host(self) -> str:
        return self.dig("mud", "host") or "localhost"

    @property
    def mud_port(self) -> int:
        return self.dig("mud", "port") or 4000

    @property
    def mud_username(self) -> str | None:
        return self.dig("mud", "username")

    @property
    def mud_password(self) -> str | None:
        return self.dig("mud", "password")

    # ---------- low-level helpers -------------------------------------------

    def dig(self, *keys: str) -> Any:
        """Fetch a nested key path from settings, e.g. dig("mud", "host")."""
        node: Any = self.settings
        for key in keys:
            if isinstance(node, dict):
                node = node.get(key)
            else:
                return None
        return node

    def __repr__(self) -> str:
        return f"Config(dir={self.dir}, tasks={','.join(self.tasks().keys())})"

    # ---------- private -----------------------------------------------------

    def _resolve_dir(self) -> str:
        raw = os.environ.get("BOUKENSHA_DIR") or self.DEFAULT_DIR
        return str(Path(raw).expanduser().resolve())

    def _load_env(self) -> None:
        env_file = Path(self.dir) / ".env"
        if env_file.exists():
            load_dotenv(env_file)

    def _load_settings(self) -> dict[str, Any]:
        settings_file = Path(self.dir) / "settings.yaml"
        if settings_file.exists():
            return yaml.safe_load(settings_file.read_text()) or {}
        return {}
```

- [ ] **Step 2: Write `tasks/base.py`, copied from `00_config` unchanged**

```python
"""Boukensha::Tasks::Base port: an abstract stateless task class.

All behaviour is expressed as classmethods/staticmethods that accept a
``settings`` dict — no instances are created.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any


class Base:
    TASK_NAME: str | None = None

    @classmethod
    def task_name(cls) -> str:
        if cls.TASK_NAME is None:
            raise NotImplementedError(f"{cls.__name__} must define TASK_NAME")
        return cls.TASK_NAME

    @classmethod
    def provider(cls, settings: dict[str, Any]) -> str:
        value = settings.get("provider")
        if not value:
            raise ValueError(f"tasks.{cls.task_name()}.provider is required in settings.yaml")
        return value

    @classmethod
    def model(cls, settings: dict[str, Any]) -> str:
        value = settings.get("model")
        if not value:
            raise ValueError(f"tasks.{cls.task_name()}.model is required in settings.yaml")
        return value

    @classmethod
    def prompt_override(cls, settings: dict[str, Any], prompt: str = "system") -> bool:
        node = settings.get("prompt_override")
        if not isinstance(node, dict):
            return False
        return node.get(prompt) is True

    @classmethod
    def prompt(
        cls,
        settings: dict[str, Any],
        name: str = "system",
        user_prompts_dir: str | None = None,
        default_prompts_dir: str | None = None,
    ) -> str | None:
        if cls.prompt_override(settings, name):
            text = cls._read_user_prompt(name, user_prompts_dir=user_prompts_dir)
            if text is not None:
                return text

        return cls._read_default_prompt(name, default_prompts_dir=default_prompts_dir)

    @classmethod
    def system_prompt(
        cls,
        settings: dict[str, Any],
        user_prompts_dir: str | None = None,
        default_prompts_dir: str | None = None,
    ) -> str | None:
        return cls.prompt(
            settings,
            "system",
            user_prompts_dir=user_prompts_dir,
            default_prompts_dir=default_prompts_dir,
        )

    # ---------- private -----------------------------------------------------

    @classmethod
    def _read_user_prompt(cls, prompt_name: str, user_prompts_dir: str | None = None) -> str | None:
        if not user_prompts_dir:
            return None
        return cls._read_file(Path(user_prompts_dir) / cls.task_name() / f"{prompt_name}.md")

    @classmethod
    def _read_default_prompt(cls, prompt_name: str, default_prompts_dir: str | None = None) -> str | None:
        if not default_prompts_dir:
            return None
        return cls._read_file(Path(default_prompts_dir) / f"{prompt_name}.md")

    @staticmethod
    def _read_file(path: Path) -> str | None:
        return path.read_text().strip() if path.exists() else None
```

- [ ] **Step 3: Write `tasks/player.py`, copied from `00_config` unchanged**

```python
from __future__ import annotations

from .base import Base


class Player(Base):
    TASK_NAME = "player"
```

- [ ] **Step 4: Write `tasks/__init__.py`**

```python
from .base import Base
from .player import Player

__all__ = ["Base", "Player"]
```

- [ ] **Step 5: Verify the package imports**

Run: `cd python/01_struct_skeleton && uv run python -c "from boukensha.config import Config; from boukensha.tasks import Player; print(Config, Player)"`
Expected: prints the two classes, no errors.

- [ ] **Step 6: Commit**

```bash
git add python/01_struct_skeleton/src/boukensha/config.py python/01_struct_skeleton/src/boukensha/tasks/
git commit -m "feat: port Config, Base, Player forward into 01_struct_skeleton"
```

---

### Task 3: Add the `Tool` dataclass

**Files:**
- Create: `python/01_struct_skeleton/src/boukensha/tool.py`

**Interfaces:**
- Produces: `Tool` — fields `name: str`, `description: str`, `parameters: dict[str, Any]`, `block: Callable[..., Any]`; `__str__` returns `#<Tool name=... description=... params=...>`. Consumed by `Context.register_tool` (Task 5) and `examples/example.py` (Task 7).

- [ ] **Step 1: Write `tool.py`**

```python
"""Boukensha::Tool port: an action the agent can invoke.

Ruby represents this with ``Struct.new(:name, :description, :parameters,
:block)``; the direct Python equivalent of a Struct — a lightweight,
auto-``__init__``, mutable field container — is a plain ``@dataclass``.
"""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from typing import Any


@dataclass
class Tool:
    name: str
    description: str
    parameters: dict[str, Any]
    block: Callable[..., Any]

    def __str__(self) -> str:
        return (
            f"#<Tool name={self.name} description={self.description[:41]} "
            f"params={list(self.parameters.keys())}>"
        )
```

- [ ] **Step 2: Verify by hand**

Run:
```bash
cd python/01_struct_skeleton
uv run python -c "
from boukensha.tool import Tool
t = Tool('move', 'Move the player in a direction (north, south, east, west, up, down)', {'direction': {'type': 'string'}}, lambda direction: direction)
print(t)
"
```
Expected: `#<Tool name=move description=Move the player in a direction (north, so params=['direction']>` (41-char truncated description, no `...` suffix — matches Ruby, which doesn't append an ellipsis for Tool).

- [ ] **Step 3: Commit**

```bash
git add python/01_struct_skeleton/src/boukensha/tool.py
git commit -m "feat: add Tool dataclass"
```

---

### Task 4: Add the `Message` dataclass

**Files:**
- Create: `python/01_struct_skeleton/src/boukensha/message.py`

**Interfaces:**
- Produces: `Message` — fields `role: str`, `content: str`, `tool_use_id: str | None = None`; `__str__` returns `#<Message role=... [tool_use_id]? content=......>`. Consumed by `Context.add_message` (Task 5).

- [ ] **Step 1: Write `message.py`**

```python
"""Boukensha::Message port: a single unit of conversation."""

from __future__ import annotations

from dataclasses import dataclass


@dataclass
class Message:
    role: str
    content: str
    tool_use_id: str | None = None

    def __str__(self) -> str:
        id_tag = f" [{self.tool_use_id}]" if self.tool_use_id else ""
        return f"#<Message role={self.role}{id_tag} content={self.content[:61]}...>"
```

- [ ] **Step 2: Verify by hand**

Run:
```bash
cd python/01_struct_skeleton
uv run python -c "
from boukensha.message import Message
print(Message('user', 'Explore north and tell me what you find.'))
print(Message('tool_result', 'You move north.', tool_use_id='toolu_01X'))
"
```
Expected:
```
#<Message role=user content=Explore north and tell me what you find....>
#<Message role=tool_result [toolu_01X] content=You move north....>
```

- [ ] **Step 3: Commit**

```bash
git add python/01_struct_skeleton/src/boukensha/message.py
git commit -m "feat: add Message dataclass"
```

---

### Task 5: Add the `Context` class

**Files:**
- Create: `python/01_struct_skeleton/src/boukensha/context.py`

**Interfaces:**
- Consumes: `Message` (Task 4, `.message`), `Tool` (Task 3, `.tool`), `Base` (Task 2, `.tasks.base`, for the `task` type hint).
- Produces: `Context(task, system=None)` with `.task`, `.system`, `.messages: list[Message]`, `.tools: dict[str, Tool]`, `.register_tool(tool)`, `.add_message(role, content, tool_use_id=None)`, `.tool_count` (property), `.turn_count` (property), `__str__`. Consumed by `examples/example.py` (Task 7).

- [ ] **Step 1: Write `context.py`**

```python
"""Boukensha::Context port: holds everything needed to make an API call.

Unlike ``Tool``/``Message`` (simple Struct-style data), Ruby's ``Context`` is
a hand-written class with behavior (``register_tool``, ``add_message``) and
derived counts — so it stays a plain Python class, not a dataclass, matching
the precedent set by ``Config`` in ``00_config``.
"""

from __future__ import annotations

from .message import Message
from .tasks.base import Base
from .tool import Tool


class Context:
    def __init__(self, task: type[Base], system: str | None = None) -> None:
        self.task = task
        self.system = system
        self.messages: list[Message] = []
        self.tools: dict[str, Tool] = {}

    def register_tool(self, tool: Tool) -> None:
        self.tools[tool.name] = tool

    def add_message(self, role: str, content: str, tool_use_id: str | None = None) -> None:
        self.messages.append(Message(role, content, tool_use_id))

    @property
    def tool_count(self) -> int:
        return len(self.tools)

    @property
    def turn_count(self) -> int:
        return len(self.messages)

    def __str__(self) -> str:
        task_name = self.task.task_name() if self.task is not None else None
        return f"#<Context task={task_name} turns={self.turn_count} tools={self.tool_count}>"
```

- [ ] **Step 2: Verify by hand**

Run:
```bash
cd python/01_struct_skeleton
uv run python -c "
from boukensha.context import Context
from boukensha.tool import Tool
from boukensha.tasks import Player

ctx = Context(task=Player, system='You are a MUD assistant.')
ctx.register_tool(Tool('move', 'Move the player', {'direction': {}}, lambda direction: direction))
ctx.add_message('user', 'go north')
print(ctx)
print(ctx.tool_count, ctx.turn_count)
"
```
Expected: `#<Context task=player turns=1 tools=1>` then `1 1`.

- [ ] **Step 3: Commit**

```bash
git add python/01_struct_skeleton/src/boukensha/context.py
git commit -m "feat: add Context class"
```

---

### Task 6: Wire up package exports

**Files:**
- Modify: `python/01_struct_skeleton/src/boukensha/__init__.py`

**Interfaces:**
- Consumes: `Config` (Task 2), `Context` (Task 5), `Message` (Task 4), `Tool` (Task 3), `tasks` subpackage (Task 2).
- Produces: `from boukensha import Config, Context, Message, Tool, tasks` — the public import surface used by `examples/example.py` (Task 7).

- [ ] **Step 1: Replace the placeholder `__init__.py`**

```python
from . import tasks
from .config import Config
from .context import Context
from .message import Message
from .tool import Tool

__all__ = ["Config", "Context", "Message", "Tool", "tasks"]
```

- [ ] **Step 2: Verify the public import surface**

Run: `cd python/01_struct_skeleton && uv run python -c "from boukensha import Config, Context, Message, Tool, tasks; print('ok')"`
Expected: `ok`, no errors.

- [ ] **Step 3: Commit**

```bash
git add python/01_struct_skeleton/src/boukensha/__init__.py
git commit -m "feat: export Config, Context, Message, Tool from boukensha package"
```

---

### Task 7: Port the runnable example

**Files:**
- Create: `python/01_struct_skeleton/examples/example.py`

**Interfaces:**
- Consumes: `Config`, `Context`, `Tool` from `boukensha` (Task 6); `Player` from `boukensha.tasks` (Task 2).
- Produces: a runnable smoke-test script, the acceptance target for this step.

- [ ] **Step 1: Write `examples/example.py`, ported from `ruby/01_struct_skeleton/examples/example.rb`**

```python
import os
from pathlib import Path

# Override the config directory so the example works from the repo root.
# In real usage a user's ~/.boukensha is picked up automatically.
os.environ.setdefault(
    "BOUKENSHA_DIR", str((Path(__file__).parent.parent.parent.parent.parent / ".boukensha").resolve())
)

from boukensha import Config, Context, Tool
from boukensha.tasks import Player

config = Config()
player_settings = config.tasks("player")
system_prompt = Player.system_prompt(
    player_settings,
    user_prompts_dir=config.user_prompts_dir,
)

ctx = Context(task=Player, system=system_prompt)

ctx.register_tool(
    Tool(
        name="move",
        description="Move the player in a direction (north, south, east, west, up, down)",
        parameters={"direction": {"type": "string", "description": "The direction to move"}},
        block=lambda direction: f"You move {direction} into a torch-lit corridor.",
    )
)

ctx.add_message("user", "Explore north and tell me what you find.")
ctx.add_message("assistant", "Sure, let me head north and take a look.")

print("=== Boukensha Step 1: Struct Skeleton ===")
print()
print(f"Config:   {config}")
print(f"Context:  {ctx}")
print(f"Tool:     {ctx.tools['move']}")
print("Messages:")
for m in ctx.messages:
    print(f"  {m}")
```

- [ ] **Step 2: Run it against the repo-root `.boukensha/`**

Run: `cd python/01_struct_skeleton && uv run examples/example.py`
Expected output (values from `../../../.boukensha/settings.yaml`):
```
=== Boukensha Step 1: Struct Skeleton ===

Config:   Config(dir=.../.boukensha, tasks=player)
Context:  #<Context task=player turns=2 tools=1>
Tool:     #<Tool name=move description=Move the player in a direction (north, so params=['direction']>
Messages:
  #<Message role=user content=Explore north and tell me what you find....>
  #<Message role=assistant content=Sure, let me head north and take a look....>
```

- [ ] **Step 3: Diff against the Ruby example's behavior**

Run: `cd ../../ruby/01_struct_skeleton && bundle exec ruby examples/example.rb`
Expected: same shape of output (struct field values, message content, tool description) — differences in `#<...>` formatting between the two languages' `to_s`/`__str__` are fine; the underlying data must match.

- [ ] **Step 4: Commit**

```bash
git add python/01_struct_skeleton/examples/example.py
git commit -m "feat: port struct-skeleton example script from Ruby"
```

---

### Task 8: Write the step README

**Files:**
- Create: `python/01_struct_skeleton/README.md`

**Interfaces:**
- Consumes: nothing (documentation only).
- Produces: user-facing docs for this step, following the same structure as `python/00_config/README.md`.

- [ ] **Step 1: Write `README.md`**

```markdown
# 01 · Struct Skeleton (Python)

Python port of `ruby/01_struct_skeleton`. Defines the data structures used to
constantly pass state around: `boukensha.Tool`, `boukensha.Message`,
`boukensha.Context`. Carries `Config`, `Base`, and `Player` forward from
`00_config` unchanged (this step drops `Config.PROMPTS_DIR` since it ships no
`prompts/` directory of its own — see `plan.md` for the full rationale).

Ruby represents these with `Struct`, chosen there for being lightweight and
readable for learning; in practice a real system would use full classes. The
direct Python equivalent of a Ruby `Struct` is a `@dataclass` — that's what
`Tool` and `Message` use here. `Context` has behavior beyond field storage
(`register_tool`, `add_message`, derived counts), so it stays a hand-written
class, matching how `Config` is written in `00_config`.

## Requirements

- Python 3.11+
- [`uv`](https://docs.astral.sh/uv/) for dependency management

## Install

\`\`\`bash
cd python/01_struct_skeleton
uv sync
\`\`\`

## Package layout

\`\`\`
python/01_struct_skeleton/
  pyproject.toml         # project metadata + deps, managed via uv
  src/boukensha/
    __init__.py            # re-exports Config, Context, Message, Tool, tasks
    config.py              # Config class (no PROMPTS_DIR — see plan.md)
    tool.py                # Tool dataclass
    message.py             # Message dataclass
    context.py             # Context class
    tasks/
      __init__.py
      base.py               # Base task class (provider/model + prompt resolution)
      player.py              # Player(Base), TASK_NAME = "player"
  examples/
    example.py              # runnable smoke-test
\`\`\`

## Data structures

### `Tool`

| Field | Description |
|---|---|
| `name` | The name of the tool |
| `description` | Shown to the agent so it knows when to invoke the tool |
| `parameters` | The arguments that need to be passed in (`dict[str, Any]`) |
| `block` | The callable that runs when the tool is called |

### `Message`

| Field | Description |
|---|---|
| `role` | Who is speaking — `"user"`, `"assistant"`, or `"tool_result"` |
| `content` | The text generated by the agent or provided by the user |
| `tool_use_id` | Links a tool result back to the specific tool call that requested it |

### `Context`

| Member | Description |
|--------|--------------|
| `Context(task, system=None)` | `task` is a task class (e.g. `Player`), not an instance |
| `.task` / `.system` | as passed to the constructor |
| `.messages` | list of `Message`, appended via `.add_message` |
| `.tools` | dict of tool name → `Tool`, populated via `.register_tool` |
| `.register_tool(tool)` | registers a `Tool` by its `.name` |
| `.add_message(role, content, tool_use_id=None)` | appends a `Message` |
| `.tool_count` / `.turn_count` | derived counts (properties) |

## Config directory resolution

Same as `00_config` — `Config()` looks for `.boukensha/` via `BOUKENSHA_DIR`,
falling back to `~/.boukensha`. This step ships no `prompts/` directory, so
`system_prompt` resolves only against a user override
(`.boukensha/prompts/player/system.md`); with no override present it returns
`None`.

## Run example

\`\`\`bash
uv run examples/example.py
\`\`\`

By default the example points `BOUKENSHA_DIR` at the repo root's
`.boukensha/` so it works out of the box from a checkout.
```

- [ ] **Step 2: Proofread the README against the actual code**

Confirm every field/method name in the tables matches `tool.py`, `message.py`, `context.py`, `config.py` exactly.

- [ ] **Step 3: Commit**

```bash
git add python/01_struct_skeleton/README.md
git commit -m "docs: add README for python/01_struct_skeleton"
```

---

## Self-Review Notes

- **Spec coverage:** Ruby's `Boukensha.Tool`, `Boukensha.Message`, `Boukensha.Context` are each covered by Tasks 3, 4, 5. `Config`/`Base`/`Player` carry-forward is Task 2. The runnable example (parity target) is Task 7. Docs are Task 8.
- **Consistency with `00_config`:** dependency set unchanged (`pyyaml`, `python-dotenv`), `uv`-managed `pyproject.toml` unchanged in shape, `Config.dig()` stays string-key-only (no symbol-checking branch, per `00_config/plan.md`'s established rationale), task classes stay classmethod-only with no instances, no test suite added.
- **Deliberate deviation from `00_config`:** `Config.PROMPTS_DIR` is dropped and no `prompts/` dir is created in this step, because that's what the Ruby diff between `00_config` and `01_struct_skeleton` shows. Confirmed by inspecting `ruby/01_struct_skeleton` — it has no `prompts/` directory.
- **Type consistency check:** `Tool.name` (`str`) is what `Context.register_tool` keys `self.tools` by; `Context.tools['move']` in `examples/example.py` matches the `name="move"` passed to `Tool(...)` in the same file. `Player` is passed as the class itself (not an instance) to `Context(task=Player, ...)`, matching `task.task_name()` being called as a classmethod in `Context.__str__`.
