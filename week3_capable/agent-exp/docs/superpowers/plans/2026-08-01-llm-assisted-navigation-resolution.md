# LLM-Assisted Navigation Resolution Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** When `navigate_to` can't deterministically resolve a destination (e.g. "the bakery," "your guild," "the newbie zone"), give the agent enough map information to resolve it itself, and let it persist that resolution as a reusable alias so the same term resolves deterministically next time.

**Architecture:** Add a new `RoomAliases` JSON store (same atomic-write pattern as `BlockedExits`/`KnowledgeManager`). `navigate_to`'s matching pipeline checks aliases first, before title/landmark search. A new `navigate_alias_add` tool resolves a destination the same way `navigate_to` does and persists the mapping. When `navigate_to` finds no match at all (not even a near-miss), its error message now includes the full list of known room titles instead of a dead end, so the agent's own reasoning can pick the right one and retry.

**Tech Stack:** Python 3, existing `boukensha` package conventions (dataclasses/plain classes, `pathlib`, atomic `os.replace` writes, `networkx` via `WorldGraph`, `pytest` + `unittest.mock.MagicMock` for tool tests).

## Global Constraints

- No nested/extra LLM call inside `navigate_to` — resolution stays in the existing agent loop; the tool itself remains pure Python.
- No changes to `explore()`, combat, or the dashboard.
- No automatic/inferred aliasing — aliasing is always an explicit `navigate_alias_add` call.
- Alias store uses the same atomic-write pattern (`.tmp` + `os.replace`) as `BlockedExits` and `KnowledgeManager`.
- Alias lookup must run *before* title/landmark matching in `_navigate_to`, so a learned alias always wins over (and fixes) an ambiguous word-overlap match.

---

## File Structure

```
src/boukensha/memory/room_aliases.py   # new: RoomAliases store (alias -> room_hash, atomic JSON)
src/boukensha/tools/navigation.py      # modified: alias-first lookup, navigate_alias_add tool,
                                        # full-title-list fallback in the no-match error message
src/boukensha/__init__.py              # modified: construct RoomAliases, pass into Navigation.register
                                        # at both existing call sites
prompts/system.md                      # modified: guidance on retrying with the exact title,
                                        # then calling navigate_alias_add
architecture.md                        # modified: document RoomAliases + navigate_alias_add
game_findings.md                       # modified: new Implemented entry
tests/test_room_aliases.py             # new
tests/test_navigation_tool.py          # modified: additions
```

---

### Task 1: `RoomAliases` store

**Files:**
- Create: `src/boukensha/memory/room_aliases.py`
- Test: `tests/test_room_aliases.py`

**Interfaces:**
- Produces: `RoomAliases(base_dir: str | Path)` with `.get(alias: str) -> str | None`, `.add(alias: str, room_hash: str) -> None`, `.read_all() -> dict[str, str]`. Persists to `{base_dir}/room_aliases.json`. Alias keys are stored and looked up lowercased.

- [ ] **Step 1: Write the failing tests**

```python
# tests/test_room_aliases.py
from __future__ import annotations
from boukensha.memory.room_aliases import RoomAliases


def test_add_and_get(tmp_path):
    aliases = RoomAliases(tmp_path)
    aliases.add("bakery", "abc123")
    assert aliases.get("bakery") == "abc123"


def test_get_is_case_insensitive(tmp_path):
    aliases = RoomAliases(tmp_path)
    aliases.add("Bakery", "abc123")
    assert aliases.get("bakery") == "abc123"
    assert aliases.get("BAKERY") == "abc123"


def test_get_missing_alias_returns_none(tmp_path):
    aliases = RoomAliases(tmp_path)
    assert aliases.get("nonexistent") is None


def test_add_overwrites_existing_alias(tmp_path):
    aliases = RoomAliases(tmp_path)
    aliases.add("guild", "old_hash")
    aliases.add("guild", "new_hash")
    assert aliases.get("guild") == "new_hash"


def test_read_all_returns_lowercased_map(tmp_path):
    aliases = RoomAliases(tmp_path)
    aliases.add("Bakery", "abc123")
    aliases.add("newbie zone", "def456")
    assert aliases.read_all() == {"bakery": "abc123", "newbie zone": "def456"}


def test_persists_across_instances(tmp_path):
    RoomAliases(tmp_path).add("bakery", "abc123")
    reloaded = RoomAliases(tmp_path)
    assert reloaded.get("bakery") == "abc123"


def test_atomic_write_no_partial_state(tmp_path):
    import os
    aliases = RoomAliases(tmp_path)
    aliases.add("bakery", "abc123")
    assert not any(f.endswith(".tmp") for f in os.listdir(tmp_path))
    assert (tmp_path / "room_aliases.json").exists()


def test_read_all_empty_when_no_file(tmp_path):
    aliases = RoomAliases(tmp_path)
    assert aliases.read_all() == {}


def test_tolerates_corrupt_file(tmp_path):
    (tmp_path / "room_aliases.json").write_text("not valid json", encoding="utf-8")
    aliases = RoomAliases(tmp_path)
    assert aliases.read_all() == {}
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `cd week3_capable/agent-exp && uv run pytest tests/test_room_aliases.py -v`
Expected: FAIL with `ModuleNotFoundError: No module named 'boukensha.memory.room_aliases'`

- [ ] **Step 3: Write the implementation**

```python
# src/boukensha/memory/room_aliases.py
"""Persist LLM-learned shorthand aliases (e.g. "bakery", "your guild") to the
room hash they were confirmed to resolve to, so a fuzzy destination that
navigate_to's deterministic title/landmark matching cannot reliably resolve
on its own only ever needs the agent's help once."""

from __future__ import annotations

import json
import os
from pathlib import Path
from typing import Any


class RoomAliases:
    def __init__(self, base_dir: str | Path) -> None:
        self._path = Path(base_dir) / "room_aliases.json"

    def get(self, alias: str) -> str | None:
        return self.read_all().get(alias.lower())

    def add(self, alias: str, room_hash: str) -> None:
        data = self.read_all()
        data[alias.lower()] = room_hash
        self._write(data)

    def read_all(self) -> dict[str, str]:
        if not self._path.exists():
            return {}
        try:
            data = json.loads(self._path.read_text(encoding="utf-8"))
        except (json.JSONDecodeError, OSError):
            return {}
        return data if isinstance(data, dict) else {}

    def _write(self, data: dict[str, Any]) -> None:
        tmp = self._path.with_suffix(".tmp")
        tmp.write_text(json.dumps(data, indent=2, ensure_ascii=False), encoding="utf-8")
        os.replace(tmp, self._path)
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `cd week3_capable/agent-exp && uv run pytest tests/test_room_aliases.py -v`
Expected: PASS (9 tests)

- [ ] **Step 5: Commit**

```bash
cd week3_capable/agent-exp
git add src/boukensha/memory/room_aliases.py tests/test_room_aliases.py
git commit -m "Add RoomAliases store for learned navigation shorthand"
```

---

### Task 2: Alias-first lookup + `navigate_alias_add` tool in `navigate_to`

**Files:**
- Modify: `src/boukensha/tools/navigation.py`
- Test: `tests/test_navigation_tool.py` (additions)

**Interfaces:**
- Consumes: `RoomAliases(base_dir).get(alias) -> str | None` / `.add(alias, room_hash) -> None` (Task 1). `Pathfinder(graph).route_by_title(start_hash, fragment) -> Route | None`, `.route_to(start_hash, end_hash) -> Route | None` (existing, `memory/pathfinder.py`). `Route.nodes: list[str]` (existing).
- Produces: `_navigate_to` now checks `aliases.get(destination)` before title/landmark matching. New tool `navigate_alias_add(alias: str, destination: str) -> str`, registered in the same `Navigation.register` call, reusing the closures `_current_room_hash`, `_landmark_haystacks`, `_route_by_landmark` already defined in that method.

Current relevant code in `src/boukensha/tools/navigation.py` (for reference — read the file before editing, it may have shifted slightly):

```python
        def _navigate_to(destination: str, **_: Any) -> str:
            if not session.is_open:
                return "error: not connected"
            start_hash = _current_room_hash()
            if start_hash is None:
                return "error: could not determine current room"
            if world_graph is None:
                graph.load()
            pf = Pathfinder(graph)
            route = pf.route_by_title(start_hash, destination)
            landmark_room: str | None = None
            haystacks = _landmark_haystacks()
            if route is None:
                found = _route_by_landmark(pf, start_hash, destination, haystacks)
                if found is not None:
                    route, landmark_room = found
```

- [ ] **Step 1: Write the failing tests**

Add to `tests/test_navigation_tool.py`:

```python
def test_navigate_to_resolves_via_alias_before_title_search(tmp_path):
    """An aliased destination must resolve directly through the alias store,
    bypassing the ambiguous word-overlap title search entirely — this is
    what lets a term like 'guild of swordsmen' stop being ambiguous once
    the agent has confirmed which guild it actually means."""
    from boukensha.tools.navigation import Navigation
    from boukensha.registry import Registry
    from boukensha.context import Context
    from boukensha.tasks.player import Player
    from boukensha.memory.room_aliases import RoomAliases

    memory_dir = tmp_path / "memory"
    graph = WorldGraph(memory_dir)
    graph.add_room("aaa", "Main Street")
    graph.add_room("bbb", "The Entrance To The Clerics' Guild")
    graph.add_room("ccc", "The Guild Of Swordsmen")
    graph.add_edge("aaa", "bbb", "west")
    graph.add_edge("aaa", "ccc", "east")

    RoomAliases(memory_dir).add("guild of swordsmen", "ccc")

    registry = Registry(Context(task=Player, system="sys"))
    session = MagicMock()
    session.is_open = True
    session.drain.return_value = ""
    session.read_until_prompt.side_effect = [
        "Main Street\n   A street.\n[ Exits: w, e ]\n",
        "You go east.\n",
        "The Guild Of Swordsmen\n   A training hall.\n[ Exits: w ]\n",
    ]
    Navigation.register(registry, session=session, memory_dir=memory_dir, world_graph=graph)

    result = registry.dispatch("navigate_to", {"destination": "guild of swordsmen"})

    assert "swordsmen" in result.lower()
    assert "1 moves" in result


def test_navigate_alias_add_resolves_current_room_and_persists(tmp_path):
    """The common flow: the agent is already standing in the room it wants
    to alias (having just reached it, e.g. via an exact-title navigate_to),
    and calls navigate_alias_add with that exact title."""
    from boukensha.tools.navigation import Navigation
    from boukensha.registry import Registry
    from boukensha.context import Context
    from boukensha.tasks.player import Player
    from boukensha.memory.room_aliases import RoomAliases

    memory_dir = tmp_path / "memory"
    graph = WorldGraph(memory_dir)

    registry = Registry(Context(task=Player, system="sys"))
    session = MagicMock()
    session.is_open = True
    session.drain.return_value = ""
    session.read_until_prompt.return_value = "The Bakery\n   Smells of fresh bread.\n[ Exits: s ]\n"
    Navigation.register(registry, session=session, memory_dir=memory_dir, world_graph=graph)

    result = registry.dispatch("navigate_alias_add", {"alias": "bakery", "destination": "The Bakery"})

    assert "bakery" in result.lower()
    aliases = RoomAliases(memory_dir)
    room_hash = aliases.get("bakery")
    assert room_hash is not None
    assert graph.graph.nodes[room_hash]["title"] == "The Bakery"


def test_navigate_alias_add_resolves_landmark_in_another_room(tmp_path):
    """Aliasing must also work for a landmark inside a different, already
    known room — not just the room the character currently stands in."""
    from boukensha.tools.navigation import Navigation
    from boukensha.registry import Registry
    from boukensha.context import Context
    from boukensha.tasks.player import Player
    from boukensha.memory.room_memory import RoomMemory
    from boukensha.memory.parser import RoomParser
    from boukensha.memory.room_aliases import RoomAliases

    memory_dir = tmp_path / "memory"
    mem = RoomMemory(memory_dir)

    start_raw = "Main Street\n   A street.\n[ Exits: n ]\n"
    square_raw = (
        "The Temple Square\n   You are standing on the temple square.\n"
        "[ Exits: s ]\n"
        "A large fountain carved from blue-streaked marble is here, bubbling merrily.\n"
    )
    start_room = RoomParser.parse(start_raw)
    square_room = RoomParser.parse(square_raw)
    start_hash, _ = mem.record(start_room)
    square_hash, _ = mem.record(square_room)

    graph = WorldGraph(memory_dir)
    graph.add_room(start_hash, "Main Street")
    graph.add_room(square_hash, "The Temple Square")
    graph.add_edge(start_hash, square_hash, "north")

    registry = Registry(Context(task=Player, system="sys"))
    session = MagicMock()
    session.is_open = True
    session.drain.return_value = ""
    session.read_until_prompt.return_value = start_raw
    Navigation.register(registry, session=session, memory_dir=memory_dir, world_graph=graph)

    result = registry.dispatch("navigate_alias_add", {"alias": "fountain", "destination": "fountain"})

    assert "temple square" in result.lower()
    assert RoomAliases(memory_dir).get("fountain") == square_hash


def test_navigate_alias_add_reports_failure_when_destination_unresolvable(tmp_path):
    from boukensha.tools.navigation import Navigation
    from boukensha.registry import Registry
    from boukensha.context import Context
    from boukensha.tasks.player import Player
    from boukensha.memory.room_aliases import RoomAliases

    memory_dir = tmp_path / "memory"
    graph = WorldGraph(memory_dir)

    registry = Registry(Context(task=Player, system="sys"))
    session = MagicMock()
    session.is_open = True
    session.drain.return_value = ""
    session.read_until_prompt.return_value = "Main Street\n   A street.\n[ Exits: n ]\n"
    Navigation.register(registry, session=session, memory_dir=memory_dir, world_graph=graph)

    result = registry.dispatch(
        "navigate_alias_add", {"alias": "newbie zone", "destination": "The Newbie Zone Entrance"}
    )

    assert "could not resolve" in result.lower()
    assert RoomAliases(memory_dir).get("newbie zone") is None
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `cd week3_capable/agent-exp && uv run pytest tests/test_navigation_tool.py -v -k "alias"`
Expected: FAIL — `navigate_to` doesn't check aliases (first test resolves via ambiguous word-overlap or fails), `navigate_alias_add` tool doesn't exist (`UnknownToolError`).

- [ ] **Step 3: Implement alias-first lookup and the new tool**

In `src/boukensha/tools/navigation.py`, add the import and construct the store alongside the existing `mem`/`graph`/`tracker` construction in `register`:

```python
from boukensha.memory.room_aliases import RoomAliases
```

```python
        mem = RoomMemory(memory_dir)
        graph = world_graph if world_graph is not None else WorldGraph(memory_dir)
        if world_graph is None:
            graph.load()
        tracker = PlayerTracker(memory_dir)
        aliases = RoomAliases(memory_dir)
```

Update `_navigate_to` to check the alias store before title/landmark matching:

```python
        def _navigate_to(destination: str, **_: Any) -> str:
            if not session.is_open:
                return "error: not connected"
            start_hash = _current_room_hash()
            if start_hash is None:
                return "error: could not determine current room"
            if world_graph is None:
                graph.load()
            pf = Pathfinder(graph)
            route: Route | None = None
            landmark_room: str | None = None
            alias_hash = aliases.get(destination)
            if alias_hash and graph.has_room(alias_hash):
                route = pf.route_to(start_hash, alias_hash)
                if route is None:
                    title = graph.graph.nodes[alias_hash].get("title", destination)
                    return (
                        f"'{destination}' is aliased to the known room '{title}', "
                        f"but no walkable path there is currently known from here — "
                        f"likely a one-way passage that was only ever walked in the "
                        f"other direction. Call explore() to find another route out "
                        f"rather than retrying navigate_to with the same destination."
                    )
            if route is None:
                route = pf.route_by_title(start_hash, destination)
            haystacks = _landmark_haystacks()
            if route is None:
                found = _route_by_landmark(pf, start_hash, destination, haystacks)
                if found is not None:
                    route, landmark_room = found
```

(the rest of `_navigate_to` — the `if route is None:` fallback block, the `path`/`dest_desc`/`walk_route` handling below — is unchanged by this task; Task 3 modifies only the final "nothing matched at all" branch inside that unchanged fallback block.)

Add the new tool's implementation function, placed after `_navigate_to` and before the `registry.tool("navigate_to", ...)` call:

```python
        def _navigate_alias_add(alias: str, destination: str, **_: Any) -> str:
            if not session.is_open:
                return "error: not connected"
            start_hash = _current_room_hash()
            if start_hash is None:
                return "error: could not determine current room"
            if world_graph is None:
                graph.load()
            pf = Pathfinder(graph)
            route = pf.route_by_title(start_hash, destination)
            if route is None:
                haystacks = _landmark_haystacks()
                found = _route_by_landmark(pf, start_hash, destination, haystacks)
                if found is not None:
                    route, _landmark_room = found
            if route is None or not route.nodes:
                return (
                    f"Could not resolve '{destination}' to a known room to alias — "
                    f"navigate_to it successfully first, then retry navigate_alias_add "
                    f"with its exact title."
                )
            room_hash = route.nodes[-1]
            aliases.add(alias, room_hash)
            title = graph.graph.nodes[room_hash].get("title", destination)
            return f"Remembered: '{alias}' now resolves directly to '{title}'."
```

Register it right after the existing `registry.tool("navigate_to", ...)` call:

```python
        registry.tool(
            "navigate_alias_add",
            description=(
                "Remember that a shorthand term (e.g. 'bakery', 'your guild', "
                "'the newbie zone') refers to a specific already-known room, so "
                "future navigate_to calls with that term resolve directly instead "
                "of failing or matching ambiguously. Call this once you've "
                "confirmed the exact room — e.g. after navigate_to succeeded "
                "using the room's exact title, or while standing in the room the "
                "shorthand refers to."
            ),
            parameters={
                "alias": {
                    "type": "string",
                    "description": "The shorthand term to remember (case-insensitive), e.g. 'bakery'",
                },
                "destination": {
                    "type": "string",
                    "description": (
                        "The exact room title (or a landmark/item/npc mentioned inside "
                        "a room) identifying which room the alias refers to — same "
                        "matching rules as navigate_to's destination"
                    ),
                },
            },
            block=_navigate_alias_add,
        )
```

Also add `Route` to the existing pathfinder import line so the type hint in `_navigate_to` resolves:

```python
from boukensha.memory.pathfinder import Pathfinder, Route, partial_word_matches, text_matches, word_overlap_matches
```

(This import already exists in the file with `Route` included — verify before adding a duplicate.)

- [ ] **Step 4: Run tests to verify they pass**

Run: `cd week3_capable/agent-exp && uv run pytest tests/test_navigation_tool.py -v`
Expected: PASS (all existing tests plus the 4 new ones)

- [ ] **Step 5: Commit**

```bash
cd week3_capable/agent-exp
git add src/boukensha/tools/navigation.py tests/test_navigation_tool.py
git commit -m "Add navigate_alias_add tool and alias-first destination lookup"
```

---

### Task 3: Full known-title list when nothing matches at all

**Files:**
- Modify: `src/boukensha/tools/navigation.py`
- Test: `tests/test_navigation_tool.py` (additions)

**Interfaces:**
- Consumes: nothing new — operates on `graph.graph.nodes(data=True)` already available in `_navigate_to`'s existing fallback block.
- Produces: when `route is None` and both `known_matches` and `near_misses` (existing local variables in `_navigate_to`'s fallback block) are empty, the returned message includes the full sorted list of known room titles (capped) instead of the current flat `"No known path to '{destination}'. Explore more of the area first."`.

Current code in `_navigate_to` (the branch this task changes — read the file first, as Task 2 may have shifted line numbers):

```python
            if route is None:
                titles = {node: attrs.get("title") or "" for node, attrs in graph.graph.nodes(data=True)}
                known_matches = text_matches(destination, titles) or text_matches(destination, haystacks)
                if known_matches:
                    matched_titles = ", ".join(sorted({titles.get(n, n) for n in known_matches}))
                    return (
                        f"'{destination}' matches an already-mapped room ({matched_titles}), "
                        f"but no walkable path there is currently known from here — likely a "
                        f"one-way passage that was only ever walked in the other direction. "
                        f"Call explore() to find another route out rather than retrying "
                        f"navigate_to with the same destination."
                    )
                near_misses = partial_word_matches(destination, titles)
                if near_misses:
                    suggestions = ", ".join(sorted({titles[n] for n in near_misses}))
                    return (
                        f"No confident match for '{destination}'. Similarly named rooms "
                        f"already mapped (none matched closely enough to route to "
                        f"automatically): {suggestions}. If one of these is actually what "
                        f"you meant, navigate_to its exact title. If the real destination "
                        f"hasn't been visited yet but is named in the CURRENT room's own "
                        f"description/exits, just move that direction directly instead of "
                        f"calling navigate_to."
                    )
                return f"No known path to '{destination}'. Explore more of the area first."
```

- [ ] **Step 1: Write the failing test**

Add to `tests/test_navigation_tool.py`:

```python
def test_navigate_to_lists_all_known_titles_when_nothing_matches_at_all(tmp_path):
    """When a destination shares no vocabulary with any mapped room's title,
    description, items, or npcs, the old message ("No known path... Explore
    more") gave the LLM nothing to work with even when it already knows
    (from its own memory of the session) which room it actually means. It
    must instead see every currently known room title so it can retry with
    the exact one."""
    from boukensha.tools.navigation import Navigation
    from boukensha.registry import Registry
    from boukensha.context import Context
    from boukensha.tasks.player import Player

    memory_dir = tmp_path / "memory"
    graph = WorldGraph(memory_dir)
    graph.add_room("aaa", "Main Street")
    graph.add_room("bbb", "The Sweetwater Pastry Shop")

    registry = Registry(Context(task=Player, system="sys"))
    session = MagicMock()
    session.is_open = True
    session.drain.return_value = ""
    session.read_until_prompt.return_value = "Main Street\n   A street.\n[ Exits: n ]\n"
    Navigation.register(registry, session=session, memory_dir=memory_dir, world_graph=graph)

    result = registry.dispatch("navigate_to", {"destination": "bakery"})

    assert "Sweetwater Pastry Shop" in result
    assert "Main Street" in result
    assert "navigate_alias_add" in result


def test_navigate_to_omits_full_title_list_when_a_near_miss_exists(tmp_path):
    """The full-list fallback must only fire when there's truly no
    near-miss either — a near-miss message is more specific and should
    still win, unchanged from existing behavior."""
    from boukensha.tools.navigation import Navigation
    from boukensha.registry import Registry
    from boukensha.context import Context
    from boukensha.tasks.player import Player

    memory_dir = tmp_path / "memory"
    graph = WorldGraph(memory_dir)
    graph.add_room("aaa", "Main Street")
    graph.add_room("bbb", "The Entrance To The Clerics' Guild")

    registry = Registry(Context(task=Player, system="sys"))
    session = MagicMock()
    session.is_open = True
    session.drain.return_value = ""
    session.read_until_prompt.return_value = "Main Street\n   A street.\n[ Exits: n ]\n"
    Navigation.register(registry, session=session, memory_dir=memory_dir, world_graph=graph)

    result = registry.dispatch("navigate_to", {"destination": "Guild of Swordsmen"})

    assert "No confident match" in result
    assert "navigate_alias_add" not in result
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `cd week3_capable/agent-exp && uv run pytest tests/test_navigation_tool.py -v -k "lists_all_known_titles or omits_full_title_list"`
Expected: FAIL — first test's assertions on the full title list and `navigate_alias_add` fail against the current flat message; second test should already pass (sanity check it isn't broken).

- [ ] **Step 3: Implement**

Replace the final `return f"No known path to '{destination}'. Explore more of the area first."` line in `_navigate_to`'s fallback block with:

```python
                all_titles = sorted({t for t in titles.values() if t})
                if all_titles:
                    _MAX_TITLES = 60
                    shown = all_titles[:_MAX_TITLES]
                    suffix = f", plus {len(all_titles) - _MAX_TITLES} more" if len(all_titles) > _MAX_TITLES else ""
                    return (
                        f"No confident match for '{destination}' — it shares no "
                        f"recognizable vocabulary with any mapped room. All "
                        f"currently known room titles: {', '.join(shown)}{suffix}. "
                        f"If one of these is actually your destination, retry "
                        f"navigate_to with its exact title, then call "
                        f"navigate_alias_add(alias='{destination}', "
                        f"destination='<exact title>') so this shorthand resolves "
                        f"directly next time. If the destination truly isn't mapped "
                        f"yet, call explore()."
                    )
                return f"No known path to '{destination}'. Explore more of the area first."
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `cd week3_capable/agent-exp && uv run pytest tests/test_navigation_tool.py -v`
Expected: PASS (all tests, including the pre-existing ones — confirms this branch change didn't disturb the near-miss/known-but-unreachable branches above it)

- [ ] **Step 5: Commit**

```bash
cd week3_capable/agent-exp
git add src/boukensha/tools/navigation.py tests/test_navigation_tool.py
git commit -m "List all known room titles when navigate_to finds no match at all"
```

---

### Task 4: Wire into app startup and system prompt

**Files:**
- Modify: `src/boukensha/__init__.py` (no functional change needed — verify `Navigation.register`'s existing call sites still work unmodified, since `RoomAliases` is constructed internally in Task 2 from the `memory_dir` already passed in)
- Modify: `prompts/system.md`

**Interfaces:**
- Consumes: `Navigation.register(registry, session=..., memory_dir=..., world_graph=..., character_name=..., prev_hash_ref=..., last_direction_ref=...)` — unchanged signature from Task 2 (Task 2 constructs `RoomAliases(memory_dir)` internally, so no caller changes are required).

- [ ] **Step 1: Confirm no signature changes are needed**

Run: `cd week3_capable/agent-exp && grep -n "Navigation.register" src/boukensha/__init__.py`
Expected: both call sites (around lines 219 and 413) pass `memory_dir` already — no edits needed here since Task 2 kept `Navigation.register`'s parameter list unchanged. This step is a verification, not a code change.

- [ ] **Step 2: Add system prompt guidance**

In `prompts/system.md`, replace this existing paragraph:

```markdown
**If `navigate_to` returns "No confident match"** with a list of similarly-named rooms, that is not the same as "no known path" — it means the name you gave is ambiguous or not yet mapped, and it deliberately did not guess. Before retrying: re-read the current room's own text and your last few known locations for the actual name/direction, and `knowledge_search` for it. Only call `explore()` to search blindly once you've confirmed the destination genuinely isn't visible or known anywhere nearby — don't just retry the same fuzzy name expecting a different result.
```

with:

```markdown
**If `navigate_to` returns "No confident match"** with a list of similarly-named rooms, or the full list of every known room title, that is not the same as "no known path" — it means the name you gave is ambiguous or not yet mapped, and it deliberately did not guess. Before retrying: re-read the current room's own text and your last few known locations for the actual name/direction, `knowledge_search` for it, and check whether the exact title you need is actually right there in the list navigate_to just gave you — you often already know which room is meant even when the fuzzy match doesn't. If you can identify the right room from that list, retry `navigate_to` with its **exact title**, then call `navigate_alias_add(alias=<the term you originally used>, destination=<the exact title that worked>)` so the same shorthand (e.g. "bakery," "your guild," "the newbie zone") resolves directly next time without this detour. Only call `explore()` to search blindly once you've confirmed the destination genuinely isn't visible or known anywhere nearby — don't just retry the same fuzzy name expecting a different result.
```

- [ ] **Step 3: Verify no test suite depends on the old prompt wording**

Run: `cd week3_capable/agent-exp && grep -rn "No confident match\|navigate_alias_add" tests/`
Expected: no test asserts on the literal system-prompt paragraph text (only `test_navigation_tool.py`'s tool-return-value assertions, unaffected by this file). If any test does match, update it to the new wording.

- [ ] **Step 4: Commit**

```bash
cd week3_capable/agent-exp
git add prompts/system.md
git commit -m "Document navigate_alias_add workflow in system prompt"
```

---

### Task 5: Documentation — architecture.md and game_findings.md

**Files:**
- Modify: `architecture.md`
- Modify: `game_findings.md`

**Interfaces:**
- None (documentation only).

- [ ] **Step 1: Update `architecture.md`'s Component Overview table**

Add a new row directly after the `Pathfinder` row (currently the row starting `| **\`Pathfinder\`** |`):

```markdown
| **`RoomAliases`** | `src/boukensha/memory/room_aliases.py` | Reads/writes `.boukensha/memory/room_aliases.json`; case-insensitive `alias -> room_hash` map. `navigate_to` checks this before title/landmark matching, so a term the agent has explicitly confirmed once (via `navigate_alias_add`) resolves deterministically thereafter, bypassing any ambiguous word-overlap match. |
```

Update the existing `navigate_to` tool row (currently starting `| **\`navigate_to\` tool** |`) to mention alias-first lookup and the new full-title-list fallback:

```markdown
| **`navigate_to` tool** | `src/boukensha/tools/navigation.py` | Python-only pathfinding + move execution; no LLM per step. Checks a learned alias first (`RoomAliases`), then matches room titles, then falls back to searching every mapped room's description/items/npcs (a landmark like "the fountain"); disambiguates multiple matches by shortest route. When nothing matches at all, its error message lists every currently known room title so the agent can retry with the exact one and then call `navigate_alias_add` to remember it — rather than a flat "no known path" dead end. Distinguishes "known room but unreachable" (one-way passage) from "no match" (with near-miss suggestions or the full title list) so the LLM gets an actionable message. |
| **`navigate_alias_add` tool** | `src/boukensha/tools/navigation.py` | Resolves a `destination` the same way `navigate_to` does (title, then landmark search, tie-broken by distance from the current room) and persists `alias -> room_hash` via `RoomAliases`. Called by the agent once it has confirmed which room a fuzzy shorthand ("bakery," "your guild") actually refers to, so future `navigate_to` calls with that shorthand resolve directly. |
```

Add `ROOMALIASFILE` (or extend the existing `MEMFILES` node's label) to the Data Flow Diagram's `inputs` subgraph and wire it into `NAVTOOL`. In the mermaid block, change:

```mermaid
        MEMFILES[".boukensha/memory/\nrooms/*.json\nworld_graph.json\nblocked_exits.json"]
```

to:

```mermaid
        MEMFILES[".boukensha/memory/\nrooms/*.json\nworld_graph.json\nblocked_exits.json\nroom_aliases.json"]
```

(No new node needed — `room_aliases.json` lives in the same `.boukensha/memory/` directory as the other files `MEMFILES` already represents, and `NAVTOOL` already has an arrow to/from that subgraph via `PATHFIND`/`WGRAPH`.)

- [ ] **Step 2: Add a new entry to `game_findings.md`**

Add under the `## Implemented` heading, as a new bullet (place it after the existing "Landmarks... live inside a room's description/items" entry, since it builds directly on that one):

```markdown
- **A destination that shares no vocabulary at all with any mapped room's
  title/description/items/npcs had no way to resolve.** Found live: "go
  find the bakery" (and similarly "go train at your guild," "go find the
  newbie zone") failed outright with a flat "No known path... Explore more
  of the area first," even when the agent itself already knew — from its
  own memory of the session, or by recognizing the real title in a list —
  exactly which room was meant. Two related problems: the room's real
  title/text might share literally no word with the term used, so no
  substring/word-overlap/near-miss match existed to suggest anything; and
  even when a match *did* exist, a generic shared word (e.g. "guild"
  matching every guild in the game — the exact bug `word_overlap_matches`
  was written to prevent) could pick the wrong one. Fixed two ways: (1)
  when `navigate_to` finds no match at all, it now lists every currently
  known room title instead of a dead end, so the agent's own reasoning
  (not string matching) can identify the right one and retry with the
  exact title; (2) a new `navigate_alias_add(alias, destination)` tool lets
  the agent persist that resolution once confirmed — `bakery -> <room
  hash>` — via a new `RoomAliases` store (`.boukensha/memory/
  room_aliases.json`), which `navigate_to` now checks *before* title/
  landmark matching, so a learned alias both resolves instantly and
  permanently bypasses any ambiguous word-overlap match for that term. See
  `memory/room_aliases.py`, `tools/navigation.py` (`_navigate_to`,
  `_navigate_alias_add`). Tests: `tests/test_room_aliases.py`,
  `tests/test_navigation_tool.py::test_navigate_to_resolves_via_alias_before_title_search`,
  `tests/test_navigation_tool.py::test_navigate_to_lists_all_known_titles_when_nothing_matches_at_all`.
```

- [ ] **Step 3: Commit**

```bash
cd week3_capable/agent-exp
git add architecture.md game_findings.md
git commit -m "Document RoomAliases and navigate_alias_add in architecture/game_findings"
```

---

### Task 6: Full test suite verification

**Files:** none (verification only)

- [ ] **Step 1: Run the full test suite**

Run: `cd week3_capable/agent-exp && uv run pytest -v`
Expected: PASS — every test in `tests/`, including all pre-existing `test_navigation_tool.py` cases (confirming the alias-first check and the full-title-list fallback didn't regress the near-miss/known-but-unreachable/landmark branches), plus the new `test_room_aliases.py` and `navigate_alias_add` tests.

- [ ] **Step 2: If anything fails, fix and re-run before proceeding**

No commit for this task — it's a checkpoint, not a deliverable.
