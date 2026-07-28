# Dashboard Overview Tab Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add an "Overview" tab to the Boukensha Flask dashboard showing summary cards (rooms known, frontier exits, entities) and per-player stats (HP/mana/move, current location, where they came from), as the new default landing tab.

**Architecture:** Two small new read-only aggregation modules (`world_stats.py`, `player_stats.py`) compute stats from data that already exists on disk (`world_graph.json`, room JSON files, `players.json`). `PlayerTracker` gains a `update_stats()` method, wired into the `check(kind="score")` MUD tool so HP/mana/move get persisted the next time the agent checks its score. A new `/api/overview` Flask route composes all of this into one JSON payload; a new tab in the existing dashboard template renders it.

**Tech Stack:** Python 3.11+, Flask 3.0, networkx (via existing `WorldGraph`), pytest, vanilla JS/CSS (no new frontend dependencies — matches the existing dashboard's dependency-free `app.js`).

## Global Constraints

- All new Python modules go under `week2_capable/agent-exp/src/boukensha/`; all new tests under `week2_capable/agent-exp/tests/`.
- Run tests with `cd week2_capable/agent-exp && .venv/bin/python -m pytest <path> -v`.
- No new dependencies — everything needed (Flask, networkx, stdlib `re`/`json`) is already in `pyproject.toml`.
- Follow existing patterns exactly: static-method parser classes like `RoomParser` (see `src/boukensha/memory/parser.py`), JSON-file persistence with atomic tmp-then-`os.replace` writes like `PlayerTracker`/`RoomMemory`/`WorldGraph`, `tmp_path`-based pytest fixtures with no real MUD/network connection (mock `MudSession` with `MagicMock` — see `tests/test_tools_mud.py`).
- Dashboard frontend is a single dark, monospace theme (`static/style.css`) — new CSS must match existing color values (`#111` background, `#1a1a1a` cards, `#333` borders, `#888` labels, `#4af` accent, `#fff`/`#ccc` text) rather than introducing a new palette.
- `DASHBOARD.md` documents every tab's data endpoint and JSON shape — the Overview tab must be documented there too, in the same format as the existing "Map" section.
- Do not change the behavior or JSON shape of any existing route (`/api/map`, `/api/players`, `/api/goal`, `/api/sessions*`) — existing tests for them must keep passing unmodified.

---

## File Structure

| File | Responsibility |
|---|---|
| `src/boukensha/memory/world_stats.py` (new) | Pure functions `frontier_stats()` and `entity_stats()` — aggregate known-vs-walked exits and unique mobs/objects across every room the graph knows about. No I/O beyond reading via `WorldGraph`/`RoomMemory` objects passed in. |
| `src/boukensha/memory/player_stats.py` (new) | `PlayerStats.parse_score()` — regexes the MUD's `score` command text into a `{hp, max_hp, mana, max_mana, move, max_move}` dict. Pure text-in, dict-out, no I/O. |
| `src/boukensha/memory/player_tracker.py` (modify) | Add `update_stats()`; fix `update()` to merge instead of overwrite so stats and position never clobber each other. |
| `src/boukensha/tools/mud.py` (modify) | Wire `PlayerStats.parse_score()` into the `check` tool so a `score` check persists stats via `PlayerTracker.update_stats()`. |
| `src/boukensha/dashboard/app.py` (modify) | Add `GET /api/overview` composing `world_stats` + `player_tracker` data. |
| `src/boukensha/dashboard/templates/index.html` (modify) | Add the Overview tab button (now first/default-active) and its `<section>`. |
| `src/boukensha/dashboard/static/app.js` (modify) | Add `loadOverview()`, wire it into tab-click routing and initial page load. |
| `src/boukensha/dashboard/static/style.css` (modify) | Add `.overview-*` card-grid styles matching the existing theme. |
| `DASHBOARD.md` (modify) | Document the Overview tab and its endpoint. |

---

### Task 1: Frontier and entity aggregate stats

**Files:**
- Create: `week2_capable/agent-exp/src/boukensha/memory/world_stats.py`
- Test: `week2_capable/agent-exp/tests/test_world_stats.py`

**Interfaces:**
- Consumes: `WorldGraph` (`.graph` property returning an `nx.DiGraph`, `.get_neighbors(room_hash) -> dict[str, str]`, `.add_room()`, `.add_edge()` — all in `src/boukensha/memory/world_graph.py`); `RoomMemory` (`.get(room_hash) -> dict | None`, `.record(room) -> tuple[str, dict]` — in `src/boukensha/memory/room_memory.py`). Room dicts have keys `title`, `description`, `exits` (dict of direction → text), `npcs` (list[str]), `items` (list[str]) — see `src/boukensha/memory/parser.py`.
- Produces: `frontier_stats(graph, mem) -> dict[str, int]` with keys `known_exits`, `walked`, `frontier`. `entity_stats(graph, mem) -> dict[str, int]` with keys `mobs`, `objects`, `total`. Both are used by Task 5's `/api/overview` route.

- [ ] **Step 1: Write the failing tests**

```python
# week2_capable/agent-exp/tests/test_world_stats.py
from boukensha.memory.world_graph import WorldGraph
from boukensha.memory.room_memory import RoomMemory
from boukensha.memory.world_stats import frontier_stats, entity_stats


def _room(title, exits, npcs=None, items=None):
    return {"title": title, "description": "d", "exits": exits, "npcs": npcs or [], "items": items or []}


def test_frontier_stats_empty_graph(tmp_path):
    graph = WorldGraph(tmp_path)
    mem = RoomMemory(tmp_path)
    assert frontier_stats(graph, mem) == {"known_exits": 0, "walked": 0, "frontier": 0}


def test_frontier_stats_counts_walked_and_unwalked_exits(tmp_path):
    graph = WorldGraph(tmp_path)
    mem = RoomMemory(tmp_path)

    room_a = _room("Room A", {"north": "a corridor", "east": "a door"})
    hash_a, _ = mem.record(room_a)
    graph.add_room(hash_a, "Room A")

    room_b = _room("Room B", {"south": "back to room a"})
    hash_b, _ = mem.record(room_b)
    graph.add_room(hash_b, "Room B")

    graph.add_edge(hash_a, hash_b, "north", to_room_exits={"south"})

    stats = frontier_stats(graph, mem)
    # Room A: north walked, east unwalked. Room B: south walked (auto reverse edge).
    assert stats == {"known_exits": 3, "walked": 2, "frontier": 1}


def test_frontier_stats_skips_graph_node_with_no_room_memory_record(tmp_path):
    graph = WorldGraph(tmp_path)
    mem = RoomMemory(tmp_path)
    graph.add_room("orphan", "Orphan Room")  # node exists in graph, never recorded via RoomMemory
    assert frontier_stats(graph, mem) == {"known_exits": 0, "walked": 0, "frontier": 0}


def test_entity_stats_counts_unique_mobs_and_objects_across_rooms(tmp_path):
    graph = WorldGraph(tmp_path)
    mem = RoomMemory(tmp_path)

    room_a = _room("Room A", {}, npcs=["a peacekeeper"], items=["a small sign"])
    hash_a, _ = mem.record(room_a)
    graph.add_room(hash_a, "Room A")

    room_b = _room("Room B", {}, npcs=["a peacekeeper", "the baker"], items=[])
    hash_b, _ = mem.record(room_b)
    graph.add_room(hash_b, "Room B")

    stats = entity_stats(graph, mem)
    # "a peacekeeper" appears in both rooms but counts once.
    assert stats == {"mobs": 2, "objects": 1, "total": 3}


def test_entity_stats_empty_graph(tmp_path):
    graph = WorldGraph(tmp_path)
    mem = RoomMemory(tmp_path)
    assert entity_stats(graph, mem) == {"mobs": 0, "objects": 0, "total": 0}
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `cd week2_capable/agent-exp && .venv/bin/python -m pytest tests/test_world_stats.py -v`
Expected: FAIL with `ModuleNotFoundError: No module named 'boukensha.memory.world_stats'`

- [ ] **Step 3: Write the implementation**

```python
# week2_capable/agent-exp/src/boukensha/memory/world_stats.py
"""Aggregate read-only stats over the world graph and room memory, for the
dashboard's Overview tab. Pure functions — no I/O beyond what the passed-in
WorldGraph/RoomMemory objects already provide."""

from __future__ import annotations

from .room_memory import RoomMemory
from .world_graph import WorldGraph


def frontier_stats(graph: WorldGraph, mem: RoomMemory) -> dict[str, int]:
    """Known exits vs. exits actually walked (has a graph edge), across
    every room the agent has recorded. 'Frontier' is known-but-unwalked —
    it deliberately does not exclude exits marked blocked in
    BlockedExits, since those are still known frontier, just not
    currently pursuable."""
    known_exits = 0
    walked = 0
    for node in graph.graph.nodes:
        room = mem.get(node)
        if not room:
            continue
        room_known = set((room.get("exits") or {}).keys())
        mapped = set(graph.get_neighbors(node).keys())
        known_exits += len(room_known)
        walked += len(room_known & mapped)
    return {"known_exits": known_exits, "walked": walked, "frontier": known_exits - walked}


def entity_stats(graph: WorldGraph, mem: RoomMemory) -> dict[str, int]:
    """Unique mob and object names seen across every known room (the same
    name appearing in multiple rooms counts once)."""
    mobs: set[str] = set()
    objects: set[str] = set()
    for node in graph.graph.nodes:
        room = mem.get(node)
        if not room:
            continue
        mobs.update(room.get("npcs") or [])
        objects.update(room.get("items") or [])
    return {"mobs": len(mobs), "objects": len(objects), "total": len(mobs) + len(objects)}
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `cd week2_capable/agent-exp && .venv/bin/python -m pytest tests/test_world_stats.py -v`
Expected: PASS (5 tests)

- [ ] **Step 5: Commit**

```bash
git add week2_capable/agent-exp/src/boukensha/memory/world_stats.py week2_capable/agent-exp/tests/test_world_stats.py
git commit -m "feat: add frontier_stats and entity_stats for the dashboard Overview tab"
```

---

### Task 2: Parse the MUD's `score` output into structured stats

**Files:**
- Create: `week2_capable/agent-exp/src/boukensha/memory/player_stats.py`
- Test: `week2_capable/agent-exp/tests/test_player_stats.py`

**Interfaces:**
- Consumes: raw `score` command text as captured from a live session (ground truth format, confirmed from real gameplay logs): `"You have 20(20) hit, 100(100) mana and 85(85) movement points. Your armor class is 100/10, and your alignment is 0."`
- Produces: `PlayerStats.parse_score(text: str) -> dict[str, int] | None` with keys `hp`, `max_hp`, `mana`, `max_mana`, `move`, `max_move`, or `None` if the text doesn't match. Used by Task 3/4's `PlayerTracker.update_stats()` wiring.

**Note on scope:** the captured `score` text has no level or gold in it — those live behind separate `check` kinds (`"levels"`, `"gold"` are already distinct enum values in `tools/mud.py`'s `_INFO_SELF`). Parsing those is out of scope for this plan; the Overview tab's player card shows HP/mana/move only. Do not invent a level/gold regex against unverified text — that would be guessing at a format nobody has confirmed.

- [ ] **Step 1: Write the failing tests**

```python
# week2_capable/agent-exp/tests/test_player_stats.py
from boukensha.memory.player_stats import PlayerStats


def test_parse_score_extracts_hp_mana_move():
    text = (
        "You have 20(20) hit, 100(100) mana and 85(85) movement points.\n"
        "Your armor class is 100/10, and your alignment is 0.\n"
    )
    assert PlayerStats.parse_score(text) == {
        "hp": 20, "max_hp": 20,
        "mana": 100, "max_mana": 100,
        "move": 85, "max_move": 85,
    }


def test_parse_score_handles_damaged_player():
    text = "You have 7(20) hit, 40(100) mana and 85(85) movement points.\n"
    stats = PlayerStats.parse_score(text)
    assert stats["hp"] == 7
    assert stats["max_hp"] == 20
    assert stats["mana"] == 40


def test_parse_score_returns_none_for_unrelated_text():
    assert PlayerStats.parse_score("You are carrying nothing.") is None


def test_parse_score_returns_none_for_empty_string():
    assert PlayerStats.parse_score("") is None
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `cd week2_capable/agent-exp && .venv/bin/python -m pytest tests/test_player_stats.py -v`
Expected: FAIL with `ModuleNotFoundError: No module named 'boukensha.memory.player_stats'`

- [ ] **Step 3: Write the implementation**

```python
# week2_capable/agent-exp/src/boukensha/memory/player_stats.py
"""Parses the MUD's 'score' command output into structured player stats."""

from __future__ import annotations

import re

_SCORE_RE = re.compile(
    r"You have (\d+)\((\d+)\) hit,\s*(\d+)\((\d+)\) mana and\s*(\d+)\((\d+)\) movement points",
    re.IGNORECASE,
)


class PlayerStats:
    @staticmethod
    def parse_score(text: str) -> dict[str, int] | None:
        m = _SCORE_RE.search(text)
        if not m:
            return None
        hp, max_hp, mana, max_mana, move, max_move = (int(g) for g in m.groups())
        return {
            "hp": hp, "max_hp": max_hp,
            "mana": mana, "max_mana": max_mana,
            "move": move, "max_move": max_move,
        }
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `cd week2_capable/agent-exp && .venv/bin/python -m pytest tests/test_player_stats.py -v`
Expected: PASS (4 tests)

- [ ] **Step 5: Commit**

```bash
git add week2_capable/agent-exp/src/boukensha/memory/player_stats.py week2_capable/agent-exp/tests/test_player_stats.py
git commit -m "feat: parse HP/mana/move out of the MUD score command"
```

---

### Task 3: Persist parsed stats on PlayerTracker

**Files:**
- Modify: `week2_capable/agent-exp/src/boukensha/memory/player_tracker.py`
- Test: `week2_capable/agent-exp/tests/test_player_tracker.py` (append)

**Interfaces:**
- Consumes: the `stats` dict shape produced by `PlayerStats.parse_score()` (Task 2) — treated opaquely, just merged in and JSON-serialized.
- Produces: `PlayerTracker.update_stats(name: str, stats: dict[str, Any]) -> None`, storing under a `"stats"` key alongside the existing `"stats_updated_at"` timestamp. `PlayerTracker.update()` (existing, for room position) is changed to merge rather than overwrite, so calling `update()` after `update_stats()` (or vice versa) never drops the other's data. Read via existing `read_all()`. Consumed by Task 4 (`tools/mud.py`) and Task 5 (`/api/overview`).

- [ ] **Step 1: Write the failing tests**

Append to `week2_capable/agent-exp/tests/test_player_tracker.py`:

```python
def test_update_stats_records_stats_for_new_player(tmp_path):
    tracker = PlayerTracker(tmp_path)
    tracker.update_stats("Hero", {"hp": 20, "max_hp": 20})
    data = tracker.read_all()
    assert data["Hero"]["stats"] == {"hp": 20, "max_hp": 20}
    assert "stats_updated_at" in data["Hero"]


def test_update_stats_preserves_existing_position(tmp_path):
    tracker = PlayerTracker(tmp_path)
    tracker.update("Hero", "abc123", "Temple Square")
    tracker.update_stats("Hero", {"hp": 20, "max_hp": 20})
    data = tracker.read_all()
    assert data["Hero"]["room_hash"] == "abc123"
    assert data["Hero"]["stats"]["hp"] == 20


def test_update_preserves_existing_stats(tmp_path):
    tracker = PlayerTracker(tmp_path)
    tracker.update_stats("Hero", {"hp": 20, "max_hp": 20})
    tracker.update("Hero", "abc123", "Temple Square")
    data = tracker.read_all()
    assert data["Hero"]["stats"] == {"hp": 20, "max_hp": 20}
    assert data["Hero"]["room_hash"] == "abc123"
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `cd week2_capable/agent-exp && .venv/bin/python -m pytest tests/test_player_tracker.py -v`
Expected: FAIL — `test_update_stats_*` fail with `AttributeError: 'PlayerTracker' object has no attribute 'update_stats'`; `test_update_preserves_existing_stats` fails because `update()` currently overwrites the whole record.

- [ ] **Step 3: Modify the implementation**

Replace the `update` method and add `update_stats` in `week2_capable/agent-exp/src/boukensha/memory/player_tracker.py`:

```python
    def update(self, name: str, room_hash: str, title: str) -> None:
        data = self.read_all()
        existing = data.get(name, {})
        prev = existing.get("room_hash")
        data[name] = {
            **existing,
            "room_hash": room_hash,
            "title": title,
            "updated_at": datetime.now(timezone.utc).isoformat(),
            "prev_room_hash": prev if prev and prev != room_hash else existing.get("prev_room_hash"),
        }
        self._write(data)

    def update_stats(self, name: str, stats: dict[str, Any]) -> None:
        data = self.read_all()
        existing = data.get(name, {})
        data[name] = {
            **existing,
            "stats": stats,
            "stats_updated_at": datetime.now(timezone.utc).isoformat(),
        }
        self._write(data)
```

This replaces the existing `update` method in place (spreading `**existing` first, same as before, just with the added spread so unrelated keys like `stats` survive). `update_stats` is new, added right after it.

- [ ] **Step 4: Run tests to verify they pass**

Run: `cd week2_capable/agent-exp && .venv/bin/python -m pytest tests/test_player_tracker.py -v`
Expected: PASS (all tests, old and new — confirm no regressions in the pre-existing `test_prev_room_hash_*` tests)

- [ ] **Step 5: Commit**

```bash
git add week2_capable/agent-exp/src/boukensha/memory/player_tracker.py week2_capable/agent-exp/tests/test_player_tracker.py
git commit -m "feat: add PlayerTracker.update_stats, merge instead of overwrite on update"
```

---

### Task 4: Wire score parsing into the `check` MUD tool

**Files:**
- Modify: `week2_capable/agent-exp/src/boukensha/tools/mud.py`
- Test: `week2_capable/agent-exp/tests/test_tools_mud.py` (append)

**Interfaces:**
- Consumes: `PlayerStats.parse_score()` (Task 2), `PlayerTracker.update_stats()` (Task 3). Both already importable from `boukensha.memory.player_stats` / `boukensha.memory.player_tracker`.
- Produces: no new public interface — this task only changes the `check` tool's runtime behavior. `tracker` and `name` are already in scope inside `Mud._register_with_session` (see existing code: `tracker = PlayerTracker(memory_dir) if memory_dir is not None else None`).

- [ ] **Step 1: Write the failing tests**

Append to `week2_capable/agent-exp/tests/test_tools_mud.py`:

```python
def test_check_score_persists_stats_to_player_tracker(tmp_path):
    registry = _make_registry()
    mock_session = MagicMock()
    mock_session.is_open = True
    mock_session.drain.return_value = ""
    mock_session.read_until_prompt.return_value = (
        "You have 20(20) hit, 100(100) mana and 85(85) movement points. > "
    )
    Mud._register_with_session(
        registry, mock_session, name="Tester", password="secret", memory_dir=tmp_path
    )
    registry.dispatch("check", {"kind": "score"})

    from boukensha.memory.player_tracker import PlayerTracker
    data = PlayerTracker(tmp_path).read_all()
    assert data["Tester"]["stats"] == {
        "hp": 20, "max_hp": 20,
        "mana": 100, "max_mana": 100,
        "move": 85, "max_move": 85,
    }


def test_check_non_score_kind_does_not_touch_player_tracker(tmp_path):
    registry = _make_registry()
    mock_session = MagicMock()
    mock_session.is_open = True
    mock_session.drain.return_value = ""
    mock_session.read_until_prompt.return_value = "You aren't carrying anything. > "
    Mud._register_with_session(
        registry, mock_session, name="Tester", password="secret", memory_dir=tmp_path
    )
    registry.dispatch("check", {"kind": "inventory"})

    from boukensha.memory.player_tracker import PlayerTracker
    assert PlayerTracker(tmp_path).read_all() == {}


def test_check_score_without_memory_dir_does_not_crash():
    """check(kind='score') must still work when the tool is registered
    without a memory_dir (tracker is None) — e.g. in older callers/tests
    that don't pass it."""
    registry = _make_registry()
    mock_session = MagicMock()
    mock_session.is_open = True
    mock_session.drain.return_value = ""
    mock_session.read_until_prompt.return_value = (
        "You have 20(20) hit, 100(100) mana and 85(85) movement points. > "
    )
    Mud._register_with_session(registry, mock_session, name="Tester", password="secret")
    result = registry.dispatch("check", {"kind": "score"})
    assert "20(20) hit" in result
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `cd week2_capable/agent-exp && .venv/bin/python -m pytest tests/test_tools_mud.py -v -k "check_score or check_non_score"`
Expected: FAIL — `test_check_score_persists_stats_to_player_tracker` fails because `PlayerTracker(tmp_path).read_all()` is `{}` (nothing wired up yet); the other two currently pass already (establishing they must keep passing).

- [ ] **Step 3: Modify the implementation**

In `week2_capable/agent-exp/src/boukensha/tools/mud.py`, add the import near the other `boukensha.memory.*` imports at the top of the file:

```python
from boukensha.memory.player_stats import PlayerStats
```

Inside `Mud._register_with_session`, near `_look_and_record` (which already closes over `session`/`tracker`/`name`), add a new closure:

```python
        def _check_and_record(kind: str) -> str:
            raw = _check_info(session, kind)
            if tracker is not None and kind.strip().lower() == "score" and not raw.startswith("error:"):
                stats = PlayerStats.parse_score(raw)
                if stats:
                    tracker.update_stats(name, stats)
            return raw
```

Then change the `check` tool's registration block from:

```python
            block=lambda kind, **_: _check_info(session, kind),
```

to:

```python
            block=lambda kind, **_: _check_and_record(kind),
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `cd week2_capable/agent-exp && .venv/bin/python -m pytest tests/test_tools_mud.py -v`
Expected: PASS (full file — confirm no regressions in unrelated `check`/`score` tests like `test_send_recovers_from_main_menu_and_resends_command`)

- [ ] **Step 5: Commit**

```bash
git add week2_capable/agent-exp/src/boukensha/tools/mud.py week2_capable/agent-exp/tests/test_tools_mud.py
git commit -m "feat: persist parsed score stats via PlayerTracker on check(kind=score)"
```

---

### Task 5: `/api/overview` route

**Files:**
- Modify: `week2_capable/agent-exp/src/boukensha/dashboard/app.py`
- Modify: `week2_capable/agent-exp/DASHBOARD.md`
- Test: `week2_capable/agent-exp/tests/test_dashboard_api.py` (append)

**Interfaces:**
- Consumes: `frontier_stats`/`entity_stats` (Task 1, `boukensha.memory.world_stats`), `PlayerTracker.read_all()` (Task 3, already used by `/api/players`), `WorldGraph` (already used by `/api/map`).
- Produces: `GET /api/overview` → JSON `{"rooms_known": int, "frontier": {...}, "entities": {...}, "players": [...]}`, where each player entry has the same shape as `/api/players` (`name`, `room_hash`, `title`, `updated_at`, `prev_room_hash`, plus now optionally `stats`/`stats_updated_at`). Consumed by Task 6's `loadOverview()` JS.

- [ ] **Step 1: Write the failing tests**

Append to `week2_capable/agent-exp/tests/test_dashboard_api.py`:

```python
def test_api_overview_returns_zero_stats_when_no_data(tmp_path):
    app, _ = _make_app(tmp_path)
    with app.test_client() as c:
        r = c.get("/api/overview")
        assert r.status_code == 200
        data = json.loads(r.data)
        assert data["rooms_known"] == 0
        assert data["frontier"] == {"known_exits": 0, "walked": 0, "frontier": 0}
        assert data["entities"] == {"mobs": 0, "objects": 0, "total": 0}
        assert data["players"] == []


def test_api_overview_reports_rooms_and_players(tmp_path):
    from boukensha.memory.world_graph import WorldGraph
    from boukensha.memory.room_memory import RoomMemory
    from boukensha.memory.player_tracker import PlayerTracker

    memory_dir = tmp_path / "memory"
    mem = RoomMemory(memory_dir)
    graph = WorldGraph(memory_dir)
    room = {"title": "Main Street", "description": "d", "exits": {"north": "..."}, "npcs": [], "items": []}
    h, _ = mem.record(room)
    graph.add_room(h, "Main Street")
    graph.save()

    tracker = PlayerTracker(memory_dir)
    tracker.update("Hero", h, "Main Street")
    tracker.update_stats("Hero", {"hp": 20, "max_hp": 20, "mana": 100, "max_mana": 100, "move": 85, "max_move": 85})

    app, _ = _make_app(tmp_path)
    with app.test_client() as c:
        r = c.get("/api/overview")
        data = json.loads(r.data)
        assert data["rooms_known"] == 1
        assert data["frontier"] == {"known_exits": 1, "walked": 0, "frontier": 1}
        assert data["players"][0]["name"] == "Hero"
        assert data["players"][0]["stats"]["hp"] == 20
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `cd week2_capable/agent-exp && .venv/bin/python -m pytest tests/test_dashboard_api.py -v -k overview`
Expected: FAIL with 404 (`assert r.status_code == 200` fails, route doesn't exist yet)

- [ ] **Step 3: Write the implementation**

In `week2_capable/agent-exp/src/boukensha/dashboard/app.py`, add a new route after `api_players` (following the exact style of the other routes — local imports inside the function body, matching `api_map`/`api_players`):

```python
    @app.route("/api/overview")
    def api_overview():
        from boukensha.memory.world_graph import WorldGraph
        from boukensha.memory.room_memory import RoomMemory
        from boukensha.memory.world_stats import frontier_stats, entity_stats
        from boukensha.memory.player_tracker import PlayerTracker

        g = WorldGraph(memory_path)
        g.load()
        mem = RoomMemory(memory_path)
        players = [
            {"name": name, **info}
            for name, info in PlayerTracker(memory_path).read_all().items()
        ]
        return jsonify({
            "rooms_known": g.graph.number_of_nodes(),
            "frontier": frontier_stats(g, mem),
            "entities": entity_stats(g, mem),
            "players": players,
        })
```

Also add documentation to `week2_capable/agent-exp/DASHBOARD.md`, in the same format as the existing "### Map" section (insert a new "### Overview" section — since Overview becomes the first/default tab, put it right after the `## Tabs` heading, before `### Live`):

```markdown
### Overview

Landing tab. Summary cards for rooms known, frontier exits (known-but-unwalked), and unique entities (mobs/objects) seen across every recorded room, plus each tracked player's last-known HP/mana/move and current location (with where they came from).

Data endpoint: `GET /api/overview`

\`\`\`json
{
  "rooms_known": 26,
  "frontier": {"known_exits": 73, "walked": 32, "frontier": 41},
  "entities": {"mobs": 16, "objects": 3, "total": 19},
  "players": [
    {
      "name": "Hero",
      "room_hash": "abc123",
      "title": "Temple Square",
      "updated_at": "2026-07-27T22:10:00+00:00",
      "prev_room_hash": "def456",
      "stats": {"hp": 20, "max_hp": 20, "mana": 100, "max_mana": 100, "move": 85, "max_move": 85},
      "stats_updated_at": "2026-07-27T22:10:05+00:00"
    }
  ]
}
\`\`\`

`stats`/`stats_updated_at` are only present once the agent has called `check(kind="score")` at least once — they reflect what the agent last saw, not necessarily the player's true current state (see the CDC/journal caveat below: this is a snapshot of agent-observed state, not ground truth).
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `cd week2_capable/agent-exp && .venv/bin/python -m pytest tests/test_dashboard_api.py -v`
Expected: PASS (full file — confirm no regressions in the existing `/api/map`, `/api/players`, `/api/goal`, `/api/sessions*` tests)

- [ ] **Step 5: Commit**

```bash
git add week2_capable/agent-exp/src/boukensha/dashboard/app.py week2_capable/agent-exp/DASHBOARD.md week2_capable/agent-exp/tests/test_dashboard_api.py
git commit -m "feat: add /api/overview route for the dashboard Overview tab"
```

---

### Task 6: Overview tab frontend

**Files:**
- Modify: `week2_capable/agent-exp/src/boukensha/dashboard/templates/index.html`
- Modify: `week2_capable/agent-exp/src/boukensha/dashboard/static/app.js`
- Modify: `week2_capable/agent-exp/src/boukensha/dashboard/static/style.css`
- Test: `week2_capable/agent-exp/tests/test_dashboard_api.py` (append — a template-rendering regression check; no test framework for the JS itself, verified manually per Step 5 below)

**Interfaces:**
- Consumes: `GET /api/overview` (Task 5) — exact JSON shape documented above.
- Produces: nothing consumed by later tasks — this is the last task in the plan.

- [ ] **Step 1: Write the failing test**

Append to `week2_capable/agent-exp/tests/test_dashboard_api.py`:

```python
def test_index_includes_overview_tab(tmp_path):
    app, _ = _make_app(tmp_path)
    with app.test_client() as c:
        r = c.get("/")
        html = r.data.decode()
        assert 'data-tab="overview"' in html
        assert 'id="tab-overview"' in html
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd week2_capable/agent-exp && .venv/bin/python -m pytest tests/test_dashboard_api.py -v -k test_index_includes_overview_tab`
Expected: FAIL — `data-tab="overview"` not present in current `index.html`

- [ ] **Step 3: Modify `templates/index.html`**

Replace the `<nav id="tabs">` block:

```html
  <nav id="tabs">
    <button class="tab-btn active" data-tab="overview">Overview</button>
    <button class="tab-btn" data-tab="live">Live</button>
    <button class="tab-btn" data-tab="map">Map</button>
    <button class="tab-btn" data-tab="waterfall">Waterfall</button>
    <button class="tab-btn" data-tab="goals">Goals</button>
    <button class="tab-btn" data-tab="sessions">Sessions</button>
  </nav>

  <section id="tab-overview" class="tab-pane active">
    <div id="overview-grid" class="overview-grid"></div>
    <h2 class="overview-heading">Player</h2>
    <div id="overview-players"></div>
  </section>
```

And change the existing `Live` section (currently `active` by default) to no longer be active:

```html
  <section id="tab-live" class="tab-pane">
    <div id="live-log"></div>
  </section>
```

(i.e. remove `active` from both the `Live` button and `#tab-live` section, since `overview` is now the default tab.)

- [ ] **Step 4: Modify `static/app.js`**

Add `overview` to the tab-click routing (in the existing `document.querySelectorAll('.tab-btn').forEach(...)` block), right alongside the existing `if (btn.dataset.tab === 'map') ...` lines:

```javascript
    if (btn.dataset.tab === 'overview') loadOverview();
    if (btn.dataset.tab === 'map') window.loadMap && window.loadMap();
```

Add the `loadOverview` function (place it near `loadGoals`/`loadSessions`, same style):

```javascript
// Overview tab
async function loadOverview() {
  const r = await fetch('/api/overview');
  const data = await r.json();

  const grid = document.getElementById('overview-grid');
  grid.innerHTML = [
    ['Rooms known', data.rooms_known],
    ['Frontier', `${data.frontier.frontier} of ${data.frontier.known_exits} exits · ${data.frontier.walked} walked`],
    ['Entities', `${data.entities.total} · ${data.entities.mobs} mobs · ${data.entities.objects} objects`],
  ].map(([label, value]) =>
    `<div class="overview-card"><div class="overview-card-label">${escapeHtml(label)}</div><div class="overview-card-value">${escapeHtml(String(value))}</div></div>`
  ).join('');

  const playersEl = document.getElementById('overview-players');
  if (!data.players.length) {
    playersEl.innerHTML = '<p class="overview-empty">No players tracked yet.</p>';
    return;
  }
  playersEl.innerHTML = data.players.map(p => {
    const stats = p.stats || {};
    const statLine = 'hp' in stats
      ? `${stats.hp}/${stats.max_hp} hp · ${stats.mana}/${stats.max_mana} mana · ${stats.move}/${stats.max_move} move`
      : 'stats not yet checked';
    const from = p.prev_room_hash ? ` — came from ${escapeHtml(p.prev_room_hash)}` : '';
    return `<div class="overview-card overview-player">
      <div class="overview-card-label">${escapeHtml(p.name)}</div>
      <div class="overview-card-value">${escapeHtml(statLine)}</div>
      <div class="overview-location">${escapeHtml(p.title || '')}${from}</div>
    </div>`;
  }).join('');
}

loadOverview();
```

Place the `loadOverview();` call (module-level, runs once on page load) right after the function definition, in the same spot the existing `const es = new EventSource('/events');` block runs unconditionally at module scope.

- [ ] **Step 5: Modify `static/style.css`**

Append:

```css
.overview-grid { display: grid; grid-template-columns: repeat(auto-fill, minmax(160px, 1fr)); gap: 12px; margin-bottom: 20px; }
.overview-card { background: #1a1a1a; border: 1px solid #333; border-radius: 6px; padding: 12px; }
.overview-card-label { color: #888; font-size: 11px; text-transform: uppercase; letter-spacing: 0.05em; margin-bottom: 6px; }
.overview-card-value { color: #fff; font-size: 20px; font-weight: bold; }
.overview-heading { font-size: 14px; color: #888; text-transform: uppercase; letter-spacing: 0.05em; margin-bottom: 10px; }
.overview-player .overview-card-value { font-size: 14px; font-weight: normal; }
.overview-location { color: #666; font-size: 12px; margin-top: 6px; }
.overview-empty { color: #666; font-size: 13px; }
```

- [ ] **Step 6: Run test to verify it passes**

Run: `cd week2_capable/agent-exp && .venv/bin/python -m pytest tests/test_dashboard_api.py -v`
Expected: PASS (full file, including the new `test_index_includes_overview_tab`)

- [ ] **Step 7: Manual verification in a browser**

The JS/CSS changes have no automated test coverage — verify by hand:

```bash
cd week2_capable/agent-exp
.venv/bin/python bin/boukensha --web --port 4568
```

Open `http://localhost:4568`. Confirm:
- Overview is the active tab on load, showing 4 cards (or fewer if no data yet) and a Player section.
- Clicking between tabs and back to Overview re-fetches and re-renders without errors (check the browser console).
- If `.boukensha/memory/` has real data (rooms, players), the numbers are non-zero and match what `/api/map` / `/api/players` show elsewhere.

- [ ] **Step 8: Commit**

```bash
git add week2_capable/agent-exp/src/boukensha/dashboard/templates/index.html week2_capable/agent-exp/src/boukensha/dashboard/static/app.js week2_capable/agent-exp/src/boukensha/dashboard/static/style.css week2_capable/agent-exp/tests/test_dashboard_api.py
git commit -m "feat: add Overview tab UI to the dashboard"
```
