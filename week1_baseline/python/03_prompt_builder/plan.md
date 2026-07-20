# 03 · The Prompt Builder (Python) Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Port `ruby/03_prompt_builder` to Python as `python/03_prompt_builder` — a standalone `uv` package that carries `Tool`/`Message`/`Context`/`Registry`/`tasks.Base`/`tasks.Player` forward **unchanged** from `02_the_registry`, **modifies** `config.py` (re-adds `PROMPTS_DIR`) and `errors.py` (adds `UnsupportedModelError`), and **adds** a `PromptBuilder` plus five API backends (`Anthropic`, `Gemini`, `Ollama`, `OllamaCloud`, `OpenAI`) that serialize `Context` into each provider's request format.

**Architecture — diff-driven porting:** Earlier ports (`00→01→02`) were purely additive: every carried-forward file was byte-identical, confirmed with `diff -rq`. That pattern **breaks starting at this step**. A file-level diff between `ruby/02_the_registry/lib` and `ruby/03_prompt_builder/lib` was run before writing this plan, and it shows a mix of three kinds of change, not just additions:

```
UNCHANGED (copy forward verbatim):  tool.rb, message.rb, registry.rb,
                                     tasks/base.rb, tasks/player.rb
MODIFIED (real, small diffs):       boukensha.rb (new requires),
                                     errors.rb (+1 class),
                                     config.rb (+1 constant, PROMPTS_DIR restored),
                                     context.rb (trailing-newline only — not a real change)
ADDED (net-new):                    prompt_builder.rb, backends/base.rb,
                                     backends/anthropic.rb, backends/gemini.rb,
                                     backends/ollama.rb, backends/ollama_cloud.rb,
                                     backends/openai.rb, prompts/system.md
```

This is the general shape every future step's plan should be built around: **diff the current Ruby step against the previous Ruby step first** (`diff -rq prevdir/lib curdir/lib` for the file list, then per-file `diff` on anything present in both), and let that diff drive the task list — unchanged files become "copy forward verbatim" tasks, modified files become small, precisely-scoped "apply this diff" tasks (quote the exact before/after, not "re-derive the whole file"), and new files become "add" tasks. Never re-read and re-transcribe a whole file from scratch when a 3-line diff tells you exactly what changed — that's slower and is exactly how drift creeps in.

**Tech Stack:** Python 3.11+, `uv`, `pyyaml` + `python-dotenv` (unchanged — `PromptBuilder`/backends only build payload dicts, they never make an HTTP call in this step, so no HTTP client dependency is needed yet).

## Global Constraints

- Python 3.11+, `uv`-managed, deps stay exactly `pyyaml>=6.0` and `python-dotenv>=1.0` — no new third-party packages. (Backends build request payloads as plain dicts; nothing here performs an actual HTTP request, so `requests`/`httpx` are not needed until a later step wires up the real API client.)
- No automated test suite (established precedent) — verification is a manual run of `examples/example.py`.
- `tool.py`, `message.py`, `registry.py`, `tasks/base.py`, `tasks/player.py` are copied forward **verbatim, byte-for-byte** from `python/02_the_registry` — confirmed unchanged in the Ruby diff.
- `context.py` is also copied forward verbatim — the only Ruby diff on `context.rb` is a trailing-newline artifact, not a functional change.
- `config.py`: re-add `Config.PROMPTS_DIR`, computed exactly as `00_config` originally had it (`(Path(__file__).parent.parent.parent / "prompts").resolve()`), since this step ships its own `prompts/system.md` again. This mirrors the Ruby diff exactly (`config.rb` gains back the constant `01_struct_skeleton`/`02_the_registry` had dropped).
- `errors.py`: add `UnsupportedModelError(Exception)` alongside the existing `UnknownToolError(Exception)`.
- **Naming collision, resolved deliberately:** Ruby's `Backends::Base` defines a class method `model_info(model)` (metadata lookup by name) AND an instance method `model_info` (no args, returns the resolved instance's metadata) — legal in Ruby because class methods and instance methods live in separate method tables. Python has no such separation: a classmethod and a property with the same name on the same class collide (whichever is defined later in the class body wins for all access). Resolution: keep `model_info` as the **classmethod** (`Base.model_info(model)` / `Anthropic.model_info(model)` — the public, documented lookup). Store the instance's resolved metadata in a private-by-convention attribute, `self._model_info`, set by `_configure_model`. This is safe because the Ruby README's public API table for backend instances lists `context_window`, `input_token_cost_per_million`, `output_token_cost_per_million`, `usage_unit`, `usage_level`, `estimate_cost` — **not** `model_info** as a public instance accessor, so nothing public is lost.
- Ruby's zero-arg instance methods that just return a computed value (`headers`, `url` on backends and on `PromptBuilder`) map to Python `@property`, not plain `()`-called methods — this keeps call sites attribute-like (`backend.headers`, not `backend.headers()`), consistent with the `Context.tool_count`/`turn_count` precedent already established in `01_struct_skeleton`.
- `estimate_cost(input_tokens:, output_tokens:)` in Ruby is required-keyword, no positional form — Python: `def estimate_cost(self, *, input_tokens: int, output_tokens: int) -> float | None`.
- Ruby's `validate_model!` error message interpolates `self.name`, the fully-qualified class name (`Boukensha::Backends::Anthropic`). Python's `cls.__name__` gives the bare name (`Anthropic`) — there's no equivalent of Ruby's `Module::Class` string. This is a language difference, not a bug; use `cls.__name__` and don't try to fake the module-qualified form.
- `tool.parameters.keys.map(&:to_s)` (building the `required` list in every backend's `to_tools`) does **not** port: `Tool.parameters` has been a plain `dict[str, Any]` with string keys since `01_struct_skeleton` — there are no symbol keys to coerce. Use `list(tool.parameters.keys())` directly. Same category of language-difference callout as the `registry.dispatch` key-transformation note from the `02_the_registry` port — document it, don't silently drop it.
- **Known upstream quirk, preserve don't fix:** Ruby's `PromptBuilder#to_messages` calls `@backend.to_messages(@context.messages)` — always exactly **one** argument. But `Anthropic#to_messages`/`Gemini#to_messages` take one arg (`messages`), while `Ollama#to_messages`/`OllamaCloud#to_messages`/`OpenAI#to_messages` take **two** (`system, messages`). Calling `PromptBuilder#to_messages` directly with an Ollama-family backend would raise `ArgumentError` in Ruby. This is confirmed as a real, unaddressed latent bug in the Ruby source (checked: `diff ruby/03_prompt_builder/lib/boukensha/prompt_builder.rb ruby/04_api_client/lib/boukensha/prompt_builder.rb` is empty — it isn't fixed in the very next step either), and it's never triggered because `examples/example.rb` only calls `builder.to_api_payload` (which routes through each backend's own `to_payload`, which calls its own `to_messages` with the correct arity internally). **Port the arities faithfully as-is** (each backend's `to_messages` keeps its real Ruby signature) rather than "fixing" `PromptBuilder`/the backends to paper over it — that would be silently changing behavior beyond this step's scope. Call this out explicitly in the README so nobody "fixes" it by accident later while porting `04_api_client`.
- Backend classes are plain hand-written classes (not dataclasses) — they carry behavior (`to_messages`, `to_tools`, `to_payload`, `estimate_cost`) and mutable-at-construction-time state (`self.model`, `self._model_info`), matching the `Context`/`Registry` precedent.
- Ruby symbols used as dict/hash values (`usage_unit: :tokens`, `usage_level: :medium`) become plain Python strings (`"tokens"`, `"medium"`) — matches the existing `Message.role` precedent (`:user`/`:assistant`/`:tool_result` → `"user"`/`"assistant"`/`"tool_result"`), not a new `Enum`.
- `MODELS` price/window data in every backend must be copied verbatim (same numbers, same model names) from the Ruby source — this is tutorial reference data, not something to "improve" or re-derive.

## File Structure

```
python/03_prompt_builder/
  pyproject.toml            # copied from 02_the_registry, description bumped
  README.md
  plan.md                   # this file
  prompts/
    system.md                 # NEW — shipped default system prompt, copied verbatim from Ruby
  src/boukensha/
    __init__.py               # re-exports everything, including backends + PromptBuilder + UnsupportedModelError
    config.py                 # MODIFIED — PROMPTS_DIR restored
    tool.py                   # unchanged, copied forward
    message.py                # unchanged, copied forward
    context.py                # unchanged, copied forward
    errors.py                 # MODIFIED — + UnsupportedModelError
    registry.py                # unchanged, copied forward
    prompt_builder.py           # NEW
    backends/
      __init__.py                # NEW
      base.py                    # NEW
      anthropic.py                # NEW
      gemini.py                   # NEW
      ollama.py                   # NEW
      ollama_cloud.py             # NEW
      openai.py                   # NEW
    tasks/
      __init__.py                # unchanged, copied forward
      base.py                     # unchanged, copied forward
      player.py                   # unchanged, copied forward
  examples/
    example.py                 # NEW, ported from ruby examples/example.rb
```

---

### Task 1: Scaffold the `uv` project and carry forward unchanged files

**Files:**
- Create: `python/03_prompt_builder/pyproject.toml`
- Create: `python/03_prompt_builder/src/boukensha/tool.py`
- Create: `python/03_prompt_builder/src/boukensha/message.py`
- Create: `python/03_prompt_builder/src/boukensha/context.py`
- Create: `python/03_prompt_builder/src/boukensha/registry.py`
- Create: `python/03_prompt_builder/src/boukensha/tasks/__init__.py`
- Create: `python/03_prompt_builder/src/boukensha/tasks/base.py`
- Create: `python/03_prompt_builder/src/boukensha/tasks/player.py`
- Create: `python/03_prompt_builder/src/boukensha/__init__.py` (placeholder, filled in Task 8)
- Create: `python/03_prompt_builder/examples/` (empty dir, populated in Task 9)

**Interfaces:**
- Produces: `Tool`, `Message`, `Context`, `Registry`, `Base` (task), `Player` — byte-identical to their `02_the_registry` counterparts. Consumed by every later task in this plan.

- [ ] **Step 1: Create `pyproject.toml`**

```toml
[project]
name = "boukensha"
version = "0.1.0"
description = "Boukensha prompt builder (Step 3)"
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

- [ ] **Step 2: Write `tool.py`, copied verbatim from `02_the_registry`**

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

- [ ] **Step 3: Write `message.py`, copied verbatim from `02_the_registry`**

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

- [ ] **Step 4: Write `context.py`, copied verbatim from `02_the_registry`**

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

- [ ] **Step 5: Write `registry.py`, copied verbatim from `02_the_registry`**

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

- [ ] **Step 6: Write `tasks/base.py`, copied verbatim from `02_the_registry`**

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

- [ ] **Step 7: Write `tasks/player.py`, copied verbatim from `02_the_registry`**

```python
from __future__ import annotations

from .base import Base


class Player(Base):
    TASK_NAME = "player"
```

- [ ] **Step 8: Write `tasks/__init__.py`, copied verbatim from `02_the_registry`**

```python
from .base import Base
from .player import Player

__all__ = ["Base", "Player"]
```

- [ ] **Step 9: Create an empty package placeholder**

Create `python/03_prompt_builder/src/boukensha/__init__.py` with just:

```python
```

- [ ] **Step 10: Run `uv sync` and verify the environment builds**

Run: `cd python/03_prompt_builder && uv sync`
Expected: creates `.venv/`, installs `pyyaml` and `python-dotenv`, no errors.

- [ ] **Step 11: Verify the carried-forward files import cleanly**

Run: `cd python/03_prompt_builder && uv run python -c "from boukensha.tool import Tool; from boukensha.message import Message; from boukensha.context import Context; from boukensha.registry import Registry; from boukensha.tasks import Player; print('ok')"`
Expected: `ok`, no errors. (`config.py`/`errors.py` don't exist yet — Tasks 2-3 add the modified versions.)

- [ ] **Step 12: Commit**

```bash
git add python/03_prompt_builder/pyproject.toml python/03_prompt_builder/src/boukensha/tool.py python/03_prompt_builder/src/boukensha/message.py python/03_prompt_builder/src/boukensha/context.py python/03_prompt_builder/src/boukensha/registry.py python/03_prompt_builder/src/boukensha/tasks/ python/03_prompt_builder/src/boukensha/__init__.py
git commit -m "chore: scaffold python/03_prompt_builder, carry forward Tool/Message/Context/Registry/tasks from 02_the_registry"
```

---

### Task 2: Modify `config.py` — restore `PROMPTS_DIR`, ship `prompts/system.md`

**Files:**
- Create: `python/03_prompt_builder/src/boukensha/config.py`
- Create: `python/03_prompt_builder/prompts/system.md`

**Interfaces:**
- Produces: `Config` with `Config.PROMPTS_DIR` restored as a class attribute (was dropped in `01_struct_skeleton`/`02_the_registry`, matching the Ruby diff that re-adds it here). Consumed by `examples/example.py` (Task 9), which will now pass `default_prompts_dir=Config.PROMPTS_DIR` to `Player.system_prompt`.

- [ ] **Step 1: Write `prompts/system.md`, copied verbatim from Ruby**

```
You are a MUD player assistant. Use the tools available to you to help the player explore, fight, and interact with the world.
```

- [ ] **Step 2: Write `config.py`**

This is `02_the_registry`'s `config.py` with exactly one addition — `PROMPTS_DIR`, restored to the same form `00_config` originally shipped it in (a class attribute resolving to `<project root>/prompts`, relative to this file's location three levels up: `config.py` → `boukensha` → `src` → project root).

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

    # Default prompts shipped alongside the library code.
    PROMPTS_DIR = str((Path(__file__).parent.parent.parent / "prompts").resolve())

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

- [ ] **Step 3: Verify by hand**

Run:
```bash
cd python/03_prompt_builder
uv run python -c "
from boukensha.config import Config
print(Config.PROMPTS_DIR)
import os
print(os.path.exists(os.path.join(Config.PROMPTS_DIR, 'system.md')))
"
```
Expected: prints the absolute path to `python/03_prompt_builder/prompts`, then `True`.

- [ ] **Step 4: Commit**

```bash
git add python/03_prompt_builder/src/boukensha/config.py python/03_prompt_builder/prompts/system.md
git commit -m "feat: restore Config.PROMPTS_DIR, ship default system prompt"
```

---

### Task 3: Modify `errors.py` — add `UnsupportedModelError`

**Files:**
- Create: `python/03_prompt_builder/src/boukensha/errors.py`

**Interfaces:**
- Produces: `UnsupportedModelError(Exception)`, alongside the existing `UnknownToolError(Exception)`. Raised by `Backends.Base.validate_model` (Task 4) when a backend is configured with an unknown model name.

- [ ] **Step 1: Write `errors.py`**

This is `02_the_registry`'s `errors.py` with one addition.

```python
"""Boukensha-specific error classes.

Ruby's ``UnknownToolError < StandardError`` and
``UnsupportedModelError < StandardError`` both map to Python's ``Exception``
— the base for ordinary application errors (not ``BaseException``, which is
reserved for system-exiting conditions like ``SystemExit``/``KeyboardInterrupt``).
"""

from __future__ import annotations


class UnknownToolError(Exception):
    """Raised when dispatch is called with a name that has no registered tool."""


class UnsupportedModelError(Exception):
    """Raised when a backend is configured with a model it does not support."""
```

- [ ] **Step 2: Verify by hand**

Run:
```bash
cd python/03_prompt_builder
uv run python -c "
from boukensha.errors import UnknownToolError, UnsupportedModelError
print(UnknownToolError, UnsupportedModelError)
"
```
Expected: prints both class objects, no errors.

- [ ] **Step 3: Commit**

```bash
git add python/03_prompt_builder/src/boukensha/errors.py
git commit -m "feat: add UnsupportedModelError"
```

---

### Task 4: Add `backends/base.py`

**Files:**
- Create: `python/03_prompt_builder/src/boukensha/backends/__init__.py` (placeholder, filled in Task 7)
- Create: `python/03_prompt_builder/src/boukensha/backends/base.py`

**Interfaces:**
- Consumes: `UnsupportedModelError` (Task 3, `..errors`).
- Produces: `Base` with classmethods `models()`, `model_info(model)`, `validate_model(model)`; instance properties `context_window`, `input_token_cost_per_million`, `output_token_cost_per_million`, `usage_unit`, `usage_level`; instance method `estimate_cost(*, input_tokens, output_tokens)`; protected helper `_configure_model(model)`. Consumed by every concrete backend (Tasks 5-6).

- [ ] **Step 1: Create the `backends/` package placeholder**

Create `python/03_prompt_builder/src/boukensha/backends/__init__.py` with just:

```python
```

- [ ] **Step 2: Write `backends/base.py`**

```python
"""Boukensha::Backends::Base port: shared backend contract for model
validation and model metadata.

Ruby defines both a class method ``model_info(model)`` (lookup by name) and
an instance method ``model_info`` (no args, returns the resolved instance's
metadata) — legal in Ruby because class methods and instance methods live in
separate method tables. Python has no such separation, so the two would
collide under one name. Resolution: ``model_info`` stays the public
classmethod; the instance's resolved metadata lives in the private
``self._model_info``, exposed only through the specific public properties
below (``context_window``, etc.) — which matches the Ruby README's
documented public instance API, which never lists ``model_info`` itself as
something instances expose.

Ruby's ``validate_model!`` interpolates ``self.name``, the fully-qualified
class name (``Boukensha::Backends::Anthropic``). Python's ``cls.__name__``
gives the bare class name (``Anthropic``) — there is no Python equivalent of
Ruby's namespaced ``Module::Class`` string; this is a language difference,
not a bug.
"""

from __future__ import annotations

from typing import Any

from ..errors import UnsupportedModelError


class Base:
    MODELS: dict[str, dict[str, Any]] | None = None

    @classmethod
    def models(cls) -> dict[str, dict[str, Any]]:
        if cls.MODELS is None:
            raise NotImplementedError(f"{cls.__name__} must define MODELS")
        return cls.MODELS

    @classmethod
    def model_info(cls, model: str) -> dict[str, Any] | None:
        return cls.models().get(str(model))

    @classmethod
    def validate_model(cls, model: str) -> str:
        model = str(model)
        if cls.model_info(model) is not None:
            return model

        supported = ", ".join(sorted(cls.models().keys()))
        raise UnsupportedModelError(
            f"{cls.__name__} does not support model {model!r}. Supported models: {supported}"
        )

    @property
    def context_window(self) -> int:
        return self._model_info["context_window"]

    @property
    def input_token_cost_per_million(self) -> float | None:
        return self._model_info["cost_per_million"]["input"]

    @property
    def output_token_cost_per_million(self) -> float | None:
        return self._model_info["cost_per_million"]["output"]

    @property
    def usage_unit(self) -> str:
        return self._model_info["usage_unit"]

    @property
    def usage_level(self) -> str | None:
        return self._model_info.get("usage_level")

    def estimate_cost(self, *, input_tokens: int, output_tokens: int) -> float | None:
        in_cost = self.input_token_cost_per_million
        out_cost = self.output_token_cost_per_million
        if in_cost is None or out_cost is None:
            return None

        return ((input_tokens * in_cost) + (output_tokens * out_cost)) / 1_000_000.0

    def _configure_model(self, model: str) -> None:
        self.model = type(self).validate_model(model)
        self._model_info = type(self).model_info(self.model)
```

- [ ] **Step 3: Verify by hand**

Run:
```bash
cd python/03_prompt_builder
uv run python -c "
from boukensha.backends.base import Base
from boukensha.errors import UnsupportedModelError

class Fake(Base):
    MODELS = {'x': {'context_window': 100, 'cost_per_million': {'input': 1.0, 'output': 2.0}, 'usage_unit': 'tokens'}}

f = Fake()
f._configure_model('x')
print(f.model, f.context_window, f.input_token_cost_per_million, f.usage_unit, f.usage_level)
print(f.estimate_cost(input_tokens=1_000_000, output_tokens=1_000_000))

try:
    f._configure_model('nope')
except UnsupportedModelError as e:
    print(f'caught: {e}')

try:
    Base.models()
except NotImplementedError as e:
    print(f'caught: {e}')
"
```
Expected:
```
x 100 1.0 tokens None
3.0
caught: Fake does not support model 'nope'. Supported models: x
caught: Base must define MODELS
```

- [ ] **Step 4: Commit**

```bash
git add python/03_prompt_builder/src/boukensha/backends/__init__.py python/03_prompt_builder/src/boukensha/backends/base.py
git commit -m "feat: add Backends.Base — model validation and metadata"
```

---

### Task 5: Add the system-prompt-as-field backends — `Anthropic`, `Gemini`

**Files:**
- Create: `python/03_prompt_builder/src/boukensha/backends/anthropic.py`
- Create: `python/03_prompt_builder/src/boukensha/backends/gemini.py`

**Interfaces:**
- Consumes: `Base` (Task 4, `.base`).
- Produces: `Anthropic(api_key, model)` and `Gemini(api_key, model)`, both with `.to_messages(messages)`, `.to_tools(tools)`, `.to_payload(context, *, max_output_tokens=1024)`, `.headers` (property), `.url` (property). Consumed by `PromptBuilder` (Task 7) and `examples/example.py` (Task 9).

**Grouped rationale:** Anthropic and Gemini are the "system prompt as a top-level payload field" family (per the Ruby README's own grouping) — both take a single-arg `to_messages(messages)`, and both keep the system prompt out of the messages list.

- [ ] **Step 1: Write `backends/anthropic.py`**

```python
"""Boukensha::Backends::Anthropic port: serializes context into the
Anthropic Messages API format (https://api.anthropic.com/v1/messages).
"""

from __future__ import annotations

from typing import Any

from .base import Base


class Anthropic(Base):
    BASE_URL = "https://api.anthropic.com/v1/messages"
    MODELS: dict[str, dict[str, Any]] = {
        "claude-haiku-4-5": {
            "context_window": 200_000,
            "cost_per_million": {"input": 1.0, "output": 5.0},
            "usage_unit": "tokens",
        },
        "claude-haiku-4-5-20251001": {
            "context_window": 200_000,
            "cost_per_million": {"input": 1.0, "output": 5.0},
            "usage_unit": "tokens",
        },
        "claude-sonnet-4-6": {
            "context_window": 1_000_000,
            "cost_per_million": {"input": 3.0, "output": 15.0},
            "usage_unit": "tokens",
        },
        "claude-opus-4-8": {
            "context_window": 1_000_000,
            "cost_per_million": {"input": 5.0, "output": 25.0},
            "usage_unit": "tokens",
        },
    }

    def __init__(self, *, api_key: str, model: str) -> None:
        self._api_key = api_key
        self._configure_model(model)

    def to_messages(self, messages: list[Any]) -> list[dict[str, Any]]:
        result: list[dict[str, Any]] = []
        for msg in messages:
            if msg.role == "tool_result":
                result.append(
                    {
                        "role": "user",
                        "content": [
                            {
                                "type": "tool_result",
                                "tool_use_id": msg.tool_use_id,
                                "content": msg.content,
                            }
                        ],
                    }
                )
            else:
                result.append({"role": msg.role, "content": msg.content})
        return result

    def to_tools(self, tools: dict[str, Any]) -> list[dict[str, Any]]:
        return [
            {
                "name": tool.name,
                "description": tool.description,
                "input_schema": {
                    "type": "object",
                    "properties": tool.parameters,
                    "required": list(tool.parameters.keys()),
                },
            }
            for tool in tools.values()
        ]

    def to_payload(self, context: Any, *, max_output_tokens: int = 1024) -> dict[str, Any]:
        return {
            "model": self.model,
            "system": context.system,
            "max_tokens": max_output_tokens,
            "tools": self.to_tools(context.tools),
            "messages": self.to_messages(context.messages),
        }

    @property
    def headers(self) -> dict[str, str]:
        return {
            "Content-Type": "application/json",
            "x-api-key": self._api_key,
            "anthropic-version": "2023-06-01",
        }

    @property
    def url(self) -> str:
        return self.BASE_URL
```

- [ ] **Step 2: Write `backends/gemini.py`**

```python
"""Boukensha::Backends::Gemini port: serializes context into the Gemini
``generateContent`` API format.
"""

from __future__ import annotations

from typing import Any

from .base import Base


class Gemini(Base):
    BASE_URL = "https://generativelanguage.googleapis.com/v1beta/models"
    MODELS: dict[str, dict[str, Any]] = {
        "gemini-3.5-flash": {
            "context_window": 1_048_576,
            "cost_per_million": {"input": 1.5, "output": 9.0},
            "usage_unit": "tokens",
        },
        "gemini-3.1-flash-lite": {
            "context_window": 1_048_576,
            "cost_per_million": {"input": 0.25, "output": 1.5},
            "usage_unit": "tokens",
        },
        "gemini-2.5-pro": {
            "context_window": 1_048_576,
            "cost_per_million": {"input": 1.25, "output": 10.0},
            "usage_unit": "tokens",
        },
        "gemini-2.5-flash": {
            "context_window": 1_048_576,
            "cost_per_million": {"input": 0.30, "output": 2.50},
            "usage_unit": "tokens",
        },
        "gemini-2.5-flash-lite": {
            "context_window": 1_048_576,
            "cost_per_million": {"input": 0.10, "output": 0.40},
            "usage_unit": "tokens",
        },
    }

    def __init__(self, *, api_key: str, model: str) -> None:
        self._api_key = api_key
        self._configure_model(model)

    def to_messages(self, messages: list[Any]) -> list[dict[str, Any]]:
        result: list[dict[str, Any]] = []
        for msg in messages:
            if msg.role == "assistant":
                result.append({"role": "model", "parts": [{"text": msg.content}]})
            elif msg.role == "tool_result":
                result.append(
                    {
                        "role": "user",
                        "parts": [
                            {
                                "functionResponse": {
                                    "name": msg.tool_use_id,
                                    "response": {"content": msg.content},
                                }
                            }
                        ],
                    }
                )
            else:
                result.append({"role": msg.role, "parts": [{"text": msg.content}]})
        return result

    def to_tools(self, tools: dict[str, Any]) -> list[dict[str, Any]]:
        if not tools:
            return []

        return [
            {
                "functionDeclarations": [
                    {
                        "name": tool.name,
                        "description": tool.description,
                        "parameters": {
                            "type": "object",
                            "properties": tool.parameters,
                            "required": list(tool.parameters.keys()),
                        },
                    }
                    for tool in tools.values()
                ]
            }
        ]

    def to_payload(self, context: Any, *, max_output_tokens: int = 1024) -> dict[str, Any]:
        return {
            "systemInstruction": {"parts": [{"text": context.system}]},
            "contents": self.to_messages(context.messages),
            "tools": self.to_tools(context.tools),
            "generationConfig": {"maxOutputTokens": max_output_tokens},
        }

    @property
    def headers(self) -> dict[str, str]:
        return {
            "Content-Type": "application/json",
            "x-goog-api-key": self._api_key,
        }

    @property
    def url(self) -> str:
        return f"{self.BASE_URL}/{self.model}:generateContent"
```

- [ ] **Step 3: Verify by hand**

Run:
```bash
cd python/03_prompt_builder
uv run python -c "
from boukensha.backends import Anthropic, Gemini
a = Anthropic(api_key='test', model='claude-haiku-4-5')
g = Gemini(api_key='test', model='gemini-2.5-flash')
print(a.url, a.context_window)
print(g.url, g.context_window)
print(g.to_tools({}))
"
```
(Note: `boukensha.backends` won't export names until Task 7 — for this step's verification, import from the submodules directly instead: `from boukensha.backends.anthropic import Anthropic` / `from boukensha.backends.gemini import Gemini`.)

Expected: no errors; prints the Anthropic/Gemini URLs and context windows, and `[]` for `Gemini.to_tools({})`.

- [ ] **Step 4: Commit**

```bash
git add python/03_prompt_builder/src/boukensha/backends/anthropic.py python/03_prompt_builder/src/boukensha/backends/gemini.py
git commit -m "feat: add Anthropic and Gemini backends"
```

---

### Task 6: Add the message-array backends — `Ollama`, `OllamaCloud`, `OpenAI`

**Files:**
- Create: `python/03_prompt_builder/src/boukensha/backends/ollama.py`
- Create: `python/03_prompt_builder/src/boukensha/backends/ollama_cloud.py`
- Create: `python/03_prompt_builder/src/boukensha/backends/openai.py`

**Interfaces:**
- Consumes: `Base` (Task 4, `.base`).
- Produces: `Ollama(model, host="http://localhost:11434")`, `OllamaCloud(api_key, model)`, `OpenAI(api_key, model)` — all with `.to_messages(system, messages)` (**two args**, not one — see the plan's Global Constraints "known upstream quirk" note), `.to_tools(tools)`, `.to_payload(context, *, max_output_tokens=1024)`, `.headers` (property), `.url` (property). Consumed by `PromptBuilder` (Task 7) and `examples/example.py` (Task 9).

**Grouped rationale:** these three share the "system prompt as a `role: system` message, tools wrapped in a `function` envelope" family (per the Ruby README's own grouping).

- [ ] **Step 1: Write `backends/ollama.py`**

```python
"""Boukensha::Backends::Ollama port: serializes context into the local
Ollama chat API format (http://localhost:11434/api/chat).
"""

from __future__ import annotations

from typing import Any

from .base import Base


class Ollama(Base):
    MODELS: dict[str, dict[str, Any]] = {
        "gemma4": {
            "context_window": 128_000,
            "cost_per_million": {"input": 0.0, "output": 0.0},
            "usage_unit": "local_compute",
        },
        "gemma4:e2b": {
            "context_window": 128_000,
            "cost_per_million": {"input": 0.0, "output": 0.0},
            "usage_unit": "local_compute",
        },
        "gemma4:e4b": {
            "context_window": 128_000,
            "cost_per_million": {"input": 0.0, "output": 0.0},
            "usage_unit": "local_compute",
        },
        "gemma4:12b": {
            "context_window": 256_000,
            "cost_per_million": {"input": 0.0, "output": 0.0},
            "usage_unit": "local_compute",
        },
        "gemma4:26b": {
            "context_window": 256_000,
            "cost_per_million": {"input": 0.0, "output": 0.0},
            "usage_unit": "local_compute",
        },
        "gemma4:31b": {
            "context_window": 256_000,
            "cost_per_million": {"input": 0.0, "output": 0.0},
            "usage_unit": "local_compute",
        },
        "qwen3:30b": {
            "context_window": 256_000,
            "cost_per_million": {"input": 0.0, "output": 0.0},
            "usage_unit": "local_compute",
        },
        "qwen3:8b": {
            "context_window": 40_000,
            "cost_per_million": {"input": 0.0, "output": 0.0},
            "usage_unit": "local_compute",
        },
        "deepseek-r1:8b": {
            "context_window": 128_000,
            "cost_per_million": {"input": 0.0, "output": 0.0},
            "usage_unit": "local_compute",
        },
    }

    def __init__(self, *, model: str, host: str = "http://localhost:11434") -> None:
        self._host = host
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
        return {"Content-Type": "application/json"}

    @property
    def url(self) -> str:
        return f"{self._host}/api/chat"
```

- [ ] **Step 2: Write `backends/ollama_cloud.py`**

```python
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
```

- [ ] **Step 3: Write `backends/openai.py`**

```python
"""Boukensha::Backends::OpenAI port: serializes context into the OpenAI
Chat Completions API format.
"""

from __future__ import annotations

from typing import Any

from .base import Base


class OpenAI(Base):
    BASE_URL = "https://api.openai.com/v1/chat/completions"
    MODELS: dict[str, dict[str, Any]] = {
        "gpt-5.5": {
            "context_window": 1_000_000,
            "cost_per_million": {"input": 5.0, "output": 30.0},
            "usage_unit": "tokens",
        },
        "gpt-5.4": {
            "context_window": 1_000_000,
            "cost_per_million": {"input": 2.5, "output": 15.0},
            "usage_unit": "tokens",
        },
        "gpt-5.4-mini": {
            "context_window": 400_000,
            "cost_per_million": {"input": 0.75, "output": 4.5},
            "usage_unit": "tokens",
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
                conversation.append({"role": "tool", "tool_call_id": msg.tool_use_id, "content": msg.content})
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
            "messages": self.to_messages(context.system, context.messages),
            "tools": self.to_tools(context.tools),
            "max_completion_tokens": max_output_tokens,
        }

    @property
    def headers(self) -> dict[str, str]:
        return {
            "Content-Type": "application/json",
            "Authorization": f"Bearer {self._api_key}",
        }

    @property
    def url(self) -> str:
        return self.BASE_URL
```

- [ ] **Step 4: Verify by hand**

Run:
```bash
cd python/03_prompt_builder
uv run python -c "
from boukensha.backends.ollama import Ollama
from boukensha.backends.ollama_cloud import OllamaCloud
from boukensha.backends.openai import OpenAI

o = Ollama(model='qwen3:8b')
oc = OllamaCloud(api_key='test', model='kimi-k2.5:cloud')
oa = OpenAI(api_key='test', model='gpt-5.4-mini')
print(o.url, o.usage_unit, o.estimate_cost(input_tokens=1000, output_tokens=1000))
print(oc.url, oc.usage_unit, oc.usage_level, oc.estimate_cost(input_tokens=1000, output_tokens=1000))
print(oa.url, oa.usage_unit)
print(o.to_messages('sys prompt', []))
"
```
Expected: no errors; `o.estimate_cost(...)` prints `0.0` (Ollama's costs are `0.0`, not `None`); `oc.estimate_cost(...)` prints `None` (`OllamaCloud`'s costs are `None`); `o.to_messages('sys prompt', [])` prints `[{'role': 'system', 'content': 'sys prompt'}]`.

- [ ] **Step 5: Commit**

```bash
git add python/03_prompt_builder/src/boukensha/backends/ollama.py python/03_prompt_builder/src/boukensha/backends/ollama_cloud.py python/03_prompt_builder/src/boukensha/backends/openai.py
git commit -m "feat: add Ollama, OllamaCloud, and OpenAI backends"
```

---

### Task 7: Wire up `backends/__init__.py` and add `PromptBuilder`

**Files:**
- Modify: `python/03_prompt_builder/src/boukensha/backends/__init__.py`
- Create: `python/03_prompt_builder/src/boukensha/prompt_builder.py`

**Interfaces:**
- Consumes: `Anthropic`, `Base`, `Gemini`, `Ollama`, `OllamaCloud`, `OpenAI` (Tasks 4-6).
- Produces: `from boukensha.backends import Anthropic, Base, Gemini, Ollama, OllamaCloud, OpenAI` (the backends' public import surface), and `PromptBuilder(context, backend)` with `.to_messages()`, `.to_tools()`, `.to_api_payload(*, max_output_tokens=1024)`, `.headers` (property), `.url` (property). Consumed by the top-level package `__init__.py` (Task 8) and `examples/example.py` (Task 9).

- [ ] **Step 1: Replace the placeholder `backends/__init__.py`**

```python
from .anthropic import Anthropic
from .base import Base
from .gemini import Gemini
from .ollama import Ollama
from .ollama_cloud import OllamaCloud
from .openai import OpenAI

__all__ = ["Anthropic", "Base", "Gemini", "Ollama", "OllamaCloud", "OpenAI"]
```

- [ ] **Step 2: Write `prompt_builder.py`**

```python
"""Boukensha::PromptBuilder port: delegates Context serialization to
whichever backend it's given.

Known upstream quirk, preserved intentionally: ``to_messages`` always calls
``backend.to_messages(context.messages)`` with exactly one argument. This
matches every backend's real signature for ``Anthropic``/``Gemini`` (which
take one arg, ``messages``), but not ``Ollama``/``OllamaCloud``/``OpenAI``
(which take two, ``system, messages``) — calling ``PromptBuilder.to_messages``
directly with one of those three backends will raise a ``TypeError``. This is
a real, unaddressed inconsistency in the Ruby source (confirmed: it isn't
fixed in ``ruby/04_api_client`` either), and it never triggers in practice
because ``to_api_payload`` routes through each backend's own ``to_payload``,
which calls that backend's ``to_messages`` with the correct arity internally.
Ported as-is rather than "fixed" — see the plan's Global Constraints.
"""

from __future__ import annotations

from typing import Any


class PromptBuilder:
    def __init__(self, context: Any, backend: Any) -> None:
        self._context = context
        self._backend = backend

    def to_messages(self) -> list[dict[str, Any]]:
        return self._backend.to_messages(self._context.messages)

    def to_tools(self) -> list[dict[str, Any]]:
        return self._backend.to_tools(self._context.tools)

    def to_api_payload(self, *, max_output_tokens: int = 1024) -> dict[str, Any]:
        return self._backend.to_payload(self._context, max_output_tokens=max_output_tokens)

    @property
    def headers(self) -> dict[str, str]:
        return self._backend.headers

    @property
    def url(self) -> str:
        return self._backend.url
```

- [ ] **Step 3: Verify by hand**

Run:
```bash
cd python/03_prompt_builder
uv run python -c "
from boukensha.backends import Anthropic
from boukensha.context import Context
from boukensha.prompt_builder import PromptBuilder
from boukensha.tasks import Player

ctx = Context(task=Player, system='You are a MUD assistant.')
ctx.add_message('user', 'hello')
backend = Anthropic(api_key='test', model='claude-haiku-4-5')
builder = PromptBuilder(ctx, backend)
print(builder.url)
print(builder.headers)
print(builder.to_api_payload())
"
```
Expected: no errors; prints the Anthropic URL, headers dict (with `x-api-key: test`), and a full payload dict with `model`, `system`, `max_tokens`, `tools: []`, and one serialized user message.

- [ ] **Step 4: Commit**

```bash
git add python/03_prompt_builder/src/boukensha/backends/__init__.py python/03_prompt_builder/src/boukensha/prompt_builder.py
git commit -m "feat: wire up backends package exports, add PromptBuilder"
```

---

### Task 8: Wire up top-level package exports

**Files:**
- Modify: `python/03_prompt_builder/src/boukensha/__init__.py`

**Interfaces:**
- Consumes: `Config` (Task 2), `Context`/`Tool`/`Message`/`Registry` (Task 1), `UnknownToolError`/`UnsupportedModelError` (Task 3), `backends` subpackage (Task 7), `PromptBuilder` (Task 7), `tasks` (Task 1).
- Produces: the full public import surface used by `examples/example.py` (Task 9).

- [ ] **Step 1: Replace the placeholder `__init__.py`**

```python
from . import backends, tasks
from .config import Config
from .context import Context
from .errors import UnknownToolError, UnsupportedModelError
from .message import Message
from .prompt_builder import PromptBuilder
from .registry import Registry
from .tool import Tool

__all__ = [
    "Config",
    "Context",
    "Message",
    "PromptBuilder",
    "Registry",
    "Tool",
    "UnknownToolError",
    "UnsupportedModelError",
    "backends",
    "tasks",
]
```

- [ ] **Step 2: Verify the public import surface**

Run: `cd python/03_prompt_builder && uv run python -c "from boukensha import Config, Context, Message, PromptBuilder, Registry, Tool, UnknownToolError, UnsupportedModelError, backends, tasks; print('ok')"`
Expected: `ok`, no errors.

- [ ] **Step 3: Commit**

```bash
git add python/03_prompt_builder/src/boukensha/__init__.py
git commit -m "feat: export PromptBuilder, backends, UnsupportedModelError from boukensha package"
```

---

### Task 9: Port the runnable example

**Files:**
- Create: `python/03_prompt_builder/examples/example.py`

**Interfaces:**
- Consumes: `Config`, `Context`, `PromptBuilder`, `Registry` from `boukensha` (Task 8); `Anthropic`, `Gemini`, `Ollama`, `OllamaCloud`, `OpenAI` from `boukensha.backends` (Task 7); `Player` from `boukensha.tasks` (Task 1).
- Produces: a runnable smoke-test script, the acceptance target for this step.

- [ ] **Step 1: Write `examples/example.py`, ported from `ruby/03_prompt_builder/examples/example.rb`**

```python
import json
import os
from pathlib import Path

# Override the config directory so the example works from the repo root.
# In real usage a user's ~/.boukensha is picked up automatically.
os.environ.setdefault(
    "BOUKENSHA_DIR", str((Path(__file__).parent.parent.parent.parent.parent / ".boukensha").resolve())
)

from boukensha import Config, Context, PromptBuilder, Registry
from boukensha.backends import Anthropic, Gemini, Ollama, OllamaCloud, OpenAI
from boukensha.tasks import Player

config = Config()
player_settings = config.tasks("player")
system_prompt = Player.system_prompt(
    player_settings,
    user_prompts_dir=config.user_prompts_dir,
    default_prompts_dir=Config.PROMPTS_DIR,
)

ctx = Context(task=Player, system=system_prompt)
registry = Registry(ctx)

registry.tool(
    "look",
    description="Look around the current room for details",
    parameters={},
    block=lambda: "A damp stone corridor stretches north. Torches flicker on the walls.",
)

registry.tool(
    "move",
    description="Move the player in a direction (north, south, east, west, up, down)",
    parameters={"direction": {"type": "string", "description": "The direction to move"}},
    block=lambda direction: f"You move {direction} into a torch-lit corridor.",
)

ctx.add_message("user", "I just arrived in the dungeon. What's around me, and can you move north?")
ctx.add_message("assistant", "Let me take a look around first.")
ctx.add_message(
    "tool_result",
    "A damp stone corridor stretches north. Torches flicker on the walls.",
    tool_use_id="toolu_01X",
)

print("=== BOUKENSHA Step 3: Prompt Builder ===")
provider = Player.provider(player_settings)
model = Player.model(player_settings)

if provider == "anthropic":
    backend = Anthropic(api_key=os.environ["ANTHROPIC_API_KEY"], model=model)
elif provider == "ollama":
    backend = Ollama(model=model)
elif provider == "ollama_cloud":
    backend = OllamaCloud(api_key=os.environ["OLLAMA_API_KEY"], model=model)
elif provider == "openai":
    backend = OpenAI(api_key=os.environ["OPENAI_API_KEY"], model=model)
elif provider == "gemini":
    backend = Gemini(api_key=os.environ["GEMINI_API_KEY"], model=model)
else:
    raise ValueError(f"Unsupported provider for player task: {provider}")

builder = PromptBuilder(ctx, backend)

print()
print(f"Config: {config}")
print(f"Provider: {provider}")
print(f"Model: {model}")
print(json.dumps(builder.to_api_payload(), indent=2))
```

- [ ] **Step 2: Run it against the repo-root `.boukensha/`**

The repo's `.boukensha/settings.yaml` sets `provider: anthropic`, so the script needs `ANTHROPIC_API_KEY` set — but `PromptBuilder` never makes an HTTP call, it only builds and prints a payload dict, so **any placeholder string works**:

Run: `cd python/03_prompt_builder && ANTHROPIC_API_KEY=test-key uv run examples/example.py`

Expected: prints the header, `Config: Config(dir=..., tasks=player)`, `Provider: anthropic`, `Model: claude-haiku-4-5`, then a pretty-printed JSON payload with `model`, `system` (now populated — this is the first step where `Config.PROMPTS_DIR` is wired back in, so `System prompt` should resolve to the shipped default text unless a user override exists), `max_tokens`, `tools` (the `look`/`move` tool schemas), and `messages` (3 entries: user, assistant, and the tool_result wrapped as `role: user` per Anthropic's convention).

- [ ] **Step 3: Spot-check against the Ruby README's documented payload shapes**

`ruby/03_prompt_builder/README.md`'s "Tool Results"/"Tool Definitions"/"Message Roles" sections document the exact JSON shape each backend produces. Confirm the Python run's `tool_result` message matches the Anthropic shape shown there (`{"role": "user", "content": [{"type": "tool_result", "tool_use_id": ..., "content": ...}]}`) and the tool schema matches the `input_schema` shape shown there.

- [ ] **Step 4: Commit**

```bash
git add python/03_prompt_builder/examples/example.py
git commit -m "feat: port prompt-builder example script from Ruby"
```

---

### Task 10: Write the step README

**Files:**
- Create: `python/03_prompt_builder/README.md`

**Interfaces:**
- Consumes: nothing (documentation only).
- Produces: user-facing docs for this step, following the structural pattern of `python/02_the_registry/README.md`, adapted for the much larger surface area of this step (backends, model tables, per-provider payload shapes).

- [ ] **Step 1: Write `README.md`**

Base the content on `ruby/03_prompt_builder/README.md`'s structure (How It Works diagram, `PromptBuilder` method table, per-backend sections, System Prompt / Tool Results / Tool Definitions / Message Roles JSON comparison tables, Considerations section) — port the prose and JSON examples as-is (they describe the wire format, which is identical regardless of implementation language), and add these Python-specific sections:

- **Package layout** — mirror the `File Structure` block from this plan.
- **`Config.PROMPTS_DIR` restored** — one paragraph noting this step re-adds the class attribute dropped in `01_struct_skeleton`/`02_the_registry`, since it now ships its own `prompts/system.md`.
- **Design note: the `model_info` naming collision** — explain the classmethod-vs-instance-property resolution from this plan's Global Constraints, briefly, so a reader of `backends/base.py` isn't confused about why there's no public `model_info` instance accessor.
- **Design note: `PromptBuilder.to_messages`'s known arity quirk** — copy the plan's "known upstream quirk" callout, so nobody "fixes" it while porting `04_api_client` without realizing it's an intentional parity choice, not an oversight.
- **Run example** — actually run `ANTHROPIC_API_KEY=test-key uv run examples/example.py` and paste the real output (don't hand-copy from the Ruby README's example, which uses different message content/tool descriptions than this step's `examples/example.rb`/`example.py` — verify against the actual script in this repo, not the general prose examples).

- [ ] **Step 2: Proofread the README against the actual code**

For every method table (`PromptBuilder`, `Backends.Base`, each concrete backend), confirm names/signatures/defaults against the real `.py` files. For the model tables, confirm the numbers match `MODELS` in each backend file exactly. Actually run the example and use its real output for the "Run example" section.

- [ ] **Step 3: Commit**

```bash
git add python/03_prompt_builder/README.md
git commit -m "docs: add README for python/03_prompt_builder"
```

---

## Self-Review Notes

- **Spec coverage:** Every Ruby file in `03_prompt_builder/lib` maps to a task: unchanged carry-forward (Task 1), modified `config.py`/`errors.py` (Tasks 2-3), new `backends/base.py` (Task 4), new `backends/{anthropic,gemini}.py` (Task 5), new `backends/{ollama,ollama_cloud,openai}.py` (Task 6), `backends/__init__.py` + `prompt_builder.py` (Task 7), top-level exports (Task 8), example (Task 9), docs (Task 10).
- **Diff-driven verification, not re-derivation:** Every "unchanged" claim in this plan (Task 1's five files, `context.py`) and every "modified" claim (Task 2/3) was confirmed with an actual `diff` against the Ruby source before this plan was written, not assumed by analogy. The diffs are quoted or described exactly (e.g., `config.rb`'s only change is the `PROMPTS_DIR` constant re-appearing).
- **Deliberate, documented deviations:** (1) `tool.parameters.keys.map(&:to_s)` doesn't port — `Tool.parameters` has been string-keyed since `01_struct_skeleton`. (2) `PromptBuilder.to_messages`'s arity mismatch with Ollama-family backends is preserved as-is, not fixed, because it's a real (if latent) upstream inconsistency, confirmed unaddressed as of `04_api_client` too. Both are called out in Global Constraints and slated for the README, following the precedent set by `00_config/plan.md`'s "Design Considerations" and `02_the_registry`'s "Design note" sections.
- **Naming collision resolved, not papered over:** the `model_info` classmethod/instance-method collision is explicitly designed around (private `_model_info` attribute, public classmethod), with the rationale documented inline in `backends/base.py`'s module docstring and cross-referenced in Global Constraints — an implementer shouldn't need to rediscover this from scratch.
- **Type consistency check:** `Registry.tool(..., block=...)` (Task 1, carried from `02_the_registry`) is used in Task 9's `example.py` for the zero-arg `look` tool (`block=lambda: "..."`) and the one-arg `move` tool (`block=lambda direction: f"..."`) — matches the established keyword-arg convention, no decorator introduced. `PromptBuilder.__init__(self, context, backend)` (Task 7) takes positional args, matching Ruby's `initialize(context, backend)` (positional, not keyword) — this is the one constructor in this plan that is NOT keyword-only, correctly mirroring Ruby's own positional-arg choice there. Every concrete backend's `__init__` (Tasks 5-6) takes `api_key`/`host`/`model` as keyword-only (`*,`), matching Ruby's `initialize(api_key:, model:)` keyword-required pattern.
