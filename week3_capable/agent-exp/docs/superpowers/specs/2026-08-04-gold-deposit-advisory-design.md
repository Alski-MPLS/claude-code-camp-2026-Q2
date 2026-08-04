# Advise depositing gold at the ATM once it reaches a threshold

## Problem

The character accumulates gold from farming but has no reminder to bank
any of it. Carried gold is at risk (death wipes gold and inventory — see
`combat.py` comment near line 49), so once gold reaches a threshold it
should be nudged into the bank. The `bank` tool (`src/boukensha/tools/
mud.py`) already supports `deposit`/`withdraw`/`balance` via an ATM
fixture, and its known location is recorded in world knowledge ("The
Entrance Hall To The Guild Of Swordsmen"). What's missing is anything
that notices the gold total and tells the agent to act.

## Scope

- Advisory only: append a note to the `score` check result when gold is
  at or above the threshold. The LLM decides when it's safe to act (not
  mid-combat, not mid-travel) — same pattern as the existing
  `_level_up_advisory` / `_sustenance_advisory` notes in `mud.py`.
- Threshold is configurable per-goal, default 200, mirroring how
  `hp_flee_threshold` already works.
- No automatic navigation or automatic `bank` call. No new "already
  nagged" state — once the agent deposits, gold drops below threshold
  and the note naturally stops appearing.

## Design

### 1. `GoalManager` (`src/boukensha/goals/goal_manager.py`)

Add `"gold_deposit_threshold": 200` to `DEFAULT_FIELDS`.

### 2. `combat.py` (`_format_goal` / `_do_goal_update`)

Add `gold_deposit_threshold` to the line list in `_format_goal` and to
the allowed-fields tuple in `_do_goal_update`, so `goal_update` can set
it exactly like `hp_flee_threshold`.

### 3. New `GoldMonitor` (`src/boukensha/goals/gold_monitor.py`)

Mirrors `CombatMonitor`'s shape:

```python
class GoldMonitor:
    @staticmethod
    def check(gold: int, goal: dict[str, Any]) -> str | None:
        threshold = int(goal.get("gold_deposit_threshold", 200))
        if gold < threshold:
            return None
        half = gold // 2
        return (
            f"\n\n[Bank] You're carrying {gold} gold — at or above your "
            f"{threshold} deposit threshold. Once it's safe (not mid-combat, "
            f"not mid-travel), deposit half ({half}) at the ATM via "
            f"bank(action='deposit', amount={half}). Known ATM location: "
            "The Entrance Hall To The Guild Of Swordsmen — navigate_to it "
            "if not already there."
        )
```

Export it from `src/boukensha/goals/__init__.py` alongside
`GoalManager`/`CombatMonitor`.

### 4. Wire a `GoalManager` into `mud.py`

Today only `Combat.register` constructs a `GoalManager`; `Mud.register`
/ `Mud._register_with_session` don't receive `goals_dir` at all. Add a
`goals_dir: str | Path | None = None` parameter to both, construct
`gm = GoalManager(goals_dir) if goals_dir is not None else None` inside
`_register_with_session`, matching the existing `tracker =
PlayerTracker(memory_dir) if memory_dir is not None else None` style
already used in that function.

### 5. Call it from `_check_and_record` in `mud.py`

In the `k == "score"` branch, after the existing level-up check:

```python
if gm is not None:
    gold = stats.get("gold")
    if gold is not None:
        advisory = GoldMonitor.check(gold, gm.read())
        if advisory:
            raw += advisory
```

### 6. Update call sites in `src/boukensha/__init__.py`

Both places that call `tools.Mud._register_with_session(...)` (there
are two near-identical blocks, ~line 207 and ~line 397-441) need
`goals_dir=_goals_dir` added to the call — `_goals_dir` is already
computed there before the call.

## Testing

- `GoldMonitor.check`: below threshold → `None`; at threshold → note
  with correct half-amount; above threshold → note.
- `_check_and_record`/`check(kind="score")` in `mud.py`: with a `gm`
  wired in and gold above threshold, the returned text contains the
  `[Bank]` note; below threshold, it doesn't.
- Existing `mud.py` tests that call `Mud._register_with_session` or
  `check(kind="score")` without a `goals_dir` must keep passing
  (advisory silently skipped when `gm is None`).

## Non-goals

- Automatic navigation to the ATM.
- Automatic `bank` deposit call.
- Tracking whether a deposit already happened this session (relies on
  gold naturally dropping below threshold after a real deposit).
