# Map tab enrichment — design

## Problem

The dashboard's Map tab (`GET /api/map`, `dashboard/static/map.js`) shows a
compass-anchored graph of rooms and directional edges, but every edge and
node looks the same regardless of what's actually known about it:

- An edge drawn because the agent physically walked that direction looks
  identical to one that only exists because `WorldGraph.add_edge` optimistically
  auto-filled the reverse direction of a walked exit — those are different
  levels of confidence (the auto-fill can be wrong for genuinely one-way
  passages) but the map doesn't say which is which.
- A room known to have more exits than are currently mapped (frontier —
  already computed in aggregate by `world_stats.frontier_stats`) isn't
  visible per-room on the map itself, only as a single combined count on
  the Overview tab.
- NPCs/items recorded on a room (`RoomMemory`) and learned aliases
  (`RoomAliases`) pointing at a room only surface in the click-through
  popup, not at a glance.
- There's no visual grouping of rooms into areas, making it hard to get a
  sense of the city's layout at a glance on a large map.

A user-supplied reference screenshot (a different, more mature map tool)
shows one way to close these gaps: color-tinted zone groupings with a
legend, a line-style legend distinguishing walked/one-way/frontier/vertical
edges, and per-room detail chips (tags, unwalked counts, aliases) shown
directly on the node.

## Design

### 1. `memory/map_enrichment.py` — new pure-function module

Follows the same pattern as `world_stats.py` (pure functions over an
already-loaded `WorldGraph` + `RoomMemory`, no I/O of their own):

- **`classify_edges(graph, mem) -> dict[(u, v), str]`** — for each edge in
  the graph, returns `"walked"` if `direction` appears in the source room's
  own recorded `exits` dict (i.e. the agent actually saw and walked that
  exit), otherwise `"inferred"` (the edge only exists because `add_edge`
  auto-filled the opposite direction — see `world_graph.py`'s existing
  comment on that behavior). This is a per-edge lookup, not a new field
  persisted to `world_graph.json` — it's derived the same way
  `frontier_stats` already derives walked-vs-known from `room["exits"]` vs
  `graph.get_neighbors(node)`.
- **`node_frontier(graph, mem) -> dict[str, int]`** — per room, the same
  known-exits-minus-mapped-exits count `frontier_stats` already computes in
  aggregate, just keyed by room hash instead of summed.
- **`node_aliases(aliases: RoomAliases) -> dict[str, list[str]]`** — inverts
  `RoomAliases.read_all()` (alias → room_hash) into room_hash → [aliases].
- **`assign_zones(graph) -> dict[str, dict]`** — runs
  `networkx.algorithms.community.greedy_modularity_communities` on
  `graph.graph.to_undirected()`, assigns each room a `zone_id` (community
  index), and labels each zone with its most common significant title word
  (reusing the tokenization already used by `pathfinder.py`'s word-overlap
  matching, so "Wall Road" rooms cluster under label "Wall Road" the same
  way pathfinder already treats title words). Returns `{room_hash: {"zone_id": int, "zone_label": str}}`.
  Recomputed fresh on every call — no persisted zone state, so it
  self-corrects as the map grows and never goes stale.

Single-room or disconnected-component graphs are valid input (community
detection degrades gracefully to one zone per component); this is exercised
by the unit tests below since `.boukensha/memory` frequently has small/test
graphs.

### 2. `/api/map` response changes (`dashboard/app.py`)

`api_map()` calls the four functions above and merges their output in:

```json
{
  "nodes": [{
    "id": "abc123", "title": "Temple Square",
    "zone_id": 2, "zone_label": "Midgaard",
    "unwalked": 1, "aliases": ["temple"],
    "npc_count": 2, "item_count": 0
  }],
  "links": [{"source": "abc123", "target": "def456", "direction": "north", "kind": "walked"}]
}
```

`npc_count`/`item_count` reuse `room.get("npcs")`/`room.get("items")`
lengths already read for the popup path — no new data source, just exposed
at the list level instead of only inside `/api/room/<id>`.

### 3. Frontend (`dashboard/static/map.js`)

- **Zone tint**: room `<rect>` fill becomes a per-zone color (from a fixed
  8-color palette, cycling by `zone_id % 8`, same palette-cycling approach
  `colorForPlayer` already uses for player star colors) instead of the
  current static navy. Kept subtle (low saturation) so the existing
  `stroke`/text stay legible.
- **Legend strip**: a new static (non-interactive, v1) row below the map
  showing: zone swatches with label + room count, and an edge-style key
  (walked = solid gray, inferred = dashed teal, vertical up/down =
  dashed amber as today). Frontier isn't an edge so it's not in this key —
  it shows per-node instead (next bullet).
- **Node content**: node box grows to fit, under the title: an "N unwalked"
  line when `unwalked > 0`, up to 3 NPC/item name pills (truncated with a
  "+N more" the same way `shortRoomLabel` already truncates long titles),
  and inline alias text (`→ <alias>`) when aliases exist. All of this is a
  summary — the existing click-to-open-popup behavior is unchanged and
  still shows full room detail (description, full exit list, full
  npc/item lists).
- **Edge rendering**: edges classified `"inferred"` get a dashed stroke in
  a distinct color (not the existing amber, which is reserved for
  vertical) instead of the current uniform solid gray; `"walked"` keeps
  today's solid gray.

No changes to layout algorithm, zoom/pan, popup mechanics, or the player
star/movement-arrow overlay — those are already correct and out of scope.

### Testing

- `tests/test_map_enrichment.py` (new, mirrors `test_world_stats.py`):
  fixed small graphs (2-3 rooms, at least one with an inferred-only reverse
  edge, at least one with more known exits than mapped) asserting
  `classify_edges`, `node_frontier`, `node_aliases`, and `assign_zones`
  return expected values, including the single-room/disconnected-component
  edge case.
- `tests/test_dashboard_api.py`: extend the existing `/api/map` test(s) to
  assert the new fields are present on a fixed fixture graph.
- No JS test harness exists in this repo today (`map.js`/`app.js` have
  none) — frontend changes are verified manually via `boukensha --web`,
  consistent with current practice for this file.

## Out of scope (YAGNI)

- Interactive legend (click a zone to highlight/filter its rooms) — static
  legend only for v1.
- Persisting zone assignments to disk — recomputed every request, cheap at
  this graph size (hundreds of rooms, not thousands).
- Capturing a real in-game zone/area name — confirmed with the user that no
  such data is currently observed from the game; zones are purely derived
  from graph structure.
