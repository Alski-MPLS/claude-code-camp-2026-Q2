# The Global Executable Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Port the Ruby `09_global_executable` step to Python by packaging BOUKENSHA as an installable distribution with a `boukensha` console command that can be run from anywhere, while leaving the step-08 library code untouched underneath.

**Architecture:** Ruby ships a gem containing `bin/boukensha` (a shebang script) plus `lib/boukensha_loader.rb` — a file *outside* the `Boukensha` module that resolves which step's `lib/boukensha.rb` to load (via `BOUKENSHA_PATH`, `~/.boukensharc`, or the bundled copy) and then boots its REPL. Python has no shebang-script equivalent of a gem executable; the idiomatic replacement is a `[project.scripts]` console-script entry point that pip/uv materializes into a real executable at install time. This step therefore adds a new **top-level module** `boukensha_loader.py` (a sibling of the `boukensha` package, not part of it — exactly mirroring the Ruby file layout) that performs the same three-tier resolution, dynamically imports whichever `boukensha` package it resolved to, and calls its `repl()`. The `boukensha` package itself (copied from step 08) is unchanged; it is simply *one of the things* `boukensha_loader.py` can load.

**Tech Stack:** Python ≥ 3.11, `uv`, `hatchling`, `pytest`, `pyyaml`, `python-dotenv`. No new third-party runtime dependencies. Verified experimentally (see Task 4) that hatchling's `sources = ["src"]` + `include = [...]` build config correctly packages a lone top-level module alongside the `boukensha/` package in the same wheel, and that `uv run <console-script-name>` invokes it.

## Global Constraints

- All source lives under `week1_baseline/python/09_global_executable/` — never modify step 08.
- Package layout matches step 08's `src/boukensha/` package, plus a new top-level `src/boukensha_loader.py` module (not inside the `boukensha/` package).
- `pyproject.toml` name field: `"boukensha-global-executable"`, version stays `"0.1.0"` — every prior Python step (00 through 08) kept `__version__`/`version` at `0.1.0` regardless of Ruby's per-step version bumps (0.8.0 → 0.9.0); don't deviate from that established Python-side convention.
- No `bin/` directory and no gemspec-equivalent file — `[project.scripts]` in `pyproject.toml` is the direct, idiomatic replacement for `bin/boukensha` + `spec.executables`.
- Do not port the ruby step 08→09 diffs to `client.rb`/`config.rb`/`repl.rb` (removed 401 handling, simplified banner, simplified config-dir resolution) — those are unrelated drift in the Ruby tree, not part of the "global executable" feature. The Python `config.py`/`repl.py`/`client.py` inherited from step 08 are already more complete than Ruby's step-09 versions; keep them as-is.
- Tests run with `pytest` from the step directory (`uv run pytest tests/ -v`).
- Follow step 08 naming/style: snake_case, `from __future__ import annotations`, type hints on all public APIs, no inline comments unless explaining a non-obvious constraint.

---

### Task 1: Scaffold step 09 from step 08

**Files:**
- Create: `week1_baseline/python/09_global_executable/` (whole tree, copied from step 08)
- Create: `week1_baseline/python/09_global_executable/pyproject.toml`
- Create: `week1_baseline/python/09_global_executable/src/boukensha/**` (all files from step 08's `src/boukensha/`)
- Create: `week1_baseline/python/09_global_executable/prompts/system.md`
- Create: `week1_baseline/python/09_global_executable/examples/example.py`
- Create: `week1_baseline/python/09_global_executable/tests/**` (all files from step 08's `tests/`)

**Interfaces:**
- Produces: a working copy of the step 08 package, installed in its own venv at `week1_baseline/python/09_global_executable/.venv/`, with `pytest` passing before any new code is added.

- [ ] **Step 1: Copy all source files from step 08 to step 09**

```bash
SRC=week1_baseline/python/08_the_repl_loop
DST=week1_baseline/python/09_global_executable
cp -r "$SRC/src" "$DST/"
cp -r "$SRC/tests" "$DST/"
cp -r "$SRC/prompts" "$DST/"
cp -r "$SRC/examples" "$DST/"
cp "$SRC/pyproject.toml" "$DST/"
cp "$SRC/.gitignore" "$DST/" 2>/dev/null || true
find "$DST" -name "__pycache__" -type d -exec rm -rf {} +
```

- [ ] **Step 2: Update `pyproject.toml` name and description**

Edit `week1_baseline/python/09_global_executable/pyproject.toml` — change:
```toml
name = "boukensha-repl-loop"
description = "Boukensha REPL loop (Step 8)"
```
to:
```toml
name = "boukensha-global-executable"
description = "Boukensha global executable (Step 9)"
```

- [ ] **Step 3: Install the package and verify baseline tests pass**

```bash
cd week1_baseline/python/09_global_executable
uv sync
uv run pytest tests/ -v
```

Expected: all existing tests pass (same count as step 08 — 08 has `test_agent.py`, `test_context.py`, `test_logger.py`, `test_quiet.py`, `test_repl.py`, `test_run_dsl.py`).

- [ ] **Step 4: Commit the scaffold**

```bash
git add week1_baseline/python/09_global_executable/
git commit -m "feat: scaffold step 09 from step 08 baseline"
```

---

### Task 2: `boukensha_loader.resolve()` — three-tier path resolution

**Files:**
- Create: `week1_baseline/python/09_global_executable/src/boukensha_loader.py`
- Create: `week1_baseline/python/09_global_executable/tests/test_boukensha_loader.py`

**Interfaces:**
- Produces:
  - `boukensha_loader.BUNDLED_SRC_DIR: str` — absolute path to this module's own `src/` directory (the directory containing `boukensha_loader.py` and the bundled `boukensha/` package)
  - `boukensha_loader.resolve() -> str` — returns the `src/` directory containing the `boukensha` package to load, checked in this order:
    1. `BOUKENSHA_PATH` env var — treated as a *step folder*; looks for `{BOUKENSHA_PATH}/src/boukensha/__init__.py`. Raises `SystemExit` with a helpful message if set but the package isn't found there.
    2. `~/.boukensharc` — a file containing a single step-folder path (same resolution/error behavior as above).
    3. `BUNDLED_SRC_DIR` (the default, when neither of the above apply).

- [ ] **Step 1: Write the failing tests**

Create `week1_baseline/python/09_global_executable/tests/test_boukensha_loader.py`:

```python
from __future__ import annotations

from pathlib import Path

import pytest

import boukensha_loader


def _make_step_dir(tmp_path: Path, *, with_package: bool = True) -> Path:
    step_dir = tmp_path / "some_step"
    pkg_dir = step_dir / "src" / "boukensha"
    pkg_dir.mkdir(parents=True)
    if with_package:
        (pkg_dir / "__init__.py").write_text("MARKER = 'fake-step'\n")
    return step_dir


def test_resolve_defaults_to_bundled_src_dir(monkeypatch, tmp_path):
    monkeypatch.delenv("BOUKENSHA_PATH", raising=False)
    monkeypatch.setattr(boukensha_loader.Path, "home", lambda: tmp_path)
    assert boukensha_loader.resolve() == boukensha_loader.BUNDLED_SRC_DIR


def test_resolve_uses_boukensha_path_env_var(monkeypatch, tmp_path):
    step_dir = _make_step_dir(tmp_path)
    monkeypatch.setenv("BOUKENSHA_PATH", str(step_dir))
    assert boukensha_loader.resolve() == str(step_dir / "src")


def test_resolve_boukensha_path_missing_package_aborts(monkeypatch, tmp_path):
    step_dir = _make_step_dir(tmp_path, with_package=False)
    monkeypatch.setenv("BOUKENSHA_PATH", str(step_dir))
    with pytest.raises(SystemExit, match="BOUKENSHA_PATH is set"):
        boukensha_loader.resolve()


def test_resolve_uses_boukensharc_file(monkeypatch, tmp_path):
    monkeypatch.delenv("BOUKENSHA_PATH", raising=False)
    step_dir = _make_step_dir(tmp_path)
    fake_home = tmp_path / "home"
    fake_home.mkdir()
    (fake_home / ".boukensharc").write_text(f"{step_dir}\n")
    monkeypatch.setattr(boukensha_loader.Path, "home", lambda: fake_home)
    assert boukensha_loader.resolve() == str(step_dir / "src")


def test_resolve_boukensharc_missing_package_aborts(monkeypatch, tmp_path):
    step_dir = _make_step_dir(tmp_path, with_package=False)
    fake_home = tmp_path / "home"
    fake_home.mkdir()
    (fake_home / ".boukensharc").write_text(f"{step_dir}\n")
    monkeypatch.delenv("BOUKENSHA_PATH", raising=False)
    monkeypatch.setattr(boukensha_loader.Path, "home", lambda: fake_home)
    with pytest.raises(SystemExit, match=r"\.boukensharc points to"):
        boukensha_loader.resolve()


def test_resolve_env_var_wins_over_boukensharc(monkeypatch, tmp_path):
    env_step = _make_step_dir(tmp_path)
    (env_step / "src" / "boukensha" / "__init__.py").write_text("MARKER = 'env'\n")

    rc_step_dir = tmp_path / "rc_step"
    rc_pkg = rc_step_dir / "src" / "boukensha"
    rc_pkg.mkdir(parents=True)
    (rc_pkg / "__init__.py").write_text("MARKER = 'rc'\n")

    fake_home = tmp_path / "home"
    fake_home.mkdir()
    (fake_home / ".boukensharc").write_text(f"{rc_step_dir}\n")
    monkeypatch.setattr(boukensha_loader.Path, "home", lambda: fake_home)
    monkeypatch.setenv("BOUKENSHA_PATH", str(env_step))

    assert boukensha_loader.resolve() == str(env_step / "src")


def test_resolve_blank_boukensharc_falls_through_to_bundled(monkeypatch, tmp_path):
    monkeypatch.delenv("BOUKENSHA_PATH", raising=False)
    fake_home = tmp_path / "home"
    fake_home.mkdir()
    (fake_home / ".boukensharc").write_text("   \n")
    monkeypatch.setattr(boukensha_loader.Path, "home", lambda: fake_home)
    assert boukensha_loader.resolve() == boukensha_loader.BUNDLED_SRC_DIR
```

- [ ] **Step 2: Run tests to confirm they fail**

```bash
cd week1_baseline/python/09_global_executable
uv run pytest tests/test_boukensha_loader.py -v
```

Expected: `ModuleNotFoundError: No module named 'boukensha_loader'`

- [ ] **Step 3: Create `boukensha_loader.py`**

Create `week1_baseline/python/09_global_executable/src/boukensha_loader.py`:

```python
"""Resolves which step folder's ``boukensha`` package to load, then boots its REPL.

This module lives *outside* the ``boukensha`` package on purpose — it is the
piece that decides which ``boukensha`` gets imported, so it can't itself be
part of the thing it's choosing between.

Resolution order:
  1. BOUKENSHA_PATH environment variable (selects which *step* src/boukensha to load)
  2. ~/.boukensharc  (a file containing a single step-folder path)
  3. The src/boukensha bundled inside this installed distribution (the latest step)

Config directory (settings.yaml, .env, system.md) is separate:
  BOUKENSHA_DIR=~/.boukensha  (default, set in env to override)

Examples:
  boukensha                                                              # uses bundled lib + ~/.boukensha
  BOUKENSHA_PATH=~/Sites/boukensha/04_api_client boukensha                # loads step 4
  BOUKENSHA_DIR=~/projects/mybot/.boukensha boukensha                    # custom config dir
  echo ~/Sites/boukensha/09_global_executable > ~/.boukensharc && boukensha  # permanent step default
"""

from __future__ import annotations

import os
import sys
from pathlib import Path

# Absolute path to this distribution's own bundled src/ directory.
BUNDLED_SRC_DIR = str(Path(__file__).parent)


def _src_dir_for(step_dir: Path) -> str:
    return str(step_dir / "src")


def _has_package(src_dir: str) -> bool:
    return (Path(src_dir) / "boukensha" / "__init__.py").is_file()


def resolve() -> str:
    """Return the src/ directory containing the ``boukensha`` package to load."""
    path_env = os.environ.get("BOUKENSHA_PATH")
    if path_env:
        step_dir = Path(path_env).expanduser().resolve()
        src_dir = _src_dir_for(step_dir)
        if _has_package(src_dir):
            return src_dir
        raise SystemExit(
            "boukensha: BOUKENSHA_PATH is set but no src/boukensha/__init__.py found at:\n"
            f"       {step_dir}\n"
            "       Make sure BOUKENSHA_PATH points to a step folder, e.g.:\n"
            "       BOUKENSHA_PATH=~/Sites/boukensha/08_the_repl_loop boukensha"
        )

    rc_file = Path.home() / ".boukensharc"
    if rc_file.is_file():
        rc_value = rc_file.read_text().strip()
        if rc_value:
            step_dir = Path(rc_value).expanduser().resolve()
            src_dir = _src_dir_for(step_dir)
            if _has_package(src_dir):
                return src_dir
            raise SystemExit(
                f"boukensha: ~/.boukensharc points to {step_dir}\n"
                "       but no src/boukensha/__init__.py was found there.\n"
                "       Update ~/.boukensharc or remove it to use the bundled default."
            )

    return BUNDLED_SRC_DIR
```

- [ ] **Step 4: Run tests to confirm they pass**

```bash
uv run pytest tests/test_boukensha_loader.py -v
```

Expected: all 7 tests PASS.

- [ ] **Step 5: Commit**

```bash
git add src/boukensha_loader.py tests/test_boukensha_loader.py
git commit -m "feat: add boukensha_loader.resolve() for BOUKENSHA_PATH/.boukensharc/bundled resolution"
```

---

### Task 3: `boukensha_loader.load_and_start_repl()` / `main()`

**Files:**
- Modify: `week1_baseline/python/09_global_executable/src/boukensha_loader.py`
- Modify: `week1_baseline/python/09_global_executable/tests/test_boukensha_loader.py`

**Interfaces:**
- Consumes: `boukensha_loader.resolve() -> str` (Task 2)
- Produces:
  - `boukensha_loader.load_and_start_repl() -> None` — resolves a src dir, prints a `[boukensha] loading from: <step_dir>` line to stdout when `BOUKENSHA_DEBUG` is set, inserts the src dir at the front of `sys.path`, imports `boukensha` fresh, and calls `boukensha.repl()`. Raises `SystemExit` with a helpful message if the resolved package has no `repl` attribute (i.e. it's a pre-step-08 package).
  - `boukensha_loader.main() -> None` — console-script entry point; calls `load_and_start_repl()`.

- [ ] **Step 1: Write the failing tests**

Add to the bottom of `tests/test_boukensha_loader.py`:

```python
import sys
from unittest.mock import MagicMock


def _install_fake_boukensha(monkeypatch, tmp_path, *, with_repl: bool) -> Path:
    step_dir = tmp_path / "fake_step"
    pkg_dir = step_dir / "src" / "boukensha"
    pkg_dir.mkdir(parents=True)
    body = "REPL_CALLS = []\n"
    if with_repl:
        body += "def repl():\n    REPL_CALLS.append(1)\n"
    (pkg_dir / "__init__.py").write_text(body)
    monkeypatch.setenv("BOUKENSHA_PATH", str(step_dir))
    return step_dir


def _clear_boukensha_modules():
    for name in [m for m in list(sys.modules) if m == "boukensha" or m.startswith("boukensha.")]:
        del sys.modules[name]


def test_load_and_start_repl_calls_repl(monkeypatch, tmp_path):
    _clear_boukensha_modules()
    _install_fake_boukensha(monkeypatch, tmp_path, with_repl=True)
    monkeypatch.delenv("BOUKENSHA_DEBUG", raising=False)

    boukensha_loader.load_and_start_repl()

    import boukensha
    assert boukensha.REPL_CALLS == [1]
    _clear_boukensha_modules()


def test_load_and_start_repl_aborts_without_repl_support(monkeypatch, tmp_path, capsys):
    _clear_boukensha_modules()
    step_dir = _install_fake_boukensha(monkeypatch, tmp_path, with_repl=False)
    monkeypatch.delenv("BOUKENSHA_DEBUG", raising=False)

    with pytest.raises(SystemExit, match="does not support the interactive REPL"):
        boukensha_loader.load_and_start_repl()

    _clear_boukensha_modules()


def test_load_and_start_repl_prints_debug_line(monkeypatch, tmp_path, capsys):
    _clear_boukensha_modules()
    step_dir = _install_fake_boukensha(monkeypatch, tmp_path, with_repl=True)
    monkeypatch.setenv("BOUKENSHA_DEBUG", "1")

    boukensha_loader.load_and_start_repl()

    captured = capsys.readouterr()
    assert f"[boukensha] loading from: {step_dir}" in captured.out
    _clear_boukensha_modules()


def test_main_delegates_to_load_and_start_repl(monkeypatch):
    called = []
    monkeypatch.setattr(boukensha_loader, "load_and_start_repl", lambda: called.append(1))
    boukensha_loader.main()
    assert called == [1]
```

- [ ] **Step 2: Run tests to confirm they fail**

```bash
uv run pytest tests/test_boukensha_loader.py -v -k "load_and_start_repl or main_delegates"
```

Expected: `AttributeError: module 'boukensha_loader' has no attribute 'load_and_start_repl'`

- [ ] **Step 3: Add `load_and_start_repl()` and `main()` to `boukensha_loader.py`**

Append to `src/boukensha_loader.py`:

```python
def load_and_start_repl() -> None:
    src_dir = resolve()
    step_dir = str(Path(src_dir).parent)

    if os.environ.get("BOUKENSHA_DEBUG"):
        print(f"[boukensha] loading from: {step_dir}")

    for name in [m for m in list(sys.modules) if m == "boukensha" or m.startswith("boukensha.")]:
        del sys.modules[name]
    sys.path.insert(0, src_dir)

    import boukensha

    if not hasattr(boukensha, "repl"):
        raise SystemExit(
            f"boukensha: the step at {step_dir}\n"
            "       does not support the interactive REPL (added in step 08).\n"
            "       Run its examples directly, e.g.:\n"
            f"         python {step_dir}/examples/*.py\n"
            "       Or point BOUKENSHA_PATH at step 08 or later."
        )

    boukensha.repl()


def main() -> None:
    load_and_start_repl()
```

- [ ] **Step 4: Run all tests**

```bash
uv run pytest tests/ -v
```

Expected: all tests pass, including the new `boukensha_loader` tests.

- [ ] **Step 5: Commit**

```bash
git add src/boukensha_loader.py tests/test_boukensha_loader.py
git commit -m "feat: add boukensha_loader.load_and_start_repl()/main() to boot the resolved step's REPL"
```

---

### Task 4: Wire up the `boukensha` console script in `pyproject.toml`

**Files:**
- Modify: `week1_baseline/python/09_global_executable/pyproject.toml`

**Interfaces:**
- Produces: after `uv sync`, `uv run boukensha` (and, once installed as a tool, a bare `boukensha` on `$PATH`) resolves and boots the bundled step's REPL.

This exact `sources`/`include` combination was verified experimentally before writing this plan: a scratch hatchling project with a top-level `boukensha_loader.py` module plus a `boukensha/` package, built with `uv build`, produced a wheel containing both `boukensha_loader.py` and `boukensha/__init__.py` at the wheel root, and `uv run boukensha` (via an editable install) executed the entry point correctly.

- [ ] **Step 1: Add `[project.scripts]` and the wheel build config**

Edit `week1_baseline/python/09_global_executable/pyproject.toml`. It currently ends with:

```toml
[tool.hatch.build.targets.wheel]
packages = ["src/boukensha"]
```

Replace that final section with:

```toml
[project.scripts]
boukensha = "boukensha_loader:main"

[tool.hatch.build.targets.wheel]
sources = ["src"]
include = ["src/boukensha/**", "src/boukensha_loader.py"]
```

(Leave everything above `[build-system]` — `[project]`, `[dependency-groups]`, `[tool.uv]` — untouched aside from the name/description already changed in Task 1.)

- [ ] **Step 2: Re-sync and verify the console script exists**

```bash
cd week1_baseline/python/09_global_executable
uv sync
ls .venv/bin/boukensha
```

Expected: the file exists and is executable.

- [ ] **Step 3: Run the console script against the bundled default**

```bash
echo "/exit" | BOUKENSHA_DIR=/tmp/boukensha-smoke-test uv run boukensha
```

Expected: prints the `BOUKENSHA MUD Assistant` banner, then `Goodbye.` on `/exit`. (Provider will show whatever `settings.yaml` defaults to; that's fine — this just proves the console script boots the bundled REPL end-to-end.)

- [ ] **Step 4: Run the full test suite**

```bash
uv run pytest tests/ -v
```

Expected: all tests still pass (this task only touches `pyproject.toml`).

- [ ] **Step 5: Commit**

```bash
git add pyproject.toml
git commit -m "feat: wire up boukensha console script via boukensha_loader:main"
```

---

### Task 5: `BOUKENSHA_PATH` and `BOUKENSHA_DEBUG` end-to-end smoke test

**Files:**
- Create: `week1_baseline/python/09_global_executable/tests/test_console_script.py`

**Interfaces:**
- Consumes: the installed `boukensha` console script (Task 4) and `BOUKENSHA_PATH` (Task 2/3)
- Produces: a subprocess-level test proving the *installed executable* — not just the Python functions — correctly switches steps and reports debug info. This is the one test in the suite that exercises the real console-script wrapper rather than calling `boukensha_loader` functions directly.

- [ ] **Step 1: Write the test**

Create `week1_baseline/python/09_global_executable/tests/test_console_script.py`:

```python
from __future__ import annotations

import os
import subprocess
import sys
from pathlib import Path

STEP_DIR = Path(__file__).parent.parent


def _run_console_script(*, env_overrides: dict[str, str], stdin_text: str = "/exit\n") -> subprocess.CompletedProcess:
    boukensha_bin = STEP_DIR / ".venv" / "bin" / "boukensha"
    env = {**os.environ, **env_overrides}
    return subprocess.run(
        [str(boukensha_bin)],
        input=stdin_text,
        env=env,
        capture_output=True,
        text=True,
        timeout=30,
    )


def test_console_script_boots_bundled_default(tmp_path):
    result = _run_console_script(env_overrides={"BOUKENSHA_DIR": str(tmp_path)})
    assert "BOUKENSHA MUD Assistant" in result.stdout
    assert "Goodbye." in result.stdout


def test_console_script_debug_flag_reports_bundled_path(tmp_path):
    result = _run_console_script(
        env_overrides={"BOUKENSHA_DIR": str(tmp_path), "BOUKENSHA_DEBUG": "1"},
    )
    assert "[boukensha] loading from:" in result.stdout
    assert str(STEP_DIR / "src") in result.stdout


def test_console_script_boukensha_path_missing_package_errors(tmp_path):
    missing_step = tmp_path / "not_a_step"
    result = _run_console_script(
        env_overrides={"BOUKENSHA_DIR": str(tmp_path), "BOUKENSHA_PATH": str(missing_step)},
    )
    assert result.returncode != 0
    assert "BOUKENSHA_PATH is set" in result.stderr
```

- [ ] **Step 2: Run the test to confirm it fails first, then passes**

```bash
cd week1_baseline/python/09_global_executable
uv run pytest tests/test_console_script.py -v
```

Expected: PASS on first run if Task 4 is complete (no red/green cycle needed here — this test exercises the already-built console script rather than driving new implementation).

- [ ] **Step 3: Run the full test suite one final time**

```bash
uv run pytest tests/ -v
```

Expected: all tests pass.

- [ ] **Step 4: Commit**

```bash
git add tests/test_console_script.py
git commit -m "test: add subprocess-level smoke tests for the installed boukensha console script"
```

---

### Task 6: README

**Files:**
- Modify: `week1_baseline/python/09_global_executable/README.md`

**Interfaces:**
- Produces: documentation matching the style of step 08's README, describing install, `BOUKENSHA_PATH`/`~/.boukensharc` resolution, and debug mode.

- [ ] **Step 1: Replace the README contents**

Replace `week1_baseline/python/09_global_executable/README.md` with:

```markdown
# Step 9 — Global Executable

Package BOUKENSHA as an installable distribution so the `boukensha` command works from anywhere on your machine.

## What this step adds

- `[project.scripts]` in `pyproject.toml` — declares the `boukensha` console-script entry point, pointing at `boukensha_loader:main`
- `src/boukensha_loader.py` — resolves *which step folder* to load from, then boots the REPL
- `src/boukensha/` — step 8's package, bundled as the default

## Install

```bash
cd 09_global_executable
uv tool install --editable .
```

After that, `boukensha` is on your `$PATH` and works from any directory. (Prefer to try it without a global install first? `uv run boukensha` from this directory does the same thing.)

## Switching steps with BOUKENSHA_PATH

The loader resolves in this order:

| Priority | Source | Example |
|----------|--------|---------|
| 1 | `BOUKENSHA_PATH` env var | `BOUKENSHA_PATH=~/Sites/boukensha/python/08_the_repl_loop boukensha` |
| 2 | `~/.boukensharc` file | `echo ~/Sites/boukensha/python/08_the_repl_loop > ~/.boukensharc` |
| 3 | Bundled default | just run `boukensha` |

`BOUKENSHA_PATH` must point to a step folder that contains `src/boukensha/__init__.py`.

## Running a specific step

```bash
# step 8 (interactive REPL)
BOUKENSHA_PATH=~/Sites/boukensha/python/08_the_repl_loop boukensha

# step 7 doesn't have a REPL — the loader tells you how to run it instead
BOUKENSHA_PATH=~/Sites/boukensha/python/07_the_run_dsl boukensha
# => boukensha: the step at .../07_the_run_dsl does not support the interactive REPL
#    Run its examples directly, e.g.: python .../07_the_run_dsl/examples/*.py
```

## Debug mode

```bash
BOUKENSHA_DEBUG=1 boukensha
# => [boukensha] loading from: /path/to/step/src
```

## The key idea

The distribution is just a **wrapper and a default**. All the teaching material stays in the numbered step folders exactly as it was. `boukensha_loader.py` doesn't copy or symlink anything — it just knows where to look, and dynamically imports whichever `boukensha` package it finds there.

## Running the tests

```sh
cd week1_baseline/python/09_global_executable
uv sync --group dev
uv run pytest tests/ -v
```
```

- [ ] **Step 2: Commit**

```bash
git add README.md
git commit -m "docs: document the boukensha console script and BOUKENSHA_PATH resolution"
```

---

## Self-Review

### Spec coverage

| Requirement (from Ruby step 09 README / source) | Python equivalent | Task |
|---|---|---|
| Gem packaging (`boukensha.gemspec`) | `pyproject.toml` `[project.scripts]` + hatchling wheel config | Task 4 |
| `bin/boukensha` shebang script | Console-script entry point (`boukensha_loader:main`) generated by pip/uv — no separate file needed | Task 4 |
| `lib/boukensha_loader.rb` resolution order (env var → rc file → bundled) | `boukensha_loader.resolve()` | Task 2 |
| Loader boots the REPL / aborts with a helpful message if unsupported | `boukensha_loader.load_and_start_repl()` | Task 3 |
| `BOUKENSHA_DEBUG` prints the loaded path | `load_and_start_repl()` debug branch | Task 3 |
| `lib/boukensha.rb` + `lib/boukensha/` bundled as default | step 08's `src/boukensha/` copied in unchanged | Task 1 |
| README covering install / BOUKENSHA_PATH / debug mode | README.md | Task 6 |
| End-to-end verification the real installed executable works | subprocess smoke tests | Task 5 |

All requirements covered. Ruby step 08→09's unrelated regressions to `client.rb`/`config.rb`/`repl.rb` are explicitly excluded per Global Constraints — confirmed by diffing `ruby/08_the_repl_loop` against `ruby/09_global_executable` and cross-checking that Python's step-08 versions of those files are already the more feature-complete baseline.

### Type consistency

- `boukensha_loader.resolve() -> str` returns a `src/` dir path — consumed identically by `load_and_start_repl()` (Task 3) and every test in Task 2/3 ✓
- `boukensha_loader.BUNDLED_SRC_DIR` referenced in both `resolve()` and its tests ✓
- `boukensha_loader.main()` has no arguments, matching the `[project.scripts]` entry point calling convention (`module:function`, invoked with no args) ✓
- `boukensha.repl()` (from step 08, untouched) is what `load_and_start_repl()` calls — signature `repl() -> None`, matches step 08's `src/boukensha/__init__.py` ✓

### Placeholder scan

No "TBD"/"add error handling"/"similar to Task N" placeholders — every step has complete code or exact commands with expected output.
