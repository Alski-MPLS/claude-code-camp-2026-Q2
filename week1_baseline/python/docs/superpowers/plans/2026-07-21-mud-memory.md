# MUD Persistent Memory (player.md / world.md) Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Give the Boukensha agent two persistent markdown files (`player.md`, `world.md`) it reads and writes itself, so it retains character state and a map of the MUD world across sessions — fully toggleable and zero-overhead when off.

**Architecture:** A new `boukensha.tools.memory.Memory` module (same shape as the existing `FileSystem`/`Mud` tool modules) owns two fixed files in a config-resolved directory. `run()`/`repl()` gain a `memory: bool | None` parameter that mirrors the existing `mud: dict | bool | None` toggle: when enabled, the current file contents are appended to the system prompt at startup and two tools (`read_memory`, `write_memory`) are registered — independent of `working_dir`, so it still works during MUD sessions (which run with `working_dir=False`).

**Tech Stack:** Python 3, pytest, existing Boukensha `Registry`/`Context`/`Config` primitives. No new dependencies.

## Global Constraints

- Scope is `week1_baseline/python/12_context/` only — do not touch earlier step folders (01–11).
- Default memory location is `~/.boukensha/memory/` (i.e. `<Config.dir>/memory`), configurable via `settings.yaml` key `memory.dir`.
- Toggle default: enabled (`memory.enabled` defaults to `True` in `settings.yaml`; `memory=False` disables outright with zero registered tools and zero prompt injection).
- Tool errors return `"error: ..."` strings, never raise — matches `file_system.py` and `mud.py`.
- `write_memory` fully overwrites the target file (no append/diff logic) — matches `write_file`'s semantics.
- Two fixed files only: `player.md`, `world.md`. No per-character split.
- All new/changed files live under `week1_baseline/python/12_context/`; run tests with `cd week1_baseline/python/12_context && python -m pytest` (uses the project's `.venv`/`pyproject.toml`).

---

### Task 1: `Config.memory_enabled` / `Config.memory_dir`

**Files:**
- Modify: `week1_baseline/python/12_context/src/boukensha/config.py:59-60` (insert new properties after the existing `mud_password` property, before the `# ---------- low-level helpers` comment)
- Test: `week1_baseline/python/12_context/tests/test_config.py` (new file)

**Interfaces:**
- Produces: `Config.memory_enabled -> bool`, `Config.memory_dir -> str` (both instance properties on `boukensha.config.Config`), used by Task 3.

- [ ] **Step 1: Write the failing tests**

Create `week1_baseline/python/12_context/tests/test_config.py`:

```python
from __future__ import annotations

from pathlib import Path

import yaml

from boukensha.config import Config


def _write_settings(tmp_path: Path, data: dict) -> None:
    (tmp_path / "settings.yaml").write_text(yaml.dump(data))


def test_memory_enabled_defaults_true(tmp_path, monkeypatch):
    monkeypatch.setenv("BOUKENSHA_DIR", str(tmp_path))
    cfg = Config()
    assert cfg.memory_enabled is True


def test_memory_enabled_respects_false(tmp_path, monkeypatch):
    monkeypatch.setenv("BOUKENSHA_DIR", str(tmp_path))
    _write_settings(tmp_path, {"memory": {"enabled": False}})
    cfg = Config()
    assert cfg.memory_enabled is False


def test_memory_dir_defaults_to_config_dir_subfolder(tmp_path, monkeypatch):
    monkeypatch.setenv("BOUKENSHA_DIR", str(tmp_path))
    cfg = Config()
    assert cfg.memory_dir == str(Path(cfg.dir) / "memory")


def test_memory_dir_respects_override(tmp_path, monkeypatch):
    monkeypatch.setenv("BOUKENSHA_DIR", str(tmp_path))
    custom = str(tmp_path / "custom_mem")
    _write_settings(tmp_path, {"memory": {"dir": custom}})
    cfg = Config()
    assert cfg.memory_dir == custom
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `cd week1_baseline/python/12_context && python -m pytest tests/test_config.py -v`
Expected: FAIL — `AttributeError: 'Config' object has no attribute 'memory_enabled'`

- [ ] **Step 3: Implement the properties**

In `week1_baseline/python/12_context/src/boukensha/config.py`, the file currently reads (around line 53-61):

```python
    @property
    def mud_password(self) -> str | None:
        return self.dig("mud", "password")

    # ---------- low-level helpers -------------------------------------------
```

Insert a new section between `mud_password` and the low-level helpers comment:

```python
    @property
    def mud_password(self) -> str | None:
        return self.dig("mud", "password")

    # ---------- persistent memory --------------------------------------------

    @property
    def memory_enabled(self) -> bool:
        value = self.dig("memory", "enabled")
        return True if value is None else bool(value)

    @property
    def memory_dir(self) -> str:
        return self.dig("memory", "dir") or str(Path(self.dir) / "memory")

    # ---------- low-level helpers -------------------------------------------
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `cd week1_baseline/python/12_context && python -m pytest tests/test_config.py -v`
Expected: PASS (4 passed)

- [ ] **Step 5: Commit**

```bash
cd week1_baseline/python/12_context
git add src/boukensha/config.py tests/test_config.py
git commit -m "feat(12): add Config.memory_enabled and Config.memory_dir"
```

---

### Task 2: `boukensha.tools.memory.Memory` module

**Files:**
- Create: `week1_baseline/python/12_context/src/boukensha/tools/memory.py`
- Modify: `week1_baseline/python/12_context/src/boukensha/tools/__init__.py`
- Test: `week1_baseline/python/12_context/tests/test_tools_memory.py` (new file)

**Interfaces:**
- Consumes: `boukensha.context.Context`, `boukensha.registry.Registry` (both existing — see `tools/file_system.py` for the registration pattern).
- Produces:
  - `Memory.register(registry: Registry, *, memory_dir: str) -> None` — registers `read_memory` and `write_memory` tools.
  - `Memory.prompt_block(memory_dir: str) -> str` — returns the injectable system-prompt text; used by Task 3.
  - Both ensure `memory_dir` and its two files (`player.md`, `world.md`) exist, creating them with default templates on first use.

- [ ] **Step 1: Write the failing tests**

Create `week1_baseline/python/12_context/tests/test_tools_memory.py`:

```python
from __future__ import annotations

from boukensha.context import Context
from boukensha.registry import Registry
from boukensha.tasks.player import Player
from boukensha.tools.memory import Memory


def _make_registry() -> Registry:
    ctx = Context(task=Player, system="sys")
    return Registry(ctx)


def test_register_adds_expected_tools(tmp_path):
    registry = _make_registry()
    Memory.register(registry, memory_dir=str(tmp_path))
    assert registry.get("read_memory") is not None
    assert registry.get("write_memory") is not None


def test_register_creates_default_files(tmp_path):
    registry = _make_registry()
    Memory.register(registry, memory_dir=str(tmp_path))
    assert (tmp_path / "player.md").exists()
    assert (tmp_path / "world.md").exists()


def test_register_creates_missing_directory(tmp_path):
    memory_dir = tmp_path / "nested" / "memory"
    registry = _make_registry()
    Memory.register(registry, memory_dir=str(memory_dir))
    assert (memory_dir / "player.md").exists()
    assert (memory_dir / "world.md").exists()


def test_read_memory_returns_default_template(tmp_path):
    registry = _make_registry()
    Memory.register(registry, memory_dir=str(tmp_path))
    result = registry.dispatch("read_memory", {"file": "player"})
    assert "nothing recorded yet" in result


def test_write_memory_then_read_memory_round_trips(tmp_path):
    registry = _make_registry()
    Memory.register(registry, memory_dir=str(tmp_path))
    write_result = registry.dispatch(
        "write_memory", {"file": "world", "content": "# World Map\n\nRoom 1 -> north -> Room 2\n"}
    )
    assert write_result.startswith("ok:")
    read_result = registry.dispatch("read_memory", {"file": "world"})
    assert read_result == "# World Map\n\nRoom 1 -> north -> Room 2\n"


def test_write_memory_overwrites_existing_content(tmp_path):
    registry = _make_registry()
    Memory.register(registry, memory_dir=str(tmp_path))
    registry.dispatch("write_memory", {"file": "player", "content": "first"})
    registry.dispatch("write_memory", {"file": "player", "content": "second"})
    result = registry.dispatch("read_memory", {"file": "player"})
    assert result == "second"


def test_read_memory_rejects_unknown_file(tmp_path):
    registry = _make_registry()
    Memory.register(registry, memory_dir=str(tmp_path))
    result = registry.dispatch("read_memory", {"file": "monsters"})
    assert result.startswith("error:")


def test_write_memory_rejects_unknown_file(tmp_path):
    registry = _make_registry()
    Memory.register(registry, memory_dir=str(tmp_path))
    result = registry.dispatch("write_memory", {"file": "monsters", "content": "x"})
    assert result.startswith("error:")
    assert not (tmp_path / "monsters.md").exists()


def test_prompt_block_contains_both_files_and_content(tmp_path):
    (tmp_path).mkdir(exist_ok=True)
    from boukensha.tools.memory import Memory as M
    M.register(_make_registry(), memory_dir=str(tmp_path))
    (tmp_path / "player.md").write_text("# Player Notes\n\nLevel 3 warrior.\n")
    block = M.prompt_block(str(tmp_path))
    assert "player.md" in block
    assert "world.md" in block
    assert "Level 3 warrior." in block


def test_prompt_block_creates_files_if_missing(tmp_path):
    memory_dir = tmp_path / "fresh"
    block = Memory.prompt_block(str(memory_dir))
    assert (memory_dir / "player.md").exists()
    assert (memory_dir / "world.md").exists()
    assert "nothing recorded yet" in block


def test_tools_module_exports_memory():
    from boukensha import tools
    assert hasattr(tools, "Memory")
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `cd week1_baseline/python/12_context && python -m pytest tests/test_tools_memory.py -v`
Expected: FAIL — `ModuleNotFoundError: No module named 'boukensha.tools.memory'`

- [ ] **Step 3: Implement `boukensha/tools/memory.py`**

Create `week1_baseline/python/12_context/src/boukensha/tools/memory.py`:

```python
"""Memory tool module: two persistent markdown files the agent maintains
itself — player.md (character state) and world.md (the map).

Modular by design: nothing in this module is imported or invoked unless the
caller opts in via ``Memory.register`` / ``Memory.prompt_block``. See
boukensha/__init__.py's ``memory`` parameter on run()/repl().
"""

from __future__ import annotations

from pathlib import Path
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from boukensha.registry import Registry

_FILES: dict[str, tuple[str, str]] = {
    "player": ("player.md", "# Player Notes\n\n(nothing recorded yet)\n"),
    "world":  ("world.md",  "# World Map\n\n(nothing recorded yet)\n"),
}

_PROMPT_HEADER = (
    "## Persistent memory\n"
    "You maintain two memory files across sessions — player.md (your character: "
    "stats, goals, notes) and world.md (the map: rooms, exits, shops, landmarks). "
    "Use read_memory/write_memory to keep them current, especially after entering "
    "a new room or a notable change to your character. Rewrite rather than let "
    "them grow unbounded."
)


def _ensure_files(memory_dir: str) -> dict[str, Path]:
    root = Path(memory_dir).expanduser()
    root.mkdir(parents=True, exist_ok=True)
    paths: dict[str, Path] = {}
    for key, (filename, template) in _FILES.items():
        path = root / filename
        if not path.exists():
            path.write_text(template, encoding="utf-8")
        paths[key] = path
    return paths


class Memory:
    """Registers read_memory/write_memory tools against a registry."""

    @staticmethod
    def register(registry: "Registry", *, memory_dir: str) -> None:
        paths = _ensure_files(memory_dir)

        def read_memory(file: str) -> str:
            path = paths.get(file.strip().lower())
            if path is None:
                return f"error: invalid file: {file!r} (expected one of {', '.join(sorted(_FILES))})"
            return path.read_text(encoding="utf-8")

        registry.tool(
            "read_memory",
            "Read the current contents of a persistent memory file.",
            {"file": {"type": "string", "description": "player | world"}},
            block=read_memory,
        )

        def write_memory(file: str, content: str) -> str:
            path = paths.get(file.strip().lower())
            if path is None:
                return f"error: invalid file: {file!r} (expected one of {', '.join(sorted(_FILES))})"
            path.write_text(content, encoding="utf-8")
            return f"ok: wrote {len(content.encode('utf-8'))} bytes to {path.name}"

        registry.tool(
            "write_memory",
            "Overwrite a persistent memory file with new content.",
            {
                "file": {"type": "string", "description": "player | world"},
                "content": {"type": "string", "description": "Full new contents of the file"},
            },
            block=write_memory,
        )

    @staticmethod
    def prompt_block(memory_dir: str) -> str:
        paths = _ensure_files(memory_dir)
        sections = "\n\n".join(
            f"--- {path.name} ---\n{path.read_text(encoding='utf-8')}"
            for path in paths.values()
        )
        return f"{_PROMPT_HEADER}\n\n{sections}"
```

- [ ] **Step 4: Export `Memory` from `tools/__init__.py`**

`week1_baseline/python/12_context/src/boukensha/tools/__init__.py` currently:

```python
"""Boukensha built-in tool modules."""

from __future__ import annotations

from .file_system import FileSystem
from .mud import Mud
from .shell import Shell

__all__ = ["FileSystem", "Mud", "Shell"]
```

Change to:

```python
"""Boukensha built-in tool modules."""

from __future__ import annotations

from .file_system import FileSystem
from .memory import Memory
from .mud import Mud
from .shell import Shell

__all__ = ["FileSystem", "Memory", "Mud", "Shell"]
```

- [ ] **Step 5: Run tests to verify they pass**

Run: `cd week1_baseline/python/12_context && python -m pytest tests/test_tools_memory.py -v`
Expected: PASS (11 passed)

- [ ] **Step 6: Commit**

```bash
cd week1_baseline/python/12_context
git add src/boukensha/tools/memory.py src/boukensha/tools/__init__.py tests/test_tools_memory.py
git commit -m "feat(12): add Memory tool module (read_memory/write_memory)"
```

---

### Task 3: Wire `memory` toggle into `run()` / `repl()`

**Files:**
- Modify: `week1_baseline/python/12_context/src/boukensha/__init__.py` (helper near `_mud_opts_from_config`; `run()` around lines 102-186; `repl()` around lines 242-313)
- Modify: `week1_baseline/python/12_context/.gitignore` (defensive entry)
- Test: `week1_baseline/python/12_context/tests/test_run_dsl.py` (append tests — it already contains the `boukensha.run()` integration-test pattern this feature needs)

**Interfaces:**
- Consumes: `Config.memory_enabled`, `Config.memory_dir` (Task 1), `tools.Memory.register`, `tools.Memory.prompt_block` (Task 2).
- Produces: `_memory_enabled(cfg: Config, memory: bool | None) -> bool` (module-level helper in `boukensha/__init__.py`, same visibility/testing style as `_mud_opts_from_config`); `run(..., memory: bool | None = None, ...)`; `repl(..., memory: bool | None = None, ...)`.

- [ ] **Step 1: Write the failing tests**

Append to `week1_baseline/python/12_context/tests/test_run_dsl.py` (add these imports at the top alongside the existing ones — `MagicMock` and `patch` are already imported; add nothing new there):

```python
def test_memory_enabled_helper_defaults_to_config():
    import boukensha
    from boukensha.config import Config

    mock_cfg = MagicMock(spec=Config)
    mock_cfg.memory_enabled = True
    assert boukensha._memory_enabled(mock_cfg, None) is True

    mock_cfg.memory_enabled = False
    assert boukensha._memory_enabled(mock_cfg, None) is False


def test_memory_enabled_helper_explicit_override_wins():
    import boukensha
    from boukensha.config import Config

    mock_cfg = MagicMock(spec=Config)
    mock_cfg.memory_enabled = False
    assert boukensha._memory_enabled(mock_cfg, True) is True

    mock_cfg.memory_enabled = True
    assert boukensha._memory_enabled(mock_cfg, False) is False


def test_run_registers_memory_tools_and_injects_prompt_by_default(monkeypatch):
    """memory=None (default) reads config (defaults to enabled) and wires everything."""
    with tempfile.TemporaryDirectory() as tmp:
        monkeypatch.setenv("BOUKENSHA_DIR", tmp)

        settings = {
            "tasks": {"player": {"provider": "anthropic", "model": "claude-haiku-4-5"}}
        }
        with open(f"{tmp}/settings.yaml", "w") as f:
            yaml.dump(settings, f)
        with open(f"{tmp}/.env", "w") as f:
            f.write("ANTHROPIC_API_KEY=test-key\n")

        fake_agent = MagicMock()
        fake_agent.run.return_value = "mocked result"

        captured_ctx = {}

        def _capture_agent(**kwargs):
            captured_ctx["context"] = kwargs["context"]
            return fake_agent

        with patch("boukensha.Agent", side_effect=_capture_agent):
            boukensha.run(task="hello", log=f"{tmp}/session.jsonl", working_dir=False)

        ctx = captured_ctx["context"]
        assert "read_memory" in ctx.tools
        assert "write_memory" in ctx.tools
        assert "player.md" in ctx.system
        assert "world.md" in ctx.system
        assert (Path(tmp) / "memory" / "player.md").exists()


def test_run_memory_false_disables_memory_entirely(monkeypatch):
    with tempfile.TemporaryDirectory() as tmp:
        monkeypatch.setenv("BOUKENSHA_DIR", tmp)

        settings = {
            "tasks": {"player": {"provider": "anthropic", "model": "claude-haiku-4-5"}}
        }
        with open(f"{tmp}/settings.yaml", "w") as f:
            yaml.dump(settings, f)
        with open(f"{tmp}/.env", "w") as f:
            f.write("ANTHROPIC_API_KEY=test-key\n")

        fake_agent = MagicMock()
        fake_agent.run.return_value = "mocked result"

        captured_ctx = {}

        def _capture_agent(**kwargs):
            captured_ctx["context"] = kwargs["context"]
            return fake_agent

        with patch("boukensha.Agent", side_effect=_capture_agent):
            boukensha.run(
                task="hello", log=f"{tmp}/session.jsonl", working_dir=False, memory=False
            )

        ctx = captured_ctx["context"]
        assert "read_memory" not in ctx.tools
        assert "write_memory" not in ctx.tools
        assert not (Path(tmp) / "memory").exists()
```

Add `from pathlib import Path` to the top of `test_run_dsl.py`'s imports (it currently imports `os`, `tempfile`, `MagicMock`/`patch`, `yaml`, and the boukensha modules — `Path` is not yet imported there).

- [ ] **Step 2: Run tests to verify they fail**

Run: `cd week1_baseline/python/12_context && python -m pytest tests/test_run_dsl.py -v -k memory`
Expected: FAIL — `AttributeError: module 'boukensha' has no attribute '_memory_enabled'`

- [ ] **Step 3: Add the `_memory_enabled` helper**

In `week1_baseline/python/12_context/src/boukensha/__init__.py`, immediately after the existing `_mud_opts_from_config` function (which ends at line 99, right before `def run(`):

```python
def _mud_opts_from_config(cfg: Config) -> dict | None:
    """Build mud kwargs from config. Returns None if mud.username is not set."""
    if not cfg.mud_username:
        return None
    return {
        "host":     cfg.mud_host,
        "port":     cfg.mud_port,
        "name":     cfg.mud_username,
        "password": cfg.mud_password,
    }


def _memory_enabled(cfg: Config, memory: bool | None) -> bool:
    """Resolve the memory toggle: explicit True/False wins, None reads config."""
    return cfg.memory_enabled if memory is None else bool(memory)


def run(
```

- [ ] **Step 4: Add the `memory` parameter and wiring to `run()`**

In `run()`'s signature (currently ends `mud: dict | bool | None = None,` / `tool_registrar: ...` at lines 117-118), add the new parameter:

```python
    mud: dict | bool | None = None,
    memory: bool | None = None,
    tool_registrar: Callable[[RunDSL], None] | None = None,
) -> str:
```

Update the docstring's Args block (after the existing `mud:` entry, before `tool_registrar:`):

```python
        mud: MUD connection options dict (host, port, name, password).
            None (default) reads from config if mud.username is set.
            False disables MUD tools entirely.
            A dict uses those connection params directly.
        memory: Persistent player.md/world.md memory toggle.
            None (default) reads from config (memory.enabled, default True).
            False disables memory entirely — no tools, no prompt injection.
            True forces it on regardless of config.
        tool_registrar: A callable that accepts a RunDSL and registers tools.
```

Immediately before `ctx = Context(task=task_class, system=resolved_system, working_dir=resolved_wd, context_window=context_window)` (line 169), insert:

```python
    resolved_memory_enabled = _memory_enabled(cfg, memory)
    if resolved_memory_enabled:
        memory_block = tools.Memory.prompt_block(cfg.memory_dir)
        resolved_system = f"{resolved_system}\n\n{memory_block}" if resolved_system else memory_block

    ctx = Context(task=task_class, system=resolved_system, working_dir=resolved_wd, context_window=context_window)
```

Immediately after the existing mud-registration block (lines 181-183):

```python
    resolved_mud = None if mud is False else (mud or _mud_opts_from_config(cfg))
    if resolved_mud:
        tools.Mud.register(registry, **resolved_mud)

    if resolved_memory_enabled:
        tools.Memory.register(registry, memory_dir=cfg.memory_dir)

    if tool_registrar is not None:
```

- [ ] **Step 5: Apply the same change to `repl()`**

`repl()` mirrors `run()` by design (per the comment above it: "Each step is a self-contained snapshot ... the boilerplate below intentionally mirrors run()"). Apply the identical edits:

Signature — add after `mud: dict | bool | None = None,` (currently line 257):

```python
    mud: dict | bool | None = None,
    memory: bool | None = None,
    tool_registrar: Callable[[RunDSL], None] | None = None,
) -> None:
```

Docstring — currently just says "See run() for full parameter documentation including the mud parameter." Update to:

```python
    """Start the interactive REPL loop.

    Same plumbing as run() but stays alive across multiple turns.
    See run() for full parameter documentation including the mud and memory parameters.
    """
```

Before `ctx = Context(...)` (currently line 295), insert the same block:

```python
    resolved_memory_enabled = _memory_enabled(cfg, memory)
    if resolved_memory_enabled:
        memory_block = tools.Memory.prompt_block(cfg.memory_dir)
        resolved_system = f"{resolved_system}\n\n{memory_block}" if resolved_system else memory_block

    ctx = Context(task=task_class, system=resolved_system, working_dir=resolved_wd, context_window=context_window)
```

After the mud-registration block (currently lines 307-309):

```python
    resolved_mud = None if mud is False else (mud or _mud_opts_from_config(cfg))
    if resolved_mud:
        tools.Mud.register(registry, **resolved_mud)

    if resolved_memory_enabled:
        tools.Memory.register(registry, memory_dir=cfg.memory_dir)

    if tool_registrar is not None:
```

- [ ] **Step 6: Add the defensive `.gitignore` entry**

Check `week1_baseline/python/12_context/.gitignore` for an existing entry; append if not already covered:

```bash
cd week1_baseline/python/12_context
grep -qxF '.boukensha/' .gitignore || echo '.boukensha/' >> .gitignore
```

This guards the case where `BOUKENSHA_DIR` is pointed inside the project (the default `~/.boukensha/memory/` already lives outside the repo).

- [ ] **Step 7: Run tests to verify they pass**

Run: `cd week1_baseline/python/12_context && python -m pytest tests/test_run_dsl.py -v -k memory`
Expected: PASS (4 passed)

- [ ] **Step 8: Run the full test suite to check for regressions**

Run: `cd week1_baseline/python/12_context && python -m pytest -v`
Expected: PASS (all tests, no failures)

- [ ] **Step 9: Commit**

```bash
cd week1_baseline/python/12_context
git add src/boukensha/__init__.py tests/test_run_dsl.py .gitignore
git commit -m "feat(12): wire memory toggle into run()/repl()"
```

---

### Task 4: `/memory` REPL command

**Files:**
- Modify: `week1_baseline/python/12_context/src/boukensha/repl.py` (HELP text, `_MUD_TOOL_NAMES` area, `handle_command`, `_banner`)
- Test: `week1_baseline/python/12_context/tests/test_repl.py` (append tests)

**Interfaces:**
- Consumes: `Repl.handle_command(text: str) -> str | None` (existing method being extended), `self._context.tools` (existing `Context.tools` dict).
- Produces: `_MEMORY_TOOL_NAMES: frozenset[str]` (module-level constant in `repl.py`), `/memory` command support in `handle_command`, updated `/file` filtering and banner tool counts.

- [ ] **Step 1: Write the failing tests**

Append to `week1_baseline/python/12_context/tests/test_repl.py`:

```python
def test_repl_memory_command_lists_registered_tools(capsys):
    repl, ctx, _ = _make_repl()
    from boukensha.registry import Registry
    registry = Registry(ctx)
    registry.tool("read_memory", "Read memory", {}, block=lambda **_: "")
    registry.tool("write_memory", "Write memory", {}, block=lambda **_: "")
    result = repl.handle_command("/memory")
    assert result == "command"
    captured = capsys.readouterr()
    assert "read_memory" in captured.out
    assert "write_memory" in captured.out


def test_repl_memory_command_when_no_memory_tools(capsys):
    repl, ctx, _ = _make_repl()
    result = repl.handle_command("/memory")
    assert result == "command"
    captured = capsys.readouterr()
    assert "no MEMORY tools registered" in captured.out


def test_repl_file_command_excludes_memory_tools(capsys):
    repl, ctx, _ = _make_repl()
    from boukensha.registry import Registry
    registry = Registry(ctx)
    registry.tool("read_memory", "Read memory", {}, block=lambda **_: "")
    registry.tool("read_file", "Read file", {}, block=lambda **_: "")
    repl.handle_command("/file")
    captured = capsys.readouterr()
    assert "read_file" in captured.out
    assert "read_memory" not in captured.out


def test_repl_memory_in_help_text(capsys):
    repl, ctx, _ = _make_repl()
    repl.handle_command("/help")
    captured = capsys.readouterr()
    assert "/memory" in captured.out
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `cd week1_baseline/python/12_context && python -m pytest tests/test_repl.py -v -k memory`
Expected: FAIL — `/memory` not recognized (`handle_command` returns `None`, so `result == "command"` assertion fails)

- [ ] **Step 3: Add `_MEMORY_TOOL_NAMES` and update `HELP`**

In `week1_baseline/python/12_context/src/boukensha/repl.py`, the current top section (lines 20-40):

```python
HELP = """\
Commands:
  /quiet   suppress logging output
  /loud    re-enable logging output
  /clear   wipe conversation history (tools stay)
  /compact drop oldest 40% of messages to free context
  /mud     list registered MUD tool names
  /file    list registered FILE tool names
  /exit    leave the REPL
  /help    show this message"""

_MUD_TOOL_NAMES: frozenset[str] = frozenset({
    "mud_connect", "mud_disconnect", "mud_status",
    "look", "examine", "check",
    "move", "flee", "set_position", "track",
    "attack", "skill_strike", "consider",
    "say", "tell", "channel_say",
    "get_item", "drop_item", "put_item", "equip_item", "consume_item",
    "cast_spell", "use_magic_item",
    "shop", "practice", "save_character", "send_raw",
})
```

Replace with:

```python
HELP = """\
Commands:
  /quiet   suppress logging output
  /loud    re-enable logging output
  /clear   wipe conversation history (tools stay)
  /compact drop oldest 40% of messages to free context
  /mud     list registered MUD tool names
  /file    list registered FILE tool names
  /memory  list registered MEMORY tool names
  /exit    leave the REPL
  /help    show this message"""

_MUD_TOOL_NAMES: frozenset[str] = frozenset({
    "mud_connect", "mud_disconnect", "mud_status",
    "look", "examine", "check",
    "move", "flee", "set_position", "track",
    "attack", "skill_strike", "consider",
    "say", "tell", "channel_say",
    "get_item", "drop_item", "put_item", "equip_item", "consume_item",
    "cast_spell", "use_magic_item",
    "shop", "practice", "save_character", "send_raw",
})

_MEMORY_TOOL_NAMES: frozenset[str] = frozenset({
    "read_memory", "write_memory",
})
```

- [ ] **Step 4: Add the `/memory` branch and fix `/file` filtering in `handle_command`**

Current (lines 138-151):

```python
        if text == "/mud":
            mud_tools = sorted(set(self._context.tools) & _MUD_TOOL_NAMES)
            if mud_tools:
                self._output("MUD tools:\n" + "\n".join(f"  {n}" for n in mud_tools))
            else:
                self._output("(no MUD tools registered)")
            return "command"
        if text == "/file":
            file_tools = sorted(set(self._context.tools) - _MUD_TOOL_NAMES)
            if file_tools:
                self._output("FILE tools:\n" + "\n".join(f"  {n}" for n in file_tools))
            else:
                self._output("(no FILE tools registered)")
            return "command"
        return None
```

Replace with:

```python
        if text == "/mud":
            mud_tools = sorted(set(self._context.tools) & _MUD_TOOL_NAMES)
            if mud_tools:
                self._output("MUD tools:\n" + "\n".join(f"  {n}" for n in mud_tools))
            else:
                self._output("(no MUD tools registered)")
            return "command"
        if text == "/file":
            file_tools = sorted(set(self._context.tools) - _MUD_TOOL_NAMES - _MEMORY_TOOL_NAMES)
            if file_tools:
                self._output("FILE tools:\n" + "\n".join(f"  {n}" for n in file_tools))
            else:
                self._output("(no FILE tools registered)")
            return "command"
        if text == "/memory":
            memory_tools = sorted(set(self._context.tools) & _MEMORY_TOOL_NAMES)
            if memory_tools:
                self._output("MEMORY tools:\n" + "\n".join(f"  {n}" for n in memory_tools))
            else:
                self._output("(no MEMORY tools registered)")
            return "command"
        return None
```

- [ ] **Step 5: Update the banner's tool counts**

Current (lines 221-224):

```python
        all_tools = set(self._context.tools)
        mud_count = len(all_tools & _MUD_TOOL_NAMES)
        file_count = len(all_tools - _MUD_TOOL_NAMES)
        tools_line = f"MUD ({mud_count})  FILE ({file_count})"
```

Replace with:

```python
        all_tools = set(self._context.tools)
        mud_count = len(all_tools & _MUD_TOOL_NAMES)
        memory_count = len(all_tools & _MEMORY_TOOL_NAMES)
        file_count = len(all_tools - _MUD_TOOL_NAMES - _MEMORY_TOOL_NAMES)
        tools_line = f"MUD ({mud_count})  FILE ({file_count})  MEMORY ({memory_count})"
```

And update the banner's command hint (current line 238):

```python
            f"  /mud or /file    list tools by group\n"
```

Replace with:

```python
            f"  /mud, /file, /memory   list tools by group\n"
```

- [ ] **Step 6: Run tests to verify they pass**

Run: `cd week1_baseline/python/12_context && python -m pytest tests/test_repl.py -v`
Expected: PASS (all tests, including the 4 new ones)

- [ ] **Step 7: Run the full test suite to check for regressions**

Run: `cd week1_baseline/python/12_context && python -m pytest -v`
Expected: PASS (all tests, no failures)

- [ ] **Step 8: Commit**

```bash
cd week1_baseline/python/12_context
git add src/boukensha/repl.py tests/test_repl.py
git commit -m "feat(12): add /memory REPL command"
```

---

## Manual verification (post-implementation)

Not part of TDD, but worth doing once all tasks are complete, since this feature touches the live REPL banner/help text which automated tests only partially cover visually:

```bash
cd week1_baseline/python/12_context
BOUKENSHA_DIR=/tmp/boukensha-memory-check python -c "
import boukensha
print(boukensha.tools.Memory)
"
ls /tmp/boukensha-memory-check/memory/  # should NOT exist yet — only created when run()/repl() actually executes
```

Then run the REPL against a local test MUD (if available) or with `mud=False` and confirm `/memory` lists `read_memory`/`write_memory`, and that `~/.boukensha/memory/player.md` / `world.md` get created and populated by the agent over a session.
