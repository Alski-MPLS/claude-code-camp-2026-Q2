# Python 05 Agent Loop Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Port `ruby/05_agent_loop` to Python — add an `Agent` class that drives the tool-call loop, add `parse_response` to every backend, add `tools` kwarg to `Client.call` and `PromptBuilder.to_api_payload`, add `LoopError` to errors, and add `max_iterations`/`max_output_tokens` helpers to `Tasks::Base`, all as a self-contained `python/05_agent_loop` project.

**Architecture:** Copy the entire `04_api_client` source tree into `05_agent_loop`, then add/modify exactly the files listed below. The `Agent` class takes `context`, `registry`, `builder`, `client`, and optional `task_settings`; `run()` drives the loop and returns the final text string. Every backend gains a `parse_response(response)` method that normalises provider-specific response shapes into a common `{"stop_reason": "tool_use"|"end_turn", "content": [...]}` dict; backends that store tool calls in conversation history (Ollama, OllamaCloud, OpenAI, Gemini) also gain an `_assistant_message`/`_assistant_parts` helper.

**Tech Stack:** Python ≥3.11, stdlib only (no new dependencies), `pytest` for tests, `uv` for package management.

## Global Constraints

- Python ≥3.11, `requires-python = ">=3.11"`
- Package name: `boukensha`, version: `0.1.0`, description: `"Boukensha agent loop (Step 5)"`
- Self-contained project: own `pyproject.toml`, own `.venv`, full copy of `boukensha` source
- No third-party HTTP libraries — `urllib.request` only (inherited from 04)
- `from __future__ import annotations` at top of every new/modified source file
- `Agent` constants: `MAX_ITERATIONS = 25`, `WRAP_UP_OUTPUT_TOKENS = 400`
- `WRAP_UP_DIRECTIVE` string (verbatim):
  ```
  You have reached your action limit for this turn. Do not call any more tools.
  Briefly summarize what you accomplished, what is still unfinished, and the
  single next action you would take.
  ```
- Normalised response shape produced by every `parse_response`:
  ```python
  {"stop_reason": "tool_use" | "end_turn", "content": [{"type": "text", "text": "..."} | {"type": "tool_use", "id": "...", "name": "...", "input": {...}}]}
  ```
- `Message.content` can be either `str` (plain text) or `list[dict]` (normalised content blocks stored for assistant turns with tool calls) — the existing `Message` dataclass stores it as `Any`
- Preserve the `to_messages` arity quirk from 04 (documented in `prompt_builder.py`) — do not fix it

---

## File Map

| Status | Path | Responsibility |
|--------|------|---------------|
| Create | `week1_baseline/python/05_agent_loop/pyproject.toml` | Project metadata |
| Create | `week1_baseline/python/05_agent_loop/src/boukensha/agent.py` | **New** — `Agent` class, loop logic |
| Modify | `week1_baseline/python/05_agent_loop/src/boukensha/errors.py` | Add `LoopError` |
| Modify | `week1_baseline/python/05_agent_loop/src/boukensha/client.py` | Add `tools` kwarg to `call()` |
| Modify | `week1_baseline/python/05_agent_loop/src/boukensha/prompt_builder.py` | Add `tools` kwarg to `to_api_payload()`; add `parse_response()` |
| Modify | `week1_baseline/python/05_agent_loop/src/boukensha/tasks/base.py` | Add `max_iterations()` and `max_output_tokens()` classmethods |
| Modify | `week1_baseline/python/05_agent_loop/src/boukensha/message.py` | Widen `content` type annotation to `Any` |
| Modify | `week1_baseline/python/05_agent_loop/src/boukensha/backends/anthropic.py` | Add `parse_response()` |
| Modify | `week1_baseline/python/05_agent_loop/src/boukensha/backends/openai.py` | Add `parse_response()`, `_assistant_message()` |
| Modify | `week1_baseline/python/05_agent_loop/src/boukensha/backends/gemini.py` | Add `parse_response()`, `_assistant_parts()` |
| Modify | `week1_baseline/python/05_agent_loop/src/boukensha/backends/ollama.py` | Add `parse_response()`, `_assistant_message()` |
| Modify | `week1_baseline/python/05_agent_loop/src/boukensha/backends/ollama_cloud.py` | Add `parse_response()`, `_assistant_message()` |
| Modify | `week1_baseline/python/05_agent_loop/src/boukensha/__init__.py` | Add `Agent`, `LoopError` to exports |
| Create | `week1_baseline/python/05_agent_loop/examples/example.py` | Drive live agent loop |
| Create | `week1_baseline/python/05_agent_loop/prompts/system.md` | Default system prompt (copy from Ruby) |
| Create | `week1_baseline/python/05_agent_loop/tests/__init__.py` | Empty test package marker |
| Create | `week1_baseline/python/05_agent_loop/tests/test_agent.py` | Unit tests for `Agent` |
| Create | `week1_baseline/python/05_agent_loop/README.md` | Documentation |

Unchanged from 04 (copy verbatim): `config.py`, `context.py`, `registry.py`, `tool.py`, `backends/base.py`, `backends/__init__.py`, `tasks/__init__.py`, `tasks/player.py`.

---

### Task 1: Scaffold project and copy source from 04_api_client

**Files:**
- Create: `week1_baseline/python/05_agent_loop/pyproject.toml`
- Create: `week1_baseline/python/05_agent_loop/tests/__init__.py`
- Create: all source files copied from `python/04_api_client/src/boukensha/`
- Create: `week1_baseline/python/05_agent_loop/prompts/system.md`

**Interfaces:**
- Produces: installable `boukensha 0.1.0` package with all 04 functionality intact

- [ ] **Step 1: Create directory skeleton**

```bash
mkdir -p week1_baseline/python/05_agent_loop/src/boukensha/backends
mkdir -p week1_baseline/python/05_agent_loop/src/boukensha/tasks
mkdir -p week1_baseline/python/05_agent_loop/examples
mkdir -p week1_baseline/python/05_agent_loop/tests
mkdir -p week1_baseline/python/05_agent_loop/prompts
```

- [ ] **Step 2: Write `pyproject.toml`**

```toml
[project]
name = "boukensha"
version = "0.1.0"
description = "Boukensha agent loop (Step 5)"
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

- [ ] **Step 3: Copy all source files from 04_api_client**

```bash
SRC=week1_baseline/python/04_api_client/src/boukensha
DST=week1_baseline/python/05_agent_loop/src/boukensha

cp $SRC/__init__.py          $DST/__init__.py
cp $SRC/client.py            $DST/client.py
cp $SRC/config.py            $DST/config.py
cp $SRC/context.py           $DST/context.py
cp $SRC/errors.py            $DST/errors.py
cp $SRC/message.py           $DST/message.py
cp $SRC/prompt_builder.py    $DST/prompt_builder.py
cp $SRC/registry.py          $DST/registry.py
cp $SRC/tool.py              $DST/tool.py
cp $SRC/backends/__init__.py   $DST/backends/__init__.py
cp $SRC/backends/base.py       $DST/backends/base.py
cp $SRC/backends/anthropic.py  $DST/backends/anthropic.py
cp $SRC/backends/gemini.py     $DST/backends/gemini.py
cp $SRC/backends/ollama.py     $DST/backends/ollama.py
cp $SRC/backends/ollama_cloud.py $DST/backends/ollama_cloud.py
cp $SRC/backends/openai.py     $DST/backends/openai.py
cp $SRC/tasks/__init__.py  $DST/tasks/__init__.py
cp $SRC/tasks/base.py      $DST/tasks/base.py
cp $SRC/tasks/player.py    $DST/tasks/player.py
```

- [ ] **Step 4: Copy system prompt and create empty test marker**

```bash
cp week1_baseline/ruby/05_agent_loop/prompts/system.md \
   week1_baseline/python/05_agent_loop/prompts/system.md
touch week1_baseline/python/05_agent_loop/tests/__init__.py
```

- [ ] **Step 5: Create venv and install**

```bash
cd week1_baseline/python/05_agent_loop
uv venv
uv pip install -e .
```

Expected: `Successfully installed boukensha-0.1.0`

- [ ] **Step 6: Verify imports**

```bash
cd week1_baseline/python/05_agent_loop
.venv/bin/python -c "from boukensha import Config, Context, Client, PromptBuilder; print('ok')"
```

Expected: `ok`

- [ ] **Step 7: Commit**

```bash
git add week1_baseline/python/05_agent_loop/pyproject.toml \
        week1_baseline/python/05_agent_loop/src/ \
        week1_baseline/python/05_agent_loop/prompts/ \
        week1_baseline/python/05_agent_loop/tests/__init__.py
git commit -m "feat: scaffold python/05_agent_loop, copy source from 04"
```

---

### Task 2: Add `LoopError`, widen `Message.content`, update `Tasks::Base`

**Files:**
- Modify: `week1_baseline/python/05_agent_loop/src/boukensha/errors.py`
- Modify: `week1_baseline/python/05_agent_loop/src/boukensha/message.py`
- Modify: `week1_baseline/python/05_agent_loop/src/boukensha/tasks/base.py`
- Create: `week1_baseline/python/05_agent_loop/tests/test_agent.py` (first batch of tests)

**Interfaces:**
- Produces:
  - `LoopError(Exception)` importable from `boukensha.errors`
  - `Message.content: Any` (accepts both `str` and `list[dict]`)
  - `Player.max_iterations(settings) -> int` (default `25`)
  - `Player.max_output_tokens(settings) -> int` (default `1024`)

- [ ] **Step 1: Write failing tests**

File: `week1_baseline/python/05_agent_loop/tests/test_agent.py`

```python
from boukensha.errors import ApiError, LoopError, UnknownToolError, UnsupportedModelError
from boukensha.tasks.player import Player


def test_loop_error_is_exception():
    err = LoopError("ran away")
    assert isinstance(err, Exception)
    assert str(err) == "ran away"


def test_existing_errors_still_present():
    assert issubclass(ApiError, Exception)
    assert issubclass(UnknownToolError, Exception)
    assert issubclass(UnsupportedModelError, Exception)


def test_player_max_iterations_default():
    assert Player.max_iterations({}) == 25


def test_player_max_iterations_from_settings():
    assert Player.max_iterations({"max_iterations": 10}) == 10


def test_player_max_output_tokens_default():
    assert Player.max_output_tokens({}) == 1024


def test_player_max_output_tokens_from_settings():
    assert Player.max_output_tokens({"max_output_tokens": 512}) == 512


def test_message_content_accepts_list():
    from boukensha.message import Message
    blocks = [{"type": "text", "text": "hi"}, {"type": "tool_use", "id": "x", "name": "f", "input": {}}]
    msg = Message(role="assistant", content=blocks)
    assert msg.content == blocks
```

- [ ] **Step 2: Install pytest and run failing tests**

```bash
cd week1_baseline/python/05_agent_loop
uv pip install pytest
.venv/bin/pytest tests/test_agent.py -v
```

Expected: multiple FAILED — `ImportError: cannot import name 'LoopError'` and `AttributeError: type object 'Player' has no attribute 'max_iterations'`

- [ ] **Step 3: Update `errors.py`**

File: `week1_baseline/python/05_agent_loop/src/boukensha/errors.py`

```python
"""Boukensha-specific error classes."""

from __future__ import annotations


class UnknownToolError(Exception):
    """Raised when dispatch is called with a name that has no registered tool."""


class UnsupportedModelError(Exception):
    """Raised when a backend is configured with a model it does not support."""


class ApiError(Exception):
    """Raised when an HTTP request to the LLM API fails."""


class LoopError(Exception):
    """Raised when the agent loop exceeds its iteration ceiling."""
```

- [ ] **Step 4: Update `message.py` — widen `content` to `Any`**

File: `week1_baseline/python/05_agent_loop/src/boukensha/message.py`

```python
"""Boukensha::Message port: a single unit of conversation."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any


@dataclass
class Message:
    role: str
    content: Any
    tool_use_id: str | None = None

    def __str__(self) -> str:
        preview = str(self.content)[:61]
        id_tag = f" [{self.tool_use_id}]" if self.tool_use_id else ""
        return f"#<Message role={self.role}{id_tag} content={preview}...>"
```

- [ ] **Step 5: Update `tasks/base.py` — add `max_iterations` and `max_output_tokens`**

File: `week1_baseline/python/05_agent_loop/src/boukensha/tasks/base.py`

```python
"""Boukensha::Tasks::Base port: an abstract stateless task class."""

from __future__ import annotations

from pathlib import Path
from typing import Any


class Base:
    TASK_NAME: str | None = None
    DEFAULT_MAX_ITERATIONS: int = 25
    DEFAULT_MAX_OUTPUT_TOKENS: int = 1024

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

    @classmethod
    def max_iterations(cls, settings: dict[str, Any]) -> int:
        return cls._integer_setting(settings, "max_iterations", cls.DEFAULT_MAX_ITERATIONS)

    @classmethod
    def max_output_tokens(cls, settings: dict[str, Any]) -> int:
        return cls._integer_setting(settings, "max_output_tokens", cls.DEFAULT_MAX_OUTPUT_TOKENS)

    # ---------- private -----------------------------------------------------

    @classmethod
    def _integer_setting(cls, settings: dict[str, Any], key: str, default: int) -> int:
        value = settings.get(key)
        if value is None:
            return default
        return int(value)

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

- [ ] **Step 6: Run all tests**

```bash
cd week1_baseline/python/05_agent_loop
.venv/bin/pytest tests/test_agent.py -v
```

Expected: `7 passed`

- [ ] **Step 7: Commit**

```bash
git add week1_baseline/python/05_agent_loop/src/boukensha/errors.py \
        week1_baseline/python/05_agent_loop/src/boukensha/message.py \
        week1_baseline/python/05_agent_loop/src/boukensha/tasks/base.py \
        week1_baseline/python/05_agent_loop/tests/test_agent.py
git commit -m "feat: add LoopError, widen Message.content, add max_iterations/max_output_tokens to Tasks::Base"
```

---

### Task 3: Update `Client.call` and `PromptBuilder` — add `tools` kwarg and `parse_response`

**Files:**
- Modify: `week1_baseline/python/05_agent_loop/src/boukensha/client.py`
- Modify: `week1_baseline/python/05_agent_loop/src/boukensha/prompt_builder.py`

**Interfaces:**
- Consumes: `backend.to_payload(context, max_output_tokens=N, tools=None|list)` (backends updated in Task 4)
- Produces:
  - `Client.call(*, max_output_tokens=1024, tools=None) -> dict`
  - `PromptBuilder.to_api_payload(*, max_output_tokens=1024, tools=None) -> dict`
  - `PromptBuilder.parse_response(response: dict) -> dict`

- [ ] **Step 1: Write failing tests**

Append to `week1_baseline/python/05_agent_loop/tests/test_agent.py`:

```python
import json
from io import BytesIO
from unittest.mock import MagicMock, patch

from boukensha.client import Client
from boukensha.errors import ApiError
from boukensha.prompt_builder import PromptBuilder


def _make_builder(url="https://api.example.com/v1/messages", payload=None):
    builder = MagicMock(spec=PromptBuilder)
    builder.url = url
    builder.headers = {"Content-Type": "application/json", "x-api-key": "test"}
    builder.to_api_payload.return_value = payload or {"model": "test", "messages": []}
    return builder


def _fake_response(body: dict):
    raw = json.dumps(body).encode()
    resp = MagicMock()
    resp.read.return_value = raw
    resp.__enter__ = lambda s: s
    resp.__exit__ = MagicMock(return_value=False)
    return resp


def test_client_call_passes_tools_none_by_default():
    builder = _make_builder()
    with patch("boukensha.client.urllib.request.urlopen", return_value=_fake_response({})):
        Client(builder).call()
    builder.to_api_payload.assert_called_once_with(max_output_tokens=1024, tools=None)


def test_client_call_passes_tools_empty_list():
    builder = _make_builder()
    with patch("boukensha.client.urllib.request.urlopen", return_value=_fake_response({})):
        Client(builder).call(tools=[])
    builder.to_api_payload.assert_called_once_with(max_output_tokens=1024, tools=[])


def test_prompt_builder_parse_response_delegates_to_backend():
    backend = MagicMock()
    backend.parse_response.return_value = {"stop_reason": "end_turn", "content": []}
    builder = PromptBuilder(MagicMock(), backend)
    result = builder.parse_response({"some": "response"})
    backend.parse_response.assert_called_once_with({"some": "response"})
    assert result == {"stop_reason": "end_turn", "content": []}
```

- [ ] **Step 2: Run tests to confirm failures**

```bash
cd week1_baseline/python/05_agent_loop
.venv/bin/pytest tests/test_agent.py::test_client_call_passes_tools_none_by_default \
                 tests/test_agent.py::test_client_call_passes_tools_empty_list \
                 tests/test_agent.py::test_prompt_builder_parse_response_delegates_to_backend -v
```

Expected: 3 FAILED

- [ ] **Step 3: Update `client.py` — add `tools` kwarg**

File: `week1_baseline/python/05_agent_loop/src/boukensha/client.py`

Replace the entire file with:

```python
"""Boukensha::Client port: makes the HTTP POST and returns the parsed JSON response.

Uses Python stdlib urllib.request — no third-party HTTP library, matching the
Ruby implementation's 'no gems' principle.
"""

from __future__ import annotations

import json
import time
import urllib.error
import urllib.request
from typing import Any

from .errors import ApiError

RETRYABLE_STATUS_CODES = {408, 409, 429, 500, 502, 503, 504}
MAX_RETRIES = 3
BASE_RETRY_DELAY = 0.5
REQUEST_TIMEOUT_SECONDS = 30


class Client:
    def __init__(self, builder: Any) -> None:
        self._builder = builder

    def call(self, *, max_output_tokens: int = 1024, tools: list | None = None) -> dict[str, Any]:
        url = self._builder.url
        payload = self._builder.to_api_payload(max_output_tokens=max_output_tokens, tools=tools)
        body = json.dumps(payload).encode()
        headers = self._builder.headers

        req = urllib.request.Request(url, data=body, headers=headers, method="POST")

        attempts = 0
        while True:
            attempts += 1
            try:
                with urllib.request.urlopen(req, timeout=REQUEST_TIMEOUT_SECONDS) as resp:
                    raw = resp.read()
                    try:
                        return json.loads(raw)
                    except json.JSONDecodeError as e:
                        raise ApiError(
                            f"API returned non-JSON response ({type(e).__name__}): {raw[:200]!r}"
                        ) from e
            except urllib.error.HTTPError as e:
                if e.code in RETRYABLE_STATUS_CODES and attempts < MAX_RETRIES:
                    time.sleep(_retry_delay(attempts))
                    continue
                body_text = e.read().decode(errors="replace")
                raise ApiError(
                    f"API request failed after {attempts} attempt{'s' if attempts != 1 else ''}"
                    f" ({e.code}): {body_text}"
                ) from e
            except urllib.error.URLError as e:
                if attempts < MAX_RETRIES:
                    time.sleep(_retry_delay(attempts))
                    continue
                raise ApiError(
                    f"API request failed after {attempts} attempts: {type(e).__name__}: {e.reason}"
                ) from e


def _retry_delay(attempt: int) -> float:
    return BASE_RETRY_DELAY * (2 ** (attempt - 1))
```

- [ ] **Step 4: Update `prompt_builder.py` — add `tools` kwarg and `parse_response`**

File: `week1_baseline/python/05_agent_loop/src/boukensha/prompt_builder.py`

```python
"""Boukensha::PromptBuilder port: delegates Context serialization to
whichever backend it's given.

Known upstream quirk, preserved intentionally: ``to_messages`` always calls
``backend.to_messages(context.messages)`` with exactly one argument. This
matches every backend's real signature for ``Anthropic``/``Gemini`` (which
take one arg, ``messages``), but not ``Ollama``/``OllamaCloud``/``OpenAI``
(which take two, ``system, messages``) — calling ``PromptBuilder.to_messages``
directly with one of those three backends will raise a ``TypeError``. This is
a real, unaddressed inconsistency in the Ruby source and never triggers in
practice because ``to_api_payload`` routes through each backend's own
``to_payload``, which calls that backend's ``to_messages`` with correct arity
internally. Ported as-is.
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

    def to_api_payload(
        self, *, max_output_tokens: int = 1024, tools: list | None = None
    ) -> dict[str, Any]:
        return self._backend.to_payload(
            self._context, max_output_tokens=max_output_tokens, tools=tools
        )

    def parse_response(self, response: dict[str, Any]) -> dict[str, Any]:
        return self._backend.parse_response(response)

    @property
    def headers(self) -> dict[str, str]:
        return self._backend.headers

    @property
    def url(self) -> str:
        return self._backend.url
```

- [ ] **Step 5: Run all tests**

```bash
cd week1_baseline/python/05_agent_loop
.venv/bin/pytest tests/test_agent.py -v
```

Expected: `10 passed`

- [ ] **Step 6: Commit**

```bash
git add week1_baseline/python/05_agent_loop/src/boukensha/client.py \
        week1_baseline/python/05_agent_loop/src/boukensha/prompt_builder.py \
        week1_baseline/python/05_agent_loop/tests/test_agent.py
git commit -m "feat: add tools kwarg to Client.call and PromptBuilder; add parse_response to PromptBuilder"
```

---

### Task 4: Add `parse_response` (and inverse helpers) to every backend

**Files:**
- Modify: `week1_baseline/python/05_agent_loop/src/boukensha/backends/anthropic.py`
- Modify: `week1_baseline/python/05_agent_loop/src/boukensha/backends/openai.py`
- Modify: `week1_baseline/python/05_agent_loop/src/boukensha/backends/gemini.py`
- Modify: `week1_baseline/python/05_agent_loop/src/boukensha/backends/ollama.py`
- Modify: `week1_baseline/python/05_agent_loop/src/boukensha/backends/ollama_cloud.py`

**Interfaces:**
- Every backend gains: `parse_response(response: dict) -> dict` — returns `{"stop_reason": "tool_use"|"end_turn", "content": [...]}`
- OpenAI, Ollama, OllamaCloud gain: `_assistant_message(content: Any) -> dict`
- Gemini gains: `_assistant_parts(content: Any) -> list`
- Every backend's `to_payload` gains `tools: list | None = None` kwarg (pass-through; when not `None`, replaces the context tools list)
- Every backend's `to_messages` now handles `msg.role == "assistant"` with list content (routes through `_assistant_message`/`_assistant_parts`)

- [ ] **Step 1: Write failing tests**

Append to `week1_baseline/python/05_agent_loop/tests/test_agent.py`:

```python
from boukensha.backends.anthropic import Anthropic
from boukensha.backends.gemini import Gemini
from boukensha.backends.ollama import Ollama
from boukensha.backends.ollama_cloud import OllamaCloud
from boukensha.backends.openai import OpenAI


# --- Anthropic parse_response ---

def test_anthropic_parse_response_end_turn():
    backend = Anthropic(api_key="k", model="claude-haiku-4-5")
    raw = {"stop_reason": "end_turn", "content": [{"type": "text", "text": "Hello"}]}
    result = backend.parse_response(raw)
    assert result["stop_reason"] == "end_turn"
    assert result["content"] == [{"type": "text", "text": "Hello"}]


def test_anthropic_parse_response_tool_use():
    backend = Anthropic(api_key="k", model="claude-haiku-4-5")
    raw = {
        "stop_reason": "tool_use",
        "content": [
            {"type": "tool_use", "id": "tu_1", "name": "read_file", "input": {"path": "f.txt"}}
        ],
    }
    result = backend.parse_response(raw)
    assert result["stop_reason"] == "tool_use"
    assert result["content"][0]["type"] == "tool_use"
    assert result["content"][0]["id"] == "tu_1"


# --- OpenAI parse_response ---

def test_openai_parse_response_end_turn():
    backend = OpenAI(api_key="k", model="gpt-5.4")
    raw = {"choices": [{"message": {"role": "assistant", "content": "Hello", "tool_calls": None}}]}
    result = backend.parse_response(raw)
    assert result["stop_reason"] == "end_turn"
    assert result["content"] == [{"type": "text", "text": "Hello"}]


def test_openai_parse_response_tool_use():
    backend = OpenAI(api_key="k", model="gpt-5.4")
    raw = {
        "choices": [{
            "message": {
                "role": "assistant",
                "content": None,
                "tool_calls": [{
                    "id": "call_1",
                    "function": {"name": "read_file", "arguments": '{"path": "f.txt"}'}
                }]
            }
        }]
    }
    result = backend.parse_response(raw)
    assert result["stop_reason"] == "tool_use"
    assert result["content"][0]["type"] == "tool_use"
    assert result["content"][0]["id"] == "call_1"
    assert result["content"][0]["input"] == {"path": "f.txt"}


# --- Gemini parse_response ---

def test_gemini_parse_response_end_turn():
    backend = Gemini(api_key="k", model="gemini-2.5-flash")
    raw = {"candidates": [{"content": {"parts": [{"text": "Hello"}]}}]}
    result = backend.parse_response(raw)
    assert result["stop_reason"] == "end_turn"
    assert result["content"] == [{"type": "text", "text": "Hello"}]


def test_gemini_parse_response_tool_use():
    backend = Gemini(api_key="k", model="gemini-2.5-flash")
    raw = {
        "candidates": [{
            "content": {
                "parts": [{"functionCall": {"name": "read_file", "args": {"path": "f.txt"}}}]
            }
        }]
    }
    result = backend.parse_response(raw)
    assert result["stop_reason"] == "tool_use"
    assert result["content"][0]["type"] == "tool_use"
    assert result["content"][0]["id"] == "read_file"
    assert result["content"][0]["name"] == "read_file"
    assert result["content"][0]["input"] == {"path": "f.txt"}


# --- Ollama parse_response ---

def test_ollama_parse_response_end_turn():
    backend = Ollama(model="gemma4")
    raw = {"message": {"role": "assistant", "content": "Hello", "tool_calls": []}}
    result = backend.parse_response(raw)
    assert result["stop_reason"] == "end_turn"
    assert result["content"] == [{"type": "text", "text": "Hello"}]


def test_ollama_parse_response_tool_use():
    backend = Ollama(model="gemma4")
    raw = {
        "message": {
            "role": "assistant",
            "content": "",
            "tool_calls": [{"function": {"name": "read_file", "arguments": {"path": "f.txt"}}}]
        }
    }
    result = backend.parse_response(raw)
    assert result["stop_reason"] == "tool_use"
    assert result["content"][0]["type"] == "tool_use"
    assert result["content"][0]["id"] == "read_file"
    assert result["content"][0]["input"] == {"path": "f.txt"}


# --- to_payload tools override ---

def test_anthropic_to_payload_empty_tools_override():
    from boukensha.context import Context
    from boukensha.tasks.player import Player
    backend = Anthropic(api_key="k", model="claude-haiku-4-5")
    ctx = Context(task=Player, system="sys")
    payload = backend.to_payload(ctx, tools=[])
    assert payload["tools"] == []
```

- [ ] **Step 2: Run tests to confirm failures**

```bash
cd week1_baseline/python/05_agent_loop
.venv/bin/pytest tests/test_agent.py -k "parse_response or tools_override" -v
```

Expected: all FAILED — `AttributeError: 'Anthropic' object has no attribute 'parse_response'`

- [ ] **Step 3: Update `backends/anthropic.py`**

Add `to_payload` with `tools` kwarg and `parse_response` to the end of the `Anthropic` class (after the existing `url` property):

```python
    def to_payload(self, context: Any, *, max_output_tokens: int = 1024, tools: list | None = None) -> dict[str, Any]:
        return {
            "model": self.model,
            "system": context.system,
            "max_tokens": max_output_tokens,
            "tools": tools if tools is not None else self.to_tools(context.tools),
            "messages": self.to_messages(context.messages),
        }

    def parse_response(self, response: dict[str, Any]) -> dict[str, Any]:
        stop_reason = "tool_use" if response.get("stop_reason") == "tool_use" else "end_turn"
        return {"stop_reason": stop_reason, "content": response.get("content") or []}
```

- [ ] **Step 4: Update `backends/openai.py`**

Add `tools` kwarg to `to_payload`, update `to_messages` to handle assistant list content, add `parse_response` and `_assistant_message`. Replace the existing `to_messages` and `to_payload` methods and add the new ones:

```python
    def to_messages(self, system: str | None, messages: list[Any]) -> list[dict[str, Any]]:
        system_message = [{"role": "system", "content": system}]
        conversation: list[dict[str, Any]] = []
        for msg in messages:
            if msg.role == "tool_result":
                conversation.append({"role": "tool", "tool_call_id": msg.tool_use_id, "content": msg.content})
            elif msg.role == "assistant":
                conversation.append(self._assistant_message(msg.content))
            else:
                conversation.append({"role": msg.role, "content": msg.content})
        return system_message + conversation

    def to_payload(self, context: Any, *, max_output_tokens: int = 1024, tools: list | None = None) -> dict[str, Any]:
        return {
            "model": self.model,
            "messages": self.to_messages(context.system, context.messages),
            "tools": tools if tools is not None else self.to_tools(context.tools),
            "max_completion_tokens": max_output_tokens,
        }

    def parse_response(self, response: dict[str, Any]) -> dict[str, Any]:
        import json as _json
        message = (response.get("choices") or [{}])[0].get("message") or {}
        tool_calls = message.get("tool_calls") or []
        content: list[dict[str, Any]] = []
        if message.get("content"):
            content.append({"type": "text", "text": message["content"]})
        for tc in tool_calls:
            content.append({
                "type": "tool_use",
                "id": tc.get("id"),
                "name": (tc.get("function") or {}).get("name"),
                "input": _json.loads((tc.get("function") or {}).get("arguments") or "{}"),
            })
        return {"stop_reason": "tool_use" if tool_calls else "end_turn", "content": content}

    def _assistant_message(self, content: Any) -> dict[str, Any]:
        import json as _json
        blocks = content if isinstance(content, list) else [{"type": "text", "text": content}]
        text_blocks = [b for b in blocks if b.get("type") == "text"]
        tool_blocks = [b for b in blocks if b.get("type") == "tool_use"]
        message: dict[str, Any] = {"role": "assistant", "content": "".join(b["text"] for b in text_blocks)}
        if tool_blocks:
            message["tool_calls"] = [
                {"id": b["id"], "type": "function", "function": {"name": b["name"], "arguments": _json.dumps(b["input"])}}
                for b in tool_blocks
            ]
        return message
```

- [ ] **Step 5: Update `backends/gemini.py`**

Update `to_messages` to handle assistant list content, add `to_payload` tools kwarg, add `parse_response` and `_assistant_parts`. Replace/add methods:

```python
    def to_messages(self, messages: list[Any]) -> list[dict[str, Any]]:
        result: list[dict[str, Any]] = []
        for msg in messages:
            if msg.role == "assistant":
                result.append({"role": "model", "parts": self._assistant_parts(msg.content)})
            elif msg.role == "tool_result":
                result.append({
                    "role": "user",
                    "parts": [{"functionResponse": {"name": msg.tool_use_id, "response": {"content": msg.content}}}],
                })
            else:
                result.append({"role": msg.role, "parts": [{"text": msg.content}]})
        return result

    def to_payload(self, context: Any, *, max_output_tokens: int = 1024, tools: list | None = None) -> dict[str, Any]:
        return {
            "systemInstruction": {"parts": [{"text": context.system}]},
            "contents": self.to_messages(context.messages),
            "tools": tools if tools is not None else self.to_tools(context.tools),
            "generationConfig": {"maxOutputTokens": max_output_tokens},
        }

    def parse_response(self, response: dict[str, Any]) -> dict[str, Any]:
        parts = ((response.get("candidates") or [{}])[0].get("content") or {}).get("parts") or []
        content: list[dict[str, Any]] = []
        tool_used = False
        for part in parts:
            if "functionCall" in part:
                fc = part["functionCall"]
                content.append({"type": "tool_use", "id": fc["name"], "name": fc["name"], "input": fc.get("args") or {}})
                tool_used = True
            elif "text" in part:
                content.append({"type": "text", "text": part["text"]})
        return {"stop_reason": "tool_use" if tool_used else "end_turn", "content": content}

    def _assistant_parts(self, content: Any) -> list[dict[str, Any]]:
        blocks = content if isinstance(content, list) else [{"type": "text", "text": content}]
        parts: list[dict[str, Any]] = []
        for b in blocks:
            if b.get("type") == "tool_use":
                parts.append({"functionCall": {"name": b["name"], "args": b["input"]}})
            else:
                parts.append({"text": b.get("text", "")})
        return parts
```

- [ ] **Step 6: Update `backends/ollama.py`**

Update `to_messages` to handle assistant list content, add `to_payload` tools kwarg, add `parse_response` and `_assistant_message`. Replace/add methods:

```python
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
```

- [ ] **Step 7: Update `backends/ollama_cloud.py`**

Same changes as `ollama.py` — `ollama_cloud` uses the identical response format. Replace/add the same methods as Step 6.

- [ ] **Step 8: Run all tests**

```bash
cd week1_baseline/python/05_agent_loop
.venv/bin/pytest tests/test_agent.py -v
```

Expected: `21 passed`

- [ ] **Step 9: Commit**

```bash
git add week1_baseline/python/05_agent_loop/src/boukensha/backends/ \
        week1_baseline/python/05_agent_loop/tests/test_agent.py
git commit -m "feat: add parse_response and assistant message helpers to all backends"
```

---

### Task 5: Implement `Agent`

**Files:**
- Create: `week1_baseline/python/05_agent_loop/src/boukensha/agent.py`
- Modify: `week1_baseline/python/05_agent_loop/src/boukensha/__init__.py`

**Interfaces:**
- Consumes: `Context`, `Registry`, `PromptBuilder` (has `parse_response`), `Client` (has `tools` kwarg), `ApiError`
- Produces: `Agent(context, registry, builder, client, task_settings=None, max_iterations=None, max_output_tokens=None).run() -> str`

- [ ] **Step 1: Write failing tests**

Append to `week1_baseline/python/05_agent_loop/tests/test_agent.py`:

```python
from boukensha.agent import Agent
from boukensha.context import Context
from boukensha.registry import Registry
from boukensha.tasks.player import Player


def _make_agent(responses, max_iterations=25, tools_side_effect=None):
    """Build an Agent wired to a sequence of mock parsed responses."""
    ctx = Context(task=Player, system="sys")
    registry = Registry(ctx)

    mock_builder = MagicMock()
    mock_builder.parse_response.side_effect = responses
    mock_builder.to_api_payload.return_value = {}

    mock_client = MagicMock()
    mock_client.call.return_value = {}

    if tools_side_effect:
        registry.tool("echo", description="echo", parameters={"msg": {"type": "string"}}, block=tools_side_effect)

    ctx.add_message("user", "hello")
    return Agent(
        context=ctx,
        registry=registry,
        builder=mock_builder,
        client=mock_client,
        max_iterations=max_iterations,
    ), mock_client, mock_builder


def test_agent_returns_text_on_end_turn():
    responses = [{"stop_reason": "end_turn", "content": [{"type": "text", "text": "Done!"}]}]
    agent, _, _ = _make_agent(responses)
    result = agent.run()
    assert result == "Done!"


def test_agent_calls_tool_then_ends():
    tool_called = []

    def echo(msg):
        tool_called.append(msg)
        return f"echo:{msg}"

    responses = [
        {
            "stop_reason": "tool_use",
            "content": [{"type": "tool_use", "id": "tu_1", "name": "echo", "input": {"msg": "hi"}}],
        },
        {"stop_reason": "end_turn", "content": [{"type": "text", "text": "All done"}]},
    ]
    ctx = Context(task=Player, system="sys")
    registry = Registry(ctx)
    registry.tool("echo", description="echo", parameters={"msg": {"type": "string"}}, block=echo)

    mock_builder = MagicMock()
    mock_builder.parse_response.side_effect = responses
    mock_builder.to_api_payload.return_value = {}
    mock_client = MagicMock()
    mock_client.call.return_value = {}

    ctx.add_message("user", "hello")
    agent = Agent(context=ctx, registry=registry, builder=mock_builder, client=mock_client)
    result = agent.run()

    assert result == "All done"
    assert tool_called == ["hi"]
    # assistant message stored before tool_result
    roles = [m.role for m in ctx.messages]
    assert roles == ["user", "assistant", "tool_result"]


def test_agent_wraps_up_at_max_iterations():
    # All responses are tool_use so the agent would loop forever without the ceiling
    tool_response = {
        "stop_reason": "tool_use",
        "content": [{"type": "tool_use", "id": "tu_1", "name": "noop", "input": {}}],
    }
    wrap_up_response = {"stop_reason": "end_turn", "content": [{"type": "text", "text": "Wrapping up"}]}

    ctx = Context(task=Player, system="sys")
    registry = Registry(ctx)
    registry.tool("noop", description="noop", parameters={}, block=lambda: "ok")

    mock_builder = MagicMock()
    # First 2 calls return tool_use, the wrap-up call returns end_turn
    mock_builder.parse_response.side_effect = [tool_response, tool_response, wrap_up_response]
    mock_builder.to_api_payload.return_value = {}
    mock_client = MagicMock()
    mock_client.call.return_value = {}

    ctx.add_message("user", "go")
    agent = Agent(context=ctx, registry=registry, builder=mock_builder, client=mock_client, max_iterations=2)
    result = agent.run()

    assert result == "Wrapping up"
    # wrap-up call must pass tools=[]
    wrap_up_call = mock_client.call.call_args_list[-1]
    assert wrap_up_call.kwargs.get("tools") == []


def test_agent_exports_from_top_level():
    import boukensha
    assert hasattr(boukensha, "Agent")
    assert hasattr(boukensha, "LoopError")
```

- [ ] **Step 2: Run tests to confirm failures**

```bash
cd week1_baseline/python/05_agent_loop
.venv/bin/pytest tests/test_agent.py::test_agent_returns_text_on_end_turn -v
```

Expected: FAILED — `ModuleNotFoundError: No module named 'boukensha.agent'`

- [ ] **Step 3: Write `agent.py`**

File: `week1_baseline/python/05_agent_loop/src/boukensha/agent.py`

```python
"""Boukensha::Agent port: drives the tool-call loop until the model signals
done or the iteration ceiling is reached.
"""

from __future__ import annotations

from typing import Any

from .errors import ApiError

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
        task_settings: dict[str, Any] | None = None,
        max_iterations: int | None = None,
        max_output_tokens: int | None = None,
    ) -> None:
        self._context = context
        self._registry = registry
        self._builder = builder
        self._client = client
        self._max_iterations = self._resolve_max_iterations(task_settings, max_iterations)
        self._max_output_tokens = self._resolve_max_output_tokens(task_settings, max_output_tokens)
        self._iteration = 0

    def run(self) -> str:
        while True:
            if self._iteration_limit_reached():
                return self._wrap_up("max_iterations")

            self._iteration += 1
            print(f"[iteration {self._iteration}/{self._max_iterations}]")

            response = self._client.call(**self._call_opts())
            parsed = self._builder.parse_response(response)

            if parsed["stop_reason"] == "tool_use":
                self._handle_tool_calls(parsed["content"])
            else:
                return self._extract_text(parsed["content"])

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
            return text.strip() or self._fallback_message(reason)
        except ApiError:
            return self._fallback_message(reason)

    def _fallback_message(self, reason: str) -> str:
        return (
            f"I reached my {self._max_iterations}-action limit for this turn before finishing "
            f"({reason}). Ask me to continue and I'll pick up from here."
        )

    def _extract_text(self, content: list[dict[str, Any]]) -> str:
        return "".join(b["text"] for b in content if b.get("type") == "text")

    def _handle_tool_calls(self, content: list[dict[str, Any]]) -> None:
        self._context.add_message("assistant", content)

        for block in content:
            if block.get("type") != "tool_use":
                continue
            name = block["name"]
            args = block["input"]
            use_id = block["id"]

            print(f"  tool call -> {name}({args})")
            result = self._registry.dispatch(name, args)
            print(f"  tool result -> {str(result)[:61]}")

            self._context.add_message("tool_result", str(result), tool_use_id=use_id)
```

- [ ] **Step 4: Update `__init__.py`**

File: `week1_baseline/python/05_agent_loop/src/boukensha/__init__.py`

```python
"""Boukensha agent loop."""

from . import backends, tasks
from .agent import Agent
from .client import Client
from .config import Config
from .context import Context
from .errors import ApiError, LoopError, UnknownToolError, UnsupportedModelError
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
    "LoopError",
    "Message",
    "PromptBuilder",
    "Registry",
    "Tool",
    "UnknownToolError",
    "UnsupportedModelError",
    "backends",
    "tasks",
]

__version__ = "0.1.0"
```

- [ ] **Step 5: Run all tests**

```bash
cd week1_baseline/python/05_agent_loop
.venv/bin/pytest tests/test_agent.py -v
```

Expected: `25 passed`

- [ ] **Step 6: Commit**

```bash
git add week1_baseline/python/05_agent_loop/src/boukensha/agent.py \
        week1_baseline/python/05_agent_loop/src/boukensha/__init__.py \
        week1_baseline/python/05_agent_loop/tests/test_agent.py
git commit -m "feat: implement Agent loop for python/05_agent_loop"
```

---

### Task 6: Write example script and README

**Files:**
- Create: `week1_baseline/python/05_agent_loop/examples/example.py`
- Create: `week1_baseline/python/05_agent_loop/README.md`

**Interfaces:**
- Consumes: all of `boukensha` — `Config`, `Context`, `Registry`, `PromptBuilder`, `Client`, `Agent`, `Player`, all backends
- Produces: runnable script mirroring `ruby/05_agent_loop/examples/example.rb`

- [ ] **Step 1: Write `examples/example.py`**

File: `week1_baseline/python/05_agent_loop/examples/example.py`

```python
import os
from pathlib import Path

os.environ.setdefault(
    "BOUKENSHA_DIR",
    str((Path(__file__).parent.parent.parent.parent.parent / ".boukensha").resolve()),
)

from boukensha import Agent, Client, Config, Context, PromptBuilder, Registry
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
agent = Agent(
    context=ctx,
    registry=registry,
    builder=builder,
    client=client,
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

print("=== BOUKENSHA Step 5: Agent Loop ===")
print()
print(f"Config: {config}")
print(f"Provider: {provider}")
print(f"Model: {model}")
print(f"Max iterations: {Player.max_iterations(player_settings)}")
print(f"Max output tokens: {Player.max_output_tokens(player_settings)}")
print()

result = agent.run()

print()
print("=== FINAL RESPONSE ===")
print(result)
```

- [ ] **Step 2: Syntax check example**

```bash
cd week1_baseline/python/05_agent_loop
.venv/bin/python -c "import ast; ast.parse(open('examples/example.py').read()); print('syntax ok')"
```

Expected: `syntax ok`

- [ ] **Step 3: Run all tests (no regression)**

```bash
cd week1_baseline/python/05_agent_loop
.venv/bin/pytest tests/test_agent.py -v
```

Expected: `25 passed`

- [ ] **Step 4: Write `README.md`**

File: `week1_baseline/python/05_agent_loop/README.md`

Contents:

```
# Python 05 Agent Loop

Python port of `ruby/05_agent_loop`. Adds `Agent` — drives the tool-call loop until the model signals `end_turn` or the iteration ceiling is reached.

## New Files

| File | Description |
|---|---|
| `src/boukensha/agent.py` | `Agent` — the loop, tool dispatch, and wind-down logic |

## Updated Files

| File | Change |
|---|---|
| `src/boukensha/errors.py` | Added `LoopError` for runaway agents |
| `src/boukensha/client.py` | `call()` now accepts a `tools` kwarg (empty list disables tools for wind-down) |
| `src/boukensha/prompt_builder.py` | Added `parse_response()`; `to_api_payload()` accepts `tools` kwarg |
| `src/boukensha/tasks/base.py` | Added `max_iterations()` and `max_output_tokens()` classmethods |
| `src/boukensha/message.py` | `content` widened to `Any` (stores normalised content blocks for assistant turns) |
| `src/boukensha/backends/*.py` | Every backend gains `parse_response()`; OpenAI/Gemini/Ollama/OllamaCloud add inverse helpers |

## How It Works

    send messages to API
            |
    stop_reason == "tool_use"?
        yes -> extract tool calls
            -> store assistant message (must precede tool_result)
            -> dispatch each tool via Registry
            -> inject results as tool_result messages
            -> go back to top
        no  -> return final text response

## Normalised Response Shape

Every backend's `parse_response` converts its provider-specific wire format into:

    {
        "stop_reason": "tool_use" | "end_turn",
        "content": [
            {"type": "text", "text": "..."},
            {"type": "tool_use", "id": "...", "name": "...", "input": {...}},
        ]
    }

`Agent` never inspects a raw provider response.

## `Agent` API

| Method | Description |
|---|---|
| `Agent(context, registry, builder, client, task_settings=None, max_iterations=None, max_output_tokens=None)` | Construct the agent |
| `agent.run()` | Run the loop; returns the final text string |

## Task Configuration (~/.boukensha/settings.yaml)

    tasks:
      player:
        provider: anthropic
        model: claude-haiku-4-5
        max_iterations: 25
        max_output_tokens: 1024

## Run Example

    cd week1_baseline/python/05_agent_loop
    uv pip install -e .
    python examples/example.py

Requires `ANTHROPIC_API_KEY` (or whichever provider is configured).

## Run Tests

    cd week1_baseline/python/05_agent_loop
    uv pip install pytest
    python -m pytest tests/ -v
```

- [ ] **Step 5: Commit**

```bash
git add week1_baseline/python/05_agent_loop/examples/example.py \
        week1_baseline/python/05_agent_loop/README.md
git commit -m "feat: add example script and README for python/05_agent_loop"
```
