# Fix directional door command in auto-explore's closed-door retry

## Problem

The `door` tool fix (see `2026-07-30-auto-loot-corpse-design.md`) corrected
`_door()` in `src/boukensha/tools/mud.py` to send `"open door <direction>"`
instead of `"open <direction>"`, matching what the live MUD server
actually accepts. `src/boukensha/tools/exploration.py:180` has the exact
same bug in a separate code path: when `explore`'s auto-retry logic tries
to open a closed (not locked) door blocking an exit, it sends
`f"open {direction}"`, which the server rejects the same way. Since the
open silently fails, the retry move also fails, and `explore` incorrectly
marks a perfectly traversable exit as blocked — persisting that wrong
conclusion into the world graph (`BlockedExits`, `WorldGraph`), which
other tools (`navigate_to`, future `explore` calls) then trust.

## Scope

- Fix the single command string at `exploration.py:180`.
- Update the two existing tests in `tests/test_exploration_tool.py` that
  assert the old wire format, to assert the corrected one.
- No new tests — the existing two tests (`test_explore_opens_closed_door_and_retries`,
  `test_explore_marks_exit_blocked_when_still_stuck_after_opening`) already
  exercise this exact code path end to end; they just need their expected
  command strings corrected.
- No shared helper/constant extracted between this file and `mud.py`'s
  `_door` — two independent one-line command constructions in unrelated
  tool registrars don't justify an abstraction.

## Design

`src/boukensha/tools/exploration.py`, inside `_explore` (around line 180):

- `direction` at this point in the function is always a real compass
  direction pulled from a room's own recorded exits (`_nearest_frontier`
  returns it from `known_exits`, which are `RoomParser`-parsed exit keys)
  — never arbitrary input. Unlike `mud.py`'s `_door`, which has to check
  `target in _DIRECTIONS` because its `target` can also be a container
  name, this call site needs no branching.
- Change:
  ```python
  session.send_command(f"open {direction}")
  ```
  to:
  ```python
  session.send_command(f"open door {direction}")
  ```

## Testing

- `tests/test_exploration_tool.py::test_explore_opens_closed_door_and_retries`:
  update the expected `sent` list's `"open south"` entry to `"open door south"`.
- `tests/test_exploration_tool.py::test_explore_marks_exit_blocked_when_still_stuck_after_opening`:
  same update, wherever it asserts the sent command list (verify at
  implementation time whether this test checks the exact sent list or
  just the mocked response sequence — update whichever it checks that
  encodes the old wire format).

## Non-goals

- No change to `mud.py`'s `_door` (already fixed).
- No change to how `explore` decides which exit to try next, or how it
  marks exits blocked — only the wire format of the one `open` command.
