# Explore Directional Door Fix Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** `explore`'s closed-door retry sends `"open door <direction>"` (the MUD's actual accepted syntax) instead of `"open <direction>"`, so a closed-but-unlocked door no longer gets wrongly marked as a permanently blocked exit.

**Architecture:** One-line fix in `src/boukensha/tools/exploration.py`'s `_explore` function, plus updating the one existing test whose expected command sequence encodes the old (wrong) wire format.

**Tech Stack:** Python 3, pytest, `unittest.mock.MagicMock` for session mocking (no live MUD server in tests).

## Global Constraints

- No change to `src/boukensha/tools/mud.py`'s `_door` — already fixed in a prior task.
- No new tests — the existing two door-retry tests in `tests/test_exploration_tool.py` already exercise this code path end to end; only their expected command strings change where they encode the old format.
- `direction` at `exploration.py:180` is always a real compass direction sourced from a room's own recorded exits (via `_nearest_frontier`) — no `_DIRECTIONS` membership check is needed here (unlike `mud.py`'s `_door`, whose `target` can also be a non-direction container name).

---

### Task 1: Fix the door-open command in `explore`'s retry logic

**Files:**
- Modify: `src/boukensha/tools/exploration.py:180`
- Modify: `tests/test_exploration_tool.py:104` (`test_explore_opens_closed_door_and_retries`'s expected `sent` list)

**Interfaces:**
- Consumes: nothing new — `direction: str` is already a local variable in `_explore` (bound at `exploration.py:118`, `route, frontier_hash, direction = found`).
- Produces: no new functions or parameters — only the literal command string sent to `session.send_command` changes.

- [ ] **Step 1: Write the failing test**

In `tests/test_exploration_tool.py`, update `test_explore_opens_closed_door_and_retries`'s final assertion (currently line 104):

```python
    assert sent == ["look", "look south", "south", "look", "open door south", "south", "look"]
```

(Replacing the current `"open south"` entry with `"open door south"` — this is the only line in this test that changes; everything else in the test stays as-is.)

- [ ] **Step 2: Run the test to verify it fails**

Run: `cd /Users/alanw/code/github/ai/claude-code-camp-2026-Q2/week2_capable/agent-exp && .venv/bin/python -m pytest tests/test_exploration_tool.py::test_explore_opens_closed_door_and_retries -v`

Expected: FAIL — `assert ['look', 'look south', 'south', 'look', 'open south', 'south', 'look'] == ['look', 'look south', 'south', 'look', 'open door south', 'south', 'look']` (current code still sends `"open south"`).

- [ ] **Step 3: Implement the fix**

In `src/boukensha/tools/exploration.py`, change line 180 from:

```python
            session.send_command(f"open {direction}")
```

to:

```python
            session.send_command(f"open door {direction}")
```

- [ ] **Step 4: Run the test to verify it passes**

Run: `cd /Users/alanw/code/github/ai/claude-code-camp-2026-Q2/week2_capable/agent-exp && .venv/bin/python -m pytest tests/test_exploration_tool.py::test_explore_opens_closed_door_and_retries -v`

Expected: PASS.

- [ ] **Step 5: Run the full exploration test file, then the full suite, to check for regressions**

Run: `cd /Users/alanw/code/github/ai/claude-code-camp-2026-Q2/week2_capable/agent-exp && .venv/bin/python -m pytest tests/test_exploration_tool.py -v`

Expected: all tests in the file PASS, including `test_explore_marks_exit_blocked_when_still_stuck_after_opening` (this test does not assert the exact `sent` list, so it is unaffected by the wire-format change, but must still pass since it exercises the same code path).

Run: `cd /Users/alanw/code/github/ai/claude-code-camp-2026-Q2/week2_capable/agent-exp && .venv/bin/python -m pytest tests/ -v`

Expected: 370 passed (same as the prior plan's final state), 4 pre-existing failures in `tests/test_room_parser.py` (unrelated to this change) — no new failures.

Note: use the venv's python binary directly (`.venv/bin/python`), not `source .venv/bin/activate` — Bash tool shell state does not persist activation across separate command invocations, so `activate` followed by a later `python` call in a new invocation silently falls back to a different `python` on `PATH`.

- [ ] **Step 6: Commit**

```bash
git add src/boukensha/tools/exploration.py tests/test_exploration_tool.py
git commit -m "fix: explore's door-retry sends 'open door <direction>' to match the door tool's fix"
```
