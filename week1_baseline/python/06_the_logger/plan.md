# 06 The Logger — Python Port Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Port `Boukensha::Logger` from Ruby `week1_baseline/ruby/06_the_logger` to Python as a drop-in addition to the existing `week1_baseline/python/05_agent_loop` codebase.

**Architecture:** Copy the full `05_agent_loop` tree into a new `06_the_logger` directory, add a `Logger` class that writes structured JSONL session files, wire it into `Agent`, add `debug!`/`debug?` to the module level, and update the example script. All existing files are copied unchanged except `agent.py`, `__init__.py`, and the example.

**Tech Stack:** Python 3.11+, `uv`, `pytest`, standard-library `json`, `pathlib`, `uuid`, `datetime` — no new third-party dependencies.

## Global Constraints

- Python 3.11+ (`requires-python = ">=3.11"` in pyproject.toml)
- Package managed with `uv` + `hatchling`; run tests with `uv run pytest`
- No new third-party dependencies — use only the stdlib (`json`, `pathlib`, `uuid`, `datetime`) plus what is already in `pyproject.toml`
- All source lives under `src/boukensha/`; tests under `tests/`
- Follow existing conventions: `from __future__ import annotations`, `_private` names, keyword-only constructor args with `*`
- Logger is a **file logger only** — it writes JSONL; it is not user-facing display output
- Every log line must contain `session_id` and `at` (ISO-8601) fields in addition to phase-specific data
- `raw()` must be a no-op unless `boukensha.debug()` returns `True`
- Session files default to `<boukensha_dir>/sessions/<session_id>.jsonl`
- `session_id` format: `YYYYMMDDTHHMMSSZ-<8 hex chars>` (UTC)
- Agent gets a default `Logger()` if none provided; existing behavior is unchanged when no logger is given (i.e. the print statements stay, they are not replaced)

---

## File Structure

| Path (relative to `week1_baseline/python/06_the_logger/`) | Action | Responsibility |
|---|---|---|
| `src/boukensha/logger.py` | **Create** | `Logger` class — JSONL session writer |
| `src/boukensha/__init__.py` | **Modify** | add `Logger`, `debug()`, `enable_debug()` exports; add module-level debug flag |
| `src/boukensha/agent.py` | **Modify** | accept optional `logger:` kwarg; call logger methods at each lifecycle point |
| `examples/example.py` | **Modify** | construct `Logger`, pass to `Agent`, print session path, update banner |
| `tests/test_logger.py` | **Create** | unit tests for `Logger` |
| `tests/test_agent.py` | **Modify** | extend existing agent tests to cover logger call sites |

Everything else (`backends/`, `client.py`, `config.py`, `context.py`, `errors.py`, `message.py`, `prompt_builder.py`, `registry.py`, `tasks/`, `tool.py`, `pyproject.toml`, `prompts/`) is copied verbatim from `05_agent_loop` — no changes.

---

## Task 1: Scaffold the 06_the_logger directory

Copy the entire `05_agent_loop` tree into `06_the_logger` and adjust the pyproject description/name. The copy is the baseline; every subsequent task modifies files inside `06_the_logger`.

**Files:**
- Create: `week1_baseline/python/06_the_logger/` (directory tree)
- Modify: `week1_baseline/python/06_the_logger/pyproject.toml`

**Interfaces:**
- Produces: a runnable Python package at `week1_baseline/python/06_the_logger/` with all `05_agent_loop` tests passing

- [ ] **Step 1: Copy the tree**

```bash
cp -r week1_baseline/python/05_agent_loop/. week1_baseline/python/06_the_logger/
```

Expected: no errors; the `plan.md` file already exists in `06_the_logger/` so this will overwrite it with the `05_agent_loop` plan — that is intentional, it will be replaced by this plan's output.

- [ ] **Step 2: Re-write plan.md with the current file content**

The copy above will overwrite `plan.md` with the 05 plan. Put this plan back:

```bash
# The plan.md you are reading right now — copy it back into place.
# If you are executing this plan, copy this file's content back to
# week1_baseline/python/06_the_logger/plan.md before proceeding.
```

- [ ] **Step 3: Update pyproject.toml description**

In `week1_baseline/python/06_the_logger/pyproject.toml`, change:

```toml
description = "Boukensha agent loop (Step 5)"
```

to:

```toml
description = "Boukensha logger (Step 6)"
```

- [ ] **Step 4: Install dependencies and run existing tests**

```bash
cd week1_baseline/python/06_the_logger
uv sync
uv run pytest tests/ -v
```

Expected: all existing `05_agent_loop` tests pass (green). If any fail, investigate before continuing.

- [ ] **Step 5: Commit**

```bash
git add week1_baseline/python/06_the_logger/
git commit -m "feat: scaffold 06_the_logger from 05_agent_loop"
```

---

## Task 2-5: Additional tasks

Tasks 2-5 are defined in the full plan below, but Task 1 is the focus for this session.

