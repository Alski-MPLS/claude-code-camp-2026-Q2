# Standard Tool Library Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Port the Ruby `10_standard_tool_library` step to Python by adding two auto-registering tool modules — `FileSystem` (6 tools: `pwd`, `list_directory`, `read_file`, `write_file`, `delete_file`, `search_files`) and `Shell` (`run_command`) — that activate whenever `working_dir` is set on `boukensha.run()` or `boukensha.repl()`.

**Architecture:** The Ruby gem adds `lib/boukensha/tools/file_system.rb` and `lib/boukensha/tools/shell.rb` as module-level registrar objects. Python mirrors this with a `boukensha/tools/` subpackage containing `file_system.py` and `shell.py`, each exposing a `FileSystem.register(registry, *, working_dir)` / `Shell.register(registry, *, working_dir, ...)` static method. The top-level `run()` and `repl()` gain three new keyword args (`working_dir`, `allowed_commands`, `shell_timeout`); when `working_dir` is truthy both modules are auto-registered before user-supplied tools. `Context` gains a `working_dir` attribute to mirror the Ruby struct. `Tools::Mud` from the Ruby source is **not** ported — it depends on the `mud_manager` Ruby gem with no Python equivalent.

**Tech Stack:** Python ≥ 3.11, `uv`, `hatchling`, `pytest`, `pyyaml`, `python-dotenv`. No new runtime dependencies — `re`, `glob`, `os`, `subprocess`, `shlex` are all stdlib.

## Global Constraints

- All source lives under `week1_baseline/python/10_standard_tool_library/` — never modify step 09.
- Package layout: `src/boukensha/` (step 09 baseline) + new `src/boukensha/tools/` subpackage.
- `pyproject.toml` name field: `"boukensha-standard-tool-library"`, version stays `"0.1.0"`.
- `Tools::Mud` is explicitly out of scope — no stub, no placeholder, no import.
- All paths in FileSystem tools are resolved relative to the working directory root; absolute paths and `..` traversals that escape the root return an `"error: ..."` string (never raise).
- `working_dir=None` in `run()`/`repl()` resolves to `os.getcwd()` (matches Ruby's `Dir.pwd` default). `working_dir=False` or `working_dir=""` disables tool registration entirely.
- `allowed_commands=None` permits any executable (Ruby default). An explicit list rejects non-listed executables before execution.
- Tests run with `uv run pytest tests/ -v` from the step directory.
- Follow step 09 naming/style: snake_case, `from __future__ import annotations`, type hints on all public APIs.

---

### Task 1: Scaffold step 10 from step 09

**Files:**
- Create: `week1_baseline/python/10_standard_tool_library/` (whole tree, copied from step 09)
- Modify: `week1_baseline/python/10_standard_tool_library/pyproject.toml`

**Interfaces:**
- Produces: a working copy of the step 09 package installed in its own venv, with all existing tests passing before any new code is added.

- [ ] **Step 1: Copy all source files from step 09 to step 10**

```bash
SRC=week1_baseline/python/09_global_executable
DST=week1_baseline/python/10_standard_tool_library
cp -r "$SRC/src" "$DST/"
cp -r "$SRC/tests" "$DST/"
cp -r "$SRC/prompts" "$DST/"
cp -r "$SRC/examples" "$DST/"
cp "$SRC/pyproject.toml" "$DST/"
cp "$SRC/.gitignore" "$DST/" 2>/dev/null || true
find "$DST" -name "__pycache__" -type d -exec rm -rf {} +
```

- [ ] **Step 2: Update `pyproject.toml` name and description**

Edit `week1_baseline/python/10_standard_tool_library/pyproject.toml` — change:
```toml
name = "boukensha-global-executable"
description = "Boukensha global executable (Step 9)"
```
to:
```toml
name = "boukensha-standard-tool-library"
description = "Boukensha standard tool library (Step 10)"
```

- [ ] **Step 3: Install and verify baseline tests pass**

```bash
cd week1_baseline/python/10_standard_tool_library
uv sync
uv run pytest tests/ -v
```

Expected: all tests from step 09 pass.

- [ ] **Step 4: Commit the scaffold**

```bash
git add week1_baseline/python/10_standard_tool_library/
git commit -m "feat: scaffold step 10 from step 09 baseline"
```

---

### Task 2: Add `working_dir` to `Context`

**Files:**
- Modify: `week1_baseline/python/10_standard_tool_library/src/boukensha/context.py`
- Modify: `week1_baseline/python/10_standard_tool_library/tests/test_context.py`

**Interfaces:**
- Produces: `Context.__init__` gains a `working_dir: str | None = None` param; the resolved absolute path is stored as `self.working_dir: str | None`. Passing `None` leaves `self.working_dir` as `None`.

- [ ] **Step 1: Write the failing test**

Add to the bottom of `tests/test_context.py`:

```python
from pathlib import Path


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
```

- [ ] **Step 2: Run test to verify it fails**

```bash
cd week1_baseline/python/10_standard_tool_library
uv run pytest tests/test_context.py -v -k "working_dir"
```

Expected: `TypeError: __init__() got an unexpected keyword argument 'working_dir'`

- [ ] **Step 3: Update `context.py`**

In `src/boukensha/context.py`, replace the `__init__` signature:

```python
def __init__(self, task: type[Base], system: str | None = None) -> None:
    self.task = task
    self.system = system
    self.messages: list[Message] = []
    self.tools: dict[str, Tool] = {}
```

with:

```python
def __init__(
    self,
    task: type[Base],
    system: str | None = None,
    working_dir: str | None = None,
) -> None:
    self.task = task
    self.system = system
    self.working_dir = str(Path(working_dir).expanduser().resolve()) if working_dir else None
    self.messages: list[Message] = []
    self.tools: dict[str, Tool] = {}
```

Also add `from pathlib import Path` to the imports at the top of `context.py`:

```python
from pathlib import Path
```

- [ ] **Step 4: Run tests to verify they pass**

```bash
uv run pytest tests/test_context.py -v
```

Expected: all context tests PASS.

- [ ] **Step 5: Commit**

```bash
git add src/boukensha/context.py tests/test_context.py
git commit -m "feat: add working_dir attribute to Context"
```

---

### Task 3: `tools/` package + `FileSystem` module

**Files:**
- Create: `week1_baseline/python/10_standard_tool_library/src/boukensha/tools/__init__.py`
- Create: `week1_baseline/python/10_standard_tool_library/src/boukensha/tools/file_system.py`
- Create: `week1_baseline/python/10_standard_tool_library/tests/test_tools_file_system.py`

**Interfaces:**
- Produces:
  - `boukensha.tools.FileSystem` — a class with a single static method `FileSystem.register(registry, *, working_dir: str) -> None` that registers `pwd`, `list_directory`, `read_file`, `write_file`, `delete_file`, `search_files` on the given registry, all sandboxed to `working_dir`.
  - Every tool returns a plain `str`. Path-escape attempts return `"error: path '...' escapes the working directory"`. Other errors return `"error: <message>"`. Success returns operation-specific strings.

- [ ] **Step 1: Write the failing tests**

Create `tests/test_tools_file_system.py`:

```python
from __future__ import annotations

from pathlib import Path

import pytest

from boukensha.context import Context
from boukensha.registry import Registry
from boukensha.tasks.player import Player
from boukensha.tools.file_system import FileSystem


def _make_registry(tmp_path: Path) -> Registry:
    ctx = Context(task=Player, system="sys")
    return Registry(ctx)


def test_pwd_returns_root(tmp_path):
    registry = _make_registry(tmp_path)
    FileSystem.register(registry, working_dir=str(tmp_path))
    result = registry.dispatch("pwd", {})
    assert result == str(tmp_path.resolve())


def test_list_directory_lists_files_and_dirs(tmp_path):
    (tmp_path / "hello.txt").write_text("hi")
    (tmp_path / "subdir").mkdir()
    registry = _make_registry(tmp_path)
    FileSystem.register(registry, working_dir=str(tmp_path))
    result = registry.dispatch("list_directory", {"path": "."})
    assert "hello.txt" in result
    assert "subdir/" in result


def test_list_directory_default_path(tmp_path):
    (tmp_path / "file.txt").write_text("content")
    registry = _make_registry(tmp_path)
    FileSystem.register(registry, working_dir=str(tmp_path))
    result = registry.dispatch("list_directory", {})
    assert "file.txt" in result


def test_list_directory_empty_dir(tmp_path):
    registry = _make_registry(tmp_path)
    FileSystem.register(registry, working_dir=str(tmp_path))
    result = registry.dispatch("list_directory", {"path": "."})
    assert result == "(empty)"


def test_list_directory_not_a_directory(tmp_path):
    (tmp_path / "file.txt").write_text("content")
    registry = _make_registry(tmp_path)
    FileSystem.register(registry, working_dir=str(tmp_path))
    result = registry.dispatch("list_directory", {"path": "file.txt"})
    assert result.startswith("error:")


def test_read_file_returns_contents(tmp_path):
    (tmp_path / "notes.txt").write_text("hello world")
    registry = _make_registry(tmp_path)
    FileSystem.register(registry, working_dir=str(tmp_path))
    result = registry.dispatch("read_file", {"path": "notes.txt"})
    assert result == "hello world"


def test_read_file_not_a_file(tmp_path):
    (tmp_path / "subdir").mkdir()
    registry = _make_registry(tmp_path)
    FileSystem.register(registry, working_dir=str(tmp_path))
    result = registry.dispatch("read_file", {"path": "subdir"})
    assert result.startswith("error:")


def test_write_file_creates_file(tmp_path):
    registry = _make_registry(tmp_path)
    FileSystem.register(registry, working_dir=str(tmp_path))
    result = registry.dispatch("write_file", {"path": "new.txt", "content": "created"})
    assert result.startswith("ok:")
    assert (tmp_path / "new.txt").read_text() == "created"


def test_write_file_reports_byte_count(tmp_path):
    registry = _make_registry(tmp_path)
    FileSystem.register(registry, working_dir=str(tmp_path))
    result = registry.dispatch("write_file", {"path": "bytes.txt", "content": "abc"})
    assert "3 bytes" in result


def test_write_file_creates_parent_directories(tmp_path):
    registry = _make_registry(tmp_path)
    FileSystem.register(registry, working_dir=str(tmp_path))
    registry.dispatch("write_file", {"path": "a/b/c.txt", "content": "nested"})
    assert (tmp_path / "a" / "b" / "c.txt").read_text() == "nested"


def test_delete_file_removes_file(tmp_path):
    (tmp_path / "target.txt").write_text("bye")
    registry = _make_registry(tmp_path)
    FileSystem.register(registry, working_dir=str(tmp_path))
    result = registry.dispatch("delete_file", {"path": "target.txt"})
    assert result.startswith("ok:")
    assert not (tmp_path / "target.txt").exists()


def test_delete_file_rejects_directory(tmp_path):
    (tmp_path / "adir").mkdir()
    registry = _make_registry(tmp_path)
    FileSystem.register(registry, working_dir=str(tmp_path))
    result = registry.dispatch("delete_file", {"path": "adir"})
    assert result.startswith("error:")


def test_path_traversal_rejected(tmp_path):
    registry = _make_registry(tmp_path)
    FileSystem.register(registry, working_dir=str(tmp_path))
    result = registry.dispatch("read_file", {"path": "../../etc/passwd"})
    assert result.startswith("error:")
    assert "escapes" in result


def test_search_files_finds_pattern(tmp_path):
    (tmp_path / "a.txt").write_text("hello world\nfoo bar\n")
    (tmp_path / "b.txt").write_text("hello again\n")
    registry = _make_registry(tmp_path)
    FileSystem.register(registry, working_dir=str(tmp_path))
    result = registry.dispatch("search_files", {"pattern": "hello"})
    assert "a.txt:1:hello world" in result
    assert "b.txt:1:hello again" in result


def test_search_files_no_matches(tmp_path):
    (tmp_path / "a.txt").write_text("nothing here\n")
    registry = _make_registry(tmp_path)
    FileSystem.register(registry, working_dir=str(tmp_path))
    result = registry.dispatch("search_files", {"pattern": "ZZZMISSING"})
    assert result == "no matches"


def test_search_files_with_glob_filter(tmp_path):
    (tmp_path / "a.py").write_text("pattern_here\n")
    (tmp_path / "b.txt").write_text("pattern_here\n")
    registry = _make_registry(tmp_path)
    FileSystem.register(registry, working_dir=str(tmp_path))
    result = registry.dispatch("search_files", {"pattern": "pattern_here", "glob": "*.py"})
    assert "a.py" in result
    assert "b.txt" not in result


def test_search_files_invalid_pattern(tmp_path):
    registry = _make_registry(tmp_path)
    FileSystem.register(registry, working_dir=str(tmp_path))
    result = registry.dispatch("search_files", {"pattern": "["})
    assert result.startswith("error: invalid pattern")
```

- [ ] **Step 2: Run tests to verify they fail**

```bash
cd week1_baseline/python/10_standard_tool_library
uv run pytest tests/test_tools_file_system.py -v
```

Expected: `ModuleNotFoundError: No module named 'boukensha.tools'`

- [ ] **Step 3: Create `src/boukensha/tools/__init__.py`**

Create `week1_baseline/python/10_standard_tool_library/src/boukensha/tools/__init__.py`:

```python
"""Boukensha built-in tool modules."""

from __future__ import annotations

from .file_system import FileSystem
from .shell import Shell

__all__ = ["FileSystem", "Shell"]
```

- [ ] **Step 4: Create `src/boukensha/tools/file_system.py`**

Create `week1_baseline/python/10_standard_tool_library/src/boukensha/tools/file_system.py`:

```python
"""FileSystem tool module: registers six sandboxed file-operation tools."""

from __future__ import annotations

import glob as _glob
import os
import re
from pathlib import Path
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from boukensha.registry import Registry


class FileSystem:
    @staticmethod
    def register(registry: Registry, *, working_dir: str) -> None:
        root = str(Path(working_dir).expanduser().resolve())

        def _resolve(path: str) -> str:
            absolute = str(Path(os.path.join(root, path)).resolve())
            if absolute == root or absolute.startswith(root + os.sep):
                return absolute
            return f"error: path '{path}' escapes the working directory"

        def _oops(msg: str) -> str:
            return f"error: {msg}"

        def pwd() -> str:
            return root

        registry.tool(
            "pwd",
            "Return the working directory — the root that all file paths are relative to.",
            {},
            block=pwd,
        )

        def list_directory(path: str = ".") -> str:
            target = _resolve(path)
            if target.startswith("error:"):
                return target
            if not os.path.isdir(target):
                return _oops(f"'{path}' is not a directory")
            entries = sorted(os.listdir(target))
            entries = [
                f"{e}/" if os.path.isdir(os.path.join(target, e)) else e
                for e in entries
            ]
            return "(empty)" if not entries else "\n".join(entries)

        registry.tool(
            "list_directory",
            "List files and subdirectories at a path relative to the working directory. Defaults to the working directory itself.",
            {"path": {"type": "string", "description": "Relative path to list (default '.')"}},
            block=list_directory,
        )

        def read_file(path: str) -> str:
            target = _resolve(path)
            if target.startswith("error:"):
                return target
            if not os.path.isfile(target):
                return _oops(f"'{path}' is not a file")
            try:
                return Path(target).read_text(encoding="utf-8")
            except Exception as e:
                return _oops(str(e))

        registry.tool(
            "read_file",
            "Read and return the full contents of a file. Path is relative to the working directory.",
            {"path": {"type": "string", "description": "Relative path to the file"}},
            block=read_file,
        )

        def write_file(path: str, content: str) -> str:
            target = _resolve(path)
            if target.startswith("error:"):
                return target
            try:
                os.makedirs(os.path.dirname(target), exist_ok=True)
                Path(target).write_text(content, encoding="utf-8")
                byte_count = len(content.encode("utf-8"))
                rel = target.removeprefix(root + os.sep)
                return f"ok: wrote {byte_count} bytes to {rel}"
            except Exception as e:
                return _oops(str(e))

        registry.tool(
            "write_file",
            "Write content to a file, creating it (and any missing parent directories) if needed, overwriting if it exists. Path is relative to the working directory.",
            {
                "path": {"type": "string", "description": "Relative path to the file"},
                "content": {"type": "string", "description": "Text content to write"},
            },
            block=write_file,
        )

        def delete_file(path: str) -> str:
            target = _resolve(path)
            if target.startswith("error:"):
                return target
            if not os.path.isfile(target):
                return _oops(f"'{path}' is not a file")
            try:
                os.remove(target)
                return f"ok: deleted {path}"
            except Exception as e:
                return _oops(str(e))

        registry.tool(
            "delete_file",
            "Delete a file. Directories are not deleted. Path is relative to the working directory.",
            {"path": {"type": "string", "description": "Relative path to the file to delete"}},
            block=delete_file,
        )

        def search_files(pattern: str, path: str = ".", glob: str = "*") -> str:
            target = _resolve(path)
            if target.startswith("error:"):
                return target

            if os.path.isfile(target):
                file_pattern = target
            else:
                file_pattern = os.path.join(target, "**", glob)

            try:
                regex = re.compile(pattern)
            except re.error as e:
                return _oops(f"invalid pattern: {e}")

            matches: list[str] = []
            for file in sorted(_glob.glob(file_pattern, recursive=True)):
                if not os.path.isfile(file):
                    continue
                rel = file.removeprefix(root + os.sep)
                try:
                    with open(file, encoding="utf-8", errors="replace") as f:
                        for lineno, line in enumerate(f, 1):
                            if regex.search(line):
                                matches.append(f"{rel}:{lineno}:{line.rstrip()}")
                except Exception as e:
                    matches.append(f"{rel}: error reading file: {e}")

            return "no matches" if not matches else "\n".join(matches)

        registry.tool(
            "search_files",
            "Search for a text pattern (literal string or Python regex) across all files in the working directory tree. Returns matching lines in 'path:line_number:content' format.",
            {
                "pattern": {"type": "string", "description": "The text or regex pattern to search for"},
                "path": {"type": "string", "description": "Subdirectory or file to search within (default '.' = entire working directory)"},
                "glob": {"type": "string", "description": "File glob to restrict which files are searched, e.g. '*.py' (default '*')"},
            },
            block=search_files,
        )
```

- [ ] **Step 5: Run tests to verify they pass**

```bash
uv run pytest tests/test_tools_file_system.py -v
```

Expected: all 18 tests PASS.

- [ ] **Step 6: Commit**

```bash
git add src/boukensha/tools/__init__.py src/boukensha/tools/file_system.py tests/test_tools_file_system.py
git commit -m "feat: add boukensha.tools.FileSystem with six sandboxed file operation tools"
```

---

### Task 4: `Shell` module

**Files:**
- Create: `week1_baseline/python/10_standard_tool_library/src/boukensha/tools/shell.py`
- Create: `week1_baseline/python/10_standard_tool_library/tests/test_tools_shell.py`

**Interfaces:**
- Consumes: `boukensha.tools` package (`__init__.py` already exports `Shell` once this file exists)
- Produces: `boukensha.tools.Shell` — a class with a static method `Shell.register(registry, *, working_dir: str, timeout: int = 30, allowed_commands: list[str] | None = None) -> None` that registers `run_command` on the registry. The tool combines stdout and stderr (like `Open3.capture2e`), respects the timeout, and checks the first token of the command against `allowed_commands` when set.

- [ ] **Step 1: Write the failing tests**

Create `tests/test_tools_shell.py`:

```python
from __future__ import annotations

import sys
from pathlib import Path

import pytest

from boukensha.context import Context
from boukensha.registry import Registry
from boukensha.tasks.player import Player
from boukensha.tools.shell import Shell


def _make_registry(tmp_path: Path) -> Registry:
    ctx = Context(task=Player, system="sys")
    return Registry(ctx)


@pytest.mark.skipif(sys.platform == "win32", reason="Unix shell commands")
def test_run_command_basic(tmp_path):
    registry = _make_registry(tmp_path)
    Shell.register(registry, working_dir=str(tmp_path))
    result = registry.dispatch("run_command", {"command": "echo hello"})
    assert "hello" in result


@pytest.mark.skipif(sys.platform == "win32", reason="Unix shell commands")
def test_run_command_merges_stderr(tmp_path):
    registry = _make_registry(tmp_path)
    Shell.register(registry, working_dir=str(tmp_path))
    result = registry.dispatch("run_command", {"command": "echo err >&2"})
    assert "err" in result


@pytest.mark.skipif(sys.platform == "win32", reason="Unix shell commands")
def test_run_command_nonzero_exit_noted(tmp_path):
    registry = _make_registry(tmp_path)
    Shell.register(registry, working_dir=str(tmp_path))
    result = registry.dispatch("run_command", {"command": "exit 1"})
    assert "[exit 1]" in result


@pytest.mark.skipif(sys.platform == "win32", reason="Unix shell commands")
def test_run_command_no_output(tmp_path):
    registry = _make_registry(tmp_path)
    Shell.register(registry, working_dir=str(tmp_path))
    result = registry.dispatch("run_command", {"command": "true"})
    assert result.startswith("(no output)")


@pytest.mark.skipif(sys.platform == "win32", reason="Unix shell commands")
def test_run_command_allowed_commands_permits(tmp_path):
    registry = _make_registry(tmp_path)
    Shell.register(registry, working_dir=str(tmp_path), allowed_commands=["echo"])
    result = registry.dispatch("run_command", {"command": "echo hi"})
    assert "hi" in result


@pytest.mark.skipif(sys.platform == "win32", reason="Unix shell commands")
def test_run_command_allowed_commands_blocks(tmp_path):
    registry = _make_registry(tmp_path)
    Shell.register(registry, working_dir=str(tmp_path), allowed_commands=["echo"])
    result = registry.dispatch("run_command", {"command": "rm -rf /"})
    assert result.startswith("error:")
    assert "allowed-commands" in result


@pytest.mark.skipif(sys.platform == "win32", reason="Unix shell commands")
def test_run_command_timeout(tmp_path):
    registry = _make_registry(tmp_path)
    Shell.register(registry, working_dir=str(tmp_path), timeout=1)
    result = registry.dispatch("run_command", {"command": "sleep 10"})
    assert result.startswith("error:")
    assert "timed out" in result


@pytest.mark.skipif(sys.platform == "win32", reason="Unix shell commands")
def test_run_command_runs_in_working_dir(tmp_path):
    (tmp_path / "probe.txt").write_text("probed")
    registry = _make_registry(tmp_path)
    Shell.register(registry, working_dir=str(tmp_path))
    result = registry.dispatch("run_command", {"command": "cat probe.txt"})
    assert "probed" in result


def test_run_command_description_includes_timeout(tmp_path):
    registry = _make_registry(tmp_path)
    Shell.register(registry, working_dir=str(tmp_path), timeout=45)
    tool = registry._context.tools["run_command"]
    assert "45" in tool.description


def test_run_command_description_includes_allowed_list(tmp_path):
    registry = _make_registry(tmp_path)
    Shell.register(registry, working_dir=str(tmp_path), allowed_commands=["python", "git"])
    tool = registry._context.tools["run_command"]
    assert "python" in tool.description
    assert "git" in tool.description
```

- [ ] **Step 2: Run tests to verify they fail**

```bash
cd week1_baseline/python/10_standard_tool_library
uv run pytest tests/test_tools_shell.py -v
```

Expected: `ImportError: cannot import name 'Shell' from 'boukensha.tools'`

- [ ] **Step 3: Create `src/boukensha/tools/shell.py`**

Create `week1_baseline/python/10_standard_tool_library/src/boukensha/tools/shell.py`:

```python
"""Shell tool module: registers a sandboxed run_command tool."""

from __future__ import annotations

import shlex
import subprocess
from pathlib import Path
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from boukensha.registry import Registry


class Shell:
    @staticmethod
    def register(
        registry: Registry,
        *,
        working_dir: str,
        timeout: int = 30,
        allowed_commands: list[str] | None = None,
    ) -> None:
        root = str(Path(working_dir).expanduser().resolve())

        def _oops(msg: str) -> str:
            return f"error: {msg}"

        allowed_note = (
            f" Allowed executables: {', '.join(allowed_commands)}."
            if allowed_commands
            else ""
        )
        description = (
            f"Run a shell command inside the working directory and return its combined "
            f"stdout+stderr output. Commands run with a {timeout}-second timeout.{allowed_note}"
        )

        def run_command(command: str) -> str:
            if allowed_commands is not None:
                try:
                    parts = shlex.split(command)
                except ValueError:
                    parts = command.strip().split()
                executable = parts[0] if parts else ""
                if executable not in allowed_commands:
                    return _oops(
                        f"'{executable}' is not in the allowed-commands list "
                        f"({', '.join(allowed_commands)})"
                    )

            try:
                result = subprocess.run(
                    command,
                    shell=True,
                    cwd=root,
                    stdout=subprocess.PIPE,
                    stderr=subprocess.STDOUT,
                    text=True,
                    timeout=timeout,
                )
                output = result.stdout.strip()
                exit_note = "" if result.returncode == 0 else f"\n[exit {result.returncode}]"
                return f"(no output){exit_note}" if not output else f"{output}{exit_note}"
            except subprocess.TimeoutExpired:
                return _oops(f"command timed out after {timeout}s: {command}")
            except FileNotFoundError as e:
                return _oops(f"command not found: {e}")
            except Exception as e:
                return _oops(str(e))

        registry.tool(
            "run_command",
            description,
            {"command": {"type": "string", "description": "The shell command to execute (e.g. 'python script.py', 'ls -la', 'git status')"}},
            block=run_command,
        )
```

- [ ] **Step 4: Run tests to verify they pass**

```bash
uv run pytest tests/test_tools_shell.py -v
```

Expected: all tests PASS.

- [ ] **Step 5: Commit**

```bash
git add src/boukensha/tools/shell.py tests/test_tools_shell.py
git commit -m "feat: add boukensha.tools.Shell with run_command tool"
```

---

### Task 5: Wire up auto-registration in `run()` and `repl()`

**Files:**
- Modify: `week1_baseline/python/10_standard_tool_library/src/boukensha/__init__.py`
- Modify: `week1_baseline/python/10_standard_tool_library/tests/test_run_dsl.py`

**Interfaces:**
- Consumes: `boukensha.tools.FileSystem.register(registry, working_dir=...)` and `boukensha.tools.Shell.register(registry, working_dir=..., timeout=..., allowed_commands=...)` (Tasks 3 and 4)
- Produces:
  - `boukensha.run()` gains `working_dir: str | bool | None = None`, `allowed_commands: list[str] | None = None`, `shell_timeout: int = 30`. When `working_dir` resolves to a truthy path, FileSystem and Shell are registered before user `tool_registrar` tools. `None` → `os.getcwd()`. `False` or `""` → skip tool registration.
  - `boukensha.repl()` gains the same three new kwargs, identical behavior.
  - `Context(working_dir=resolved_wd)` is passed the resolved path.
  - `boukensha.tools` is exported from `__all__`.

- [ ] **Step 1: Write the failing tests**

Add to the bottom of `tests/test_run_dsl.py`:

```python
import os
import tempfile
import yaml
from unittest.mock import MagicMock, patch


def _make_boukensha_dir(tmp_path):
    settings = {
        "tasks": {"player": {"provider": "anthropic", "model": "claude-haiku-4-5"}}
    }
    with open(f"{tmp_path}/settings.yaml", "w") as f:
        yaml.dump(settings, f)
    with open(f"{tmp_path}/.env", "w") as f:
        f.write("ANTHROPIC_API_KEY=test-key\n")
    return tmp_path


def test_run_registers_filesystem_tools_when_working_dir_set(monkeypatch, tmp_path):
    bdir = _make_boukensha_dir(tmp_path / "bdir")
    wdir = tmp_path / "wdir"
    wdir.mkdir()
    monkeypatch.setenv("BOUKENSHA_DIR", str(bdir))

    captured_registry = []

    def fake_agent_init(**kwargs):
        captured_registry.append(kwargs["registry"])
        m = MagicMock()
        m.run.return_value = "done"
        return m

    with patch("boukensha.Agent", side_effect=fake_agent_init):
        import boukensha
        boukensha.run(
            task="test",
            working_dir=str(wdir),
            log=f"{tmp_path}/test.jsonl",
        )

    registry = captured_registry[0]
    tool_names = set(registry._context.tools.keys())
    assert "pwd" in tool_names
    assert "list_directory" in tool_names
    assert "read_file" in tool_names
    assert "write_file" in tool_names
    assert "delete_file" in tool_names
    assert "search_files" in tool_names
    assert "run_command" in tool_names


def test_run_skips_tools_when_working_dir_false(monkeypatch, tmp_path):
    bdir = _make_boukensha_dir(tmp_path / "bdir")
    monkeypatch.setenv("BOUKENSHA_DIR", str(bdir))

    captured_registry = []

    def fake_agent_init(**kwargs):
        captured_registry.append(kwargs["registry"])
        m = MagicMock()
        m.run.return_value = "done"
        return m

    with patch("boukensha.Agent", side_effect=fake_agent_init):
        import boukensha
        boukensha.run(
            task="test",
            working_dir=False,
            log=f"{tmp_path}/test.jsonl",
        )

    registry = captured_registry[0]
    assert "pwd" not in registry._context.tools
    assert "run_command" not in registry._context.tools


def test_run_defaults_working_dir_to_cwd(monkeypatch, tmp_path):
    bdir = _make_boukensha_dir(tmp_path / "bdir")
    monkeypatch.setenv("BOUKENSHA_DIR", str(bdir))

    captured_ctx = []

    def fake_agent_init(**kwargs):
        captured_ctx.append(kwargs["context"])
        m = MagicMock()
        m.run.return_value = "done"
        return m

    with patch("boukensha.Agent", side_effect=fake_agent_init):
        import boukensha
        boukensha.run(task="test", log=f"{tmp_path}/test.jsonl")

    assert captured_ctx[0].working_dir == os.getcwd()


def test_tools_exported():
    import boukensha
    assert hasattr(boukensha, "tools")
    assert hasattr(boukensha.tools, "FileSystem")
    assert hasattr(boukensha.tools, "Shell")
```

- [ ] **Step 2: Run tests to verify they fail**

```bash
cd week1_baseline/python/10_standard_tool_library
uv run pytest tests/test_run_dsl.py -v -k "working_dir or tools_exported or skips_tools or defaults_working"
```

Expected: `TypeError: run() got an unexpected keyword argument 'working_dir'`

- [ ] **Step 3: Update `src/boukensha/__init__.py`**

Replace the existing import:
```python
from . import backends, tasks
```
with:
```python
from . import backends, tasks, tools
```

Add `"tools"` to `__all__`.

For `run()`, replace its current signature ending at `tool_registrar`:
```python
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
    tool_registrar: Callable[[RunDSL], None] | None = None,
) -> str:
```
with:
```python
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
    working_dir: str | bool | None = None,
    allowed_commands: list[str] | None = None,
    shell_timeout: int = 30,
    tool_registrar: Callable[[RunDSL], None] | None = None,
) -> str:
```

Inside `run()`, find:
```python
    ctx = Context(task=task_class, system=resolved_system)
    registry = Registry(ctx)

    if tool_registrar is not None:
        dsl = RunDSL(registry)
        tool_registrar(dsl)
```
Replace with:
```python
    resolved_wd: str | None
    if working_dir is None:
        resolved_wd = os.getcwd()
    elif not working_dir:
        resolved_wd = None
    else:
        resolved_wd = str(working_dir)

    ctx = Context(task=task_class, system=resolved_system, working_dir=resolved_wd)
    registry = Registry(ctx)

    if resolved_wd:
        tools.FileSystem.register(registry, working_dir=resolved_wd)
        tools.Shell.register(
            registry,
            working_dir=resolved_wd,
            timeout=shell_timeout,
            allowed_commands=allowed_commands,
        )

    if tool_registrar is not None:
        dsl = RunDSL(registry)
        tool_registrar(dsl)
```

Make the identical three changes to `repl()`:

Replace `repl()`'s current signature ending at `tool_registrar`:
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
```
with:
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
    working_dir: str | bool | None = None,
    allowed_commands: list[str] | None = None,
    shell_timeout: int = 30,
    tool_registrar: Callable[[RunDSL], None] | None = None,
) -> None:
```

Inside `repl()`, find:
```python
    ctx = Context(task=task_class, system=resolved_system)
    registry = Registry(ctx)

    if tool_registrar is not None:
        dsl = RunDSL(registry)
        tool_registrar(dsl)
```
Replace with:
```python
    resolved_wd: str | None
    if working_dir is None:
        resolved_wd = os.getcwd()
    elif not working_dir:
        resolved_wd = None
    else:
        resolved_wd = str(working_dir)

    ctx = Context(task=task_class, system=resolved_system, working_dir=resolved_wd)
    registry = Registry(ctx)

    if resolved_wd:
        tools.FileSystem.register(registry, working_dir=resolved_wd)
        tools.Shell.register(
            registry,
            working_dir=resolved_wd,
            timeout=shell_timeout,
            allowed_commands=allowed_commands,
        )

    if tool_registrar is not None:
        dsl = RunDSL(registry)
        tool_registrar(dsl)
```

- [ ] **Step 4: Run the full test suite**

```bash
uv run pytest tests/ -v
```

Expected: all tests PASS, including the four new ones.

- [ ] **Step 5: Commit**

```bash
git add src/boukensha/__init__.py tests/test_run_dsl.py
git commit -m "feat: wire working_dir/allowed_commands/shell_timeout into run() and repl() with auto-registration"
```

---

### Task 6: README and example script

**Files:**
- Modify: `week1_baseline/python/10_standard_tool_library/README.md`
- Modify: `week1_baseline/python/10_standard_tool_library/examples/example.py`

**Interfaces:**
- Produces: documentation describing the two new tool modules, their auto-registration behavior, and the three new kwargs on `run()`/`repl()`. The example script mirrors the Ruby `examples/example.rb`.

- [ ] **Step 1: Replace the README**

Replace `week1_baseline/python/10_standard_tool_library/README.md` with:

```markdown
# Step 10 — A Standard Tool Library

Boukensha now ships two built-in tool modules. Instead of manually registering tools, the framework gives the agent a standard library of capabilities out of the box when `working_dir` is set.

## What's new

### `boukensha.tools.FileSystem`

Registers automatically when `working_dir` is set:

| Tool | Description |
|------|-------------|
| `pwd` | Return the working directory |
| `list_directory` | List files at a path (default `.`) |
| `read_file` | Read a file's contents |
| `write_file` | Write (or create) a file |
| `delete_file` | Delete a file |
| `search_files` | Grep for a regex pattern across the working tree, returns `path:line:content` matches |

All paths are **relative to the working directory**. Absolute paths and `..` traversals that escape the root are rejected with an error string.

### `boukensha.tools.Shell`

Registers automatically when `working_dir` is set:

| Tool | Description |
|------|-------------|
| `run_command` | Run a shell command inside the working directory |

Commands run with a configurable timeout and an optional allow-list of permitted executables.

### New `boukensha.run` / `boukensha.repl` keyword arguments

```python
boukensha.run(
    task="...",
    working_dir="/my/project",          # None (default) = os.getcwd(); False = no tools
    allowed_commands=["python", "git"], # None = allow all (default)
    shell_timeout=30                    # seconds, default 30
)
```

`allowed_commands=None` permits any executable. Pass an explicit list to lock the agent down:

```python
# Only allow python and git — rm, curl, etc. will be rejected
boukensha.run(task="...", allowed_commands=["python", "git"])
```

### Direct registration

Both modules can be registered manually for finer control:

```python
from boukensha.tools import FileSystem, Shell

FileSystem.register(registry, working_dir="/my/project")
Shell.register(registry, working_dir="/my/project", timeout=10, allowed_commands=["python"])
```

## Run the example

```sh
cd week1_baseline/python/10_standard_tool_library
uv sync
uv run python examples/example.py

# or via the global executable pointed at this step:
BOUKENSHA_PATH=~/Sites/boukensha/python/10_standard_tool_library boukensha
```

## Running the tests

```sh
uv run pytest tests/ -v
```
```

- [ ] **Step 2: Replace the example script**

Replace `week1_baseline/python/10_standard_tool_library/examples/example.py` with:

```python
#!/usr/bin/env python
"""Step 10 — A Standard Tool Library demo.

Demonstrates auto-registration of FileSystem and Shell tools via working_dir.
"""

from __future__ import annotations

import os
from pathlib import Path

import sys
sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

os.environ.setdefault(
    "BOUKENSHA_DIR",
    str(Path(__file__).parent.parent.parent.parent.parent / ".boukensha"),
)

import boukensha

cfg = boukensha.Config()
print(f"Config: {cfg}")
print(f"API key set? {bool(os.environ.get('ANTHROPIC_API_KEY'))}")
print()

boukensha.run(
    task=(
        "List the files in the current working directory, read one of them, "
        "then tell me what you found."
    ),
    working_dir=str(Path(__file__).parent),
)
```

- [ ] **Step 3: Run the full test suite one final time**

```bash
cd week1_baseline/python/10_standard_tool_library
uv run pytest tests/ -v
```

Expected: all tests PASS.

- [ ] **Step 4: Commit**

```bash
git add README.md examples/example.py
git commit -m "docs: document standard tool library and update example script"
```

---

## Self-Review

### Spec coverage

| Requirement (from Ruby step 10 README / source) | Python equivalent | Task |
|---|---|---|
| `Tools::FileSystem` module with 6 tools | `boukensha/tools/file_system.py` `FileSystem.register()` | Task 3 |
| `Tools::Shell` module with `run_command` | `boukensha/tools/shell.py` `Shell.register()` | Task 4 |
| Auto-register both when `working_dir:` is set | `run()` and `repl()` auto-register when `resolved_wd` is truthy | Task 5 |
| `working_dir:` defaults to `Dir.pwd` / `os.getcwd()` | `None` → `os.getcwd()` sentinel pattern | Task 5 |
| `working_dir: false` to opt out | `False` → `resolved_wd = None` → skip registration | Task 5 |
| `allowed_commands:` allow-list | `Shell.register(..., allowed_commands=...)` first-token check | Task 4 |
| `shell_timeout:` configurable | `Shell.register(..., timeout=...)` passed to `subprocess.run` | Task 4 |
| Path traversal rejected at tool level | `_resolve()` checks absolute path starts with root | Task 3 |
| `search_files` with `pattern`, `path`, `glob` params | Identical three params, uses `re` + `glob.glob(recursive=True)` | Task 3 |
| `Tools::Mud` | **Out of scope** — depends on `mud_manager` Ruby gem; no Python equivalent | — |
| Direct registration API | `FileSystem.register(registry, working_dir=...)` static methods | Tasks 3–4 |
| README and example | `README.md` updated; `examples/example.py` updated | Task 6 |

### Placeholder scan

No "TBD"/"TODO"/"similar to Task N"/"add error handling" patterns — every step contains complete, runnable code.

### Type consistency

- `FileSystem.register(registry: Registry, *, working_dir: str) -> None` — called in Task 5 with `resolved_wd: str` (truthy guard ensures it) ✓
- `Shell.register(registry: Registry, *, working_dir: str, timeout: int = 30, allowed_commands: list[str] | None = None) -> None` — called in Task 5 with matching kwargs ✓
- `Context(task=..., system=..., working_dir=resolved_wd)` — `working_dir: str | None` added in Task 2; `resolved_wd` is `str | None` ✓
- `registry.tool(name, description, parameters, block=fn)` — all tools use the exact Python `Registry.tool()` signature (positional name/description/parameters, keyword-only `block`) ✓
- `registry.dispatch(name, args)` in tests — matches `Registry.dispatch(name: str, args: dict | None)` ✓
