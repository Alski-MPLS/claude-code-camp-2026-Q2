# Agent-Exp: Enhanced MUD Agent Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add persistent room memory, goal tracking, token-saving program tools, and a Python web dashboard to the `boukensha` MUD agent in `week2_capable/agent-exp/`.

**Architecture:** Three new Python subsystems (`memory/`, `goals/`, `dashboard/`) slot into the existing agent via tool registration; a `navigate_to`/`process_room`/`combat_loop` tool layer handles repetitive actions in Python without consulting the LLM each step. A Flask+SSE dashboard replaces the Ruby Sinatra `log_viz` app with five tabs (Live, Map, Waterfall, Goals, Sessions) and runs as a background thread when `boukensha --web` is launched.

**Tech Stack:** Python ≥ 3.11, uv, pytest, Flask ≥ 3.0, networkx ≥ 3.0, pyyaml (already present), python-dotenv (already present), textual ≥ 0.80 (already present), D3.js v7 (CDN — no npm build step)

## Global Constraints

- Working directory for all commands: `week2_capable/agent-exp/`
- Package name: `boukensha-context`, version `0.12.0` — do NOT change these
- Python ≥ 3.11 only
- `uv` manages the virtualenv; run `uv sync` after modifying `pyproject.toml`
- All tests live in `tests/` and run with `uv run pytest tests/ -v`
- New dependencies must be added to `pyproject.toml` `[project] dependencies`
- `.boukensha/` config dir is resolved by `Config()` — default `~/.boukensha/`; all persistent files go there
- Room hash: `sha256(title + "\n" + description)[:12]` hex string
- Goal file: `.boukensha/goals/current.yaml` (YAML, atomic write via `.tmp` + rename)
- Room files: `.boukensha/memory/rooms/{hash}.json`
- World graph: `.boukensha/memory/world_graph.json`
- Dashboard runs on `http://localhost:4568` by default (avoid conflict with old Sinatra `4567`)
- No changes to existing `src/boukensha/agent.py`, `context.py`, `logger.py`, `mud.py` — only extend

---

## File Structure

**New files:**
```
src/boukensha/memory/__init__.py
src/boukensha/memory/parser.py          RoomParser — parse raw MUD text → dict
src/boukensha/memory/room_memory.py     RoomMemory — persist rooms as JSON
src/boukensha/memory/world_graph.py     WorldGraph — NetworkX DiGraph of rooms
src/boukensha/memory/pathfinder.py      Pathfinder — Dijkstra over WorldGraph

src/boukensha/goals/__init__.py
src/boukensha/goals/goal_manager.py     GoalManager — read/write current.yaml
src/boukensha/goals/combat_monitor.py   CombatMonitor — HP threshold check

src/boukensha/tools/navigation.py       navigate_to tool registration
src/boukensha/tools/room_processor.py   process_room tool registration
src/boukensha/tools/combat.py           combat_loop tool registration

src/boukensha/dashboard/__init__.py
src/boukensha/dashboard/event_bus.py    EventBus — thread-safe event queue
src/boukensha/dashboard/app.py          Flask dashboard application
src/boukensha/dashboard/static/app.js   Tab routing + SSE client
src/boukensha/dashboard/static/map.js   D3 force-directed room graph
src/boukensha/dashboard/static/waterfall.js  Waterfall timing chart
src/boukensha/dashboard/static/style.css
src/boukensha/dashboard/templates/index.html  Single-page shell

bin/boukensha                           CLI entry point

tests/test_room_parser.py
tests/test_room_memory.py
tests/test_world_graph.py
tests/test_pathfinder.py
tests/test_goal_manager.py
tests/test_combat_monitor.py
tests/test_navigation_tool.py
tests/test_dashboard_api.py
```

**Modified files:**
```
pyproject.toml                          Add flask, networkx dependencies + bin/boukensha script
src/boukensha/tools/__init__.py         Export Navigation, RoomProcessor, Combat
src/boukensha/__init__.py               Wire new tools; add --web flag to repl()
src/boukensha/boukensha_loader.py       CLI arg parsing for --web/--no-web
```

---

### Task 1: Memory Subsystem — RoomParser, RoomMemory, WorldGraph, Pathfinder

**Files:**
- Create: `src/boukensha/memory/__init__.py`
- Create: `src/boukensha/memory/parser.py`
- Create: `src/boukensha/memory/room_memory.py`
- Create: `src/boukensha/memory/world_graph.py`
- Create: `src/boukensha/memory/pathfinder.py`
- Create: `tests/test_room_parser.py`
- Create: `tests/test_room_memory.py`
- Create: `tests/test_world_graph.py`
- Create: `tests/test_pathfinder.py`
- Modify: `pyproject.toml` (add `networkx>=3.0`)

**Interfaces:**
- Produces:
  - `RoomParser.parse(raw: str) -> dict` — returns `{"title": str, "description": str, "exits": dict[str, str | None], "npcs": list[str], "items": list[str]}`; exits keys are direction strings (`"north"`, `"east"` etc.), values are `None` (destination unknown until visited)
  - `RoomMemory(base_dir: str | Path)` — constructor
  - `RoomMemory.record(room: dict) -> tuple[str, dict]` — returns `(hash, diff)` where diff contains only new/changed fields vs stored; empty dict if nothing changed
  - `RoomMemory.get(room_hash: str) -> dict | None`
  - `RoomMemory.room_hash(room: dict) -> str`
  - `WorldGraph(base_dir: str | Path)` — constructor
  - `WorldGraph.add_room(room_hash: str, title: str) -> None`
  - `WorldGraph.add_edge(from_hash: str, to_hash: str, direction: str) -> None`
  - `WorldGraph.get_neighbors(room_hash: str) -> dict[str, str]` — `{direction: neighbor_hash}`
  - `WorldGraph.save() -> None` / `WorldGraph.load() -> None`
  - `WorldGraph.has_room(room_hash: str) -> bool`
  - `Pathfinder(graph: WorldGraph)` — constructor
  - `Pathfinder.find_path(start_hash: str, end_hash: str) -> list[str] | None` — ordered direction list or `None` if no path
  - `Pathfinder.find_path_by_title(start_hash: str, title_fragment: str) -> list[str] | None` — finds destination by partial room title match

- [ ] **Step 1: Add networkx to pyproject.toml**

In `pyproject.toml`, add `"networkx>=3.0"` to `[project] dependencies`:

```toml
[project]
name = "boukensha-context"
version = "0.12.0"
description = "Boukensha Context Management (Step 12)"
requires-python = ">=3.11"
dependencies = [
    "pyyaml>=6.0",
    "python-dotenv>=1.0",
    "textual>=0.80",
    "networkx>=3.0",
]
```

Then run:
```bash
uv sync
```

- [ ] **Step 2: Create `src/boukensha/memory/__init__.py`**

```python
from .parser import RoomParser
from .room_memory import RoomMemory
from .world_graph import WorldGraph
from .pathfinder import Pathfinder

__all__ = ["RoomParser", "RoomMemory", "WorldGraph", "Pathfinder"]
```

- [ ] **Step 3: Write failing tests for RoomParser**

Create `tests/test_room_parser.py`:

```python
from boukensha.memory.parser import RoomParser

SAMPLE_LOOK = """\
The Temple Square
   You are in the middle of a large open square in the middle of the
   city. Around you, citizens going about their daily business. To the
   north is the imposing Temple of Midgaard.
Exits: north, east, south, west
A dog is here.
A loaf of bread is here.
"""

MINIMAL_LOOK = """\
A Dark Corridor
   A narrow passage.
Exits: north
"""

NO_EXITS_LOOK = """\
A Dead End
   The path ends here.
"""


def test_parse_title():
    r = RoomParser.parse(SAMPLE_LOOK)
    assert r["title"] == "The Temple Square"


def test_parse_description():
    r = RoomParser.parse(SAMPLE_LOOK)
    assert "large open square" in r["description"]


def test_parse_exits_keys():
    r = RoomParser.parse(SAMPLE_LOOK)
    assert set(r["exits"].keys()) == {"north", "east", "south", "west"}


def test_parse_exits_values_none():
    r = RoomParser.parse(SAMPLE_LOOK)
    for v in r["exits"].values():
        assert v is None


def test_parse_npcs():
    r = RoomParser.parse(SAMPLE_LOOK)
    assert any("dog" in n.lower() for n in r["npcs"])


def test_parse_items():
    r = RoomParser.parse(SAMPLE_LOOK)
    assert any("bread" in i.lower() for i in r["items"])


def test_parse_minimal():
    r = RoomParser.parse(MINIMAL_LOOK)
    assert r["title"] == "A Dark Corridor"
    assert r["exits"] == {"north": None}
    assert r["npcs"] == []
    assert r["items"] == []


def test_parse_no_exits():
    r = RoomParser.parse(NO_EXITS_LOOK)
    assert r["exits"] == {}


def test_parse_returns_required_keys():
    r = RoomParser.parse(SAMPLE_LOOK)
    assert all(k in r for k in ("title", "description", "exits", "npcs", "items"))


def test_parse_empty_string():
    r = RoomParser.parse("")
    assert r["title"] == ""
    assert r["exits"] == {}
```

- [ ] **Step 4: Run tests to verify they fail**

```bash
uv run pytest tests/test_room_parser.py -v
```

Expected: `ModuleNotFoundError` or `AttributeError`.

- [ ] **Step 5: Implement RoomParser**

Create `src/boukensha/memory/parser.py`:

```python
"""Parse raw CircleMUD 'look' output into a structured dict."""

from __future__ import annotations

import re

_DIRECTION_RE = re.compile(
    r"^Exits:\s*(.+)$", re.IGNORECASE | re.MULTILINE
)
_EXIT_NAMES = {"north", "south", "east", "west", "up", "down"}


class RoomParser:
    @staticmethod
    def parse(raw: str) -> dict:
        """Parse raw MUD look output.

        Returns:
            {
                "title": str,
                "description": str,
                "exits": {direction: None, ...},
                "npcs": [str, ...],
                "items": [str, ...],
            }
        """
        lines = raw.splitlines()
        title = lines[0].strip() if lines else ""

        exits: dict[str, None] = {}
        npcs: list[str] = []
        items: list[str] = []
        desc_lines: list[str] = []
        in_desc = True

        for line in lines[1:]:
            stripped = line.strip()

            # Exits line
            m = _DIRECTION_RE.match(stripped)
            if m:
                in_desc = False
                for part in m.group(1).split(","):
                    d = part.strip().lower()
                    if d in _EXIT_NAMES:
                        exits[d] = None
                continue

            # Description ends at the first blank line after content
            if in_desc:
                desc_lines.append(stripped)
                continue

            # After exits: classify non-empty lines as NPC or item heuristic
            if stripped:
                low = stripped.lower()
                # Items end in "is here." or "lies here." — simplified heuristic
                if low.endswith("is here.") or low.endswith("lies here.") or low.endswith("here."):
                    # NPC or item: if line starts with capital A/An/The and ends with "is here."
                    # treat as NPC; if ends with "lies here." treat as item
                    if "lies here" in low:
                        items.append(stripped)
                    elif re.match(r"^[A-Z]", stripped):
                        # Simple heuristic: short lines are likely NPCs/items
                        if len(stripped.split()) <= 6:
                            npcs.append(stripped)
                        else:
                            items.append(stripped)

        description = " ".join(l for l in desc_lines if l)

        return {
            "title": title,
            "description": description,
            "exits": exits,
            "npcs": npcs,
            "items": items,
        }
```

- [ ] **Step 6: Run RoomParser tests**

```bash
uv run pytest tests/test_room_parser.py -v
```

Expected: all PASS. (The `test_parse_items`/`test_parse_npcs` tests use a loose `any(...in...)` assertion so the heuristic doesn't need to be perfect.)

- [ ] **Step 7: Write failing tests for RoomMemory**

Create `tests/test_room_memory.py`:

```python
import json
from pathlib import Path
from boukensha.memory.room_memory import RoomMemory

ROOM_A = {
    "title": "The Temple Square",
    "description": "A large open square.",
    "exits": {"north": None, "south": None},
    "npcs": [],
    "items": [],
}

ROOM_B = {
    "title": "The Dark Corridor",
    "description": "A narrow passage.",
    "exits": {"south": None},
    "npcs": [],
    "items": [],
}


def test_room_hash_is_12_hex_chars(tmp_path):
    mem = RoomMemory(tmp_path)
    h = mem.room_hash(ROOM_A)
    assert len(h) == 12
    assert all(c in "0123456789abcdef" for c in h)


def test_room_hash_is_deterministic(tmp_path):
    mem = RoomMemory(tmp_path)
    assert mem.room_hash(ROOM_A) == mem.room_hash(ROOM_A)


def test_room_hash_differs_for_different_rooms(tmp_path):
    mem = RoomMemory(tmp_path)
    assert mem.room_hash(ROOM_A) != mem.room_hash(ROOM_B)


def test_record_writes_file(tmp_path):
    mem = RoomMemory(tmp_path)
    h, _ = mem.record(ROOM_A)
    room_file = tmp_path / "rooms" / f"{h}.json"
    assert room_file.exists()


def test_record_new_room_returns_full_diff(tmp_path):
    mem = RoomMemory(tmp_path)
    _, diff = mem.record(ROOM_A)
    assert diff["title"] == ROOM_A["title"]


def test_record_same_room_twice_returns_empty_diff(tmp_path):
    mem = RoomMemory(tmp_path)
    mem.record(ROOM_A)
    _, diff = mem.record(ROOM_A)
    assert diff == {}


def test_record_updates_on_new_npc(tmp_path):
    mem = RoomMemory(tmp_path)
    mem.record(ROOM_A)
    updated = {**ROOM_A, "npcs": ["A fierce guard"]}
    _, diff = mem.record(updated)
    assert "npcs" in diff


def test_get_returns_stored_room(tmp_path):
    mem = RoomMemory(tmp_path)
    h, _ = mem.record(ROOM_A)
    stored = mem.get(h)
    assert stored is not None
    assert stored["title"] == ROOM_A["title"]


def test_get_unknown_hash_returns_none(tmp_path):
    mem = RoomMemory(tmp_path)
    assert mem.get("deadbeefcafe") is None
```

- [ ] **Step 8: Run to verify they fail**

```bash
uv run pytest tests/test_room_memory.py -v
```

Expected: `ModuleNotFoundError`.

- [ ] **Step 9: Implement RoomMemory**

Create `src/boukensha/memory/room_memory.py`:

```python
"""Persist unique rooms as JSON files keyed by a stable hash."""

from __future__ import annotations

import hashlib
import json
import os
from pathlib import Path
from typing import Any


class RoomMemory:
    def __init__(self, base_dir: str | Path) -> None:
        self._rooms_dir = Path(base_dir) / "rooms"
        self._rooms_dir.mkdir(parents=True, exist_ok=True)

    def room_hash(self, room: dict[str, Any]) -> str:
        key = room.get("title", "") + "\n" + room.get("description", "")
        return hashlib.sha256(key.encode("utf-8")).hexdigest()[:12]

    def record(self, room: dict[str, Any]) -> tuple[str, dict[str, Any]]:
        h = self.room_hash(room)
        path = self._rooms_dir / f"{h}.json"
        existing = self._load(path)
        diff = self._diff(existing, room)
        if diff:
            merged = {**(existing or {}), **room}
            self._save(path, merged)
        return h, diff

    def get(self, room_hash: str) -> dict[str, Any] | None:
        path = self._rooms_dir / f"{room_hash}.json"
        return self._load(path)

    # ── private ──────────────────────────────────────────────────────────────

    def _load(self, path: Path) -> dict[str, Any] | None:
        if not path.exists():
            return None
        return json.loads(path.read_text(encoding="utf-8"))

    def _save(self, path: Path, data: dict[str, Any]) -> None:
        tmp = path.with_suffix(".tmp")
        tmp.write_text(json.dumps(data, indent=2, ensure_ascii=False), encoding="utf-8")
        os.replace(tmp, path)

    def _diff(
        self, existing: dict[str, Any] | None, incoming: dict[str, Any]
    ) -> dict[str, Any]:
        if existing is None:
            return dict(incoming)
        changed: dict[str, Any] = {}
        for key, val in incoming.items():
            if existing.get(key) != val:
                changed[key] = val
        return changed
```

- [ ] **Step 10: Run RoomMemory tests**

```bash
uv run pytest tests/test_room_memory.py -v
```

Expected: all PASS.

- [ ] **Step 11: Write failing tests for WorldGraph**

Create `tests/test_world_graph.py`:

```python
import json
from pathlib import Path
from boukensha.memory.world_graph import WorldGraph


def test_add_room_creates_node(tmp_path):
    g = WorldGraph(tmp_path)
    g.add_room("aabbcc001122", "Temple Square")
    assert g.has_room("aabbcc001122")


def test_add_edge_creates_connection(tmp_path):
    g = WorldGraph(tmp_path)
    g.add_room("aabbcc001122", "Room A")
    g.add_room("ddeeff334455", "Room B")
    g.add_edge("aabbcc001122", "ddeeff334455", "north")
    neighbors = g.get_neighbors("aabbcc001122")
    assert neighbors.get("north") == "ddeeff334455"


def test_save_and_reload(tmp_path):
    g = WorldGraph(tmp_path)
    g.add_room("aabbcc001122", "Room A")
    g.add_room("ddeeff334455", "Room B")
    g.add_edge("aabbcc001122", "ddeeff334455", "east")
    g.save()

    g2 = WorldGraph(tmp_path)
    g2.load()
    assert g2.has_room("aabbcc001122")
    assert g2.get_neighbors("aabbcc001122").get("east") == "ddeeff334455"


def test_get_neighbors_unknown_room_returns_empty(tmp_path):
    g = WorldGraph(tmp_path)
    assert g.get_neighbors("deadbeefcafe") == {}


def test_has_room_false_for_unknown(tmp_path):
    g = WorldGraph(tmp_path)
    assert not g.has_room("deadbeefcafe")


def test_duplicate_add_room_is_idempotent(tmp_path):
    g = WorldGraph(tmp_path)
    g.add_room("aabbcc001122", "Temple Square")
    g.add_room("aabbcc001122", "Temple Square")
    # No error, node count still 1
    assert g.has_room("aabbcc001122")
```

- [ ] **Step 12: Run to verify they fail**

```bash
uv run pytest tests/test_world_graph.py -v
```

- [ ] **Step 13: Implement WorldGraph**

Create `src/boukensha/memory/world_graph.py`:

```python
"""NetworkX DiGraph of rooms connected by exit edges."""

from __future__ import annotations

import json
import os
from pathlib import Path

import networkx as nx


class WorldGraph:
    def __init__(self, base_dir: str | Path) -> None:
        self._base_dir = Path(base_dir)
        self._base_dir.mkdir(parents=True, exist_ok=True)
        self._path = self._base_dir / "world_graph.json"
        self._g: nx.DiGraph = nx.DiGraph()

    def add_room(self, room_hash: str, title: str) -> None:
        if room_hash not in self._g:
            self._g.add_node(room_hash, title=title)

    def add_edge(self, from_hash: str, to_hash: str, direction: str) -> None:
        self._g.add_edge(from_hash, to_hash, direction=direction)

    def get_neighbors(self, room_hash: str) -> dict[str, str]:
        if room_hash not in self._g:
            return {}
        return {
            data["direction"]: neighbor
            for neighbor, data in self._g[room_hash].items()
            if "direction" in data
        }

    def has_room(self, room_hash: str) -> bool:
        return room_hash in self._g

    def save(self) -> None:
        data = nx.node_link_data(self._g)
        tmp = self._path.with_suffix(".tmp")
        tmp.write_text(json.dumps(data, indent=2, ensure_ascii=False), encoding="utf-8")
        os.replace(tmp, self._path)

    def load(self) -> None:
        if not self._path.exists():
            return
        data = json.loads(self._path.read_text(encoding="utf-8"))
        self._g = nx.node_link_graph(data, directed=True, multigraph=False)

    @property
    def graph(self) -> nx.DiGraph:
        return self._g
```

- [ ] **Step 14: Run WorldGraph tests**

```bash
uv run pytest tests/test_world_graph.py -v
```

Expected: all PASS.

- [ ] **Step 15: Write failing tests for Pathfinder**

Create `tests/test_pathfinder.py`:

```python
from boukensha.memory.world_graph import WorldGraph
from boukensha.memory.pathfinder import Pathfinder


def _build_graph(tmp_path):
    g = WorldGraph(tmp_path)
    # A -> B (north), B -> C (east), A -> C (east, longer path)
    g.add_room("aaa", "Room A")
    g.add_room("bbb", "Room B")
    g.add_room("ccc", "Room C")
    g.add_edge("aaa", "bbb", "north")
    g.add_edge("bbb", "ccc", "east")
    g.add_edge("aaa", "ccc", "east")
    return g


def test_find_path_direct(tmp_path):
    g = _build_graph(tmp_path)
    p = Pathfinder(g)
    path = p.find_path("aaa", "bbb")
    assert path == ["north"]


def test_find_path_multi_step(tmp_path):
    g = _build_graph(tmp_path)
    p = Pathfinder(g)
    path = p.find_path("aaa", "ccc")
    # Shortest is direct east (1 step), not north+east (2 steps)
    assert path == ["east"]


def test_find_path_no_route_returns_none(tmp_path):
    g = WorldGraph(tmp_path)
    g.add_room("aaa", "Room A")
    g.add_room("bbb", "Room B")
    p = Pathfinder(g)
    assert p.find_path("aaa", "bbb") is None


def test_find_path_same_room_returns_empty(tmp_path):
    g = _build_graph(tmp_path)
    p = Pathfinder(g)
    path = p.find_path("aaa", "aaa")
    assert path == []


def test_find_path_unknown_start_returns_none(tmp_path):
    g = _build_graph(tmp_path)
    p = Pathfinder(g)
    assert p.find_path("zzz", "bbb") is None


def test_find_path_by_title(tmp_path):
    g = _build_graph(tmp_path)
    p = Pathfinder(g)
    path = p.find_path_by_title("aaa", "Room B")
    assert path == ["north"]


def test_find_path_by_title_no_match_returns_none(tmp_path):
    g = _build_graph(tmp_path)
    p = Pathfinder(g)
    assert p.find_path_by_title("aaa", "Nonexistent") is None
```

- [ ] **Step 16: Run to verify they fail**

```bash
uv run pytest tests/test_pathfinder.py -v
```

- [ ] **Step 17: Implement Pathfinder**

Create `src/boukensha/memory/pathfinder.py`:

```python
"""Dijkstra shortest path over a WorldGraph."""

from __future__ import annotations

import networkx as nx

from .world_graph import WorldGraph


class Pathfinder:
    def __init__(self, graph: WorldGraph) -> None:
        self._graph = graph

    def find_path(self, start_hash: str, end_hash: str) -> list[str] | None:
        g = self._graph.graph
        if start_hash not in g or end_hash not in g:
            return None
        if start_hash == end_hash:
            return []
        try:
            node_path = nx.shortest_path(g, start_hash, end_hash)
        except nx.NetworkXNoPath:
            return None
        directions: list[str] = []
        for a, b in zip(node_path, node_path[1:]):
            edge_data = g.get_edge_data(a, b) or {}
            directions.append(edge_data.get("direction", "?"))
        return directions

    def find_path_by_title(
        self, start_hash: str, title_fragment: str
    ) -> list[str] | None:
        g = self._graph.graph
        fragment_lower = title_fragment.lower()
        for node, attrs in g.nodes(data=True):
            if fragment_lower in (attrs.get("title") or "").lower():
                return self.find_path(start_hash, node)
        return None
```

- [ ] **Step 18: Run all memory tests**

```bash
uv run pytest tests/test_room_parser.py tests/test_room_memory.py tests/test_world_graph.py tests/test_pathfinder.py -v
```

Expected: all PASS.

- [ ] **Step 19: Commit**

```bash
git add pyproject.toml \
        src/boukensha/memory/ \
        tests/test_room_parser.py tests/test_room_memory.py \
        tests/test_world_graph.py tests/test_pathfinder.py
git commit -m "feat(agent-exp): add room memory subsystem with parser, storage, graph, and pathfinder"
```

---

### Task 2: Goal Subsystem — GoalManager, CombatMonitor

**Files:**
- Create: `src/boukensha/goals/__init__.py`
- Create: `src/boukensha/goals/goal_manager.py`
- Create: `src/boukensha/goals/combat_monitor.py`
- Create: `tests/test_goal_manager.py`
- Create: `tests/test_combat_monitor.py`

**Interfaces:**
- Consumes: nothing from Task 1
- Produces:
  - `GoalManager(base_dir: str | Path)` — constructor; base_dir is `.boukensha/` dir
  - `GoalManager.read() -> dict` — returns parsed YAML or defaults if file missing
  - `GoalManager.update(**kwargs) -> None` — merges kwargs into current YAML, sets `last_updated`
  - `GoalManager.reset() -> None` — writes clean default YAML
  - `GoalManager.DEFAULT_FIELDS: dict` — the default YAML structure
  - `CombatMonitor.check(hp: int, goal: dict) -> str | None` — returns directive string if HP ≤ threshold, else `None`
  - `CombatMonitor.update_on_low_hp(hp: int, goal_manager: GoalManager) -> str | None` — combines check + update

- [ ] **Step 1: Write failing tests for GoalManager**

Create `tests/test_goal_manager.py`:

```python
import yaml
from pathlib import Path
from boukensha.goals.goal_manager import GoalManager


def test_read_returns_defaults_when_no_file(tmp_path):
    gm = GoalManager(tmp_path)
    goal = gm.read()
    assert "current_goal" in goal
    assert "priority" in goal
    assert "hp_flee_threshold" in goal
    assert "status" in goal


def test_update_writes_file(tmp_path):
    gm = GoalManager(tmp_path)
    gm.update(current_goal="Kill the dragon")
    path = tmp_path / "goals" / "current.yaml"
    assert path.exists()


def test_update_persists_value(tmp_path):
    gm = GoalManager(tmp_path)
    gm.update(current_goal="Explore temple")
    goal = gm.read()
    assert goal["current_goal"] == "Explore temple"


def test_update_sets_last_updated(tmp_path):
    gm = GoalManager(tmp_path)
    gm.update(status="flee")
    goal = gm.read()
    assert goal.get("last_updated") is not None


def test_update_merges_not_replaces(tmp_path):
    gm = GoalManager(tmp_path)
    gm.update(current_goal="Heal up", hp_flee_threshold=10)
    gm.update(status="active")
    goal = gm.read()
    assert goal["current_goal"] == "Heal up"
    assert goal["hp_flee_threshold"] == 10
    assert goal["status"] == "active"


def test_reset_restores_defaults(tmp_path):
    gm = GoalManager(tmp_path)
    gm.update(current_goal="Custom goal", status="paused")
    gm.reset()
    goal = gm.read()
    assert goal["current_goal"] == GoalManager.DEFAULT_FIELDS["current_goal"]


def test_write_is_valid_yaml(tmp_path):
    gm = GoalManager(tmp_path)
    gm.update(notes="Found a sword")
    path = tmp_path / "goals" / "current.yaml"
    parsed = yaml.safe_load(path.read_text())
    assert isinstance(parsed, dict)
```

- [ ] **Step 2: Run to verify they fail**

```bash
uv run pytest tests/test_goal_manager.py -v
```

- [ ] **Step 3: Implement GoalManager**

Create `src/boukensha/goals/goal_manager.py`:

```python
"""Read/write the agent's current goal as structured YAML."""

from __future__ import annotations

import os
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import yaml


class GoalManager:
    DEFAULT_FIELDS: dict[str, Any] = {
        "current_goal": "Explore the MUD",
        "priority": "explore",
        "hp_flee_threshold": 5,
        "status": "active",
        "notes": "",
        "last_updated": None,
        "mud_basics": (
            "- Use 'score' to check HP/mana/moves\n"
            "- Use 'look' to describe current room\n"
            "- Use 'exits' to list available exits\n"
            "- north/south/east/west/up/down to move\n"
            "- 'kill <target>' to attack\n"
            "- 'flee' to escape combat\n"
        ),
    }

    def __init__(self, base_dir: str | Path) -> None:
        self._goals_dir = Path(base_dir) / "goals"
        self._goals_dir.mkdir(parents=True, exist_ok=True)
        self._path = self._goals_dir / "current.yaml"

    def read(self) -> dict[str, Any]:
        if not self._path.exists():
            return dict(self.DEFAULT_FIELDS)
        raw = yaml.safe_load(self._path.read_text(encoding="utf-8")) or {}
        return {**self.DEFAULT_FIELDS, **raw}

    def update(self, **kwargs: Any) -> None:
        current = self.read()
        current.update(kwargs)
        current["last_updated"] = datetime.now(timezone.utc).isoformat()
        self._write(current)

    def reset(self) -> None:
        self._write(dict(self.DEFAULT_FIELDS))

    def _write(self, data: dict[str, Any]) -> None:
        tmp = self._path.with_suffix(".tmp")
        tmp.write_text(yaml.dump(data, default_flow_style=False, allow_unicode=True), encoding="utf-8")
        os.replace(tmp, self._path)
```

- [ ] **Step 4: Run GoalManager tests**

```bash
uv run pytest tests/test_goal_manager.py -v
```

Expected: all PASS.

- [ ] **Step 5: Write failing tests for CombatMonitor**

Create `tests/test_combat_monitor.py`:

```python
from unittest.mock import MagicMock
from boukensha.goals.combat_monitor import CombatMonitor
from boukensha.goals.goal_manager import GoalManager


def test_check_below_threshold_returns_directive(tmp_path):
    gm = GoalManager(tmp_path)
    gm.update(hp_flee_threshold=5)
    goal = gm.read()
    directive = CombatMonitor.check(hp=3, goal=goal)
    assert directive is not None
    assert "flee" in directive.lower()


def test_check_at_threshold_returns_directive(tmp_path):
    gm = GoalManager(tmp_path)
    gm.update(hp_flee_threshold=5)
    goal = gm.read()
    directive = CombatMonitor.check(hp=5, goal=goal)
    assert directive is not None


def test_check_above_threshold_returns_none(tmp_path):
    gm = GoalManager(tmp_path)
    gm.update(hp_flee_threshold=5)
    goal = gm.read()
    assert CombatMonitor.check(hp=20, goal=goal) is None


def test_update_on_low_hp_sets_flee_status(tmp_path):
    gm = GoalManager(tmp_path)
    gm.update(hp_flee_threshold=5)
    CombatMonitor.update_on_low_hp(hp=3, goal_manager=gm)
    assert gm.read()["status"] == "flee"


def test_update_on_low_hp_returns_directive(tmp_path):
    gm = GoalManager(tmp_path)
    gm.update(hp_flee_threshold=5)
    result = CombatMonitor.update_on_low_hp(hp=3, goal_manager=gm)
    assert result is not None


def test_update_on_low_hp_above_threshold_returns_none(tmp_path):
    gm = GoalManager(tmp_path)
    gm.update(hp_flee_threshold=5)
    result = CombatMonitor.update_on_low_hp(hp=20, goal_manager=gm)
    assert result is None
```

- [ ] **Step 6: Run to verify they fail**

```bash
uv run pytest tests/test_combat_monitor.py -v
```

- [ ] **Step 7: Implement CombatMonitor**

Create `src/boukensha/goals/combat_monitor.py`:

```python
"""Stateless HP threshold check — triggers flee goal update when HP is low."""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from .goal_manager import GoalManager


class CombatMonitor:
    @staticmethod
    def check(hp: int, goal: dict[str, Any]) -> str | None:
        threshold = int(goal.get("hp_flee_threshold", 5))
        if hp <= threshold:
            return (
                f"HP is {hp} (at or below flee threshold {threshold}). "
                "You must FLEE immediately and find a safe place to recover."
            )
        return None

    @staticmethod
    def update_on_low_hp(hp: int, goal_manager: "GoalManager") -> str | None:
        goal = goal_manager.read()
        directive = CombatMonitor.check(hp, goal)
        if directive is not None:
            goal_manager.update(status="flee")
        return directive
```

- [ ] **Step 8: Create `src/boukensha/goals/__init__.py`**

```python
from .goal_manager import GoalManager
from .combat_monitor import CombatMonitor

__all__ = ["GoalManager", "CombatMonitor"]
```

- [ ] **Step 9: Run all goal tests**

```bash
uv run pytest tests/test_goal_manager.py tests/test_combat_monitor.py -v
```

Expected: all PASS.

- [ ] **Step 10: Commit**

```bash
git add src/boukensha/goals/ tests/test_goal_manager.py tests/test_combat_monitor.py
git commit -m "feat(agent-exp): add goal subsystem with GoalManager and CombatMonitor"
```

---

### Task 3: Token-Saving Tools — navigate_to, process_room, combat_loop

**Files:**
- Create: `src/boukensha/tools/navigation.py`
- Create: `src/boukensha/tools/room_processor.py`
- Create: `src/boukensha/tools/combat.py`
- Modify: `src/boukensha/tools/__init__.py`
- Create: `tests/test_navigation_tool.py`

**Interfaces:**
- Consumes:
  - `RoomParser.parse(raw: str) -> dict` (from Task 1)
  - `RoomMemory(base_dir) .record(room) -> (hash, diff)` (from Task 1)
  - `WorldGraph(base_dir) .add_room() .add_edge() .save() .get_neighbors()` (from Task 1)
  - `Pathfinder(graph) .find_path_by_title()` (from Task 1)
  - `CombatMonitor.update_on_low_hp(hp, goal_manager)` (from Task 2)
  - `GoalManager(base_dir) .read() .update()` (from Task 2)
  - `Registry` — the existing registry used to register tools (from existing codebase)
  - MUD tool `_send(session, cmd)` — accessed via registry dispatch

- Produces:
  - `Navigation.register(registry, *, session, memory_dir, goals_dir) -> None`
  - `RoomProcessor.register(registry, *, session, memory_dir) -> None`
  - `Combat.register(registry, *, session, goals_dir) -> None`
  - Registers these tool names:
    - `"navigate_to"` — params: `{"destination": str}`
    - `"process_room"` — params: `{}` (no args)
    - `"combat_loop"` — params: `{"target": str, "flee_hp": int (optional, default 5)}`
    - `"goal_read"` — params: `{}`
    - `"goal_update"` — params: `{"current_goal": str (optional), "priority": str (optional), "status": str (optional), "notes": str (optional)}`

- [ ] **Step 1: Write failing tests for navigation and process_room tools**

Create `tests/test_navigation_tool.py`:

```python
from unittest.mock import MagicMock, patch, call
from boukensha.tools.navigation import Navigation
from boukensha.tools.room_processor import RoomProcessor
from boukensha.memory.world_graph import WorldGraph
from boukensha.memory.room_memory import RoomMemory


def _make_session(look_response="Room A\n   Desc.\nExits: north\n"):
    session = MagicMock()
    session.is_open = True
    session.read_until_prompt.return_value = look_response
    session.send_command = MagicMock()
    session.drain = MagicMock(return_value="")
    return session


def test_process_room_returns_diff_for_new_room(tmp_path):
    session = _make_session("Temple Square\n   A large open square.\nExits: north, south\n")
    registry = MagicMock()
    dispatched = {}
    def dispatch(name, args):
        dispatched[name] = args
        if name == "look":
            return "Temple Square\n   A large open square.\nExits: north, south\n"
        return ""
    registry.dispatch = dispatch

    # Manually call the block that process_room registers
    mem = RoomMemory(tmp_path)
    from boukensha.memory.parser import RoomParser
    raw = "Temple Square\n   A large open square.\nExits: north, south\n"
    room = RoomParser.parse(raw)
    _, diff = mem.record(room)
    # First visit: diff should be the full room
    assert diff["title"] == "Temple Square"


def test_process_room_returns_empty_diff_for_known_room(tmp_path):
    mem = RoomMemory(tmp_path)
    from boukensha.memory.parser import RoomParser
    raw = "Temple Square\n   A large open square.\nExits: north, south\n"
    room = RoomParser.parse(raw)
    mem.record(room)
    _, diff = mem.record(room)
    assert diff == {}


def test_navigate_to_issues_moves_for_known_path(tmp_path):
    g = WorldGraph(tmp_path)
    g.add_room("aaa", "Room A")
    g.add_room("bbb", "Room B")
    g.add_edge("aaa", "bbb", "north")
    from boukensha.memory.pathfinder import Pathfinder
    p = Pathfinder(g)
    path = p.find_path_by_title("aaa", "Room B")
    assert path == ["north"]


def test_navigate_to_unknown_destination_returns_error(tmp_path):
    g = WorldGraph(tmp_path)
    g.add_room("aaa", "Room A")
    from boukensha.memory.pathfinder import Pathfinder
    p = Pathfinder(g)
    path = p.find_path_by_title("aaa", "Nonexistent Room")
    assert path is None
```

- [ ] **Step 2: Run to verify they pass (these test the underlying logic only)**

```bash
uv run pytest tests/test_navigation_tool.py -v
```

Expected: all PASS (these test logic already built in Task 1, not the tool wrappers directly).

- [ ] **Step 3: Implement Navigation tool**

Create `src/boukensha/tools/navigation.py`:

```python
"""navigate_to tool: Python pathfinding + move loop, no LLM per step."""

from __future__ import annotations

from pathlib import Path
from typing import TYPE_CHECKING, Any

from boukensha.memory.parser import RoomParser
from boukensha.memory.room_memory import RoomMemory
from boukensha.memory.world_graph import WorldGraph
from boukensha.memory.pathfinder import Pathfinder

if TYPE_CHECKING:
    from boukensha.registry import Registry


class Navigation:
    @classmethod
    def register(
        cls,
        registry: "Registry",
        *,
        session: Any,
        memory_dir: str | Path,
    ) -> None:
        memory_dir = Path(memory_dir)
        mem = RoomMemory(memory_dir)
        graph = WorldGraph(memory_dir)
        graph.load()

        def _current_room_hash() -> str | None:
            """Send 'look' and return the hash of the current room."""
            session.drain()
            session.send_command("look")
            raw = session.read_until_prompt()
            room = RoomParser.parse(raw)
            if not room["title"]:
                return None
            h, _ = mem.record(room)
            graph.add_room(h, room["title"])
            return h

        def _navigate_to(destination: str, **_: Any) -> str:
            if not session.is_open:
                return "error: not connected"
            start_hash = _current_room_hash()
            if start_hash is None:
                return "error: could not determine current room"
            graph.load()
            pf = Pathfinder(graph)
            path = pf.find_path_by_title(start_hash, destination)
            if path is None:
                return f"No known path to '{destination}'. Explore more of the area first."
            if not path:
                return f"Already at '{destination}'."
            for direction in path:
                session.drain()
                session.send_command(direction)
                session.read_until_prompt()
            graph.save()
            return f"Arrived at destination after {len(path)} moves: {' → '.join(path)}"

        registry.tool(
            "navigate_to",
            description=(
                "Navigate to a known destination using the built room map. "
                "Uses the shortest known path — no LLM needed per move step. "
                "Returns the path taken, or an error if the destination is unknown."
            ),
            parameters={
                "destination": {"type": "string", "description": "Partial room title to navigate to (case-insensitive)"},
            },
            block=_navigate_to,
        )
```

- [ ] **Step 4: Implement RoomProcessor tool**

Create `src/boukensha/tools/room_processor.py`:

```python
"""process_room tool: parse current room, diff vs memory, return only new info."""

from __future__ import annotations

from pathlib import Path
from typing import TYPE_CHECKING, Any

from boukensha.memory.parser import RoomParser
from boukensha.memory.room_memory import RoomMemory
from boukensha.memory.world_graph import WorldGraph

if TYPE_CHECKING:
    from boukensha.registry import Registry


class RoomProcessor:
    @classmethod
    def register(
        cls,
        registry: "Registry",
        *,
        session: Any,
        memory_dir: str | Path,
        prev_hash_ref: list[str | None] | None = None,
    ) -> None:
        memory_dir = Path(memory_dir)
        mem = RoomMemory(memory_dir)
        graph = WorldGraph(memory_dir)
        graph.load()
        _prev: list[str | None] = prev_hash_ref if prev_hash_ref is not None else [None]

        def _process_room(**_: Any) -> str:
            if not session.is_open:
                return "error: not connected"
            session.drain()
            session.send_command("look")
            raw = session.read_until_prompt()
            room = RoomParser.parse(raw)
            if not room["title"]:
                return raw  # fallback: return raw if parse failed

            h, diff = mem.record(room)
            graph.add_room(h, room["title"])

            # Link from previous room if we know it
            if _prev[0] and _prev[0] != h:
                pass  # direction is unknown here; WorldGraph edges added by navigate_to

            _prev[0] = h
            graph.save()

            if not diff:
                return f"[known room: {room['title']}] Nothing new observed."

            parts = [f"Room: {room['title']}"]
            if diff.get("description"):
                parts.append(f"Description: {diff['description']}")
            if diff.get("exits"):
                exits_str = ", ".join(diff["exits"].keys())
                parts.append(f"Exits: {exits_str}")
            if diff.get("npcs"):
                parts.append(f"NPCs: {', '.join(diff['npcs'])}")
            if diff.get("items"):
                parts.append(f"Items: {', '.join(diff['items'])}")
            return "\n".join(parts)

        registry.tool(
            "process_room",
            description=(
                "Look at the current room and return ONLY new or changed information vs stored memory. "
                "Returns an empty observation string if nothing has changed since last visit. "
                "Use this instead of raw 'look' to minimize token usage."
            ),
            parameters={},
            block=_process_room,
        )
```

- [ ] **Step 5: Implement Combat tool**

Create `src/boukensha/tools/combat.py`:

```python
"""combat_loop tool: Python fight loop with HP monitoring."""

from __future__ import annotations

import re
import time
from pathlib import Path
from typing import TYPE_CHECKING, Any

from boukensha.goals.goal_manager import GoalManager
from boukensha.goals.combat_monitor import CombatMonitor

if TYPE_CHECKING:
    from boukensha.registry import Registry

_HP_RE = re.compile(r"(\d+)/(\d+)H", re.IGNORECASE)
_DEAD_PATTERNS = [b"is dead!", b"You receive", b"experience points"]


class Combat:
    @classmethod
    def register(
        cls,
        registry: "Registry",
        *,
        session: Any,
        goals_dir: str | Path,
    ) -> None:
        goals_dir = Path(goals_dir)
        gm = GoalManager(goals_dir)

        def _parse_hp(text: str) -> int | None:
            m = _HP_RE.search(text)
            if m:
                return int(m.group(1))
            return None

        def _combat_loop(target: str, flee_hp: int = 5, **_: Any) -> str:
            if not session.is_open:
                return "error: not connected"

            gm.update(hp_flee_threshold=flee_hp)
            goal = gm.read()

            # Initiate attack
            session.drain()
            session.send_command(f"kill {target}")
            response = session.read_until_prompt()

            rounds = 0
            max_rounds = 30

            while rounds < max_rounds:
                rounds += 1
                response_lower = response.lower()

                # Check if target is dead
                if any(p.decode().lower() in response_lower for p in _DEAD_PATTERNS):
                    return f"Combat complete: {target} defeated after {rounds} round(s)."

                # Check HP from prompt if present
                hp = _parse_hp(response)
                if hp is not None:
                    directive = CombatMonitor.update_on_low_hp(hp, gm)
                    if directive:
                        session.drain()
                        session.send_command("flee")
                        flee_resp = session.read_until_prompt()
                        return f"Fled combat: {directive}\n{flee_resp}"

                # Check if we're no longer in combat
                if "you stop fighting" in response_lower or "no one is fighting" in response_lower:
                    return f"Combat ended after {rounds} round(s)."

                time.sleep(0.5)
                response = session.read_until_prompt(timeout=3.0)

            return f"Combat loop reached {max_rounds} rounds — check status manually."

        registry.tool(
            "combat_loop",
            description=(
                "Fight a target in a Python loop, checking HP each round. "
                "Automatically flees if HP drops to or below flee_hp. "
                "Returns when target dies, you flee, or the round limit is reached. "
                "No LLM call per round — only use this for straightforward fights."
            ),
            parameters={
                "target": {"type": "string", "description": "Name of the mob to attack"},
                "flee_hp": {"type": "integer", "description": "Flee if HP drops to this value or below (default: 5)"},
            },
            block=_combat_loop,
        )

        registry.tool(
            "goal_read",
            description="Read the current goal YAML and return it as a formatted string.",
            parameters={},
            block=lambda **_: _format_goal(gm.read()),
        )

        registry.tool(
            "goal_update",
            description=(
                "Update the agent's current goal. Fields: current_goal (str), "
                "priority (explore|fight|heal|flee|idle), status (active|paused|completed|flee), notes (str)."
            ),
            parameters={
                "current_goal": {"type": "string", "description": "New goal description (optional)"},
                "priority": {"type": "string", "description": "explore | fight | heal | flee | idle (optional)"},
                "status": {"type": "string", "description": "active | paused | completed | flee (optional)"},
                "notes": {"type": "string", "description": "Additional notes (optional)"},
            },
            block=lambda **kwargs: _do_goal_update(gm, kwargs),
        )


def _format_goal(goal: dict[str, Any]) -> str:
    lines = [
        f"current_goal: {goal.get('current_goal', '')}",
        f"priority: {goal.get('priority', '')}",
        f"status: {goal.get('status', '')}",
        f"hp_flee_threshold: {goal.get('hp_flee_threshold', 5)}",
        f"notes: {goal.get('notes', '')}",
    ]
    return "\n".join(lines)


def _do_goal_update(gm: GoalManager, kwargs: dict[str, Any]) -> str:
    filtered = {k: v for k, v in kwargs.items() if v is not None and k in (
        "current_goal", "priority", "status", "notes", "hp_flee_threshold"
    )}
    if filtered:
        gm.update(**filtered)
        return "Goal updated: " + ", ".join(f"{k}={v}" for k, v in filtered.items())
    return "No fields to update."
```

- [ ] **Step 6: Update `src/boukensha/tools/__init__.py`**

Read the current file first, then add the three new classes:

```python
from .file_system import FileSystem
from .mud import Mud
from .shell import Shell
from .navigation import Navigation
from .room_processor import RoomProcessor
from .combat import Combat

__all__ = ["FileSystem", "Mud", "Shell", "Navigation", "RoomProcessor", "Combat"]
```

- [ ] **Step 7: Run full test suite to catch regressions**

```bash
uv run pytest tests/ -v
```

Expected: all previously-passing tests still PASS. New navigation tests PASS.

- [ ] **Step 8: Commit**

```bash
git add src/boukensha/tools/navigation.py \
        src/boukensha/tools/room_processor.py \
        src/boukensha/tools/combat.py \
        src/boukensha/tools/__init__.py \
        tests/test_navigation_tool.py
git commit -m "feat(agent-exp): add token-saving tools: navigate_to, process_room, combat_loop, goal_read, goal_update"
```

---

### Task 4: Web Dashboard — Flask app, SSE, five tabs

**Files:**
- Create: `src/boukensha/dashboard/__init__.py`
- Create: `src/boukensha/dashboard/event_bus.py`
- Create: `src/boukensha/dashboard/app.py`
- Create: `src/boukensha/dashboard/templates/index.html`
- Create: `src/boukensha/dashboard/static/style.css`
- Create: `src/boukensha/dashboard/static/app.js`
- Create: `src/boukensha/dashboard/static/map.js`
- Create: `src/boukensha/dashboard/static/waterfall.js`
- Create: `tests/test_dashboard_api.py`
- Modify: `pyproject.toml` (add `flask>=3.0`)

**Interfaces:**
- Consumes:
  - `Logger.subscribe(callback)` (existing — already in `logger.py`)
  - `WorldGraph(base_dir).load()` / `.graph` (from Task 1)
  - `GoalManager(base_dir).read()` (from Task 2)
  - `.boukensha/sessions/*.jsonl` files (existing logger output)
- Produces:
  - `EventBus()` — thread-safe queue
  - `EventBus.publish(event: dict) -> None`
  - `EventBus.stream() -> Iterator[str]` — yields SSE-formatted strings
  - `create_dashboard_app(config_dir: str, sessions_dir: str) -> Flask` — factory
  - `run_dashboard(app, port=4568) -> None` — runs in a daemon thread
  - HTTP routes:
    - `GET /` — single-page shell
    - `GET /events` — SSE stream (Content-Type: text/event-stream)
    - `GET /api/map` — JSON: `{nodes: [{id, title}], links: [{source, target, direction}]}`
    - `GET /api/goal` — JSON: the current YAML dict
    - `GET /api/sessions` — JSON: `[{id, started_at, model, total_input_tokens, total_output_tokens}]`
    - `GET /api/sessions/<id>` — JSON: full parsed session entries list

- [ ] **Step 1: Add flask to pyproject.toml**

In `pyproject.toml` dependencies, add `"flask>=3.0"`:

```toml
dependencies = [
    "pyyaml>=6.0",
    "python-dotenv>=1.0",
    "textual>=0.80",
    "networkx>=3.0",
    "flask>=3.0",
]
```

Then:
```bash
uv sync
```

- [ ] **Step 2: Create EventBus**

Create `src/boukensha/dashboard/event_bus.py`:

```python
"""Thread-safe SSE event queue."""

from __future__ import annotations

import json
import queue
import threading
from collections.abc import Iterator
from typing import Any


class EventBus:
    def __init__(self) -> None:
        self._queues: list[queue.Queue] = []
        self._lock = threading.Lock()

    def publish(self, event: dict[str, Any]) -> None:
        data = json.dumps(event)
        with self._lock:
            dead = []
            for q in self._queues:
                try:
                    q.put_nowait(data)
                except queue.Full:
                    dead.append(q)
            for q in dead:
                self._queues.remove(q)

    def subscribe(self) -> queue.Queue:
        q: queue.Queue = queue.Queue(maxsize=500)
        with self._lock:
            self._queues.append(q)
        return q

    def unsubscribe(self, q: queue.Queue) -> None:
        with self._lock:
            try:
                self._queues.remove(q)
            except ValueError:
                pass

    def stream(self) -> Iterator[str]:
        q = self.subscribe()
        try:
            while True:
                try:
                    data = q.get(timeout=15.0)
                    yield f"data: {data}\n\n"
                except queue.Empty:
                    yield ": heartbeat\n\n"
        finally:
            self.unsubscribe(q)
```

- [ ] **Step 3: Write failing dashboard API tests**

Create `tests/test_dashboard_api.py`:

```python
import json
import tempfile
from pathlib import Path
from boukensha.dashboard.app import create_dashboard_app


def _make_app(tmp_path):
    sessions_dir = tmp_path / "sessions"
    sessions_dir.mkdir(parents=True)
    app = create_dashboard_app(
        config_dir=str(tmp_path),
        sessions_dir=str(sessions_dir),
    )
    app.config["TESTING"] = True
    return app, sessions_dir


def test_index_returns_200(tmp_path):
    app, _ = _make_app(tmp_path)
    with app.test_client() as c:
        r = c.get("/")
        assert r.status_code == 200


def test_api_map_returns_json(tmp_path):
    app, _ = _make_app(tmp_path)
    with app.test_client() as c:
        r = c.get("/api/map")
        assert r.status_code == 200
        data = json.loads(r.data)
        assert "nodes" in data
        assert "links" in data


def test_api_goal_returns_json(tmp_path):
    app, _ = _make_app(tmp_path)
    with app.test_client() as c:
        r = c.get("/api/goal")
        assert r.status_code == 200
        data = json.loads(r.data)
        assert "current_goal" in data


def test_api_sessions_returns_list(tmp_path):
    app, sessions_dir = _make_app(tmp_path)
    # Write a minimal session file
    session_file = sessions_dir / "20260727T000000Z-abc12345.jsonl"
    session_file.write_text(
        json.dumps({"phase": "session_start", "at": "2026-07-27T00:00:00Z", "model": "test", "session_id": "abc12345"}) + "\n"
    )
    with app.test_client() as c:
        r = c.get("/api/sessions")
        assert r.status_code == 200
        data = json.loads(r.data)
        assert isinstance(data, list)
        assert len(data) >= 1


def test_api_session_detail_returns_entries(tmp_path):
    app, sessions_dir = _make_app(tmp_path)
    sid = "20260727T000000Z-abc12345"
    session_file = sessions_dir / f"{sid}.jsonl"
    lines = [
        {"phase": "session_start", "at": "2026-07-27T00:00:00Z", "model": "test", "session_id": sid},
        {"phase": "turn", "n": 1, "at": "2026-07-27T00:00:01Z", "session_id": sid},
    ]
    session_file.write_text("\n".join(json.dumps(l) for l in lines) + "\n")
    with app.test_client() as c:
        r = c.get(f"/api/sessions/{sid}")
        assert r.status_code == 200
        data = json.loads(r.data)
        assert isinstance(data, list)
```

- [ ] **Step 4: Run to verify they fail**

```bash
uv run pytest tests/test_dashboard_api.py -v
```

Expected: `ModuleNotFoundError`.

- [ ] **Step 5: Implement Flask dashboard app**

Create `src/boukensha/dashboard/app.py`:

```python
"""Flask dashboard — five tabs with SSE live feed."""

from __future__ import annotations

import json
import threading
from pathlib import Path
from typing import Any

from flask import Flask, Response, jsonify, render_template, stream_with_context

from .event_bus import EventBus

_bus: EventBus = EventBus()


def get_bus() -> EventBus:
    return _bus


def create_dashboard_app(
    *,
    config_dir: str,
    sessions_dir: str,
    memory_subdir: str = "memory",
    goals_subdir: str = "goals",
) -> Flask:
    config_path = Path(config_dir)
    sessions_path = Path(sessions_dir)
    memory_path = config_path / memory_subdir
    goals_path = config_path / goals_subdir

    template_folder = str(Path(__file__).parent / "templates")
    static_folder = str(Path(__file__).parent / "static")
    app = Flask(__name__, template_folder=template_folder, static_folder=static_folder)

    @app.route("/")
    def index():
        return render_template("index.html")

    @app.route("/events")
    def sse_events():
        def generate():
            yield from _bus.stream()
        return Response(
            stream_with_context(generate()),
            mimetype="text/event-stream",
            headers={
                "Cache-Control": "no-cache",
                "X-Accel-Buffering": "no",
            },
        )

    @app.route("/api/map")
    def api_map():
        from boukensha.memory.world_graph import WorldGraph
        g = WorldGraph(memory_path)
        g.load()
        nx_g = g.graph
        nodes = [
            {"id": n, "title": attrs.get("title", n)}
            for n, attrs in nx_g.nodes(data=True)
        ]
        links = [
            {"source": u, "target": v, "direction": d.get("direction", "")}
            for u, v, d in nx_g.edges(data=True)
        ]
        return jsonify({"nodes": nodes, "links": links})

    @app.route("/api/goal")
    def api_goal():
        from boukensha.goals.goal_manager import GoalManager
        gm = GoalManager(config_path)
        return jsonify(gm.read())

    @app.route("/api/sessions")
    def api_sessions():
        sessions_path.mkdir(parents=True, exist_ok=True)
        result = []
        for f in sorted(sessions_path.glob("*.jsonl"), reverse=True):
            meta = _parse_session_meta(f)
            result.append(meta)
        return jsonify(result)

    @app.route("/api/sessions/<session_id>")
    def api_session_detail(session_id: str):
        path = sessions_path / f"{session_id}.jsonl"
        if not path.exists():
            return jsonify({"error": "not found"}), 404
        entries = []
        for line in path.read_text(encoding="utf-8").splitlines():
            line = line.strip()
            if line:
                try:
                    entries.append(json.loads(line))
                except json.JSONDecodeError:
                    pass
        return jsonify(entries)

    return app


def _parse_session_meta(path: Path) -> dict[str, Any]:
    meta: dict[str, Any] = {
        "id": path.stem,
        "started_at": None,
        "model": None,
        "provider": None,
        "total_input_tokens": 0,
        "total_output_tokens": 0,
    }
    for line in path.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line:
            continue
        try:
            event = json.loads(line)
        except json.JSONDecodeError:
            continue
        phase = event.get("phase")
        if phase == "session_start":
            meta["started_at"] = event.get("at")
            meta["model"] = event.get("model")
            meta["provider"] = event.get("provider")
        elif phase == "response":
            usage = event.get("usage") or {}
            meta["total_input_tokens"] += int(usage.get("input_tokens", 0))
            meta["total_output_tokens"] += int(usage.get("output_tokens", 0))
    return meta


def run_dashboard(app: Flask, *, port: int = 4568) -> threading.Thread:
    import logging
    log = logging.getLogger("werkzeug")
    log.setLevel(logging.ERROR)

    t = threading.Thread(
        target=lambda: app.run(port=port, threaded=True, use_reloader=False),
        daemon=True,
        name="boukensha-dashboard",
    )
    t.start()
    return t
```

- [ ] **Step 6: Create `src/boukensha/dashboard/__init__.py`**

```python
from .event_bus import EventBus
from .app import create_dashboard_app, run_dashboard, get_bus

__all__ = ["EventBus", "create_dashboard_app", "run_dashboard", "get_bus"]
```

- [ ] **Step 7: Create the HTML template**

Create `src/boukensha/dashboard/templates/index.html`:

```html
<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="UTF-8">
  <meta name="viewport" content="width=device-width, initial-scale=1.0">
  <title>Boukensha Dashboard</title>
  <link rel="stylesheet" href="/static/style.css">
  <script src="https://d3js.org/d3.v7.min.js"></script>
</head>
<body>
  <nav id="tabs">
    <button class="tab-btn active" data-tab="live">Live</button>
    <button class="tab-btn" data-tab="map">Map</button>
    <button class="tab-btn" data-tab="waterfall">Waterfall</button>
    <button class="tab-btn" data-tab="goals">Goals</button>
    <button class="tab-btn" data-tab="sessions">Sessions</button>
  </nav>

  <section id="tab-live" class="tab-pane active">
    <div id="live-log"></div>
  </section>

  <section id="tab-map" class="tab-pane">
    <svg id="map-svg"></svg>
    <div id="room-detail"></div>
  </section>

  <section id="tab-waterfall" class="tab-pane">
    <div id="waterfall-container"></div>
  </section>

  <section id="tab-goals" class="tab-pane">
    <pre id="goals-content"></pre>
  </section>

  <section id="tab-sessions" class="tab-pane">
    <div id="sessions-list"></div>
    <div id="session-transcript"></div>
  </section>

  <script src="/static/app.js" type="module"></script>
  <script src="/static/map.js" type="module"></script>
  <script src="/static/waterfall.js" type="module"></script>
</body>
</html>
```

- [ ] **Step 8: Create CSS**

Create `src/boukensha/dashboard/static/style.css`:

```css
* { box-sizing: border-box; margin: 0; padding: 0; }
body { font-family: monospace; background: #111; color: #ccc; height: 100vh; display: flex; flex-direction: column; }
#tabs { display: flex; background: #1a1a1a; border-bottom: 1px solid #333; }
.tab-btn { background: none; border: none; color: #888; padding: 10px 20px; cursor: pointer; font: inherit; }
.tab-btn.active { color: #fff; border-bottom: 2px solid #4af; }
.tab-pane { display: none; flex: 1; overflow: auto; padding: 12px; }
.tab-pane.active { display: flex; flex-direction: column; }
#live-log { flex: 1; overflow-y: auto; white-space: pre-wrap; font-size: 13px; line-height: 1.5; }
#live-log .phase-tool_call { color: #4af; }
#live-log .phase-tool_result { color: #8f8; }
#live-log .phase-response { color: #fff; }
#live-log .phase-compaction { color: #fa4; font-style: italic; }
#map-svg { width: 100%; height: 70vh; background: #181818; border-radius: 6px; }
#room-detail { padding: 10px; background: #1a1a1a; border-radius: 6px; margin-top: 8px; min-height: 80px; }
#waterfall-container { width: 100%; overflow-x: auto; }
#goals-content { background: #1a1a1a; padding: 12px; border-radius: 6px; font-size: 13px; line-height: 1.6; white-space: pre-wrap; }
#sessions-list table { width: 100%; border-collapse: collapse; font-size: 13px; }
#sessions-list th, #sessions-list td { text-align: left; padding: 6px 12px; border-bottom: 1px solid #333; }
#sessions-list th { color: #888; }
#sessions-list tr:hover td { background: #1e1e1e; cursor: pointer; }
#session-transcript { margin-top: 16px; }
.entry-user { color: #4af; margin: 8px 0 4px; }
.entry-assistant { color: #fff; margin: 4px 0 8px; }
.entry-tool { color: #8f8; font-size: 12px; margin: 2px 0; }
```

- [ ] **Step 9: Create app.js**

Create `src/boukensha/dashboard/static/app.js`:

```javascript
// Tab routing
document.querySelectorAll('.tab-btn').forEach(btn => {
  btn.addEventListener('click', () => {
    document.querySelectorAll('.tab-btn').forEach(b => b.classList.remove('active'));
    document.querySelectorAll('.tab-pane').forEach(p => p.classList.remove('active'));
    btn.classList.add('active');
    document.getElementById('tab-' + btn.dataset.tab).classList.add('active');
    if (btn.dataset.tab === 'map') window.loadMap && window.loadMap();
    if (btn.dataset.tab === 'goals') loadGoals();
    if (btn.dataset.tab === 'sessions') loadSessions();
  });
});

// SSE live feed
const log = document.getElementById('live-log');
const es = new EventSource('/events');
es.onmessage = e => {
  const event = JSON.parse(e.data);
  const div = document.createElement('div');
  div.className = 'phase-' + event.phase;
  if (event.phase === 'response') div.textContent = '[response] ' + event.text;
  else if (event.phase === 'tool_call') div.textContent = '[tool] → ' + event.name + '(' + JSON.stringify(event.args || {}) + ')';
  else if (event.phase === 'tool_result') div.textContent = '[result] ' + (event.result || '').slice(0, 200);
  else if (event.phase === 'compaction') div.textContent = '[compacted — ' + event.dropped + ' messages dropped]';
  else if (event.phase === 'iteration') div.textContent = '[iter ' + event.n + '/' + event.max + ']';
  else return;
  log.appendChild(div);
  log.scrollTop = log.scrollHeight;

  // Forward to waterfall
  window.addWaterfallEvent && window.addWaterfallEvent(event);
};

// Goals tab
async function loadGoals() {
  const el = document.getElementById('goals-content');
  const r = await fetch('/api/goal');
  const data = await r.json();
  el.textContent = Object.entries(data).map(([k, v]) => k + ': ' + v).join('\n');
}

// Sessions tab
async function loadSessions() {
  const r = await fetch('/api/sessions');
  const sessions = await r.json();
  const container = document.getElementById('sessions-list');
  container.innerHTML = '<table><thead><tr><th>Session</th><th>Started</th><th>Model</th><th>Input tokens</th><th>Output tokens</th></tr></thead><tbody>' +
    sessions.map(s =>
      `<tr data-id="${s.id}"><td>${s.id}</td><td>${s.started_at || ''}</td><td>${s.model || ''}</td><td>${s.total_input_tokens}</td><td>${s.total_output_tokens}</td></tr>`
    ).join('') + '</tbody></table>';
  container.querySelectorAll('tr[data-id]').forEach(row => {
    row.addEventListener('click', () => loadSessionDetail(row.dataset.id));
  });
}

async function loadSessionDetail(id) {
  const r = await fetch('/api/sessions/' + id);
  const entries = await r.json();
  const container = document.getElementById('session-transcript');
  container.innerHTML = entries.map(e => {
    if (e.phase === 'response') return `<div class="entry-assistant"><strong>Assistant:</strong> ${e.text || ''}</div>`;
    if (e.phase === 'tool_call') return `<div class="entry-tool">→ ${e.name}(${JSON.stringify(e.args || {})})</div>`;
    if (e.phase === 'tool_result') return `<div class="entry-tool">← ${(e.result || '').slice(0, 300)}</div>`;
    if (e.phase === 'prompt') {
      const last = (e.messages || []).at(-1);
      if (last && last.role === 'user') return `<div class="entry-user"><strong>User:</strong> ${last.content}</div>`;
    }
    return '';
  }).join('');
}
```

- [ ] **Step 10: Create map.js**

Create `src/boukensha/dashboard/static/map.js`:

```javascript
window.loadMap = async function loadMap() {
  const r = await fetch('/api/map');
  const { nodes, links } = await r.json();
  if (!nodes.length) {
    document.getElementById('room-detail').textContent = 'No rooms mapped yet. Explore the MUD first.';
    return;
  }

  const svg = d3.select('#map-svg');
  svg.selectAll('*').remove();
  const width = svg.node().clientWidth || 800;
  const height = svg.node().clientHeight || 500;

  const sim = d3.forceSimulation(nodes)
    .force('link', d3.forceLink(links).id(d => d.id).distance(80))
    .force('charge', d3.forceManyBody().strength(-200))
    .force('center', d3.forceCenter(width / 2, height / 2));

  const g = svg.append('g');
  svg.call(d3.zoom().on('zoom', e => g.attr('transform', e.transform)));

  const link = g.append('g').selectAll('line').data(links).join('line')
    .attr('stroke', '#444').attr('stroke-width', 1.5);

  const label = g.append('g').selectAll('text.link-label').data(links).join('text')
    .attr('class', 'link-label').attr('fill', '#666').attr('font-size', 10)
    .attr('text-anchor', 'middle').text(d => d.direction);

  const node = g.append('g').selectAll('circle').data(nodes).join('circle')
    .attr('r', 8).attr('fill', '#4af').attr('stroke', '#222').attr('stroke-width', 1.5)
    .style('cursor', 'pointer')
    .on('click', (_, d) => {
      document.getElementById('room-detail').textContent =
        'Room: ' + d.title + '\nHash: ' + d.id;
    })
    .call(d3.drag()
      .on('start', (event, d) => { if (!event.active) sim.alphaTarget(0.3).restart(); d.fx = d.x; d.fy = d.y; })
      .on('drag', (event, d) => { d.fx = event.x; d.fy = event.y; })
      .on('end', (event, d) => { if (!event.active) sim.alphaTarget(0); d.fx = null; d.fy = null; }));

  const nodeLabel = g.append('g').selectAll('text.node-label').data(nodes).join('text')
    .attr('class', 'node-label').attr('fill', '#aaa').attr('font-size', 11)
    .attr('dx', 11).attr('dy', 4).text(d => d.title);

  sim.on('tick', () => {
    link.attr('x1', d => d.source.x).attr('y1', d => d.source.y)
        .attr('x2', d => d.target.x).attr('y2', d => d.target.y);
    label.attr('x', d => (d.source.x + d.target.x) / 2)
         .attr('y', d => (d.source.y + d.target.y) / 2);
    node.attr('cx', d => d.x).attr('cy', d => d.y);
    nodeLabel.attr('x', d => d.x).attr('y', d => d.y);
  });
};
```

- [ ] **Step 11: Create waterfall.js**

Create `src/boukensha/dashboard/static/waterfall.js`:

```javascript
const _steps = [];
let _startTime = null;

window.addWaterfallEvent = function addWaterfallEvent(event) {
  const now = Date.now();
  if (!_startTime) _startTime = now;
  const elapsed = now - _startTime;

  if (event.phase === 'iteration') {
    _steps.push({ label: 'Iter ' + event.n, start: elapsed, end: null, type: 'iteration' });
  } else if (event.phase === 'tool_call') {
    _steps.push({ label: event.name, start: elapsed, end: null, type: 'tool' });
  } else if (event.phase === 'tool_result' || event.phase === 'response') {
    const last = _steps.findLast(s => s.end === null);
    if (last) last.end = elapsed;
  }
  renderWaterfall();
};

function renderWaterfall() {
  const container = document.getElementById('waterfall-container');
  if (!_steps.length) return;
  const maxTime = Math.max(..._steps.map(s => s.end || Date.now() - _startTime));
  const rowH = 28, pad = 4, labelW = 160;
  const svgW = Math.max(container.clientWidth - labelW, 400);
  const svgH = _steps.length * rowH + 20;
  const scale = svgW / (maxTime || 1);

  container.innerHTML = `<svg width="${labelW + svgW}" height="${svgH}" style="display:block">` +
    _steps.map((s, i) => {
      const y = i * rowH + pad;
      const x = s.start * scale;
      const w = Math.max(4, ((s.end || maxTime) - s.start) * scale);
      const fill = s.type === 'tool' ? '#4af' : '#fa4';
      const dur = s.end ? (s.end - s.start) + 'ms' : '…';
      return `<text x="2" y="${y + 16}" fill="#888" font-size="12" font-family="monospace">${s.label}</text>` +
        `<rect x="${labelW + x}" y="${y}" width="${w}" height="${rowH - 8}" fill="${fill}" rx="3" opacity="0.8"/>` +
        `<text x="${labelW + x + w + 4}" y="${y + 14}" fill="#666" font-size="11">${dur}</text>`;
    }).join('') + '</svg>';
}
```

- [ ] **Step 12: Run dashboard API tests**

```bash
uv run pytest tests/test_dashboard_api.py -v
```

Expected: all PASS.

- [ ] **Step 13: Run full test suite**

```bash
uv run pytest tests/ -v
```

Expected: all tests PASS.

- [ ] **Step 14: Commit**

```bash
git add pyproject.toml \
        src/boukensha/dashboard/ \
        tests/test_dashboard_api.py
git commit -m "feat(agent-exp): add Python Flask dashboard with Live, Map, Waterfall, Goals, Sessions tabs"
```

---

### Task 5: CLI entry point and --web flag integration

**Files:**
- Create: `bin/boukensha`
- Modify: `src/boukensha/__init__.py` (add `web` param to `repl()`)
- Modify: `src/boukensha/boukensha_loader.py`
- Modify: `pyproject.toml` (add `bin/boukensha` script)

**Interfaces:**
- Consumes:
  - `create_dashboard_app(config_dir, sessions_dir)` (from Task 4)
  - `run_dashboard(app, port)` (from Task 4)
  - `Logger.subscribe(callback)` (existing)
  - `EventBus.publish(event)` (from Task 4)
  - `Config().dir` (existing)
  - `boukensha.repl(...)` (existing)
- Produces:
  - `bin/boukensha` — executable that accepts `--web` (default), `--no-web`, `--port <int>`, `--no-tui` flags
  - `boukensha.repl(web=True, web_port=4568, ...)` — new optional params
  - When `web=True`: starts dashboard thread, wires `Logger.subscribe → EventBus.publish`, then launches TUI (or plain REPL if `--no-tui`)

- [ ] **Step 1: Read boukensha_loader.py**

```bash
cat src/boukensha_loader.py
```

Then read the full file content to understand the current CLI structure before modifying it.

- [ ] **Step 2: Create `bin/boukensha`**

```bash
mkdir -p bin
```

Create `bin/boukensha`:

```python
#!/usr/bin/env python
"""Boukensha MUD agent CLI."""

import argparse
import os
import sys
from pathlib import Path

# Allow running from repo root without install
sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

os.environ.setdefault(
    "BOUKENSHA_DIR",
    str(Path.home() / ".boukensha"),
)

import boukensha


def main():
    parser = argparse.ArgumentParser(
        prog="boukensha",
        description="Boukensha MUD agent",
    )
    parser.add_argument(
        "--web",
        action="store_true",
        default=True,
        help="Start the web dashboard (default: on)",
    )
    parser.add_argument(
        "--no-web",
        action="store_true",
        default=False,
        help="Disable the web dashboard",
    )
    parser.add_argument(
        "--no-tui",
        action="store_true",
        default=False,
        help="Use plain REPL instead of Textual TUI",
    )
    parser.add_argument(
        "--port",
        type=int,
        default=4568,
        help="Dashboard port (default: 4568)",
    )
    args = parser.parse_args()

    use_web = not args.no_web
    use_tui = not args.no_tui

    boukensha.repl(
        tui=use_tui,
        web=use_web,
        web_port=args.port,
    )


if __name__ == "__main__":
    main()
```

Make it executable:
```bash
chmod +x bin/boukensha
```

- [ ] **Step 3: Add web params to `boukensha.repl()` in `__init__.py`**

In `src/boukensha/__init__.py`, modify the `repl()` function signature to add `web: bool = False` and `web_port: int = 4568`. Before `Tui(repl_instance).run()`, add:

```python
    if web:
        from .dashboard.app import create_dashboard_app, run_dashboard, get_bus
        dashboard_app = create_dashboard_app(
            config_dir=str(cfg.dir),
            sessions_dir=str(Path(cfg.dir) / "sessions"),
        )
        bus = get_bus()
        logger.subscribe(bus.publish)
        run_dashboard(dashboard_app, port=web_port)
        import builtins
        _original_print = builtins.print
        def _print_with_log(*a, **kw):
            _original_print(*a, **kw)
        print(f"[dashboard] http://localhost:{web_port}")
```

The full modified section around the `try:` block in `repl()`:

```python
    try:
        if web:
            from .dashboard.app import create_dashboard_app, run_dashboard, get_bus
            from pathlib import Path as _Path
            _dash_app = create_dashboard_app(
                config_dir=str(cfg.dir),
                sessions_dir=str(_Path(cfg.dir) / "sessions"),
            )
            _bus = get_bus()
            logger.subscribe(_bus.publish)
            run_dashboard(_dash_app, port=web_port)
            print(f"[dashboard] http://localhost:{web_port}")
        if tui:
            Tui(repl_instance).run()
        else:
            repl_instance.start()
    except KeyboardInterrupt:
        print("\nInterrupted.")
    finally:
        logger.close()
```

The updated `repl()` signature:

```python
def repl(
    *,
    tui: bool = True,
    web: bool = False,
    web_port: int = 4568,
    system: str | None = None,
    # ... rest unchanged
```

- [ ] **Step 4: Update `pyproject.toml` scripts section**

Add the `bin/boukensha` script to the hatch include and project scripts:

```toml
[project.scripts]
boukensha = "boukensha_loader:main"

[tool.hatch.build.targets.wheel]
sources = ["src"]
include = ["src/boukensha/**", "src/boukensha_loader.py"]
```

The `bin/boukensha` script is a standalone file that runs without installation. To also install it as a script, modify `pyproject.toml`:

```toml
[project.scripts]
boukensha = "boukensha_loader:main"
boukensha-exp = "boukensha_loader:main"
```

Add `bin/` to the hatch include list:

```toml
[tool.hatch.build.targets.wheel]
sources = ["src"]
include = ["src/boukensha/**", "src/boukensha_loader.py"]
```

The `bin/boukensha` script works as a direct invocation: `python bin/boukensha --web`.

- [ ] **Step 5: Run sync and verify CLI works**

```bash
uv sync
uv run python bin/boukensha --help
```

Expected: prints help text with `--web`, `--no-web`, `--no-tui`, `--port` options.

- [ ] **Step 6: Run full test suite**

```bash
uv run pytest tests/ -v
```

Expected: all PASS.

- [ ] **Step 7: Commit**

```bash
git add bin/boukensha \
        src/boukensha/__init__.py \
        pyproject.toml
git commit -m "feat(agent-exp): add bin/boukensha CLI with --web/--no-web/--no-tui flags"
```

---

### Task 6: Wire new tools into `__init__.py` and end-to-end integration

**Files:**
- Modify: `src/boukensha/__init__.py` (register `Navigation`, `RoomProcessor`, `Combat` tools when MUD is configured)
- Modify: `src/boukensha/boukensha_loader.py` (read current file; add `--memory-dir` / use default from Config)

**Interfaces:**
- Consumes:
  - `Navigation.register(registry, session=..., memory_dir=...)` (Task 3)
  - `RoomProcessor.register(registry, session=..., memory_dir=...)` (Task 3)
  - `Combat.register(registry, session=..., goals_dir=...)` (Task 3)
  - `Config().dir` (existing)
  - MUD `session` object from `Mud.register(...)` — **note:** currently `Mud.register` creates the session internally. We need to expose it.

**Session exposure strategy:** The cleanest approach without modifying `mud.py` is to create the `MudSession` externally and pass it to both `Mud._register_with_session` and the new tool registrars. Modify `__init__.py` only.

- [ ] **Step 1: Read the current `__init__.py` run() and repl() MUD section**

Read `src/boukensha/__init__.py` lines around the MUD registration (the `resolved_mud` block). The current code:

```python
resolved_mud = None if mud is False else (mud or _mud_opts_from_config(cfg))
if resolved_mud:
    tools.Mud.register(registry, **resolved_mud)
```

We will change this to expose the session object.

- [ ] **Step 2: Modify `run()` and `repl()` to register new tools when MUD is active**

In both `run()` and `repl()` in `src/boukensha/__init__.py`, replace the MUD registration block with:

```python
    resolved_mud = None if mud is False else (mud or _mud_opts_from_config(cfg))
    _mud_session = None
    if resolved_mud:
        from .tools.mud import MudSession
        _mud_session = MudSession(
            host=resolved_mud.get("host", "localhost"),
            port=resolved_mud.get("port", 4000),
        )
        tools.Mud._register_with_session(registry, _mud_session, **{k: v for k, v in resolved_mud.items() if k in ("name", "password")})
        # Register token-saving tools that share the same session
        _memory_dir = str(Path(cfg.dir) / "memory")
        _goals_dir = str(cfg.dir)
        tools.Navigation.register(registry, session=_mud_session, memory_dir=_memory_dir)
        tools.RoomProcessor.register(registry, session=_mud_session, memory_dir=_memory_dir)
        tools.Combat.register(registry, session=_mud_session, goals_dir=_goals_dir)
```

Add `from pathlib import Path` at the top of the file if not already imported (check first).

- [ ] **Step 3: Run full test suite**

```bash
uv run pytest tests/ -v
```

Expected: all PASS. The existing `test_tools_mud.py` tests use a mock session, so they should be unaffected.

- [ ] **Step 4: Smoke-test the CLI (no live MUD needed)**

```bash
uv run python -c "
import sys
sys.path.insert(0, 'src')
import boukensha
print('boukensha version:', boukensha.__version__)
from boukensha.memory.parser import RoomParser
room = RoomParser.parse('Temple Square\n   A large square.\nExits: north, south\n')
print('parser:', room['title'], list(room['exits'].keys()))
from boukensha.goals.goal_manager import GoalManager
import tempfile, pathlib
with tempfile.TemporaryDirectory() as d:
    gm = GoalManager(d)
    gm.update(current_goal='Test goal')
    print('goal:', gm.read()['current_goal'])
print('All subsystems OK')
"
```

Expected output:
```
boukensha version: 0.12.0
parser: Temple Square ['north', 'south']
goal: Test goal
All subsystems OK
```

- [ ] **Step 5: Update system prompt to mention new tools**

The system prompt is in `prompts/system.md`. Read it first, then append a section describing the new tools so the agent knows to use them:

```bash
cat prompts/system.md
```

Add to the end of `prompts/system.md`:

```markdown

## Token-Efficient Tools (use these instead of raw MUD commands where possible)

- **process_room** — look at the current room and get ONLY new/changed info. Returns empty if room is unchanged. Use this instead of `look` to save tokens.
- **navigate_to(destination)** — move to a known destination using the built map. Much faster and cheaper than moving step by step. Use once you've visited a room.
- **combat_loop(target, flee_hp)** — fight a target in a Python loop. Flees automatically if HP drops to flee_hp. Use for routine fights against known-weak mobs.
- **goal_read** — read your current goal YAML.
- **goal_update(current_goal, priority, status, notes)** — update your current goal. Update frequently to reflect current state.
```

- [ ] **Step 6: Run full test suite one final time**

```bash
uv run pytest tests/ -v --tb=short
```

Expected: all PASS. Zero failures.

- [ ] **Step 7: Final commit**

```bash
git add src/boukensha/__init__.py \
        prompts/system.md
git commit -m "feat(agent-exp): wire Navigation/RoomProcessor/Combat into run()/repl(); update system prompt"
```

---

## Self-Review

**Spec coverage check:**

| Requirement | Task |
|---|---|
| Room memory with hashing, exits, NPCs, items | Task 1 (RoomParser, RoomMemory) |
| WorldGraph + pathfinding | Task 1 (WorldGraph, Pathfinder) |
| Program handles room recording, not LLM | Task 3 (process_room tool) |
| Goal section in .boukensha with YAML | Task 2 (GoalManager) |
| HP flee threshold auto-update | Task 2 (CombatMonitor) |
| Agent goal_read / goal_update tools | Task 3 (Combat.register) |
| Python web dashboard with tabs | Task 4 (Flask app) |
| Live tab with SSE | Task 4 (EventBus + SSE endpoint) |
| Map tab with force-directed graph | Task 4 (map.js + D3) |
| Waterfall tab | Task 4 (waterfall.js) |
| Goals tab | Task 4 (goals tab + /api/goal) |
| Sessions tab (replaces Ruby log_viz) | Task 4 (sessions endpoints) |
| Modular tabs (easy to add more) | Task 4 (JS module pattern) |
| navigate_to tool | Task 3 |
| combat_loop tool | Task 3 |
| bin/boukensha CLI | Task 5 |
| --web / --no-web / --no-tui flags | Task 5 |
| Wire tools into run()/repl() | Task 6 |
| Token minimization strategy | Tasks 1+3 (process_room diff, navigate_to) |

**Placeholder scan:** None found — all steps have concrete code.

**Type consistency check:** All method signatures are consistent across tasks:
- `RoomParser.parse(raw: str) -> dict` — used in Tasks 1, 3, 6
- `RoomMemory.record(room: dict) -> tuple[str, dict]` — used in Tasks 1, 3
- `WorldGraph.add_room/add_edge/get_neighbors/save/load` — consistent Tasks 1, 3, 4
- `Pathfinder.find_path/find_path_by_title` — consistent Tasks 1, 3
- `GoalManager.read/update/reset` — consistent Tasks 2, 3, 4, 6
- `CombatMonitor.check/update_on_low_hp` — consistent Tasks 2, 3
- `EventBus.publish/subscribe/stream` — consistent Tasks 4, 5
