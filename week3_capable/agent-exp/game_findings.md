# Game Findings

Running log of things learned about how this particular MUD behaves — quirks,
rules, and mechanics discovered during live play that aren't reflected in the
code yet. Add an entry whenever something surprising turns up; move it into
actual code/tests once it's implemented (leave the entry, just note where it
landed).

## Open

- **No light-source tracking yet.** `explore()` now refuses to walk into a
  room it detects as dark (see Implemented below) instead of blindly
  entering it, but it has no way to check whether the agent is actually
  carrying a lit torch/lantern before deciding to retry a dark exit — it just
  marks the exit blocked and leaves it blocked until someone calls
  `BlockedExits.unmark()`. Equipment slots are now tracked (see Implemented
  below), so this is a matter of reading the `light` slot from
  `PlayerTracker`'s stored equipment, not adding new tracking. Next step:
  wire that check into `explore()`'s dark-exit retry path.

## Implemented

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

  Both parsers normalize wear locations through one canonical slot table
  (`equipment_parser._CANONICAL_SLOTS` / `canonical_slot`), derived from
  `ObjectWear` and `MobEquipSlot` in the week0 world parser's `constants.py`,
  so `<worn around neck>` from the equipment listing and `TAKE NECK` from
  `identify` both resolve to `neck`.

  Open item — dual-slot categories collapse. CircleMUD has genuinely paired
  slots (`RING_R`/`RING_L`, `NECK_1`/`NECK_2`, `WRIST_R`/`WRIST_L`) that print
  the identical `<worn on finger>` / `<worn around neck>` / `<worn around
  wrist>` label. Because the canonical table maps both members to one key,
  `parse_equipment` records only one item per category (last one wins), and an
  upgrade advisory for those slots compares against whichever ring/amulet/
  bracelet was listed second. Wearing two rings is normal play, not an edge
  case — fixing it properly needs a list-per-slot representation in
  `PlayerTracker`, which is out of scope for the current pass.

  Caveat: `parse_identify`'s regexes are built against the stock CircleMUD
  `identify` output format, unverified against this server's actual output
  — first live `identify` cast after deployment should confirm the format
  matches, and this note should be updated (or the regexes fixed) if not.

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
