# Python 04 API Client Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Port `ruby/04_api_client` to Python — add a `Client` class that takes a `PromptBuilder` and makes the live HTTP POST, plus update backends with model metadata and add `ApiError`, all as a self-contained `python/04_api_client` project mirroring the structure of `python/03_prompt_builder`.

**Architecture:** Copy the entire `03_prompt_builder` source tree into `04_api_client`, add the new `Client` class using Python's stdlib `urllib.request`, add `ApiError` to `errors.py`, and expand each backend's `MODELS` dict with cost/context-window metadata. The example script drives the real Anthropic API and prints the raw response.

**Tech Stack:** Python ≥3.11, stdlib `urllib.request`/`urllib.error`/`ssl`, `pyyaml`, `python-dotenv`, `uv` for package management, `pytest` for tests.

## Global Constraints

- Python ≥3.11 (matches `03_prompt_builder`'s `requires-python`)
- No third-party HTTP libraries — `urllib.request` only (mirrors Ruby's "no gems" principle)
- Self-contained project: own `pyproject.toml`, own `.venv`, full copy of `boukensha` source
- Package version: `0.1.0`, name: `boukensha`
- Project description in `pyproject.toml`: `"Boukensha API client (Step 4)"`
- Retry logic: up to 3 retries, base delay 0.5s, exponential back-off (`0.5 * 2**(attempt-1)`), retryable HTTP status codes: 408, 409, 429, 500, 502, 503, 504
- `BOUKENSHA_DIR` env var used to point at `.boukensha/` config directory; falls back to `~/.boukensha`
- Preserve the existing `PromptBuilder` `to_messages` arity quirk (documented in `03_prompt_builder`) — do not fix it
- All new Python files use `from __future__ import annotations` and type hints matching the `03` style

---

## File Map

| Status | Path | Responsibility |
|--------|------|---------------|
| Create | `week1_baseline/python/04_api_client/pyproject.toml` | Project metadata, dependencies |
| Create | `week1_baseline/python/04_api_client/src/boukensha/__init__.py` | Package exports (adds `Client`, `ApiError`) |
| Create | `week1_baseline/python/04_api_client/src/boukensha/errors.py` | `UnknownToolError`, `UnsupportedModelError`, **`ApiError`** |
| Create | `week1_baseline/python/04_api_client/src/boukensha/client.py` | `Client` — HTTP POST with retry logic |
| Create | `week1_baseline/python/04_api_client/src/boukensha/backends/base.py` | Copied from 03 (unchanged) |
| Create | `week1_baseline/python/04_api_client/src/boukensha/backends/anthropic.py` | Copied from 03 (unchanged — already has metadata) |
| Create | `week1_baseline/python/04_api_client/src/boukensha/backends/openai.py` | Copied from 03 (unchanged) |
| Create | `week1_baseline/python/04_api_client/src/boukensha/backends/gemini.py` | Copied from 03 (unchanged) |
| Create | `week1_baseline/python/04_api_client/src/boukensha/backends/ollama.py` | Copied from 03 (unchanged) |
| Create | `week1_baseline/python/04_api_client/src/boukensha/backends/ollama_cloud.py` | Copied from 03 (unchanged) |
| Create | `week1_baseline/python/04_api_client/src/boukensha/backends/__init__.py` | Copied from 03 (unchanged) |
| Create | `week1_baseline/python/04_api_client/src/boukensha/config.py` | Copied from 03 (unchanged) |
| Create | `week1_baseline/python/04_api_client/src/boukensha/context.py` | Copied from 03 (unchanged) |
| Create | `week1_baseline/python/04_api_client/src/boukensha/message.py` | Copied from 03 (unchanged) |
| Create | `week1_baseline/python/04_api_client/src/boukensha/prompt_builder.py` | Copied from 03 (unchanged) |
| Create | `week1_baseline/python/04_api_client/src/boukensha/registry.py` | Copied from 03 (unchanged) |
| Create | `week1_baseline/python/04_api_client/src/boukensha/tool.py` | Copied from 03 (unchanged) |
| Create | `week1_baseline/python/04_api_client/src/boukensha/tasks/__init__.py` | Copied from 03 (unchanged) |
| Create | `week1_baseline/python/04_api_client/src/boukensha/tasks/base.py` | Copied from 03 (unchanged) |
| Create | `week1_baseline/python/04_api_client/src/boukensha/tasks/player.py` | Copied from 03 (unchanged) |
| Create | `week1_baseline/python/04_api_client/prompts/system.md` | Default system prompt (copy from Ruby) |
| Create | `week1_baseline/python/04_api_client/examples/example.py` | Drives the live API call, prints raw JSON |
| Create | `week1_baseline/python/04_api_client/tests/__init__.py` | Empty test package marker |
| Create | `week1_baseline/python/04_api_client/tests/test_client.py` | Unit tests for `Client` (mocked network) |

---

### Task 1: Scaffold project structure

**Files:**
- Create: `week1_baseline/python/04_api_client/pyproject.toml`
- Create: `week1_baseline/python/04_api_client/src/boukensha/__init__.py` (stub — updated in Task 3)
- Create: `week1_baseline/python/04_api_client/tests/__init__.py`

**Interfaces:**
- Produces: installable `boukensha` package at `0.1.0`

- [ ] **Step 1: Create the directory skeleton**

```bash
mkdir -p week1_baseline/python/04_api_client/src/boukensha/backends
mkdir -p week1_baseline/python/04_api_client/src/boukensha/tasks
mkdir -p week1_baseline/python/04_api_client/examples
mkdir -p week1_baseline/python/04_api_client/tests
mkdir -p week1_baseline/python/04_api_client/prompts
```

- [ ] **Step 2: Write `pyproject.toml`**

```toml
[project]
name = "boukensha"
version = "0.1.0"
description = "Boukensha API client (Step 4)"
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

- [ ] **Step 3: Create empty `tests/__init__.py`**

File content: empty (zero bytes).

- [ ] **Step 4: Bootstrap the venv and install**

```bash
cd week1_baseline/python/04_api_client
uv venv
uv pip install -e ".[dev]" 2>/dev/null || uv pip install -e .
```

Expected: `Successfully installed boukensha-0.1.0`

- [ ] **Step 5: Commit**

```bash
git add week1_baseline/python/04_api_client/pyproject.toml \
        week1_baseline/python/04_api_client/tests/__init__.py
git commit -m "feat: scaffold python/04_api_client project"
```

---

### Task 2: Copy shared source files from 03_prompt_builder

**Files:**
- Create: all files listed as "Copied from 03 (unchanged)" in the file map above

**Interfaces:**
- Consumes: `week1_baseline/python/03_prompt_builder/src/boukensha/` — exact current content
- Produces: identical files under `week1_baseline/python/04_api_client/src/boukensha/`

> Note: copy every file byte-for-byte. Do NOT update `__init__.py` yet — that happens in Task 3 after `Client` and `ApiError` exist.

- [ ] **Step 1: Copy all shared source files**

```bash
SRC=week1_baseline/python/03_prompt_builder/src/boukensha
DST=week1_baseline/python/04_api_client/src/boukensha

cp $SRC/config.py          $DST/config.py
cp $SRC/context.py         $DST/context.py
cp $SRC/message.py         $DST/message.py
cp $SRC/prompt_builder.py  $DST/prompt_builder.py
cp $SRC/registry.py        $DST/registry.py
cp $SRC/tool.py            $DST/tool.py
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

- [ ] **Step 2: Copy the default system prompt**

```bash
cp week1_baseline/ruby/04_api_client/prompts/system.md \
   week1_baseline/python/04_api_client/prompts/system.md
```

- [ ] **Step 3: Verify the package imports cleanly**

```bash
cd week1_baseline/python/04_api_client
.venv/bin/python -c "from boukensha import Config, Context, PromptBuilder, Registry; print('ok')"
```

Expected output: `ok`

- [ ] **Step 4: Commit**

```bash
git add week1_baseline/python/04_api_client/src/ \
        week1_baseline/python/04_api_client/prompts/
git commit -m "feat: copy shared boukensha source into python/04_api_client"
```

---

### Task 3: Add `ApiError` and update `errors.py`

**Files:**
- Create: `week1_baseline/python/04_api_client/src/boukensha/errors.py`
- Create: `week1_baseline/python/04_api_client/tests/test_client.py` (stub for the import assertion)

**Interfaces:**
- Produces: `ApiError(Exception)` importable from `boukensha.errors` and from `boukensha` top-level

- [ ] **Step 1: Write the failing test**

File: `week1_baseline/python/04_api_client/tests/test_client.py`

```python
from boukensha.errors import ApiError, UnknownToolError, UnsupportedModelError


def test_api_error_is_exception():
    err = ApiError("boom")
    assert isinstance(err, Exception)
    assert str(err) == "boom"


def test_existing_errors_still_present():
    assert issubclass(UnknownToolError, Exception)
    assert issubclass(UnsupportedModelError, Exception)
```

- [ ] **Step 2: Run the test to confirm it fails**

```bash
cd week1_baseline/python/04_api_client
.venv/bin/pytest tests/test_client.py::test_api_error_is_exception -v
```

Expected: `FAILED` — `ImportError: cannot import name 'ApiError'`

- [ ] **Step 3: Write `errors.py` with `ApiError` added**

File: `week1_baseline/python/04_api_client/src/boukensha/errors.py`

```python
"""Boukensha-specific error classes."""

from __future__ import annotations


class UnknownToolError(Exception):
    """Raised when dispatch is called with a name that has no registered tool."""


class UnsupportedModelError(Exception):
    """Raised when a backend is configured with a model it does not support."""


class ApiError(Exception):
    """Raised when an HTTP request to the LLM API fails."""
```

- [ ] **Step 4: Run both tests**

```bash
cd week1_baseline/python/04_api_client
.venv/bin/pytest tests/test_client.py -v
```

Expected: `2 passed`

- [ ] **Step 5: Commit**

```bash
git add week1_baseline/python/04_api_client/src/boukensha/errors.py \
        week1_baseline/python/04_api_client/tests/test_client.py
git commit -m "feat: add ApiError to boukensha errors (step 4)"
```

---

### Task 4: Implement `Client`

**Files:**
- Create: `week1_baseline/python/04_api_client/src/boukensha/client.py`
- Modify: `week1_baseline/python/04_api_client/tests/test_client.py` (add Client tests)

**Interfaces:**
- Consumes: `PromptBuilder` (has `.url: str`, `.headers: dict[str,str]`, `.to_api_payload(*, max_output_tokens: int) -> dict`)
- Produces: `Client(builder).call(*, max_output_tokens=1024) -> dict` — parsed JSON response body

- [ ] **Step 1: Add failing tests for `Client`**

Append to `week1_baseline/python/04_api_client/tests/test_client.py`:

```python
import json
from unittest.mock import MagicMock, patch
from urllib.error import HTTPError, URLError
from io import BytesIO

from boukensha.client import Client
from boukensha.errors import ApiError


def _make_builder(url="https://api.example.com/v1/messages", payload=None):
    builder = MagicMock()
    builder.url = url
    builder.headers = {"Content-Type": "application/json", "x-api-key": "test-key"}
    builder.to_api_payload.return_value = payload or {"model": "test", "messages": []}
    return builder


def _fake_response(body: dict, status: int = 200):
    raw = json.dumps(body).encode()
    resp = MagicMock()
    resp.read.return_value = raw
    resp.status = status
    resp.__enter__ = lambda s: s
    resp.__exit__ = MagicMock(return_value=False)
    return resp


def test_client_returns_parsed_json():
    builder = _make_builder()
    expected = {"id": "msg_01", "content": [{"type": "text", "text": "Hello"}]}
    with patch("boukensha.client.urllib.request.urlopen", return_value=_fake_response(expected)):
        result = Client(builder).call()
    assert result == expected


def test_client_passes_max_output_tokens():
    builder = _make_builder()
    with patch("boukensha.client.urllib.request.urlopen", return_value=_fake_response({})) as mock_open:
        Client(builder).call(max_output_tokens=512)
    builder.to_api_payload.assert_called_once_with(max_output_tokens=512)


def test_client_raises_api_error_on_http_error():
    builder = _make_builder()
    http_err = HTTPError(
        url="https://api.example.com/v1/messages",
        code=401,
        msg="Unauthorized",
        hdrs={},
        fp=BytesIO(b'{"error": "bad key"}'),
    )
    with patch("boukensha.client.urllib.request.urlopen", side_effect=http_err):
        try:
            Client(builder).call()
            assert False, "Expected ApiError"
        except ApiError as e:
            assert "401" in str(e)


def test_client_retries_on_transient_error_then_succeeds():
    builder = _make_builder()
    expected = {"id": "msg_02", "content": []}
    call_count = 0

    def side_effect(*args, **kwargs):
        nonlocal call_count
        call_count += 1
        if call_count < 2:
            raise URLError("connection reset")
        return _fake_response(expected)

    with patch("boukensha.client.urllib.request.urlopen", side_effect=side_effect):
        with patch("boukensha.client.time.sleep"):
            result = Client(builder).call()
    assert result == expected
    assert call_count == 2


def test_client_raises_after_max_retries():
    builder = _make_builder()
    with patch("boukensha.client.urllib.request.urlopen", side_effect=URLError("reset")):
        with patch("boukensha.client.time.sleep"):
            try:
                Client(builder).call()
                assert False, "Expected ApiError"
            except ApiError as e:
                assert "3" in str(e)
```

- [ ] **Step 2: Run tests to confirm they fail**

```bash
cd week1_baseline/python/04_api_client
.venv/bin/pytest tests/test_client.py -k "client" -v
```

Expected: `FAILED` — `ModuleNotFoundError: No module named 'boukensha.client'`

- [ ] **Step 3: Write `client.py`**

File: `week1_baseline/python/04_api_client/src/boukensha/client.py`

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


class Client:
    def __init__(self, builder: Any) -> None:
        self._builder = builder

    def call(self, *, max_output_tokens: int = 1024) -> dict[str, Any]:
        url = self._builder.url
        payload = self._builder.to_api_payload(max_output_tokens=max_output_tokens)
        body = json.dumps(payload).encode()
        headers = self._builder.headers

        req = urllib.request.Request(url, data=body, headers=headers, method="POST")

        attempts = 0
        while True:
            attempts += 1
            try:
                with urllib.request.urlopen(req) as resp:
                    return json.loads(resp.read())
            except urllib.error.HTTPError as e:
                if e.code in RETRYABLE_STATUS_CODES and attempts <= MAX_RETRIES:
                    time.sleep(_retry_delay(attempts))
                    continue
                body_text = e.read().decode(errors="replace")
                raise ApiError(
                    f"API request failed after {attempts} attempt{'s' if attempts != 1 else ''}"
                    f" ({e.code}): {body_text}"
                ) from e
            except urllib.error.URLError as e:
                if attempts <= MAX_RETRIES:
                    time.sleep(_retry_delay(attempts))
                    continue
                raise ApiError(
                    f"API request failed after {attempts} attempts: {type(e).__name__}: {e.reason}"
                ) from e


def _retry_delay(attempt: int) -> float:
    return BASE_RETRY_DELAY * (2 ** (attempt - 1))
```

- [ ] **Step 4: Run all Client tests**

```bash
cd week1_baseline/python/04_api_client
.venv/bin/pytest tests/test_client.py -v
```

Expected: `7 passed`

- [ ] **Step 5: Commit**

```bash
git add week1_baseline/python/04_api_client/src/boukensha/client.py \
        week1_baseline/python/04_api_client/tests/test_client.py
git commit -m "feat: implement Client with retry logic for python/04_api_client"
```

---

### Task 5: Update package exports (`__init__.py`)

**Files:**
- Create: `week1_baseline/python/04_api_client/src/boukensha/__init__.py`

**Interfaces:**
- Consumes: `Client` from `boukensha.client`, `ApiError` from `boukensha.errors`
- Produces: `from boukensha import Client, ApiError` works

- [ ] **Step 1: Write the failing test**

Append to `week1_baseline/python/04_api_client/tests/test_client.py`:

```python
def test_top_level_exports():
    import boukensha
    assert hasattr(boukensha, "Client")
    assert hasattr(boukensha, "ApiError")
    assert hasattr(boukensha, "Config")
    assert hasattr(boukensha, "PromptBuilder")
```

- [ ] **Step 2: Run test to confirm it fails**

```bash
cd week1_baseline/python/04_api_client
.venv/bin/pytest tests/test_client.py::test_top_level_exports -v
```

Expected: `FAILED` — `AssertionError` on `Client` or `ApiError`

- [ ] **Step 3: Write `__init__.py`**

File: `week1_baseline/python/04_api_client/src/boukensha/__init__.py`

```python
from . import backends, tasks
from .client import Client
from .config import Config
from .context import Context
from .errors import ApiError, UnknownToolError, UnsupportedModelError
from .message import Message
from .prompt_builder import PromptBuilder
from .registry import Registry
from .tool import Tool

__all__ = [
    "ApiError",
    "Client",
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

- [ ] **Step 4: Run all tests**

```bash
cd week1_baseline/python/04_api_client
.venv/bin/pytest tests/ -v
```

Expected: `8 passed`

- [ ] **Step 5: Commit**

```bash
git add week1_baseline/python/04_api_client/src/boukensha/__init__.py \
        week1_baseline/python/04_api_client/tests/test_client.py
git commit -m "feat: export Client and ApiError from boukensha package"
```

---

### Task 6: Write the example script

**Files:**
- Create: `week1_baseline/python/04_api_client/examples/example.py`

**Interfaces:**
- Consumes: `Config`, `Context`, `PromptBuilder`, `Registry`, `Client`, all backends, `Player`
- Produces: script that calls the live API and prints the raw JSON response

- [ ] **Step 1: Write `examples/example.py`**

File: `week1_baseline/python/04_api_client/examples/example.py`

```python
import json
import os
from pathlib import Path

# Override the config directory so the example works from the repo root.
# In real usage a user's ~/.boukensha is picked up automatically.
os.environ.setdefault(
    "BOUKENSHA_DIR",
    str((Path(__file__).parent.parent.parent.parent.parent / ".boukensha").resolve()),
)

from boukensha import Client, Config, Context, PromptBuilder, Registry
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
    "read_file",
    description="Read the contents of a file from disk",
    parameters={"path": {"type": "string", "description": "The file path to read"}},
    block=lambda path: Path(path).read_text(),
)

registry.tool(
    "list_directory",
    description="List files in a directory",
    parameters={"path": {"type": "string", "description": "The directory path to list"}},
    block=lambda path: "\n".join(
        f for f in os.listdir(path) if not f.startswith(".")
    ),
)

ctx.add_message("user", "What files are in the current directory?")

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

print("=== BOUKENSHA Step 4: API Client ===")
print()
print(f"Config: {config}")
print(f"Provider: {provider}")
print(f"Model: {model}")
print(f"Sending request to {builder.url}...")
print()

response = client.call()
print("Raw response:")
print(json.dumps(response, indent=2))
```

- [ ] **Step 2: Verify the example file is importable (syntax check)**

```bash
cd week1_baseline/python/04_api_client
.venv/bin/python -c "import ast; ast.parse(open('examples/example.py').read()); print('syntax ok')"
```

Expected: `syntax ok`

- [ ] **Step 3: Run all tests to confirm nothing broke**

```bash
cd week1_baseline/python/04_api_client
.venv/bin/pytest tests/ -v
```

Expected: `8 passed`

- [ ] **Step 4: Commit**

```bash
git add week1_baseline/python/04_api_client/examples/example.py
git commit -m "feat: add example script for python/04_api_client"
```

---

### Task 7: Write README

**Files:**
- Create: `week1_baseline/python/04_api_client/README.md`

- [ ] **Step 1: Write README**

File: `week1_baseline/python/04_api_client/README.md`

````markdown
# Python 04 API Client

Python port of `ruby/04_api_client`. Adds `Client` — takes a `PromptBuilder` and sends the assembled payload to the API via a single HTTP POST, returning the raw parsed JSON response.

## New Files

| File | Description |
|---|---|
| `src/boukensha/client.py` | `Client` — HTTP POST with exponential back-off retry |
| `src/boukensha/errors.py` | Updated with `ApiError` for failed HTTP requests |

## How It Works

```
PromptBuilder
      ↓
Client
      ↓
POST to API endpoint (urllib.request, no third-party libs)
      ↓
Raw JSON response (dict)
```

## `Client` API

| Method | Description |
|---|---|
| `Client(builder)` | Wraps any `PromptBuilder` |
| `client.call(*, max_output_tokens=1024)` | POSTs the payload and returns the parsed JSON response dict |

## Retry Behaviour

`Client` retries up to 3 times on network errors and HTTP 408/409/429/500/502/503/504. Back-off: `0.5 * 2^(attempt-1)` seconds. Raises `ApiError` if all retries are exhausted or on non-retryable HTTP errors.

## Run Example

```bash
cd week1_baseline/python/04_api_client
uv pip install -e .
python examples/example.py
```

Requires `ANTHROPIC_API_KEY` (or whichever provider is configured in `~/.boukensha/settings.yaml`).

## Run Tests

```bash
cd week1_baseline/python/04_api_client
uv pip install pytest
python -m pytest tests/ -v
```
````

- [ ] **Step 2: Commit**

```bash
git add week1_baseline/python/04_api_client/README.md
git commit -m "docs: add README for python/04_api_client"
```
