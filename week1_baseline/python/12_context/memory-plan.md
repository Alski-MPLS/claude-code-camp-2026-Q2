# Memory Plan — Explicit Room-Graph Tool for `boukensha`

## Problem

Today the agent's only memory of the MUD's geography is whatever room
descriptions happen to still be sitting in `Context.messages`. There is no
`Room`/`Map` data structure anywhere in `tools/mud.py` — `look`, `exits`, and
movement commands are thin pass-throughs to the raw socket
(`src/boukensha/tools/mud.py`), and the model has to reconstruct "where have I
been" purely from in-context text. `Context.compact_messages()`
(`src/boukensha/context.py`) drops the oldest messages once usage crosses
`compaction_threshold` (default 0.85), with no awareness of which messages
described navigation-critical facts. The longer a session runs, the more
likely a room's description has already been pruned, so "go back to the
shop" degrades from a recall problem into a guessing problem.

The fix: build a persistent room-graph that lives *outside* the chat context
and is queried via tools, not remembered via prose.

---

## Decision 1 — Room identity (node keys)

The MUD reuses room titles constantly ("A Dark Forest Path" appears dozens
of times), so titles alone can't key nodes.

### Option A — Fingerprint hash
Hash the static parts of a `look` result (title + description, with dynamic
content like mobs/items/weather stripped out) into a room ID.

- **Summary**: Cheapest to implement — one hash function, no MUD cooperation
  required.
- **Tradeoff**: Hash collisions are possible for genuinely similar rooms;
  fragile if the MUD varies phrasing (e.g. weather-dependent description
  text) since that changes the hash for what is really the same room.

### Option B — Composite key
Key nodes by `(title, description_hash, sorted(exit_directions))` instead of
a single opaque hash.

- **Summary**: More robust than Option A — two rooms need identical title
  *and* identical description *and* identical exit set to collide, which is
  rare even with repeated titles.
- **Tradeoff**: Slightly more bookkeeping (three fields instead of one), and
  still vulnerable if the MUD's exit set for a room changes dynamically
  (e.g. a door that closes).

### Option C — Server-assigned vnum
Use the MUD's internal room vnum if it can be queried (some CircleMUD builds
expose this via `stat`/`rinfo`-style commands).

- **Summary**: Ground-truth identity, immune to text-matching issues
  entirely.
- **Tradeoff**: Vnum-revealing commands are typically admin/builder-only —
  likely unavailable to a normal player character. Would need to verify
  against the actual MUD before relying on it.

**Recommendation: Option B (composite key).** It's nearly as cheap as
Option A but meaningfully more collision-resistant, and it doesn't depend on
MUD cooperation the way Option C does. Treat Option C as a bonus upgrade if
testing shows the MUD actually exposes vnums to players.

---

## Decision 2 — Edge model

### Option A — Coordinate/grid model
Track relative (x, y, z) coordinates, incrementing/decrementing per
direction moved (north = +y, etc.). "Path back" becomes inverting the move
sequence.

- **Summary**: Very simple to reason about and cheap to compute a return
  path.
- **Tradeoff**: Assumes Euclidean, grid-like geography. Breaks silently on
  one-way exits, portals, teleports, or non-orthogonal layouts — all common
  in CircleMUD — and gives false confidence because the coordinates still
  "look" consistent even when wrong.

### Option B — Directed graph, edges observed not assumed
Node = room (per Decision 1), edge = `(from_room, direction, to_room)`,
recorded only when actually traversed and confirmed. Do **not** auto-add the
reverse edge — only add it once the agent actually walks back and it's
confirmed to lead to `from_room`.

- **Summary**: Robust to one-way exits and irregular geography; naturally
  encodes "exit exists but untested" vs. "exit confirmed."
- **Tradeoff**: More bookkeeping than coordinates, and needs real
  pathfinding (BFS/Dijkstra) rather than simple arithmetic to compute a
  route back.

**Recommendation: Option B.** Given this MUD's exits are known to be
sometimes one-way (portals, doors, etc.), coordinates would produce
plausible-looking but wrong routes. A directed graph with observed-not-assumed
edges is the standard approach for MUD-mapping bots for exactly this reason.

---

## Decision 3 — Where the graph lives and how it's populated

### Option A — Parse inside the LLM's own reasoning
Let the model itself decide what to record, via a `record_room` tool it
calls voluntarily after each `look`.

- **Summary**: No new parsing code — reuses the model's language
  understanding.
- **Tradeoff**: Unreliable by construction — the model can forget to call
  it, call it inconsistently, or normalize text differently each time,
  which reintroduces exactly the flakiness this plan exists to remove.

### Option B — Deterministic parser between socket and LLM
A regex/heuristic parser in Python intercepts every `look`/`move`/`exits`
response and extracts (title, description, exits) automatically —
independent of whether the LLM does anything with it.

- **Summary**: Deterministic, always runs, doesn't depend on the model
  remembering to do anything.
- **Tradeoff**: CircleMUD output formatting must be reverse-engineered and
  kept in sync if the MUD's room-echo format ever changes; some edge cases
  (rooms with no obvious "Obvious exits:" line, special rooms) will need
  fallback handling.

**Recommendation: Option B.** It matches the reliability goal directly — the
whole point is to stop depending on the model to "remember" things.

For persistence:

- **In-memory structure**: `networkx.DiGraph`, built up as rooms/edges are
  observed — gives BFS/Dijkstra shortest-path for free.
- **On-disk persistence**: serialize to JSON (node fingerprints + edge list)
  next to the existing `.boukensha` config directory (`Config` already
  resolves this location), one file per character/MUD, so the map survives
  process restarts instead of resetting every session.

---

## Decision 4 — How the agent accesses the map

### Option A — Passive context injection
Automatically prepend a map summary to the system prompt or inject it as a
message each turn.

- **Summary**: Zero extra tool calls required from the agent.
- **Tradeoff**: Competes for context-window budget on every single turn
  (directly at odds with this folder's whole context-management theme), and
  grows unboundedly as the map grows — would itself need its own
  summarization/truncation logic.

### Option B — On-demand tools
Expose the map as callable tools the agent invokes only when it needs them:
  - `map_here()` — current room + which exits are known vs. unexplored
  - `map_path_to(room)` — shortest path as a literal direction sequence to
    execute
  - `map_summary()` — compact dump of the known graph for re-orientation

- **Summary**: Costs nothing when not needed; directly solves "conversation
  got compacted, agent lost the map" since the map is queried fresh, not
  recalled from history.
- **Tradeoff**: Requires the agent to know to call these tools — worth a
  one-line mention in `prompts/system.md` steering it to use them when
  navigating.

**Recommendation: Option B.** It's the natural fit for this codebase: the
existing architecture note in `12_architecture.md` already frames
`Context`/`Agent` around minimizing and being deliberate about token spend
(compaction, turn-token ceilings). Passive injection works directly against
that design; on-demand tool calls work with it.

---

## Recommended overall approach

1. **Identity**: composite key `(title, description_hash, sorted(exits))`
   (Decision 1, Option B).
2. **Edges**: directed graph, edges recorded only on confirmed traversal, no
   assumed symmetry (Decision 2, Option B).
3. **Capture**: deterministic Python-side parser sitting between the socket
   response and the LLM, in a new module — e.g. `src/boukensha/tools/map.py`
   — parsing `look`/`exits`/movement output automatically on every call
   (Decision 3, Option B).
4. **Storage**: `networkx.DiGraph` in memory, persisted as JSON near the
   existing `.boukensha` config dir (Decision 3).
5. **Access**: expose `map_here()`, `map_path_to()`, `map_summary()` as
   tools registered the same way as the rest of `tools/mud.py` (via
   `Registry`), keeping `tools/mud.py` as the "dumb socket pipe" and the new
   module as the "derived world model" — consistent with the existing
   `Context`-owns-data / `Agent`-owns-control-flow split described in
   `12_architecture.md` (Decision 4, Option B).

This keeps the map as a source of truth that's independent of — and
immune to — message compaction, while fitting the codebase's existing
architectural seams rather than cutting across them.
