# 02 · The Tool Registry (Python) Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Port `ruby/02_the_registry` to Python as `python/02_the_registry` — a standalone `uv` package that carries every file from `01_struct_skeleton` forward **unchanged** and adds two new pieces: `UnknownToolError` and `Registry` (register tools, dispatch calls by name).

**Architecture:** Confirmed by diffing the Ruby source: `diff -rq ruby/01_struct_skeleton/lib ruby/02_the_registry/lib` shows `config.rb`, `tool.rb`, `message.rb`, `context.rb`, `tasks/base.rb`, `tasks/player.rb` are **byte-identical** between the two steps. Only `lib/boukensha.rb` (the require-list) changes, and two files are added: `errors.rb` (`UnknownToolError`) and `registry.rb` (`Registry`). So this step is purely additive on top of `01_struct_skeleton` — no existing behavior changes. Each numbered step under `week1_baseline/python/` is a self-contained `uv` project (no cross-step imports), so Task 1 re-creates the five carried-forward files verbatim, exactly as `01_struct_skeleton` did for `00_config`.

**Tech Stack:** Python 3.11+, `uv` for dependency management, `pyyaml` + `python-dotenv` (unchanged from prior steps — no new dependencies needed; `Registry`/`UnknownToolError` need only stdlib).

## Global Constraints

- Python 3.11+, dependency-managed via `uv` (`pyproject.toml`, `uv sync`) — same toolchain as `00_config`/`01_struct_skeleton`.
- Dependencies stay at exactly `pyyaml>=6.0` and `python-dotenv>=1.0` — no new third-party packages.
- No automated test suite (matches Ruby original and prior Python steps' precedent) — verification is a manual run of `examples/example.py`, output compared against the Ruby example's documented expected output (README.md's "Expected Output" block, since the live Ruby toolchain may not be runnable in this environment — see `01_struct_skeleton`'s Task 7 precedent, which hit exactly this and fell back to comparing against source/docs).
- `config.py`, `tool.py`, `message.py`, `context.py`, `tasks/base.py`, `tasks/player.py` are copied forward **verbatim, byte-for-byte** from `python/01_struct_skeleton` — confirmed identical in the Ruby source, so no re-derivation, no "improvements," no drift.
- Ruby `class UnknownToolError < StandardError; end` → Python `class UnknownToolError(Exception): pass`. `StandardError` is Ruby's base for ordinary application errors; Python's `Exception` is the equivalent base (not `BaseException`, which is reserved for system-exiting conditions).
- `Registry` mirrors `Context`'s precedent: a plain hand-written class with `__init__`, not a dataclass — it has behavior (`tool`, `dispatch`), not just data.
- The tool-registration "block" parameter stays a plain callable passed as a keyword argument (`block=lambda ...`), matching the pattern `01_struct_skeleton/examples/example.py` already established for `Tool(block=...)`. Do not introduce a decorator-based registration API — that would be a bigger idiom shift than this port calls for, and would break consistency with how `Tool` is already constructed elsewhere in this codebase.
- Ruby's `dispatch` calls `args.transform_keys(&:to_sym)` before invoking the block, because Ruby blocks with keyword parameters require symbol keys while JSON/API responses arrive as string-keyed hashes — the README's "Considerations" section calls this out as a deliberate, visible gotcha. **This does not port to Python**: Python keyword arguments are already string-based (`**kwargs` matches on string names), so `tool.block(**args)` needs no key-transformation step. Document this as a language-difference callout in the README (matching the precedent in `00_config/plan.md`'s "Design Considerations" section, which documents *why* something doesn't carry over), not as a silently-dropped feature.
- Truncation lengths for `Tool.__str__`/`Message.__str__` are unchanged from `01_struct_skeleton` (`description[:41]`, `content[:61]`) — these files are copied verbatim, not reimplemented.

## File Structure

```
python/02_the_registry/
  pyproject.toml            # project metadata + deps, copied from 01_struct_skeleton, description bumped
  README.md                 # usage docs for this step
  plan.md                   # this file
  src/boukensha/
    __init__.py              # re-exports Config, Context, Message, Tool, Registry, UnknownToolError, tasks
    config.py                 # Config class — copied verbatim from 01_struct_skeleton
    tool.py                    # Tool dataclass — copied verbatim from 01_struct_skeleton
    message.py                  # Message dataclass — copied verbatim from 01_struct_skeleton
    context.py                   # Context class — copied verbatim from 01_struct_skeleton
    errors.py                     # UnknownToolError (new)
    registry.py                    # Registry class (new)
    tasks/
      __init__.py
      base.py                  # Base task class — copied verbatim from 01_struct_skeleton
      player.py                # Player(Base) — copied verbatim from 01_struct_skeleton
  examples/
    example.py                # runnable smoke-test, ported from ruby examples/example.rb
```

---

### Task 1: Scaffold the `uv` project and carry forward unchanged files

**Files:**
- Create: `python/02_the_registry/pyproject.toml`
- Create: `python/02_the_registry/src/boukensha/config.py`
- Create: `python/02_the_registry/src/boukensha/tool.py`
- Create: `python/02_the_registry/src/boukensha/message.py`
- Create: `python/02_the_registry/src/boukensha/context.py`
- Create: `python/02_the_registry/src/boukensha/tasks/__init__.py`
- Create: `python/02_the_registry/src/boukensha/tasks/base.py`
- Create: `python/02_the_registry/src/boukensha/tasks/player.py`
- Create: `python/02_the_registry/src/boukensha/__init__.py` (placeholder, filled in Task 4)
- Create: `python/02_the_registry/examples/` (empty dir, populated in Task 5)

**Interfaces:**
- Produces: `Config`, `Base`, `Player`, `Tool`, `Message`, `Context` — every one of these importable and behaviorally identical to their `01_struct_skeleton` counterparts. `Registry` (Task 3) will consume `Tool` (to construct instances) and `Context` (to call `.register_tool`/read `.tools`).

- [ ] **Step 1: Create `pyproject.toml`**

```toml
[project]
name = "boukensha"
version = "0.1.0"
description = "Boukensha tool registry (Step 2)"
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

- [ ] **Step 2: Write `config.py`, copied verbatim from `01_struct_skeleton`**

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

- [ ] **Step 3: Write `tool.py`, copied verbatim from `01_struct_skeleton`**

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

- [ ] **Step 4: Write `message.py`, copied verbatim from `01_struct_skeleton`**

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

- [ ] **Step 5: Write `context.py`, copied verbatim from `01_struct_skeleton`**

```python
"""Boukensha::Context port: holds everything needed to make an API call.

Unlike ``Tool``/``Message`` (simple Struct-style data), Ruby's ``Context`` is
a hand-written class with behavior (``register_tool``, ``add_message``) and
derived counts — so it stays a plain Python class, not a dataclass, matching
the precedent set by ``Config``.
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

- [ ] **Step 6: Write `tasks/base.py`, copied verbatim from `01_struct_skeleton`**

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

- [ ] **Step 7: Write `tasks/player.py`, copied verbatim from `01_struct_skeleton`**

```python
from __future__ import annotations

from .base import Base


class Player(Base):
    TASK_NAME = "player"
```

- [ ] **Step 8: Write `tasks/__init__.py`, copied verbatim from `01_struct_skeleton`**

```python
from .base import Base
from .player import Player

__all__ = ["Base", "Player"]
```

- [ ] **Step 9: Create an empty package placeholder**

Create `python/02_the_registry/src/boukensha/__init__.py` with just:

```python
```

(empty file — real content added in Task 4, once `Registry`/`UnknownToolError` exist to export)

- [ ] **Step 10: Run `uv sync` and verify the environment builds**

Run: `cd python/02_the_registry && uv sync`
Expected: creates `.venv/`, installs `pyyaml` and `python-dotenv`, no errors.

- [ ] **Step 11: Verify the carried-forward package imports and behaves identically to `01_struct_skeleton`**

Run:
```bash
cd python/02_the_registry
uv run python -c "
from boukensha.config import Config
from boukensha.tasks import Player
from boukensha.context import Context
from boukensha.tool import Tool
from boukensha.message import Message
ctx = Context(task=Player, system='test')
ctx.register_tool(Tool('move', 'Move the player', {'direction': {}}, lambda direction: direction))
ctx.add_message('user', 'go north')
print(ctx)
"
```
Expected: `#<Context task=player turns=1 tools=1>` — identical behavior to `01_struct_skeleton`'s Task 5 verification.

- [ ] **Step 12: Commit**

```bash
git add python/02_the_registry/pyproject.toml python/02_the_registry/src/boukensha/config.py python/02_the_registry/src/boukensha/tool.py python/02_the_registry/src/boukensha/message.py python/02_the_registry/src/boukensha/context.py python/02_the_registry/src/boukensha/tasks/ python/02_the_registry/src/boukensha/__init__.py
git commit -m "chore: scaffold python/02_the_registry, carry forward Config/Tool/Message/Context/tasks from 01_struct_skeleton"
```

---

### Task 2: Add `UnknownToolError`

**Files:**
- Create: `python/02_the_registry/src/boukensha/errors.py`

**Interfaces:**
- Produces: `UnknownToolError(Exception)` — raised by `Registry.dispatch` (Task 3) when no tool is registered under the requested name.

- [ ] **Step 1: Write `errors.py`**

```python
"""Boukensha-specific error classes.

Ruby's ``UnknownToolError < StandardError`` maps to Python's
``Exception`` — the base for ordinary application errors (not
``BaseException``, which is reserved for system-exiting conditions like
``SystemExit``/``KeyboardInterrupt``).
"""

from __future__ import annotations


class UnknownToolError(Exception):
    """Raised when dispatch is called with a name that has no registered tool."""
```

- [ ] **Step 2: Verify by hand**

Run:
```bash
cd python/02_the_registry
uv run python -c "
from boukensha.errors import UnknownToolError
try:
    raise UnknownToolError(\"No tool registered as 'flee'\")
except UnknownToolError as e:
    print(f'caught: {e}')
"
```
Expected: `caught: No tool registered as 'flee'`

- [ ] **Step 3: Commit**

```bash
git add python/02_the_registry/src/boukensha/errors.py
git commit -m "feat: add UnknownToolError"
```

---

### Task 3: Add the `Registry` class

**Files:**
- Create: `python/02_the_registry/src/boukensha/registry.py`

**Interfaces:**
- Consumes: `Tool` (Task 1, `.tool`), `Context` (Task 1, `.register_tool`/`.tools`), `UnknownToolError` (Task 2, `.errors`).
- Produces: `Registry(context)` with `.tool(name, description, parameters=None, *, block)` (constructs a `Tool`, registers it on the context, returns it) and `.dispatch(name, args=None)` (looks up a tool by name, raises `UnknownToolError` if missing, else calls `tool.block(**args)`). Consumed by `examples/example.py` (Task 5).

- [ ] **Step 1: Write `registry.py`**

```python
"""Boukensha::Registry port: registers tools on a Context and dispatches
calls to them by name.

Ruby's ``dispatch`` converts string-keyed args to symbol keys
(``args.transform_keys(&:to_sym)``) before calling the block, because Ruby
blocks with keyword parameters require symbol keys while the args arrive
string-keyed (as they would from parsed JSON). Python has no such gap:
keyword arguments are matched by string name already, so ``tool.block(**args)``
needs no key-transformation step — the "gotcha" the Ruby original calls out
is language-specific and doesn't carry over.
"""

from __future__ import annotations

from collections.abc import Callable
from typing import Any

from .context import Context
from .errors import UnknownToolError
from .tool import Tool


class Registry:
    def __init__(self, context: Context) -> None:
        self._context = context

    def tool(
        self,
        name: str,
        description: str,
        parameters: dict[str, Any] | None = None,
        *,
        block: Callable[..., Any],
    ) -> Tool:
        registered = Tool(str(name), description, parameters or {}, block)
        self._context.register_tool(registered)
        return registered

    def dispatch(self, name: str, args: dict[str, Any] | None = None) -> Any:
        tool = self._context.tools.get(str(name))
        if tool is None:
            raise UnknownToolError(f"No tool registered as '{name}'")
        return tool.block(**(args or {}))
```

- [ ] **Step 2: Verify by hand**

Run:
```bash
cd python/02_the_registry
uv run python -c "
from boukensha.context import Context
from boukensha.registry import Registry
from boukensha.errors import UnknownToolError
from boukensha.tasks import Player

ctx = Context(task=Player)
registry = Registry(ctx)
registry.tool('shout', 'Shout a message', {'message': {'type': 'string'}}, block=lambda message: message.upper())

print(registry.dispatch('shout', {'message': 'dragon spotted'}))
try:
    registry.dispatch('flee')
except UnknownToolError as e:
    print(f'caught: {e}')
"
```
Expected:
```
DRAGON SPOTTED
caught: No tool registered as 'flee'
```

- [ ] **Step 3: Commit**

```bash
git add python/02_the_registry/src/boukensha/registry.py
git commit -m "feat: add Registry class"
```

---

### Task 4: Wire up package exports

**Files:**
- Modify: `python/02_the_registry/src/boukensha/__init__.py`

**Interfaces:**
- Consumes: `Config` (Task 1), `Context` (Task 1), `Message` (Task 1), `Tool` (Task 1), `tasks` subpackage (Task 1), `Registry` (Task 3), `UnknownToolError` (Task 2).
- Produces: `from boukensha import Config, Context, Message, Tool, Registry, UnknownToolError, tasks` — the public import surface used by `examples/example.py` (Task 5).

- [ ] **Step 1: Replace the placeholder `__init__.py`**

```python
from . import tasks
from .config import Config
from .context import Context
from .errors import UnknownToolError
from .message import Message
from .registry import Registry
from .tool import Tool

__all__ = ["Config", "Context", "Message", "Registry", "Tool", "UnknownToolError", "tasks"]
```

- [ ] **Step 2: Verify the public import surface**

Run: `cd python/02_the_registry && uv run python -c "from boukensha import Config, Context, Message, Tool, Registry, UnknownToolError, tasks; print('ok')"`
Expected: `ok`, no errors.

- [ ] **Step 3: Commit**

```bash
git add python/02_the_registry/src/boukensha/__init__.py
git commit -m "feat: export Registry, UnknownToolError from boukensha package"
```

---

### Task 5: Port the runnable example

**Files:**
- Create: `python/02_the_registry/examples/example.py`

**Interfaces:**
- Consumes: `Config`, `Context`, `Registry`, `UnknownToolError` from `boukensha` (Task 4); `Player` from `boukensha.tasks` (Task 1).
- Produces: a runnable smoke-test script, the acceptance target for this step.

- [ ] **Step 1: Write `examples/example.py`, ported from `ruby/02_the_registry/examples/example.rb`**

```python
import os
from pathlib import Path

# Override the config directory so the example works from the repo root.
# In real usage a user's ~/.boukensha is picked up automatically.
os.environ.setdefault(
    "BOUKENSHA_DIR", str((Path(__file__).parent.parent.parent.parent.parent / ".boukensha").resolve())
)

from boukensha import Config, Context, Registry, UnknownToolError
from boukensha.tasks import Player

config = Config()
player_settings = config.tasks("player")
system_prompt = Player.system_prompt(
    player_settings,
    user_prompts_dir=config.user_prompts_dir,
)

ctx = Context(task=Player, system=system_prompt)
registry = Registry(ctx)

# Notice that we now register the tools through the registry instead of
# directly on the context, like the previous step did. They will still be
# attached to context which is why we pass it into our registry when we
# initialize it.
registry.tool(
    "move",
    description="Move the player in a direction (north, south, east, west, up, down)",
    parameters={"direction": {"type": "string"}},
    block=lambda direction: f"You move {direction} into a torch-lit corridor.",
)

registry.tool(
    "shout",
    description="Shout a message so everyone in the zone can hear it",
    parameters={"message": {"type": "string"}},
    block=lambda message: message.upper(),
)

print("=== BOUKENSHA Step 2: Tool Registry ===")
print()
print(f"Config:  {config}")
print(f"Context: {ctx}")
print("Tools:")
for t in ctx.tools.values():
    print(f"  {t}")
print()

# Here we are mimicking what the agent would do when it needs to call a tool
# from the registry. We are still missing the actual code that would decide
# when to call the registry for a tool.
print("Dispatching 'shout' with message='dragon spotted'...")
result = registry.dispatch("shout", {"message": "dragon spotted"})
print(f"Result: {result}")
print()

print("Dispatching 'move' with direction='north'...")
result = registry.dispatch("move", {"direction": "north"})
print(f"Result: {result}")
print()

try:
    registry.dispatch("flee")
except UnknownToolError as e:
    print(f"UnknownToolError caught: {e}")
```

- [ ] **Step 2: Run it against the repo-root `.boukensha/`**

Run: `cd python/02_the_registry && uv run examples/example.py`
Expected output (values from `../../../.boukensha/settings.yaml`; compare shape/values against the Ruby README's "Expected Output" block):
```
=== BOUKENSHA Step 2: Tool Registry ===

Config:  Config(dir=.../.boukensha, tasks=player)
Context: #<Context task=player turns=0 tools=2>
Tools:
  #<Tool name=move description=Move the player in a direction (north, so params=['direction']>
  #<Tool name=shout description=Shout a message so everyone in the zone ca params=['message']>

Dispatching 'shout' with message='dragon spotted'...
Result: DRAGON SPOTTED

Dispatching 'move' with direction='north'...
Result: You move north into a torch-lit corridor.

UnknownToolError caught: No tool registered as 'flee'
```

- [ ] **Step 3: Compare against the Ruby README's documented expected output**

The Ruby toolchain may not be runnable in this environment (as it wasn't for `01_struct_skeleton`'s Task 7 — an old system Ruby, no compatible bundler). If `bundle exec ruby examples/example.rb` (run from `ruby/02_the_registry`) works, run it and diff outputs. If not, compare the Python run's output against `ruby/02_the_registry/README.md`'s "Expected Output" section instead — same values, same tool dispatch sequence, same error message text (`No tool registered as 'flee'`).

- [ ] **Step 4: Commit**

```bash
git add python/02_the_registry/examples/example.py
git commit -m "feat: port tool-registry example script from Ruby"
```

---

### Task 6: Write the step README

**Files:**
- Create: `python/02_the_registry/README.md`

**Interfaces:**
- Consumes: nothing (documentation only).
- Produces: user-facing docs for this step, following the structural pattern of `python/01_struct_skeleton/README.md` and `python/00_config/README.md`.

- [ ] **Step 1: Write `README.md`**

```markdown
# 02 · The Tool Registry (Python)

Python port of `ruby/02_the_registry`. The Registry is how BOUKENSHA manages
what capabilities the agent can use — it stores tools and dispatches calls to
them by name. Carries `Config`, `Base`, `Player`, `Tool`, `Message`, `Context`
forward from `01_struct_skeleton` **unchanged** (confirmed byte-identical
against the Ruby source: `diff -rq ruby/01_struct_skeleton/lib
ruby/02_the_registry/lib` shows only two files added, nothing modified). This
step adds `boukensha.errors.UnknownToolError` and `boukensha.registry.Registry`.

## How it works

The agent never calls a tool directly. It emits a structured request (name +
args) and the `Registry` looks up the tool and runs it:

```
Agent:     "Hey registry, call move with direction='north'"
Registry:  looks up "move" in the tool table
Registry:  found it, calls the block with the provided args
Registry:  here's the result
```

## Requirements

- Python 3.11+
- [`uv`](https://docs.astral.sh/uv/) for dependency management

## Install

\`\`\`bash
cd python/02_the_registry
uv sync
\`\`\`

## Package layout

\`\`\`
python/02_the_registry/
  pyproject.toml         # project metadata + deps, managed via uv
  src/boukensha/
    __init__.py            # re-exports Config, Context, Message, Tool, Registry, UnknownToolError, tasks
    config.py              # Config class (unchanged from 01_struct_skeleton)
    tool.py                # Tool dataclass (unchanged)
    message.py             # Message dataclass (unchanged)
    context.py             # Context class (unchanged)
    errors.py              # UnknownToolError
    registry.py            # Registry class
    tasks/
      __init__.py
      base.py               # Base task class
      player.py              # Player(Base), TASK_NAME = "player"
  examples/
    example.py              # runnable smoke-test
\`\`\`

## `Registry`

| Method | Description |
|---|---|
| `Registry(context)` | wraps a `Context`; tools registered through the registry are still stored on that context |
| `.tool(name, description, parameters=None, *, block)` | constructs a `Tool` and registers it on the context; returns the `Tool` |
| `.dispatch(name, args=None)` | looks up a tool by name and calls `tool.block(**args)`; raises `UnknownToolError` if no tool is registered under that name |

## `UnknownToolError`

Raised when `dispatch` is called with a name that has no registered tool. A
harness needs explicit error boundaries — an unrecognised tool name should
never silently fail.

\`\`\`
UnknownToolError: No tool registered as 'flee'
\`\`\`

## Design note: no key-transformation step in `dispatch`

Ruby's `dispatch` calls `args.transform_keys(&:to_sym)` before invoking the
block, because Ruby blocks with keyword parameters require **symbol** keys,
while the args arrive **string**-keyed (as they would from parsed JSON). This
is called out in the Ruby README as a deliberate, visible gotcha.

Python has no such gap: keyword arguments are already matched by string name
(`tool.block(**args)` works directly on a string-keyed dict), so there is
nothing to transform. This is a language difference, not a dropped feature.

## Run example

\`\`\`bash
uv run examples/example.py
\`\`\`

Expected output:

\`\`\`
=== BOUKENSHA Step 2: Tool Registry ===

Config:  Config(dir=..., tasks=player)
Context: #<Context task=player turns=0 tools=2>
Tools:
  #<Tool name=move description=Move the player in a direction (north, so params=['direction']>
  #<Tool name=shout description=Shout a message so everyone in the zone ca params=['message']>

Dispatching 'shout' with message='dragon spotted'...
Result: DRAGON SPOTTED

Dispatching 'move' with direction='north'...
Result: You move north into a torch-lit corridor.

UnknownToolError caught: No tool registered as 'flee'
\`\`\`
```

- [ ] **Step 2: Proofread the README against the actual code**

Confirm every field/method name and every example output line matches `registry.py`, `errors.py`, and a real `uv run examples/example.py` invocation exactly.

- [ ] **Step 3: Commit**

```bash
git add python/02_the_registry/README.md
git commit -m "docs: add README for python/02_the_registry"
```

---

## Self-Review Notes

- **Spec coverage:** Ruby's `Boukensha::Registry` and `Boukensha::UnknownToolError` are covered by Tasks 3 and 2. Carrying forward `Config`/`Tool`/`Message`/`Context`/`Base`/`Player` unchanged is Task 1, confirmed against the Ruby diff (`diff -rq ruby/01_struct_skeleton/lib ruby/02_the_registry/lib`), not assumed. The runnable example (parity target) is Task 5. Docs are Task 6.
- **Consistency with `01_struct_skeleton`/`00_config`:** dependency set unchanged, `uv`-managed `pyproject.toml` unchanged in shape, no test suite added, `Context`/`Registry` both stay hand-written classes (not dataclasses) since both have behavior beyond field storage, `Tool`/`Message` stay dataclasses (data-only, carried forward verbatim).
- **Deliberate, documented deviation:** Ruby's `args.transform_keys(&:to_sym)` in `dispatch` does not port — Python's string-keyed `**kwargs` makes it unnecessary. This is called out explicitly in both the plan (Global Constraints) and the README ("Design note") rather than silently dropped, following the precedent set by `00_config/plan.md`'s "Design Considerations" section for documenting language-driven differences.
- **API shape decision:** `Registry.tool`'s `block` parameter stays a plain keyword-argument callable (matching how `Tool(block=...)` is already constructed in `01_struct_skeleton/examples/example.py`), not a decorator. This was a deliberate choice to avoid introducing a new registration idiom this port doesn't need — flagged in Global Constraints so an implementer doesn't "improve" it into a decorator API.
- **Type consistency check:** `Registry.__init__(self, context: Context)` stores `self._context` (underscore-prefixed, matching Ruby's `@context` having no public accessor — Ruby's `attr_reader` is absent for it). `Registry.tool(...)` constructs `Tool(str(name), description, parameters or {}, block)`, matching `Tool`'s field order (`name, description, parameters, block`) from `01_struct_skeleton/tool.py`. `Registry.dispatch` reads `self._context.tools.get(str(name))`, matching `Context.tools`'s type (`dict[str, Tool]`, keyed by `tool.name` via `register_tool`).
