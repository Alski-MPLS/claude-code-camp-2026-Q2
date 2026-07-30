# Auto-loot Corpse and Directional Door Fix Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** After `combat_loop` kills a target it automatically loots the corpse, and the `door` tool sends the MUD's actual syntax (`open door <direction>`) when targeting a compass direction.

**Architecture:** Two small, independent changes in existing files — no new files, no new tools. `combat_loop` (`src/boukensha/tools/combat.py`) gains an `auto_loot` parameter and calls the existing `_get_item` helper from `mud.py` on a kill. `_door` (`src/boukensha/tools/mud.py`) inspects whether its `target` is a compass direction and changes the command string it builds accordingly.

**Tech Stack:** Python 3, pytest, `unittest.mock.MagicMock` for session mocking (no live MUD server in tests).

## Global Constraints

- No new tool parameters beyond `auto_loot: bool = True` on `combat_loop` — `door`'s public signature (`action`, `target`) does not change.
- Do not touch `src/boukensha/tools/exploration.py`'s raw `"open {direction}"` command construction — out of scope per the approved spec (`docs/superpowers/specs/2026-07-30-auto-loot-corpse-design.md`).
- No hunger/thirst automation, no auto key-to-door matching — explicitly non-goals in the spec.
- Existing tests in `tests/test_combat.py` and `tests/test_tools_mud.py` must keep passing; update mocks/assertions where the new behavior legitimately changes what's sent, per spec's Testing section.

---

### Task 1: Auto-loot corpse after a kill in `combat_loop`

**Files:**
- Modify: `src/boukensha/tools/combat.py:12` (import), `src/boukensha/tools/combat.py:63-145` (`_combat_loop` and its tool registration)
- Modify: `tests/test_combat.py:92-110` (`test_combat_loop_proceeds_when_consider_looks_safe` needs an extra mocked response for the loot step)
- Test: `tests/test_combat.py` (new tests appended)

**Interfaces:**
- Consumes: `_get_item(session: MudSession, item: str, container: str | None, count: int | None) -> str` from `boukensha.tools.mud` (already defined at `src/boukensha/tools/mud.py:955`; sends `"get {item} {container}"` via the module's `_send` helper and returns the MUD's response text).
- Produces: `combat_loop` tool gains parameter `auto_loot: bool = True`. Return value on a kill becomes `f"Combat complete: {target} defeated after {rounds} round(s).\nLoot: {loot_resp}"` when `auto_loot` is true; unchanged (`f"Combat complete: {target} defeated after {rounds} round(s)."`) when false.

- [ ] **Step 1: Write the failing tests**

First, update the existing test (it currently asserts an exact
2-element `sent` list, which the new auto-loot call will break once
Step 3 lands) — replace `test_combat_loop_proceeds_when_consider_looks_safe`
in `tests/test_combat.py` with:

```python
def test_combat_loop_proceeds_when_consider_looks_safe(tmp_path):
    registry = _make_registry()
    mock_session = MagicMock()
    mock_session.is_open = True
    mock_session.drain.return_value = ""
    mock_session.read_until_prompt.side_effect = [
        "This will be a piece of cake.\n",              # consider
        "The rat is dead! You receive experience points.\n",  # kill
        "You didn't find anything.\n",  # get all corpse
    ]
    Combat.register(
        registry, session=mock_session, goals_dir=tmp_path,
        current_npcs_ref=[["a rat"]],
    )

    result = registry.dispatch("combat_loop", {"target": "rat"})

    assert "defeated" in result
    sent = [c.args[0] for c in mock_session.send_command.call_args_list]
    assert sent == ["consider rat", "kill rat", "get all corpse"]
```

Then append two new tests to `tests/test_combat.py`:

```python
def test_combat_loop_auto_loots_corpse_after_kill(tmp_path):
    registry = _make_registry()
    mock_session = MagicMock()
    mock_session.is_open = True
    mock_session.drain.return_value = ""
    mock_session.read_until_prompt.side_effect = [
        "This will be a piece of cake.\n",
        "The rat is dead! You receive experience points.\n",
        "You get a handful of gold coins from the corpse of the rat.\n",
    ]
    Combat.register(
        registry, session=mock_session, goals_dir=tmp_path,
        current_npcs_ref=[["a rat"]],
    )

    result = registry.dispatch("combat_loop", {"target": "rat"})

    assert "defeated" in result
    assert "Loot: You get a handful of gold coins" in result
    sent = [c.args[0] for c in mock_session.send_command.call_args_list]
    assert sent == ["consider rat", "kill rat", "get all corpse"]


def test_combat_loop_auto_loot_false_skips_looting(tmp_path):
    registry = _make_registry()
    mock_session = MagicMock()
    mock_session.is_open = True
    mock_session.drain.return_value = ""
    mock_session.read_until_prompt.return_value = "The rat is dead! You receive experience points.\n"
    Combat.register(registry, session=mock_session, goals_dir=tmp_path)

    result = registry.dispatch(
        "combat_loop", {"target": "rat", "force": True, "auto_loot": False}
    )

    assert "defeated" in result
    assert "Loot:" not in result
    sent = [c.args[0] for c in mock_session.send_command.call_args_list]
    assert "get all corpse" not in sent
```

This is the version to actually add — use `tmp_path`, not `tempfile.mkdtemp()`, for both new tests, matching every other test in the file.

- [ ] **Step 2: Run tests to verify they fail**

Run: `cd /Users/alanw/code/github/ai/claude-code-camp-2026-Q2/week2_capable/agent-exp && python -m pytest tests/test_combat.py -v`
Expected: `test_combat_loop_auto_loots_corpse_after_kill` and `test_combat_loop_auto_loot_false_skips_looting` FAIL (no `Loot:` in output yet); `test_combat_loop_proceeds_when_consider_looks_safe` FAILS on the `sent ==` assertion (only 2 elements sent, test now expects 3) — since we already edited it to expect 3, this confirms the current code doesn't loot yet.

- [ ] **Step 3: Implement auto-loot in `_combat_loop`**

In `src/boukensha/tools/combat.py`, change the import at line 12:

```python
from boukensha.tools.mud import _match_npc, _no_living_target_message, _get_item
```

Change the death-check branch inside `_combat_loop` (currently lines 106-108):

```python
                # Check if target is dead
                if any(p in response_lower for p in _DEAD_PATTERNS):
                    result = f"Combat complete: {target} defeated after {rounds} round(s)."
                    if auto_loot:
                        loot_resp = _get_item(session, "all", "corpse", None)
                        result += f"\nLoot: {loot_resp}"
                    return result
```

Change the function signature (currently line 63):

```python
        def _combat_loop(
            target: str,
            flee_hp: int = 5,
            force: bool = False,
            auto_loot: bool = True,
            **_: Any,
        ) -> str:
```

Update the tool registration's description and parameters (currently
lines 129-145) to document the new parameter:

```python
        registry.tool(
            "combat_loop",
            description=(
                "Fight a target in a Python loop, checking HP each round. "
                "Always considers the target first and refuses to attack if it looks far "
                "too dangerous (e.g. \"Do you feel lucky, punk?\") — pass force=true to "
                "attack anyway. Otherwise automatically flees if HP drops to or below flee_hp. "
                "On a kill, automatically loots the corpse (get all corpse) and includes the "
                "loot result in the response — pass auto_loot=false to skip this and inspect "
                "the corpse yourself first. "
                "Returns when target dies, you flee, or the round limit is reached. "
                "No LLM call per round — only use this for straightforward fights."
            ),
            parameters={
                "target": {"type": "string", "description": "Name of the mob to attack"},
                "flee_hp": {"type": "integer", "description": "Flee if HP drops to this value or below (default: 5)"},
                "force": {"type": "boolean", "description": "Skip the pre-fight danger check and attack even if consider looks dangerous (default: false)"},
                "auto_loot": {"type": "boolean", "description": "Automatically loot the corpse on a kill (default: true)"},
            },
            block=_combat_loop,
        )
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `cd /Users/alanw/code/github/ai/claude-code-camp-2026-Q2/week2_capable/agent-exp && python -m pytest tests/test_combat.py -v`
Expected: all tests in the file PASS, including the two new ones and the updated `test_combat_loop_proceeds_when_consider_looks_safe`.

- [ ] **Step 5: Run the full test suite to check for regressions**

Run: `cd /Users/alanw/code/github/ai/claude-code-camp-2026-Q2/week2_capable/agent-exp && python -m pytest tests/ -v`
Expected: all tests PASS (in particular, check `test_combat_monitor.py` and any other file importing from `combat.py` still passes — the flee branch is untouched, so it should be unaffected).

- [ ] **Step 6: Commit**

```bash
git add src/boukensha/tools/combat.py tests/test_combat.py
git commit -m "feat: auto-loot corpse after combat_loop kill"
```

---

### Task 2: Fix directional door commands

**Files:**
- Modify: `src/boukensha/tools/mud.py:864-871` (`_door` function)
- Test: `tests/test_tools_mud.py` (new tests appended)

**Interfaces:**
- Consumes: `_DIRECTIONS: set[str]` module-level constant already defined at `src/boukensha/tools/mud.py:95` (`{"north", "east", "south", "west", "up", "down"}`); `_guard`, `_check_enum`, `_send`, `_DOOR_OPS` already defined in the same module.
- Produces: no signature change to the `_door` function or the `door` tool — only the constructed command string changes when `target` is a direction.

- [ ] **Step 1: Write the failing tests**

Append to `tests/test_tools_mud.py`:

```python
def test_door_open_with_direction_sends_open_door_direction():
    registry = _make_registry()
    mock_session = MagicMock()
    mock_session.is_open = True
    mock_session.drain.return_value = ""
    mock_session.read_until_prompt.return_value = "Okay.\n"
    Mud._register_with_session(registry, mock_session, name="Tester", password="secret")

    result = registry.dispatch("door", {"action": "open", "target": "east"})

    mock_session.send_command.assert_called_once_with("open door east")
    assert "Okay" in result


def test_door_open_with_item_name_unchanged():
    registry = _make_registry()
    mock_session = MagicMock()
    mock_session.is_open = True
    mock_session.drain.return_value = ""
    mock_session.read_until_prompt.return_value = "You open the chest.\n"
    Mud._register_with_session(registry, mock_session, name="Tester", password="secret")

    result = registry.dispatch("door", {"action": "open", "target": "chest"})

    mock_session.send_command.assert_called_once_with("open chest")
    assert "chest" in result


def test_door_lock_with_direction_sends_lock_door_direction():
    registry = _make_registry()
    mock_session = MagicMock()
    mock_session.is_open = True
    mock_session.drain.return_value = ""
    mock_session.read_until_prompt.return_value = "*click*\n"
    Mud._register_with_session(registry, mock_session, name="Tester", password="secret")

    result = registry.dispatch("door", {"action": "lock", "target": "north"})

    mock_session.send_command.assert_called_once_with("lock door north")
    assert "click" in result
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `cd /Users/alanw/code/github/ai/claude-code-camp-2026-Q2/week2_capable/agent-exp && python -m pytest tests/test_tools_mud.py -k door -v`
Expected: `test_door_open_with_direction_sends_open_door_direction` and
`test_door_lock_with_direction_sends_lock_door_direction` FAIL (current
code sends `"open east"` / `"lock north"`, not the `door`-qualified form).
`test_door_open_with_item_name_unchanged` PASSES already (behavior for
non-direction targets is unchanged) — that's expected and fine, it locks
in current behavior before the change.

- [ ] **Step 3: Implement the fix**

Replace `_door` in `src/boukensha/tools/mud.py` (currently lines 864-871):

```python
def _door(session: MudSession, action: str, target: str) -> str:
    err = _guard(session)
    if err:
        return err
    err = _check_enum(action, _DOOR_OPS, "action")
    if err:
        return err
    action = action.strip().lower()
    t = target.strip().lower()
    if t in _DIRECTIONS:
        return _send(session, f"{action} door {t}")
    return _send(session, f"{action} {target}")
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `cd /Users/alanw/code/github/ai/claude-code-camp-2026-Q2/week2_capable/agent-exp && python -m pytest tests/test_tools_mud.py -k door -v`
Expected: all three tests PASS.

- [ ] **Step 5: Run the full test suite to check for regressions**

Run: `cd /Users/alanw/code/github/ai/claude-code-camp-2026-Q2/week2_capable/agent-exp && python -m pytest tests/ -v`
Expected: all tests PASS. In particular confirm `tests/test_navigation_tool.py` and `tests/test_exploration_tool.py` are untouched and still pass — they exercise raw `"open {direction}"` sent directly by `exploration.py`, a separate code path from `_door`, and this task does not modify `exploration.py`.

- [ ] **Step 6: Commit**

```bash
git add src/boukensha/tools/mud.py tests/test_tools_mud.py
git commit -m "fix: door tool sends 'open door <direction>' for directional targets"
```
