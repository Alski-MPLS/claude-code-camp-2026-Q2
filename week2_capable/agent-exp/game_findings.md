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
