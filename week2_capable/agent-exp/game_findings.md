# Game Findings

Running log of things learned about how this particular MUD behaves — quirks,
rules, and mechanics discovered during live play that aren't reflected in the
code yet. Add an entry whenever something surprising turns up; move it into
actual code/tests once it's implemented (leave the entry, just note where it
landed).

## Open

- **No equipment/light-source tracking yet.** `explore()` now refuses to walk
  into a room it detects as dark (see Implemented below) instead of blindly
  entering it, but it has no way to check whether the agent is actually
  carrying a lit torch/lantern before deciding to retry a dark exit — it just
  marks the exit blocked and leaves it blocked until someone calls
  `BlockedExits.unmark()`. Next step: a way to check current light-source
  state (e.g. via `check equipment`) and auto-retry dark-marked exits once
  one is equipped.

## Implemented

- **process_room hid a room's items/npcs on every revisit after the
  first.** Found live in the same fountain incident: `process_room` only
  returns the *diff* vs. stored memory to save tokens, so on a revisit to
  an already-known room it returned only `"[known room: X] Nothing new
  observed."` — completely hiding the fountain (an unchanged item) even
  though it's the whole reason the agent was there. It now always includes
  current NPCs/items on a known-room revisit, only omitting them (falling
  back to "Nothing new observed") when the room genuinely has none. See
  `tools/room_processor.py` (`_process_room`). Tests:
  `tests/test_room_processor.py`.

- **navigate_to/explore silently moving the character corrupted the map
  the next time a raw `move` was used.** Found live: The Bakery ended up
  with two different, impossible "south" exits (one to The General Store,
  one to Main Street) after mixing `explore()`/`navigate_to` with the raw
  `move` tool in the same session. Root cause: `move`/`process_room` share
  a `prev_hash_ref` — the "last known room" pointer used to record which
  edge a move just walked — but `navigate_to` and `explore()` never
  updated it, since they track position independently inside a single tool
  call. So after either of those silently repositioned the character, the
  next raw `move` call recorded its edge from a stale, no-longer-current
  room. Both tools now sync `prev_hash_ref` (and clear the stale
  `last_direction_ref` flag) every time they determine the current room,
  the same way `move`/`process_room` already did. Same class of bug
  independently found and fixed via `WorldGraph.add_edge`'s
  `to_room_exits` check above, but this was the *systemic* source of it —
  worth checking the live map periodically for any other rooms with two
  edges sharing a direction (`tests/test_position_sync.py` has the
  detection query used to find these). See `tools/navigation.py`,
  `tools/exploration.py` (`_current_room_hash` in both). Tests:
  `tests/test_position_sync.py`.

- **Landmarks (fountains, wells, statues, etc.) live inside a room's
  description/items, not as their own room title.** Found live: asked to
  "go to the fountain and drink," the agent walked past The Temple Square
  (which really does have "A large fountain carved from blue-streaked
  marble is here, bubbling merrily." in its parsed items) because
  `navigate_to` only ever matched room *titles*, and the agent had no
  reliable way to recall which room it was in besides whatever was still in
  its context window. `navigate_to` now falls back to searching every known
  room's description/items/npcs for the fragment when no title matches, and
  reports which room it found it in (e.g. "Arrived at 'fountain' (found in
  'The Temple Square')..."). The actual `drink` action itself already
  worked fine (`consume_item(mode="drink", target=...)` — the MUD resolves
  the target itself) — this was purely a wayfinding gap. See
  `tools/navigation.py` (`_route_by_landmark`). Tests:
  `tests/test_navigation_tool.py::test_navigate_to_finds_landmark_mentioned_inside_a_room`,
  `tests/test_navigation_tool.py::test_navigate_to_still_prefers_a_title_match_over_landmark_search`.

- **Some passages are one-way.** Found live: walking south from The Bakery
  into The General Store got an auto-inferred "north back to the Bakery"
  edge (the assumed-bidirectional heuristic added earlier), but the General
  Store's own real recorded `look` exits only ever showed `south` — no
  `north`. The connection only works one direction. `WorldGraph.add_edge`
  now takes an optional `to_room_exits` set (the destination room's real,
  actually-observed exits); when provided, it refuses to fabricate a reverse
  edge that isn't among them, instead of blindly assuming bidirectionality.
  All call sites that have just parsed/looked-up the destination room now
  pass this through: `tools/_walk.py` (`walk_route`, via `RoomMemory`),
  `tools/mud.py` (`_move_and_record`), `tools/room_processor.py`
  (`_process_room`), `tools/exploration.py` (`_explore`). Tests:
  `tests/test_world_graph.py::test_add_edge_skips_reverse_fill_when_destination_exits_dont_include_it`
  and the two tests immediately after it (still-fills-when-included,
  fills-when-unknown).

- **Dark rooms require a light source.** The MUD's dark-room response is
  literally just `"It is pitch black..."` — no title, description, or exits —
  whether peeked at or stood in. `explore()` now peeks with `look <direction>`
  before ever moving into an unexplored exit; if that reveals darkness, the
  exit is marked blocked (reason `"dark (needs a light source)"`) without the
  character ever stepping in. If the peek doesn't catch it (e.g. through a
  closed door) and the character ends up standing in the dark after the real
  move, it retreats back out immediately and marks the exit blocked the same
  way. See `memory/darkness.py` (detection), `memory/blocked_exits.py`
  (reason field), and `tools/exploration.py` (`_explore`). Tests:
  `tests/test_darkness.py`,
  `tests/test_exploration_tool.py::test_explore_never_walks_into_darkness_when_peek_reveals_it`,
  `tests/test_exploration_tool.py::test_explore_retreats_from_darkness_when_peek_misses_it`.
