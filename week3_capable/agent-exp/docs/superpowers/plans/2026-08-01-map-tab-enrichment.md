# Map Tab Enrichment Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Enrich the dashboard's Map tab with zone tinting, walked-vs-inferred edge styling, and per-room detail chips (unwalked count, NPC/item tags, aliases), plus a legend, so the map communicates map confidence and area structure at a glance instead of rendering every room/edge identically.

**Architecture:** A new pure-function module (`memory/map_enrichment.py`) derives all new data (edge classification, per-room frontier counts, alias reverse-lookup, zone clustering) from the existing `WorldGraph`/`RoomMemory`/`RoomAliases` stores — no new persisted state. `/api/map` merges this into its existing response shape. `map.js` renders the new fields: zone-tinted room rects, a static legend strip, dashed/colored edges by classification, and extra text lines inside each room node.

**Tech Stack:** Python 3.14, Flask, NetworkX 3.6 (`networkx.algorithms.community.greedy_modularity_communities`, already a project dependency), pytest, vanilla JS + D3 (existing `map.js`, no new frontend dependencies).

## Global Constraints

- Design doc: `docs/superpowers/specs/2026-08-01-map-tab-enrichment-design.md` — follow it exactly; deviations must be called out.
- No new persisted state — zones/classification/frontier/aliases are computed fresh on every `/api/map` call, mirroring `world_stats.py`'s existing pattern.
- No new frontend dependencies or JS test harness — this repo has none for `map.js`/`app.js` today; verify frontend changes manually via `boukensha --web`.
- Existing map behavior (compass layout, zoom/pan, popup-on-click, player star overlay, `refreshTick` polling) must be unchanged — only additive rendering.
- Follow existing code patterns: pure functions taking `WorldGraph`/`RoomMemory` objects (see `world_stats.py`), atomic-write stores unchanged (`RoomAliases` is read-only here), route handlers do local imports inside the function body (see `dashboard/app.py`'s existing routes).

---

### Task 1: `map_enrichment.py` — edge classification and per-room frontier

**Files:**
- Create: `src/boukensha/memory/map_enrichment.py`
- Test: `tests/test_map_enrichment.py`

**Interfaces:**
- Consumes: `WorldGraph` (`.graph` property → `nx.DiGraph`, `.get_neighbors(room_hash) -> dict[str, str]`) and `RoomMemory` (`.get(room_hash) -> dict | None`, room dicts have `"exits": dict[str, str]`) from `src/boukensha/memory/world_graph.py` and `src/boukensha/memory/room_memory.py` — both unchanged, same objects `world_stats.py` already consumes.
- Produces:
  - `classify_edges(graph: WorldGraph, mem: RoomMemory) -> dict[tuple[str, str], str]` — maps `(source_hash, target_hash) -> "walked" | "inferred"`.
  - `node_frontier(graph: WorldGraph, mem: RoomMemory) -> dict[str, int]` — maps `room_hash -> unwalked_count`.

- [ ] **Step 1: Write the failing tests**

```python
# tests/test_map_enrichment.py
from boukensha.memory.world_graph import WorldGraph
from boukensha.memory.room_memory import RoomMemory
from boukensha.memory.map_enrichment import classify_edges, node_frontier


def _room(title, exits, npcs=None, items=None):
    return {"title": title, "description": "d", "exits": exits, "npcs": npcs or [], "items": items or []}


def test_classify_edges_walked_vs_inferred(tmp_path):
    graph = WorldGraph(tmp_path)
    mem = RoomMemory(tmp_path)

    room_a = _room("Room A", {"north": "a corridor"})
    hash_a, _ = mem.record(room_a)
    graph.add_room(hash_a, "Room A")

    room_b = _room("Room B", {})  # B's own exits don't mention south — the reverse edge is inferred
    hash_b, _ = mem.record(room_b)
    graph.add_room(hash_b, "Room B")

    # to_room_exits omitted (defaults to None = "unknown yet") so WorldGraph
    # optimistically auto-fills the south reverse edge — passing an empty
    # set here would instead tell it "confirmed no such exit" and suppress
    # the reverse edge entirely, which is not what we're testing.
    graph.add_edge(hash_a, hash_b, "north")

    classification = classify_edges(graph, mem)
    assert classification[(hash_a, hash_b)] == "walked"
    assert classification[(hash_b, hash_a)] == "inferred"


def test_classify_edges_empty_graph(tmp_path):
    graph = WorldGraph(tmp_path)
    mem = RoomMemory(tmp_path)
    assert classify_edges(graph, mem) == {}


def test_node_frontier_counts_unmapped_known_exits(tmp_path):
    graph = WorldGraph(tmp_path)
    mem = RoomMemory(tmp_path)

    room_a = _room("Room A", {"north": "a corridor", "east": "a door"})
    hash_a, _ = mem.record(room_a)
    graph.add_room(hash_a, "Room A")

    room_b = _room("Room B", {"south": "back to room a"})
    hash_b, _ = mem.record(room_b)
    graph.add_room(hash_b, "Room B")

    graph.add_edge(hash_a, hash_b, "north", to_room_exits={"south"})

    frontier = node_frontier(graph, mem)
    assert frontier[hash_a] == 1  # east is known but unmapped
    assert frontier[hash_b] == 0  # south is walked (auto reverse edge)


def test_node_frontier_skips_node_with_no_room_memory_record(tmp_path):
    graph = WorldGraph(tmp_path)
    mem = RoomMemory(tmp_path)
    graph.add_room("orphan", "Orphan Room")
    assert node_frontier(graph, mem) == {"orphan": 0}
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `.venv/bin/pytest tests/test_map_enrichment.py -v`
Expected: FAIL with `ModuleNotFoundError: No module named 'boukensha.memory.map_enrichment'`

- [ ] **Step 3: Write the implementation**

```python
# src/boukensha/memory/map_enrichment.py
"""Derived, read-only enrichment of the world graph for the dashboard Map
tab: edge confidence (walked vs. inferred), per-room frontier counts, alias
reverse-lookup, and zone clustering. All functions are pure and recompute
from WorldGraph/RoomMemory/RoomAliases on every call — nothing here is
persisted, mirroring world_stats.py's existing pattern."""

from __future__ import annotations

from collections import Counter

from networkx.algorithms.community import greedy_modularity_communities

from .pathfinder import significant_words, words
from .room_aliases import RoomAliases
from .room_memory import RoomMemory
from .world_graph import WorldGraph

_ZONE_PALETTE = [
    "#3a5f8a", "#8a3a5f", "#5f8a3a", "#8a6a3a",
    "#3a8a7a", "#6a3a8a", "#8a3a3a", "#3a8a3a",
]


def classify_edges(graph: WorldGraph, mem: RoomMemory) -> dict[tuple[str, str], str]:
    """For every edge (u, v, direction) in the graph: "walked" if `direction`
    is among the source room's own recorded exits (the agent actually saw
    and walked it), else "inferred" (WorldGraph.add_edge auto-filled the
    opposite direction of some other walked edge)."""
    result: dict[tuple[str, str], str] = {}
    for u, v, data in graph.graph.edges(data=True):
        direction = data.get("direction")
        room = mem.get(u)
        known_exits = set((room or {}).get("exits") or {})
        result[(u, v)] = "walked" if direction in known_exits else "inferred"
    return result


def node_frontier(graph: WorldGraph, mem: RoomMemory) -> dict[str, int]:
    """Per room: count of exits the room is known to have (from RoomMemory)
    that have no corresponding graph edge yet — the same known-minus-mapped
    computation world_stats.frontier_stats already does in aggregate, keyed
    per room instead of summed."""
    result: dict[str, int] = {}
    for node in graph.graph.nodes:
        room = mem.get(node)
        if not room:
            result[node] = 0
            continue
        room_known = set((room.get("exits") or {}).keys())
        mapped = set(graph.get_neighbors(node).keys())
        result[node] = len(room_known - mapped)
    return result


def node_aliases(aliases: RoomAliases) -> dict[str, list[str]]:
    """Invert RoomAliases (alias -> room_hash) into room_hash -> [aliases]."""
    result: dict[str, list[str]] = {}
    for alias, room_hash in aliases.read_all().items():
        result.setdefault(room_hash, []).append(alias)
    return result


def assign_zones(graph: WorldGraph) -> dict[str, dict]:
    """Cluster rooms into zones via greedy modularity community detection on
    the undirected graph, and label each zone with its most common
    significant title word. Recomputed fresh every call — no persisted zone
    state, so it self-corrects as the map grows."""
    undirected = graph.graph.to_undirected()
    result: dict[str, dict] = {}
    if undirected.number_of_nodes() == 0:
        return result
    communities = list(greedy_modularity_communities(undirected))
    for zone_id, members in enumerate(communities):
        word_counts: Counter[str] = Counter()
        for member in members:
            title = graph.graph.nodes[member].get("title", "")
            title_words = significant_words(words(title)) or words(title)
            # `words`/`significant_words` return sets, whose iteration order
            # is hash-randomized per process — feed Counter.update a sorted
            # list so tie-breaking in most_common() below is deterministic
            # across runs instead of flipping randomly on every server
            # restart.
            word_counts.update(sorted(title_words))
        zone_label = word_counts.most_common(1)[0][0].title() if word_counts else f"Zone {zone_id}"
        for member in members:
            result[member] = {
                "zone_id": zone_id,
                "zone_label": zone_label,
                "zone_color": _ZONE_PALETTE[zone_id % len(_ZONE_PALETTE)],
            }
    return result
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `.venv/bin/pytest tests/test_map_enrichment.py -v`
Expected: PASS (4 tests)

- [ ] **Step 5: Commit**

```bash
git add src/boukensha/memory/map_enrichment.py tests/test_map_enrichment.py
git commit -m "Add classify_edges and node_frontier to map_enrichment"
```

---

### Task 2: `map_enrichment.py` — aliases and zone clustering

**Files:**
- Modify: `tests/test_map_enrichment.py` (append tests; `node_aliases`/`assign_zones` implementations were already written in Task 1's Step 3 — this task is test coverage for them)

**Interfaces:**
- Consumes: `RoomAliases` (`.read_all() -> dict[str, str]`, alias → room_hash) from `src/boukensha/memory/room_aliases.py`, unchanged. `WorldGraph.graph.nodes[room_hash]["title"] -> str`.
- Produces: `node_aliases(aliases: RoomAliases) -> dict[str, list[str]]`, `assign_zones(graph: WorldGraph) -> dict[str, dict]` where each value is `{"zone_id": int, "zone_label": str, "zone_color": str}` — both already implemented in Task 1; this task only adds tests, run them, and fix anything they reveal.

- [ ] **Step 1: Write the failing tests**

```python
# append to tests/test_map_enrichment.py
from boukensha.memory.room_aliases import RoomAliases
from boukensha.memory.map_enrichment import node_aliases, assign_zones


def test_node_aliases_inverts_alias_store(tmp_path):
    aliases = RoomAliases(tmp_path)
    aliases.add("bakery", "hash_a")
    aliases.add("the bakery", "hash_a")
    aliases.add("temple", "hash_b")

    result = node_aliases(aliases)
    assert sorted(result["hash_a"]) == ["bakery", "the bakery"]
    assert result["hash_b"] == ["temple"]


def test_node_aliases_empty_store(tmp_path):
    aliases = RoomAliases(tmp_path)
    assert node_aliases(aliases) == {}


def test_assign_zones_empty_graph(tmp_path):
    graph = WorldGraph(tmp_path)
    assert assign_zones(graph) == {}


def test_assign_zones_single_room(tmp_path):
    # Single-word title avoids a tie between two equally-frequent words,
    # which would otherwise make the expected label ambiguous.
    graph = WorldGraph(tmp_path)
    graph.add_room("hash_a", "Bakery")
    zones = assign_zones(graph)
    assert zones["hash_a"]["zone_id"] == 0
    assert zones["hash_a"]["zone_label"] == "Bakery"
    assert zones["hash_a"]["zone_color"].startswith("#")


def test_assign_zones_disconnected_components_get_different_zones(tmp_path):
    graph = WorldGraph(tmp_path)
    graph.add_room("hash_a", "Wall Road")
    graph.add_room("hash_b", "Wall Road")
    graph.add_edge("hash_a", "hash_b", "north", to_room_exits={"south"})

    graph.add_room("hash_c", "Poor Alley")
    graph.add_room("hash_d", "Poor Alley")
    graph.add_edge("hash_c", "hash_d", "north", to_room_exits={"south"})

    zones = assign_zones(graph)
    assert zones["hash_a"]["zone_id"] == zones["hash_b"]["zone_id"]
    assert zones["hash_c"]["zone_id"] == zones["hash_d"]["zone_id"]
    assert zones["hash_a"]["zone_id"] != zones["hash_c"]["zone_id"]
```

- [ ] **Step 2: Run tests to verify they fail or pass**

Run: `.venv/bin/pytest tests/test_map_enrichment.py -v`
Expected: since `node_aliases`/`assign_zones` were already implemented in Task 1, these should PASS immediately. If any fail, fix `map_enrichment.py` (do not weaken the test) — most likely failure mode is `significant_words` filtering out every word of a short title (e.g. "Temple Square" → both words are ≥5 chars so this won't happen, but a title like "The Bar" would fall through to the `words(title)` fallback already coded in `assign_zones`).

- [ ] **Step 3: Run full test file to confirm all 9 tests pass**

Run: `.venv/bin/pytest tests/test_map_enrichment.py -v`
Expected: PASS (9 tests total)

- [ ] **Step 4: Commit**

```bash
git add tests/test_map_enrichment.py
git commit -m "Add test coverage for node_aliases and assign_zones"
```

---

### Task 3: Wire enrichment into `/api/map`

**Files:**
- Modify: `src/boukensha/dashboard/app.py:52-66` (the `api_map` route)
- Modify: `tests/test_dashboard_api.py` (extend map test)

**Interfaces:**
- Consumes: `classify_edges`, `node_frontier`, `node_aliases`, `assign_zones` from `src/boukensha/memory/map_enrichment.py` (Task 1/2). `RoomMemory(memory_path)` and `RoomAliases(memory_path)` constructed the same way `RoomMemory` is already constructed elsewhere in `app.py` (e.g. `api_room`).
- Produces: `/api/map` JSON response nodes gain `zone_id: int`, `zone_label: str`, `zone_color: str`, `unwalked: int`, `aliases: list[str]`, `npc_count: int`, `item_count: int` (defaulting to `0`/`[]`/`"Zone 0"`-style values when a room has no memory record, matching existing null-safety in `frontier_stats`/`entity_stats`); links gain `kind: "walked" | "inferred"`.

- [ ] **Step 1: Write the failing test**

```python
# append to tests/test_dashboard_api.py
def test_api_map_includes_enrichment_fields(tmp_path):
    from boukensha.memory.world_graph import WorldGraph
    from boukensha.memory.room_memory import RoomMemory

    memory_dir = tmp_path / "memory"
    graph = WorldGraph(memory_dir)
    mem = RoomMemory(memory_dir)

    room_a = {"title": "Temple Square", "description": "d", "exits": {"north": "x"}, "npcs": ["a guard"], "items": []}
    hash_a, _ = mem.record(room_a)
    graph.add_room(hash_a, "Temple Square")

    room_b = {"title": "Wall Road", "description": "d", "exits": {}, "npcs": [], "items": []}
    hash_b, _ = mem.record(room_b)
    graph.add_room(hash_b, "Wall Road")

    # to_room_exits omitted so the south reverse edge is auto-filled as
    # "inferred" (see the note in test_map_enrichment.py's equivalent case).
    graph.add_edge(hash_a, hash_b, "north")
    graph.save()

    app, _ = _make_app(tmp_path)
    with app.test_client() as c:
        r = c.get("/api/map")
        assert r.status_code == 200
        data = json.loads(r.data)

    node_a = next(n for n in data["nodes"] if n["id"] == hash_a)
    assert node_a["npc_count"] == 1
    assert node_a["item_count"] == 0
    assert "zone_id" in node_a
    assert "zone_label" in node_a
    assert node_a["aliases"] == []

    link = next(l for l in data["links"] if l["source"] == hash_a and l["target"] == hash_b)
    assert link["kind"] == "walked"
    reverse = next(l for l in data["links"] if l["source"] == hash_b and l["target"] == hash_a)
    assert reverse["kind"] == "inferred"
```

- [ ] **Step 2: Run test to verify it fails**

Run: `.venv/bin/pytest tests/test_dashboard_api.py::test_api_map_includes_enrichment_fields -v`
Expected: FAIL with `KeyError: 'npc_count'` (field not yet in response)

- [ ] **Step 3: Implement — replace the `api_map` route**

```python
    @app.route("/api/map")
    def api_map():
        from boukensha.memory.world_graph import WorldGraph
        from boukensha.memory.room_memory import RoomMemory
        from boukensha.memory.room_aliases import RoomAliases
        from boukensha.memory.map_enrichment import (
            classify_edges, node_frontier, node_aliases, assign_zones,
        )

        g = WorldGraph(memory_path)
        g.load()
        nx_g = g.graph
        mem = RoomMemory(memory_path)
        aliases = RoomAliases(memory_path)

        frontier = node_frontier(g, mem)
        alias_map = node_aliases(aliases)
        zones = assign_zones(g)
        edge_kinds = classify_edges(g, mem)

        nodes = []
        for n, attrs in nx_g.nodes(data=True):
            room = mem.get(n) or {}
            zone = zones.get(n, {"zone_id": 0, "zone_label": "Zone 0", "zone_color": "#3a5f8a"})
            nodes.append({
                "id": n,
                "title": attrs.get("title", n),
                "zone_id": zone["zone_id"],
                "zone_label": zone["zone_label"],
                "zone_color": zone["zone_color"],
                "unwalked": frontier.get(n, 0),
                "aliases": alias_map.get(n, []),
                "npc_count": len(room.get("npcs") or []),
                "item_count": len(room.get("items") or []),
            })
        links = [
            {
                "source": u, "target": v,
                "direction": d.get("direction", ""),
                "kind": edge_kinds.get((u, v), "walked"),
            }
            for u, v, d in nx_g.edges(data=True)
        ]
        return jsonify({"nodes": nodes, "links": links})
```

- [ ] **Step 4: Run test to verify it passes**

Run: `.venv/bin/pytest tests/test_dashboard_api.py -v`
Expected: PASS (all tests in the file, including the new one)

- [ ] **Step 5: Commit**

```bash
git add src/boukensha/dashboard/app.py tests/test_dashboard_api.py
git commit -m "Wire map_enrichment fields into /api/map response"
```

---

### Task 4: Render zone tint, edge classification, and node chips in `map.js`

**Files:**
- Modify: `src/boukensha/dashboard/static/map.js`
- Modify: `src/boukensha/dashboard/static/style.css`
- Modify: `src/boukensha/dashboard/templates/index.html:30-38`

**Interfaces:**
- Consumes: the enriched `/api/map` response from Task 3 — each node now has `zone_id`, `zone_label`, `zone_color`, `unwalked`, `aliases`, `npc_count`, `item_count`; each link has `kind`. Existing `shortRoomLabel`, `escapeHtml`, `RECT_W`/`RECT_H` constants, `layoutNodes`, `nodeById`, `VERTICAL` set — all unchanged, reused as-is.
- Produces: no new exported functions (this is leaf rendering code); `window.loadMap` keeps its existing signature/behavior, only its rendered output changes.

**Deviation from the design doc's phrasing:** the design doc's frontend section describes "NPC/item name pills," but its own API section only exposes `npc_count`/`item_count` (counts, not names) to avoid duplicating the full name lists the popup already fetches from `/api/room/<id>`. This task renders a count summary line (e.g. "2 npcs, 1 item") rather than named pills — consistent with the API shape actually implemented in Task 3. Full names remain available via the existing click-to-open popup, unchanged.

- [ ] **Step 1: Add a legend container to the template**

In `src/boukensha/dashboard/templates/index.html`, inside `<section id="tab-map">`, after the closing `</div>` of `#map-container`:

```html
      <div id="map-legend"></div>
```

Full block becomes:

```html
  <section id="tab-map" class="tab-pane">
    <div id="map-status"></div>
    <div id="map-container">
      <svg id="map-svg"></svg>
      <div id="room-popup" hidden>
        <div id="room-popup-arrow"></div>
        <div id="room-popup-body"></div>
      </div>
    </div>
    <div id="map-legend"></div>
  </section>
```

- [ ] **Step 2: Add legend and chip CSS**

In `src/boukensha/dashboard/static/style.css`, after the existing `#map-svg` rule (line 15):

```css
#map-legend { display: flex; flex-wrap: wrap; gap: 16px; padding: 8px 2px; font-size: 11px; color: #aaa; }
.legend-group { display: flex; align-items: center; gap: 6px; flex-wrap: wrap; }
.legend-swatch { display: inline-block; width: 12px; height: 12px; border-radius: 2px; }
.legend-line { display: inline-block; width: 20px; height: 0; border-top: 2px solid; vertical-align: middle; }
.legend-line.inferred { border-top-style: dashed; }
.room-node-chip { font-size: 9px; fill: #ccc; }
.room-node-alias { font-size: 9px; fill: #7ad; font-style: italic; }
```

- [ ] **Step 3: Render zone-tinted rects and classified edges**

In `map.js`, the edge-drawing block (currently around line ~410, `g.append('g').selectAll('line')...`) — replace the `stroke`/`stroke-dasharray` attrs to also account for `kind`:

```js
  g.append('g').selectAll('line').data(drawLinks).join('line')
    .attr('x1', d => d.source.x).attr('y1', d => d.source.y)
    .attr('x2', d => d.target.x).attr('y2', d => d.target.y)
    .attr('stroke', d => {
      const dir = (d.direction || '').toLowerCase();
      if (VERTICAL.has(dir)) return '#a84';
      return d.kind === 'inferred' ? '#4a8' : '#444';
    })
    .attr('stroke-width', 1.5)
    .attr('stroke-dasharray', d => {
      const dir = (d.direction || '').toLowerCase();
      if (VERTICAL.has(dir)) return '4,3';
      return d.kind === 'inferred' ? '3,3' : null;
    });
```

Note: `drawLinks` currently dedupes A↔B pairs (`seenPairs`) picking whichever direction was encountered first from the `links` array order — since both directions of a dedup'd pair might have different `kind` (e.g. one walked, one inferred), this will show whichever one happened to be kept. This matches the existing dedup behavior (it already picks one arbitrary direction's label) and is acceptable — the popup and node's own `unwalked` count are the source of truth for exact per-direction state.

The room rect fill (currently `.attr('fill', '#1e3a5f')` in the `nodeGroup.append('rect')` block) becomes zone-colored:

```js
  nodeGroup.append('rect')
    .attr('width', RECT_W).attr('height', RECT_H)
    .attr('rx', 4)
    .attr('fill', d => d.zone_color || '#1e3a5f')
    .attr('stroke', '#4af').attr('stroke-width', 1.5);
```

- [ ] **Step 4: Grow node boxes and render chips/unwalked/alias text**

Increase `RECT_H` from `30` to `54` (still `const RECT_H = 54;` alongside `RECT_W`) to fit the extra lines. After the existing title `<text>` append (the block with `.text(d => shortRoomLabel(d.title))`), add:

```js
  nodeGroup.filter(d => d.unwalked > 0).append('text')
    .attr('x', RECT_W / 2).attr('y', RECT_H / 2 + 14)
    .attr('text-anchor', 'middle').attr('class', 'room-node-chip')
    .attr('stroke', '#181818').attr('stroke-width', 2).attr('paint-order', 'stroke fill')
    .text(d => `${d.unwalked} unwalked`);

  nodeGroup.filter(d => (d.npc_count + d.item_count) > 0).append('text')
    .attr('x', RECT_W / 2).attr('y', RECT_H / 2 + 26)
    .attr('text-anchor', 'middle').attr('class', 'room-node-chip')
    .attr('stroke', '#181818').attr('stroke-width', 2).attr('paint-order', 'stroke fill')
    .text(d => {
      const parts = [];
      if (d.npc_count) parts.push(`${d.npc_count} npc${d.npc_count === 1 ? '' : 's'}`);
      if (d.item_count) parts.push(`${d.item_count} item${d.item_count === 1 ? '' : 's'}`);
      return parts.join(', ');
    });

  nodeGroup.filter(d => d.aliases && d.aliases.length).append('text')
    .attr('x', RECT_W / 2).attr('y', RECT_H / 2 + 38)
    .attr('text-anchor', 'middle').attr('class', 'room-node-alias')
    .attr('stroke', '#181818').attr('stroke-width', 2).attr('paint-order', 'stroke fill')
    .text(d => `→ ${shortRoomLabel(d.aliases[0])}`);
```

Also update the `translate` transform on `nodeGroup` (the `.attr('transform', d => \`translate(${d.x - RECT_W / 2},${d.y - RECT_H / 2})\`)` line) — no change needed since it already derives from `RECT_W`/`RECT_H` constants, but confirm `GRID` (220, top of file) still gives enough vertical clearance between rows now that boxes are taller; if node rows visually overlap after this change, increase `GRID` to `260`.

- [ ] **Step 5: Render the legend**

In `window.loadMap`, after `status.textContent = ...` is set and before the early-return-on-empty check resolves (i.e., add this after the `if (!nodes.length) { ...; return; }` block, once we know we have nodes), build the legend from the actual node/link data just fetched:

```js
  const legend = document.getElementById('map-legend');
  const zoneCounts = new Map();
  for (const n of nodes) {
    const key = n.zone_id;
    if (!zoneCounts.has(key)) zoneCounts.set(key, { label: n.zone_label, color: n.zone_color, count: 0 });
    zoneCounts.get(key).count += 1;
  }
  const zoneHtml = [...zoneCounts.values()]
    .map(z => `<span class="legend-group"><span class="legend-swatch" style="background:${z.color}"></span>${escapeHtml(z.label)} (${z.count})</span>`)
    .join('');
  const edgeHtml = `
    <span class="legend-group"><span class="legend-line" style="border-color:#444"></span>walked</span>
    <span class="legend-group"><span class="legend-line inferred" style="border-color:#4a8"></span>known, never walked</span>
    <span class="legend-group"><span class="legend-line inferred" style="border-color:#a84"></span>displaced or vertical</span>
  `;
  legend.innerHTML = zoneHtml + edgeHtml;
```

Place this block right after `for (const n of nodes) { const p = grid.get(n.id) ...; n.y = p.y; }` (the loop that assigns `n.x`/`n.y` from the layout grid) so `nodes` already carries the enrichment fields fetched from `/api/map` at that point.

Also clear the legend in the empty-map branch — in the `if (!nodes.length) { ... }` block, add `document.getElementById('map-legend').innerHTML = '';` alongside the existing `d3.select('#map-svg').selectAll('*').remove();`.

- [ ] **Step 6: Manual verification**

Run: `.venv/bin/python bin/boukensha --web --port 4569` (or the project's existing launch command — check `README.md`/`SETUP.md` if this differs), then open `http://localhost:4569`, click the Map tab, and confirm:
- Room boxes are tinted by zone and a legend with zone swatches + room counts appears below the map.
- Edges to rooms only reachable via an inferred reverse edge render dashed/differently colored than walked edges, and the legend explains the line styles.
- Rooms with unwalked exits show an "N unwalked" line; rooms with NPCs/items show a count line; rooms with a learned alias show "→ alias".
- Clicking a room node still opens the existing full-detail popup unchanged.
- The Overview/Goals/Sessions/Live/Waterfall tabs are unaffected.

- [ ] **Step 7: Run the full test suite**

Run: `.venv/bin/pytest -v`
Expected: PASS (all tests, including the new `test_map_enrichment.py` and the extended `test_dashboard_api.py`)

- [ ] **Step 8: Commit**

```bash
git add src/boukensha/dashboard/static/map.js src/boukensha/dashboard/static/style.css src/boukensha/dashboard/templates/index.html
git commit -m "Render zone tint, edge classification, and room chips on Map tab"
```
