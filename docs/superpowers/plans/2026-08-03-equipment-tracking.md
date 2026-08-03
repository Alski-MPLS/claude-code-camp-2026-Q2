# Equipment Tracking & Upgrade Advisories Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Give the Boukensha MUD agent structured memory of its equipment loadout and identified item stats, and surface an advisory when an identified item is a stronger upgrade than what's currently worn in the same slot.

**Architecture:** Two new pure-parsing/storage modules (`memory/equipment_parser.py`, `memory/item_stats.py`) plumbed into the existing `tools/mud.py` tool-registration pattern, following the same shape already used for `PlayerStats`/`check(kind="score")` and `KnowledgeManager`. `PlayerTracker` gains an `update_equipment` method alongside its existing `update`/`update_stats`.

**Tech Stack:** Python 3.11+, pytest, PyYAML (already a dependency — used by `KnowledgeManager`).

## Global Constraints

- Package root: `week3_capable/agent-exp/` — all paths below are relative to this directory.
- Run tests with `uv run pytest tests/ -v` (per repo README) from `week3_capable/agent-exp/`.
- No new tool registered for casting `identify` — reuse the existing `cast_spell`/`use_magic_item` tools (see `src/boukensha/tools/mud.py`).
- No auto-equip — comparisons only produce advisory text appended to a tool result; the LLM decides whether to call `equip_item`.
- No dashboard changes in this plan.
- Follow existing patterns: YAML stores use the atomic tempfile-then-`os.replace` write pattern (see `KnowledgeManager._save`); JSON stores use the same pattern (see `PlayerTracker._write`).

---

### Task 1: Equipment/identify parsers

**Files:**
- Create: `src/boukensha/memory/equipment_parser.py`
- Test: `tests/test_equipment_parser.py`

**Interfaces:**
- Produces:
  - `parse_equipment(text: str) -> dict[str, str] | None` — maps slot key (e.g. `"finger"`, `"wielded"`, `"light"`) to item description. Returns `None` if no `<...>` equipment lines are found.
  - `parse_identify(text: str) -> dict | None` — returns `{"name": str, "wear_slot": str | None, "affects": dict[str, int]}` or `None` if the text has no `Object '...'` line (i.e. isn't identify output).

- [ ] **Step 1: Write the failing tests**

```python
# tests/test_equipment_parser.py
from boukensha.memory.equipment_parser import parse_equipment, parse_identify


def test_parse_equipment_extracts_worn_slots():
    text = (
        "You are using:\n"
        "<used as light>       a small candle\n"
        "<worn on finger>      a gold ring\n"
        "<worn on body>        a suit of leather armor\n"
        "<wielded>              a long sword\n"
    )
    assert parse_equipment(text) == {
        "light": "a small candle",
        "finger": "a gold ring",
        "body": "a suit of leather armor",
        "wielded": "a long sword",
    }


def test_parse_equipment_returns_none_when_no_slot_lines():
    assert parse_equipment("You are using: nothing.\n") is None


def test_parse_equipment_returns_none_for_empty_string():
    assert parse_equipment("") is None


def test_parse_equipment_strips_trailing_whitespace_from_item_name():
    text = "<worn on head>        a leather cap   \n"
    assert parse_equipment(text) == {"head": "a leather cap"}


def test_parse_identify_extracts_name_slot_and_affects():
    text = (
        "You feel informed:\n"
        "Object 'a gold ring', Item type: WORN\n"
        "This item can be worn on: FINGER\n"
        "Can affect you as :\n"
        "   Affects: HITROLL By 2\n"
        "   Affects: DAMROLL By 1\n"
        "   Affects: AC By -10\n"
    )
    parsed = parse_identify(text)
    assert parsed == {
        "name": "a gold ring",
        "wear_slot": "finger",
        "affects": {"hitroll": 2, "damroll": 1, "ac": -10},
    }


def test_parse_identify_infers_wielded_slot_for_weapons_without_worn_on_line():
    text = (
        "Object 'a long sword', Item type: WEAPON\n"
        "Can affect you as :\n"
        "   Affects: HITROLL By 1\n"
    )
    parsed = parse_identify(text)
    assert parsed["wear_slot"] == "wielded"
    assert parsed["affects"] == {"hitroll": 1}


def test_parse_identify_wear_slot_none_when_neither_marker_present():
    text = (
        "Object 'a bag of holding', Item type: CONTAINER\n"
        "Can affect you as :\n"
        "   Affects: STR By 1\n"
    )
    parsed = parse_identify(text)
    assert parsed["wear_slot"] is None
    assert parsed["affects"] == {"str": 1}


def test_parse_identify_returns_empty_affects_when_no_affects_lines():
    text = "Object 'a rusty spoon', Item type: OTHER\n"
    parsed = parse_identify(text)
    assert parsed["affects"] == {}


def test_parse_identify_returns_none_for_non_identify_text():
    assert parse_identify("You aren't holding that item.\n") is None


def test_parse_identify_returns_none_for_empty_string():
    assert parse_identify("") is None
```

- [ ] **Step 2: Run tests to verify they fail**

Run (from `week3_capable/agent-exp/`): `uv run pytest tests/test_equipment_parser.py -v`
Expected: FAIL with `ModuleNotFoundError: No module named 'boukensha.memory.equipment_parser'`

- [ ] **Step 3: Write the implementation**

```python
# src/boukensha/memory/equipment_parser.py
"""Parses raw CircleMUD 'equipment' and 'identify' output into structured data."""

from __future__ import annotations

import re

_EQUIP_LINE_RE = re.compile(r"<([^>]+)>\s*(.+)")
_WORN_PREFIXES = ("worn on ", "used as ", "worn as ")


def _normalize_slot(label: str) -> str:
    label = label.strip().lower()
    for prefix in _WORN_PREFIXES:
        if label.startswith(prefix):
            return label[len(prefix):].strip()
    return label


def parse_equipment(text: str) -> dict[str, str] | None:
    """Parse 'equipment' command output into {slot_key: item_description}."""
    slots: dict[str, str] = {}
    for line in text.splitlines():
        m = _EQUIP_LINE_RE.search(line)
        if not m:
            continue
        slot = _normalize_slot(m.group(1))
        item = m.group(2).strip()
        if item:
            slots[slot] = item
    return slots or None


_IDENTIFY_OBJECT_RE = re.compile(r"Object '([^']+)'")
_IDENTIFY_WEAR_RE = re.compile(r"can be worn on:\s*(\w+)", re.IGNORECASE)
_IDENTIFY_WEAPON_RE = re.compile(r"Item type:\s*WEAPON", re.IGNORECASE)
_IDENTIFY_AFFECT_RE = re.compile(r"Affects:\s*(\w+)\s*By\s*(-?\d+)", re.IGNORECASE)


def parse_identify(text: str) -> dict | None:
    """Parse 'identify' spell/scroll output into name, wear slot, and stat affects."""
    obj_m = _IDENTIFY_OBJECT_RE.search(text)
    if not obj_m:
        return None

    name = obj_m.group(1)

    wear_m = _IDENTIFY_WEAR_RE.search(text)
    if wear_m:
        wear_slot: str | None = wear_m.group(1).strip().lower()
    elif _IDENTIFY_WEAPON_RE.search(text):
        wear_slot = "wielded"
    else:
        wear_slot = None

    affects = {
        m.group(1).lower(): int(m.group(2))
        for m in _IDENTIFY_AFFECT_RE.finditer(text)
    }

    return {"name": name, "wear_slot": wear_slot, "affects": affects}
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `uv run pytest tests/test_equipment_parser.py -v`
Expected: PASS (9 tests)

- [ ] **Step 5: Commit**

```bash
git add src/boukensha/memory/equipment_parser.py tests/test_equipment_parser.py
git commit -m "Add equipment/identify output parsers"
```

---

### Task 2: Item stats store

**Files:**
- Create: `src/boukensha/memory/item_stats.py`
- Test: `tests/test_item_stats.py`

**Interfaces:**
- Consumes: nothing from Task 1 directly (stores whatever dict it's given), but is designed to store the `{"wear_slot": ..., "affects": {...}}` shape produced by `parse_identify` (minus `name`, which becomes the store key).
- Produces:
  - `ItemStatsStore(base_dir: str | Path)` 
  - `.save(item_name: str, stats: dict) -> None`
  - `.get(item_name: str) -> dict | None`
  - `.read_all() -> dict[str, dict]`

- [ ] **Step 1: Write the failing tests**

```python
# tests/test_item_stats.py
from boukensha.memory.item_stats import ItemStatsStore


def test_read_all_empty_when_no_file(tmp_path):
    store = ItemStatsStore(tmp_path)
    assert store.read_all() == {}


def test_save_and_get_round_trip(tmp_path):
    store = ItemStatsStore(tmp_path)
    store.save("a gold ring", {"wear_slot": "finger", "affects": {"ac": -10, "hitroll": 2}})
    result = store.get("a gold ring")
    assert result["wear_slot"] == "finger"
    assert result["affects"] == {"ac": -10, "hitroll": 2}
    assert "timestamp" in result


def test_get_is_case_insensitive(tmp_path):
    store = ItemStatsStore(tmp_path)
    store.save("A Gold Ring", {"wear_slot": "finger", "affects": {}})
    assert store.get("a gold ring") is not None
    assert store.get("A GOLD RING") is not None


def test_get_returns_none_for_unknown_item(tmp_path):
    store = ItemStatsStore(tmp_path)
    assert store.get("nonexistent") is None


def test_save_overwrites_existing_entry(tmp_path):
    store = ItemStatsStore(tmp_path)
    store.save("a gold ring", {"wear_slot": "finger", "affects": {"ac": -5}})
    store.save("a gold ring", {"wear_slot": "finger", "affects": {"ac": -10}})
    assert store.get("a gold ring")["affects"] == {"ac": -10}
    assert len(store.read_all()) == 1


def test_persists_across_instances(tmp_path):
    ItemStatsStore(tmp_path).save("a long sword", {"wear_slot": "wielded", "affects": {"hitroll": 1}})
    reloaded = ItemStatsStore(tmp_path).get("a long sword")
    assert reloaded["affects"] == {"hitroll": 1}


def test_atomic_write_no_partial_state(tmp_path):
    import os
    store = ItemStatsStore(tmp_path)
    store.save("a gold ring", {"wear_slot": "finger", "affects": {}})
    assert not any(f.endswith(".tmp") for f in os.listdir(tmp_path))
    assert (tmp_path / "item_stats.yaml").exists()
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `uv run pytest tests/test_item_stats.py -v`
Expected: FAIL with `ModuleNotFoundError: No module named 'boukensha.memory.item_stats'`

- [ ] **Step 3: Write the implementation**

```python
# src/boukensha/memory/item_stats.py
"""World-scoped store of identified item stats (AC, hitroll, damroll, stat mods)."""

from __future__ import annotations

import os
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import yaml


class ItemStatsStore:
    def __init__(self, base_dir: str | Path) -> None:
        self._path = Path(base_dir) / "item_stats.yaml"
        self._path.parent.mkdir(parents=True, exist_ok=True)

    def save(self, item_name: str, stats: dict[str, Any]) -> None:
        data = self._load()
        data[item_name.strip().lower()] = {
            **stats,
            "timestamp": datetime.now(timezone.utc).isoformat(),
        }
        self._save(data)

    def get(self, item_name: str) -> dict[str, Any] | None:
        return self._load().get(item_name.strip().lower())

    def read_all(self) -> dict[str, dict[str, Any]]:
        return self._load()

    # ── private ──────────────────────────────────────────────────────────────

    def _load(self) -> dict[str, dict[str, Any]]:
        if not self._path.exists():
            return {}
        raw = yaml.safe_load(self._path.read_text(encoding="utf-8"))
        return raw if isinstance(raw, dict) else {}

    def _save(self, data: dict[str, dict[str, Any]]) -> None:
        tmp = self._path.with_suffix(".tmp")
        tmp.write_text(
            yaml.dump(data, default_flow_style=False, allow_unicode=True),
            encoding="utf-8",
        )
        os.replace(tmp, self._path)
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `uv run pytest tests/test_item_stats.py -v`
Expected: PASS (7 tests)

- [ ] **Step 5: Commit**

```bash
git add src/boukensha/memory/item_stats.py tests/test_item_stats.py
git commit -m "Add ItemStatsStore for identified item stats"
```

---

### Task 3: PlayerTracker.update_equipment

**Files:**
- Modify: `src/boukensha/memory/player_tracker.py`
- Test: `tests/test_player_tracker.py` (append)

**Interfaces:**
- Consumes: nothing new.
- Produces: `PlayerTracker.update_equipment(name: str, slots: dict[str, str]) -> None`, writing `data[name]["equipment"]` and `data[name]["equipment_updated_at"]`, merged with (not replacing) any existing `room_hash`/`stats` for that player — same merge behavior as `update`/`update_stats`.

- [ ] **Step 1: Write the failing tests**

```python
# append to tests/test_player_tracker.py

def test_update_equipment_records_slots_for_new_player(tmp_path):
    tracker = PlayerTracker(tmp_path)
    tracker.update_equipment("Hero", {"finger": "a gold ring", "wielded": "a long sword"})
    data = tracker.read_all()
    assert data["Hero"]["equipment"] == {"finger": "a gold ring", "wielded": "a long sword"}
    assert "equipment_updated_at" in data["Hero"]


def test_update_equipment_preserves_existing_position_and_stats(tmp_path):
    tracker = PlayerTracker(tmp_path)
    tracker.update("Hero", "abc123", "Temple Square")
    tracker.update_stats("Hero", {"hp": 20, "max_hp": 20})
    tracker.update_equipment("Hero", {"finger": "a gold ring"})
    data = tracker.read_all()
    assert data["Hero"]["room_hash"] == "abc123"
    assert data["Hero"]["stats"]["hp"] == 20
    assert data["Hero"]["equipment"] == {"finger": "a gold ring"}


def test_update_equipment_overwrites_previous_loadout(tmp_path):
    tracker = PlayerTracker(tmp_path)
    tracker.update_equipment("Hero", {"finger": "a copper ring"})
    tracker.update_equipment("Hero", {"finger": "a gold ring"})
    data = tracker.read_all()
    assert data["Hero"]["equipment"] == {"finger": "a gold ring"}
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `uv run pytest tests/test_player_tracker.py -v -k update_equipment`
Expected: FAIL with `AttributeError: 'PlayerTracker' object has no attribute 'update_equipment'`

- [ ] **Step 3: Write the implementation**

Add to `src/boukensha/memory/player_tracker.py`, alongside the existing `update_stats` method:

```python
    def update_equipment(self, name: str, slots: dict[str, str]) -> None:
        data = self.read_all()
        existing = data.get(name, {})
        data[name] = {
            **existing,
            "equipment": slots,
            "equipment_updated_at": datetime.now(timezone.utc).isoformat(),
        }
        self._write(data)
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `uv run pytest tests/test_player_tracker.py -v`
Expected: PASS (all tests in the file, including the 3 new ones)

- [ ] **Step 5: Commit**

```bash
git add src/boukensha/memory/player_tracker.py tests/test_player_tracker.py
git commit -m "Add PlayerTracker.update_equipment"
```

---

### Task 4: Persist parsed equipment from check(kind="equipment")

**Files:**
- Modify: `src/boukensha/tools/mud.py`
- Test: `tests/test_tools_mud.py` (append)

**Interfaces:**
- Consumes: `parse_equipment` from Task 1 (`boukensha.memory.equipment_parser`), `PlayerTracker.update_equipment` from Task 3.
- Produces: no new public interface — `check(kind="equipment")` now has the side effect of persisting to the tracker when `memory_dir` was passed to `_register_with_session`.

- [ ] **Step 1: Write the failing tests**

```python
# append to tests/test_tools_mud.py

def test_check_equipment_persists_slots_to_player_tracker(tmp_path):
    registry = _make_registry()
    mock_session = MagicMock()
    mock_session.is_open = True
    mock_session.drain.return_value = ""
    mock_session.read_until_prompt.return_value = (
        "You are using:\n"
        "<worn on finger>      a gold ring\n"
        "<wielded>              a long sword\n"
        "> "
    )
    Mud._register_with_session(
        registry, mock_session, name="Tester", password="secret", memory_dir=tmp_path
    )
    registry.dispatch("check", {"kind": "equipment"})

    from boukensha.memory.player_tracker import PlayerTracker
    data = PlayerTracker(tmp_path).read_all()
    assert data["Tester"]["equipment"] == {
        "finger": "a gold ring",
        "wielded": "a long sword",
    }


def test_check_equipment_without_memory_dir_does_not_crash():
    registry = _make_registry()
    mock_session = MagicMock()
    mock_session.is_open = True
    mock_session.drain.return_value = ""
    mock_session.read_until_prompt.return_value = "<wielded> a long sword\n> "
    Mud._register_with_session(registry, mock_session, name="Tester", password="secret")
    result = registry.dispatch("check", {"kind": "equipment"})
    assert "a long sword" in result


def test_check_equipment_with_no_items_worn_does_not_crash(tmp_path):
    registry = _make_registry()
    mock_session = MagicMock()
    mock_session.is_open = True
    mock_session.drain.return_value = ""
    mock_session.read_until_prompt.return_value = "You are using: nothing.\n> "
    Mud._register_with_session(
        registry, mock_session, name="Tester", password="secret", memory_dir=tmp_path
    )
    result = registry.dispatch("check", {"kind": "equipment"})
    assert "nothing" in result
    from boukensha.memory.player_tracker import PlayerTracker
    assert PlayerTracker(tmp_path).read_all() == {}
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `uv run pytest tests/test_tools_mud.py -v -k check_equipment`
Expected: FAIL — `data["Tester"]` raises `KeyError` (nothing persisted yet) on the first test; other two should already pass incidentally (add them now so they guard the coming change).

- [ ] **Step 3: Write the implementation**

In `src/boukensha/tools/mud.py`:

1. Add the import near the top, with the other `boukensha.memory` imports:

```python
from boukensha.memory.equipment_parser import parse_equipment
```

2. In `_check_and_record` (inside `_register_with_session`), extend the existing `if kind.strip().lower() == "score" and not raw.startswith("error:"):` branch with an `elif`:

```python
        def _check_and_record(kind: str) -> str:
            raw = _check_info(session, kind)
            k = kind.strip().lower()
            if k == "score" and not raw.startswith("error:"):
                stats = PlayerStats.parse_score(raw)
                if stats:
                    previous_level = None
                    if tracker is not None:
                        previous = (tracker.read_all().get(name) or {}).get("stats") or {}
                        previous_level = previous.get("level")
                        tracker.update_stats(name, {**previous, **stats})
                    raw += _sustenance_advisory(stats)
                    new_level = stats.get("level")
                    if (
                        previous_level is not None
                        and new_level is not None
                        and new_level > previous_level
                    ):
                        raw += _level_up_advisory(previous_level, stats)
            elif k == "equipment" and not raw.startswith("error:"):
                slots = parse_equipment(raw)
                if slots and tracker is not None:
                    tracker.update_equipment(name, slots)
            return raw
```

(This replaces the existing `if kind.strip().lower() == "score" ...` line with the `k = kind.strip().lower()` / `if k == "score"` / `elif k == "equipment"` structure shown above — the body of the `score` branch is unchanged, just reindented under the new `k` variable.)

- [ ] **Step 4: Run tests to verify they pass**

Run: `uv run pytest tests/test_tools_mud.py -v`
Expected: PASS (full file, including the 3 new tests and all pre-existing ones — confirms the `score` branch refactor didn't regress anything)

- [ ] **Step 5: Commit**

```bash
git add src/boukensha/tools/mud.py tests/test_tools_mud.py
git commit -m "Persist parsed equipment slots from check(kind='equipment')"
```

---

### Task 5: Identify parsing, storage, and upgrade advisory on cast_spell/use_magic_item

**Files:**
- Modify: `src/boukensha/tools/mud.py`
- Test: `tests/test_tools_mud.py` (append)

**Interfaces:**
- Consumes: `parse_identify` (Task 1), `ItemStatsStore` (Task 2), `PlayerTracker.update_equipment`/`read_all` (Task 3 — already used elsewhere in this file).
- Produces: no new public interface — `cast_spell` and `use_magic_item` tool results now include an `[Equipment]` advisory suffix when the command's output was an `identify` result for a slot that's occupied by a previously-identified item with a lower total score.

- [ ] **Step 1: Write the failing tests**

```python
# append to tests/test_tools_mud.py

def _identify_output(name: str, wear_slot: str | None, affects: dict[str, int]) -> str:
    lines = [f"Object '{name}', Item type: WORN"]
    if wear_slot:
        lines.append(f"This item can be worn on: {wear_slot.upper()}")
    lines.append("Can affect you as :")
    for k, v in affects.items():
        lines.append(f"   Affects: {k.upper()} By {v}")
    return "\n".join(lines) + " > "


def test_cast_spell_identify_saves_item_stats(tmp_path):
    registry = _make_registry()
    mock_session = MagicMock()
    mock_session.is_open = True
    mock_session.drain.return_value = ""
    mock_session.read_until_prompt.return_value = _identify_output(
        "a gold ring", "finger", {"ac": -10, "hitroll": 2}
    )
    Mud._register_with_session(
        registry, mock_session, name="Tester", password="secret", memory_dir=tmp_path
    )

    registry.dispatch("cast_spell", {"spell": "identify", "target": "gold ring"})

    from boukensha.memory.item_stats import ItemStatsStore
    saved = ItemStatsStore(tmp_path).get("a gold ring")
    assert saved["wear_slot"] == "finger"
    assert saved["affects"] == {"ac": -10, "hitroll": 2}


def test_cast_spell_non_identify_result_does_not_touch_item_stats(tmp_path):
    registry = _make_registry()
    mock_session = MagicMock()
    mock_session.is_open = True
    mock_session.drain.return_value = ""
    mock_session.read_until_prompt.return_value = "You failed to concentrate. > "
    Mud._register_with_session(
        registry, mock_session, name="Tester", password="secret", memory_dir=tmp_path
    )

    registry.dispatch("cast_spell", {"spell": "magic missile", "target": "rat"})

    from boukensha.memory.item_stats import ItemStatsStore
    assert ItemStatsStore(tmp_path).read_all() == {}


def test_use_magic_item_identify_appends_upgrade_advisory_when_slot_occupied(tmp_path):
    from boukensha.memory.item_stats import ItemStatsStore
    from boukensha.memory.player_tracker import PlayerTracker

    ItemStatsStore(tmp_path).save(
        "a copper ring", {"wear_slot": "finger", "affects": {"ac": -2, "hitroll": 0}}
    )
    PlayerTracker(tmp_path).update_equipment("Tester", {"finger": "a copper ring"})

    registry = _make_registry()
    mock_session = MagicMock()
    mock_session.is_open = True
    mock_session.drain.return_value = ""
    mock_session.read_until_prompt.return_value = _identify_output(
        "a gold ring", "finger", {"ac": -10, "hitroll": 2}
    )
    Mud._register_with_session(
        registry, mock_session, name="Tester", password="secret", memory_dir=tmp_path
    )

    result = registry.dispatch(
        "use_magic_item", {"item": "scroll of identify", "mode": "recite", "target_args": "gold ring"}
    )

    assert "[Equipment]" in result
    assert "a gold ring" in result
    assert "finger" in result
    assert "a copper ring" in result


def test_use_magic_item_identify_omits_advisory_when_slot_empty(tmp_path):
    registry = _make_registry()
    mock_session = MagicMock()
    mock_session.is_open = True
    mock_session.drain.return_value = ""
    mock_session.read_until_prompt.return_value = _identify_output(
        "a gold ring", "finger", {"ac": -10, "hitroll": 2}
    )
    Mud._register_with_session(
        registry, mock_session, name="Tester", password="secret", memory_dir=tmp_path
    )

    result = registry.dispatch(
        "use_magic_item", {"item": "scroll of identify", "mode": "recite", "target_args": "gold ring"}
    )

    assert "[Equipment]" not in result


def test_use_magic_item_identify_omits_advisory_when_current_item_never_identified(tmp_path):
    from boukensha.memory.player_tracker import PlayerTracker
    PlayerTracker(tmp_path).update_equipment("Tester", {"finger": "a mystery ring"})

    registry = _make_registry()
    mock_session = MagicMock()
    mock_session.is_open = True
    mock_session.drain.return_value = ""
    mock_session.read_until_prompt.return_value = _identify_output(
        "a gold ring", "finger", {"ac": -10, "hitroll": 2}
    )
    Mud._register_with_session(
        registry, mock_session, name="Tester", password="secret", memory_dir=tmp_path
    )

    result = registry.dispatch(
        "use_magic_item", {"item": "scroll of identify", "mode": "recite", "target_args": "gold ring"}
    )

    assert "[Equipment]" not in result


def test_use_magic_item_identify_omits_advisory_when_new_item_not_better(tmp_path):
    from boukensha.memory.item_stats import ItemStatsStore
    from boukensha.memory.player_tracker import PlayerTracker

    ItemStatsStore(tmp_path).save(
        "a platinum ring", {"wear_slot": "finger", "affects": {"ac": -20, "hitroll": 5}}
    )
    PlayerTracker(tmp_path).update_equipment("Tester", {"finger": "a platinum ring"})

    registry = _make_registry()
    mock_session = MagicMock()
    mock_session.is_open = True
    mock_session.drain.return_value = ""
    mock_session.read_until_prompt.return_value = _identify_output(
        "a gold ring", "finger", {"ac": -10, "hitroll": 2}
    )
    Mud._register_with_session(
        registry, mock_session, name="Tester", password="secret", memory_dir=tmp_path
    )

    result = registry.dispatch(
        "use_magic_item", {"item": "scroll of identify", "mode": "recite", "target_args": "gold ring"}
    )

    assert "[Equipment]" not in result


def test_identify_without_memory_dir_does_not_crash():
    registry = _make_registry()
    mock_session = MagicMock()
    mock_session.is_open = True
    mock_session.drain.return_value = ""
    mock_session.read_until_prompt.return_value = _identify_output(
        "a gold ring", "finger", {"ac": -10}
    )
    Mud._register_with_session(registry, mock_session, name="Tester", password="secret")
    result = registry.dispatch("cast_spell", {"spell": "identify", "target": "gold ring"})
    assert "a gold ring" in result
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `uv run pytest tests/test_tools_mud.py -v -k identify`
Expected: FAIL — `test_cast_spell_identify_saves_item_stats` fails because `ItemStatsStore(tmp_path).read_all()` is empty; the advisory tests fail because `"[Equipment]"` is never in `result`.

- [ ] **Step 3: Write the implementation**

In `src/boukensha/tools/mud.py`:

1. Extend the import added in Task 4:

```python
from boukensha.memory.equipment_parser import parse_equipment, parse_identify
from boukensha.memory.item_stats import ItemStatsStore
```

2. In `_register_with_session`, alongside where `mem`/`graph`/`tracker` are constructed, add:

```python
        item_stats = ItemStatsStore(memory_dir) if memory_dir is not None else None
```

3. Add a module-level helper (near `_level_up_advisory`/`_sustenance_advisory`):

```python
def _format_affects(affects: dict[str, int]) -> str:
    if not affects:
        return "no known bonuses"
    ordered = sorted(affects.items(), key=lambda kv: (kv[0] != "ac", kv[0]))
    return ", ".join(f"{k.upper()} {v:+d}" for k, v in ordered)


def _affects_score(affects: dict[str, int]) -> int:
    # Lower AC is better in CircleMUD; every other tracked affect (hitroll,
    # damroll, stat mods) is better when higher — negate AC so a single sum
    # ranks both consistently.
    return sum(-v if k == "ac" else v for k, v in affects.items())


def _equipment_upgrade_advisory(
    parsed: dict, item_stats: "ItemStatsStore", tracker: "PlayerTracker | None", name: str
) -> str:
    item_stats.save(parsed["name"], {"wear_slot": parsed["wear_slot"], "affects": parsed["affects"]})

    slot = parsed["wear_slot"]
    if not slot or tracker is None:
        return ""

    current_slots = (tracker.read_all().get(name) or {}).get("equipment") or {}
    current_item = current_slots.get(slot)
    if not current_item or current_item.strip().lower() == parsed["name"].strip().lower():
        return ""

    current_stats = item_stats.get(current_item)
    if not current_stats:
        return ""

    new_affects = parsed["affects"]
    current_affects = current_stats.get("affects") or {}
    if _affects_score(new_affects) <= _affects_score(current_affects):
        return ""

    return (
        f"\n\n[Equipment] '{parsed['name']}' ({_format_affects(new_affects)}) is stronger "
        f"than what's currently worn in your {slot} slot ('{current_item}', "
        f"{_format_affects(current_affects)}). Consider equip_item(item={parsed['name']!r}, "
        f"action=\"wear\")."
    )
```

4. Add a shared wrapper that both `cast_spell` and `use_magic_item` call after getting their raw result:

```python
        def _record_identify_if_present(raw: str) -> str:
            if raw.startswith("error:"):
                return raw
            parsed = parse_identify(raw)
            if parsed and item_stats is not None:
                raw += _equipment_upgrade_advisory(parsed, item_stats, tracker, name)
            return raw
```

Place this nested function inside `_register_with_session`, near `_look_and_record`/`_check_and_record`, since it closes over `item_stats`, `tracker`, and `name`.

5. Change the `cast_spell` tool's `block` from:

```python
            block=lambda spell, target=None, **_: _guard(session) or _send(
                session, f"cast '{spell}' {target}" if target else f"cast '{spell}'"
            ),
```

to:

```python
            block=lambda spell, target=None, **_: _guard(session) or _record_identify_if_present(
                _send(session, f"cast '{spell}' {target}" if target else f"cast '{spell}'")
            ),
```

6. Change the `use_magic_item` tool's `block` from:

```python
            block=lambda item, mode, target_args=None, **_: _use_magic_item(session, item, mode, target_args),
```

to:

```python
            block=lambda item, mode, target_args=None, **_: _record_identify_if_present(
                _use_magic_item(session, item, mode, target_args)
            ),
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `uv run pytest tests/test_tools_mud.py -v`
Expected: PASS (full file — all Task 4 and Task 5 tests plus every pre-existing test)

- [ ] **Step 5: Run the full test suite**

Run: `uv run pytest tests/ -v`
Expected: PASS, no regressions anywhere in the package.

- [ ] **Step 6: Commit**

```bash
git add src/boukensha/tools/mud.py tests/test_tools_mud.py
git commit -m "Save identified item stats and advise on equipment upgrades"
```

---

### Task 6: Update game_findings.md

**Files:**
- Modify: `game_findings.md`

**Interfaces:**
- Consumes: nothing (documentation only).
- Produces: nothing consumed by other tasks.

The existing "Open" entry (lines 11-18) covers both light-source tracking
*and* general equipment tracking under one bullet. This plan implements the
equipment-quality half (AC/hitroll/damroll/stat tracking + upgrade
advisories) but not light-source-specific detection — split the entry so the
still-open part stays visible and the implemented part is documented in the
usual "Implemented" style used elsewhere in this file.

- [ ] **Step 1: Replace the existing "Open" bullet**

In `game_findings.md`, replace:

```markdown
- **No equipment/light-source tracking yet.** `explore()` now refuses to walk
  into a room it detects as dark (see Implemented below) instead of blindly
  entering it, but it has no way to check whether the agent is actually
  carrying a lit torch/lantern before deciding to retry a dark exit — it just
  marks the exit blocked and leaves it blocked until someone calls
  `BlockedExits.unmark()`. Next step: a way to check current light-source
  state (e.g. via `check equipment`) and auto-retry dark-marked exits once
  one is equipped.
```

with:

```markdown
- **No light-source tracking yet.** `explore()` now refuses to walk into a
  room it detects as dark (see Implemented below) instead of blindly
  entering it, but it has no way to check whether the agent is actually
  carrying a lit torch/lantern before deciding to retry a dark exit — it just
  marks the exit blocked and leaves it blocked until someone calls
  `BlockedExits.unmark()`. Equipment slots are now tracked (see Implemented
  below), so this is a matter of reading the `light` slot from
  `PlayerTracker`'s stored equipment, not adding new tracking. Next step:
  wire that check into `explore()`'s dark-exit retry path.
```

- [ ] **Step 2: Add an "Implemented" entry**

Add this bullet under the `## Implemented` heading in `game_findings.md`
(after the heading, following the existing style of newest-relevant entries
at the top of that section):

```markdown
- **Equipment quality tracking and upgrade advisories.** The agent now
  parses `check(kind="equipment")` output into per-slot loadout data
  (`memory/equipment_parser.py:parse_equipment`), persisted via
  `PlayerTracker.update_equipment`. Casting/reciting `identify` (via the
  existing `cast_spell`/`use_magic_item` tools) is parsed by
  `parse_identify` into AC/hitroll/damroll/stat-mod affects, saved
  world-scoped in `memory/item_stats.py:ItemStatsStore`, and — when both the
  newly identified item and whatever currently occupies its wear slot have
  known stats — an `[Equipment]` advisory is appended to the tool result
  suggesting `equip_item` when the new item scores higher. See
  `tools/mud.py` (`_record_identify_if_present`,
  `_equipment_upgrade_advisory`). Tests: `tests/test_equipment_parser.py`,
  `tests/test_item_stats.py`, `tests/test_tools_mud.py`.

  Caveat: `parse_identify`'s regexes are built against the stock CircleMUD
  `identify` output format, unverified against this server's actual output
  — first live `identify` cast after deployment should confirm the format
  matches, and this note should be updated (or the regexes fixed) if not.
```

- [ ] **Step 3: Commit**

```bash
git add game_findings.md
git commit -m "Document equipment tracking in game_findings.md"
```
</content>
