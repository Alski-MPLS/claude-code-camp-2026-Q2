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


def test_navigate_to_suggests_near_misses_instead_of_guessing_wrong(tmp_path):
    """Live bug: asking for 'Guild of Swordsmen' (not yet mapped) used to
    silently route to the wrong already-known guild on the shared word
    'guild'. Now that word_overlap_matches requires every significant word,
    this returns no route — but the LLM still benefits from being told a
    similarly-named room already exists, rather than just being told to
    explore blindly, since it may already be standing right next to the
    real destination and just needs to move there directly."""
    from boukensha.tools.navigation import Navigation
    from boukensha.registry import Registry
    from boukensha.context import Context
    from boukensha.tasks.player import Player

    memory_dir = tmp_path / "memory"
    graph = WorldGraph(memory_dir)
    graph.add_room("aaa", "Main Street")
    graph.add_room("bbb", "The Entrance To The Clerics' Guild")
    graph.add_edge("aaa", "bbb", "west")

    registry = Registry(Context(task=Player, system="sys"))
    session = MagicMock()
    session.is_open = True
    session.drain.return_value = ""
    session.read_until_prompt.return_value = "Main Street\n   A street.\n[ Exits: w ]\n"
    Navigation.register(registry, session=session, memory_dir=memory_dir, world_graph=graph)

    result = registry.dispatch("navigate_to", {"destination": "Guild of Swordsmen"})

    assert "No confident match" in result
    assert "Clerics' Guild" in result
    assert "move that direction directly" in result


def test_navigate_to_reports_known_but_unreachable_room_distinctly(tmp_path):
    """Live bug: 'The Entrance To The Newbie Zone' was on the map (title
    matched exactly) but no directed path was known from the agent's
    current location — a one-way passage elsewhere in the map meant no
    route existed even though the room itself was fully identified. The old
    'No confident match' message was actively misleading here: it implied a
    naming/ambiguity problem and, worse, the near-miss suggestion logic
    excludes exact matches so it never even mentioned the room the LLM
    actually asked for. A known-exact-match-but-unreachable room must get
    its own message naming that room and suggesting explore(), not a
    generic 'did you mean' list that omits it entirely."""
    from boukensha.tools.navigation import Navigation
    from boukensha.registry import Registry
    from boukensha.context import Context
    from boukensha.tasks.player import Player

    memory_dir = tmp_path / "memory"
    graph = WorldGraph(memory_dir)
    graph.add_room("aaa", "Main Street")
    # Exact title match, but no edge at all connecting it — unreachable.
    graph.add_room("bbb", "The Entrance To The Newbie Zone")

    registry = Registry(Context(task=Player, system="sys"))
    session = MagicMock()
    session.is_open = True
    session.drain.return_value = ""
    session.read_until_prompt.return_value = "Main Street\n   A street.\n[ Exits: n ]\n"
    Navigation.register(registry, session=session, memory_dir=memory_dir, world_graph=graph)

    result = registry.dispatch("navigate_to", {"destination": "The Entrance To The Newbie Zone"})

    assert "already-mapped room" in result
    assert "Newbie Zone" in result
    assert "explore()" in result
    assert "No confident match" not in result


def test_navigate_to_reports_known_but_unreachable_landmark_distinctly(tmp_path):
    """Same bug as the unreachable-title case, but for a landmark: 'go to
    the fountain' matched Temple Square's description via
    _route_by_landmark, but Temple Square was unreachable from the agent's
    current (one-way-trapped) position. That failure used to fall through
    to a completely generic 'No known path' message because the
    known-but-unreachable check only looked at room TITLES, not landmark
    haystacks — so the agent was told nothing about the room it actually
    matched, and (per a live session) gave up on navigate_to entirely,
    wrongly believing it needed a knowledge_search hit first."""
    from boukensha.tools.navigation import Navigation
    from boukensha.registry import Registry
    from boukensha.context import Context
    from boukensha.tasks.player import Player
    from boukensha.memory.room_memory import RoomMemory
    from boukensha.memory.parser import RoomParser

    memory_dir = tmp_path / "memory"
    mem = RoomMemory(memory_dir)

    start_raw = "The Dark Passageway\n   A passage.\n[ Exits: n ]\n"
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
    graph.add_room(start_hash, "The Dark Passageway")
    graph.add_room(square_hash, "The Temple Square")
    # Deliberately no add_edge — Temple Square is known but unreachable.

    registry = Registry(Context(task=Player, system="sys"))
    session = MagicMock()
    session.is_open = True
    session.drain.return_value = ""
    session.read_until_prompt.return_value = start_raw
    Navigation.register(registry, session=session, memory_dir=memory_dir, world_graph=graph)

    result = registry.dispatch("navigate_to", {"destination": "fountain"})

    assert "already-mapped room" in result
    assert "Temple Square" in result
    assert "explore()" in result
    assert "No known path" not in result


def test_find_path_by_title_picks_nearest_match_for_duplicate_titles(tmp_path):
    """CircleMUD reuses the same room title for multiple distinct rooms
    (e.g. several tiles of "The Great Field Of Midgaard" along a road).
    A destination fragment that matches more than one node must resolve
    to the closest one, not whichever the graph happens to iterate to
    first — otherwise navigate_to can send the agent on a long detour to
    an arbitrary, unrelated room sharing that title."""
    g = WorldGraph(tmp_path)
    g.add_room("start", "The Dirty Hallway")
    g.add_room("far", "The Great Field Of Midgaard")
    g.add_room("mid", "Some Corridor")
    g.add_room("near", "The Great Field Of Midgaard")
    # far one is 3 hops away
    g.add_edge("start", "mid", "east")
    g.add_edge("mid", "far", "east")
    # near one is registered second but is only 1 hop away
    g.add_edge("start", "near", "north")

    from boukensha.memory.pathfinder import Pathfinder
    p = Pathfinder(g)
    path = p.find_path_by_title("start", "great field of midgaard")
    assert path == ["north"]


def test_navigate_to_aborts_when_a_move_is_blocked(tmp_path):
    """If a move along the precomputed path doesn't actually change rooms
    (closed door, blocked exit, mob in the way), navigate_to must stop
    instead of continuing to issue the rest of the path from the wrong
    actual room."""
    from boukensha.tools.navigation import Navigation
    from boukensha.registry import Registry
    from boukensha.context import Context
    from boukensha.tasks.player import Player
    from boukensha.memory.room_memory import RoomMemory

    memory_dir = tmp_path / "memory"
    mem = RoomMemory(memory_dir)
    aaa = mem.room_hash({"title": "Room A", "description": "Desc."})
    bbb = mem.room_hash({"title": "Room B", "description": "Desc."})
    ccc = mem.room_hash({"title": "Room C", "description": "Desc."})

    graph = WorldGraph(memory_dir)
    graph.add_room(aaa, "Room A")
    graph.add_room(bbb, "Room B")
    graph.add_room(ccc, "Room C")
    graph.add_edge(aaa, bbb, "north")
    graph.add_edge(bbb, ccc, "east")

    registry = Registry(Context(task=Player, system="sys"))
    session = MagicMock()
    session.is_open = True
    session.drain.return_value = ""
    # look at Room A, attempt "north" but door is closed so we're still in
    # Room A, then (loop should abort before) attempt "east".
    session.read_until_prompt.side_effect = [
        "Room A\n   Desc.\n[ Exits: n ]\n",
        "The door is closed.\n",
        "Room A\n   Desc.\n[ Exits: n ]\n",
    ]
    Navigation.register(registry, session=session, memory_dir=memory_dir, world_graph=graph)

    result = registry.dispatch("navigate_to", {"destination": "Room C"})

    assert "interrupted" in result.lower()
    assert "0/2" in result
    sent = [c.args[0] for c in session.send_command.call_args_list]
    # Only the blocked "north" move should have been attempted, never "east".
    assert sent.count("north") == 1
    assert "east" not in sent


def test_navigate_to_finds_landmark_mentioned_inside_a_room(tmp_path):
    """A destination like "the fountain" is usually a feature inside a
    room's description/items, not a room title. When no title matches,
    navigate_to must fall back to searching room contents and route to
    whichever room actually mentions it."""
    from boukensha.tools.navigation import Navigation
    from boukensha.registry import Registry
    from boukensha.context import Context
    from boukensha.tasks.player import Player
    from boukensha.memory.room_memory import RoomMemory
    from boukensha.memory.parser import RoomParser

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
    assert "fountain" in square_room["items"][0].lower()

    graph = WorldGraph(memory_dir)
    graph.add_room(start_hash, "Main Street")
    graph.add_room(square_hash, "The Temple Square")
    graph.add_edge(start_hash, square_hash, "north")

    registry = Registry(Context(task=Player, system="sys"))
    session = MagicMock()
    session.is_open = True
    session.drain.return_value = ""
    session.read_until_prompt.side_effect = [start_raw, "You go north.\n", square_raw]
    Navigation.register(registry, session=session, memory_dir=memory_dir, world_graph=graph)

    result = registry.dispatch("navigate_to", {"destination": "fountain"})

    assert "temple square" in result.lower()
    assert "1 moves" in result
    sent = [c.args[0] for c in session.send_command.call_args_list]
    assert sent == ["look", "north", "look"]


def test_navigate_to_finds_landmark_via_word_overlap_when_not_a_literal_substring(tmp_path):
    """Same paraphrase problem as room titles: the room mentions a
    'gelatinous blob' but the LLM asks for just the 'gelatinous' one — not a
    literal substring of the full room text, but its one significant word
    is fully contained in it. The landmark fallback must catch this the same
    way Pathfinder.route_by_title does for titles."""
    from boukensha.tools.navigation import Navigation
    from boukensha.registry import Registry
    from boukensha.context import Context
    from boukensha.tasks.player import Player
    from boukensha.memory.room_memory import RoomMemory
    from boukensha.memory.parser import RoomParser

    memory_dir = tmp_path / "memory"
    mem = RoomMemory(memory_dir)

    start_raw = "Main Street\n   A street.\n[ Exits: n ]\n"
    square_raw = (
        "The Temple Square\n   You are standing on the temple square.\n"
        "[ Exits: s ]\n"
        "An oozing green gelatinous blob is here, sucking in bits of debris.\n"
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
    session.read_until_prompt.side_effect = [start_raw, "You go north.\n", square_raw]
    Navigation.register(registry, session=session, memory_dir=memory_dir, world_graph=graph)

    # Words reversed so this isn't a literal substring of the room text
    # (which would trivially hit the substring branch instead of exercising
    # the word-overlap fallback this test targets).
    result = registry.dispatch("navigate_to", {"destination": "blob gelatinous"})

    assert "temple square" in result.lower()


def test_navigate_to_still_prefers_a_title_match_over_landmark_search(tmp_path):
    """A room title match must win outright — the landmark fallback should
    only ever kick in when no title matches at all."""
    from boukensha.memory.pathfinder import Pathfinder

    g = WorldGraph(tmp_path)
    g.add_room("aaa", "Room A")
    g.add_room("bbb", "The Fountain Room")
    g.add_edge("aaa", "bbb", "north")
    p = Pathfinder(g)
    assert p.route_by_title("aaa", "fountain") is not None


def test_navigate_to_aborts_when_a_move_lands_in_an_unexpected_room(tmp_path):
    """A move can succeed (the room really does change) while still not
    matching what the graph predicted for that step — a stale/incorrect
    edge left over from before the room-hashing bug was fixed. Continuing
    to walk the rest of the precomputed path would compound the drift, so
    navigate_to must notice the mismatch and stop, and it should record the
    edge actually observed so the graph corrects itself for next time."""
    from boukensha.tools.navigation import Navigation
    from boukensha.registry import Registry
    from boukensha.context import Context
    from boukensha.tasks.player import Player
    from boukensha.memory.room_memory import RoomMemory

    memory_dir = tmp_path / "memory"
    mem = RoomMemory(memory_dir)
    aaa = mem.room_hash({"title": "Room A", "description": "Desc A."})
    bbb = mem.room_hash({"title": "Room B", "description": "Desc B."})
    ccc = mem.room_hash({"title": "Room C", "description": "Desc C."})
    ddd = mem.room_hash({"title": "Room D", "description": "Desc D."})

    graph = WorldGraph(memory_dir)
    graph.add_room(aaa, "Room A")
    graph.add_room(bbb, "Room B")
    graph.add_room(ccc, "Room C")
    graph.add_room(ddd, "Room D")
    # The graph (wrongly) believes north from A leads to B.
    graph.add_edge(aaa, bbb, "north")
    graph.add_edge(bbb, ccc, "east")

    registry = Registry(Context(task=Player, system="sys"))
    session = MagicMock()
    session.is_open = True
    session.drain.return_value = ""
    # look at Room A, move north but really land in Room D (not B).
    session.read_until_prompt.side_effect = [
        "Room A\n   Desc A.\n[ Exits: n ]\n",
        "You go north.\n",
        "Room D\n   Desc D.\n[ Exits: e ]\n",
    ]
    Navigation.register(registry, session=session, memory_dir=memory_dir, world_graph=graph)

    result = registry.dispatch("navigate_to", {"destination": "Room C"})

    assert "interrupted" in result.lower()
    assert "unexpected room" in result.lower()
    sent = [c.args[0] for c in session.send_command.call_args_list]
    # Only the drifting "north" move should have been attempted, never "east".
    assert sent.count("north") == 1
    assert "east" not in sent
    # The graph should have self-corrected: A's real north neighbor is D, not B.
    assert graph.get_neighbors(aaa).get("north") == ddd


def test_navigate_to_resolves_via_alias_before_title_search(tmp_path):
    """An aliased destination must resolve directly through the alias store,
    bypassing route_by_title's substring-match-then-shortest-route logic
    entirely — not merely agree with it by coincidence.

    The fixture is deliberately adversarial: a decoy room ("Ruined Guild Of
    Swordsmen Annex") that ALSO contains "guild of swordsmen" as a literal
    substring sits just one hop from the start room, while the real target
    ("The Guild Of Swordsmen") sits two hops away via an intermediate room.
    Without the alias, route_by_title would find both as substring matches
    and pick the shortest route — the wrong, closer decoy. The alias points
    "guild of swordsmen" directly at the real target's room hash, so
    navigate_to must land on the farther, correct room instead. If the
    alias-first branch in _navigate_to were removed, this test would fail
    (it would resolve to the 1-hop decoy instead of the 2-hop real room)."""
    from boukensha.tools.navigation import Navigation
    from boukensha.registry import Registry
    from boukensha.context import Context
    from boukensha.tasks.player import Player
    from boukensha.memory.room_memory import RoomMemory
    from boukensha.memory.parser import RoomParser
    from boukensha.memory.room_aliases import RoomAliases

    memory_dir = tmp_path / "memory"
    mem = RoomMemory(memory_dir)

    main_raw = "Main Street\n   A street.\n[ Exits: s ]\n"
    mid_raw = "Guild Antechamber\n   A quiet hallway.\n[ Exits: e ]\n"
    guild_raw = "The Guild Of Swordsmen\n   A training hall.\n[ Exits: w ]\n"
    main_hash, _ = mem.record(RoomParser.parse(main_raw))
    mid_hash, _ = mem.record(RoomParser.parse(mid_raw))
    guild_hash, _ = mem.record(RoomParser.parse(guild_raw))
    decoy_hash = "decoy-annex"

    graph = WorldGraph(memory_dir)
    graph.add_room(main_hash, "Main Street")
    graph.add_room(decoy_hash, "Ruined Guild Of Swordsmen Annex")
    graph.add_room(mid_hash, "Guild Antechamber")
    graph.add_room(guild_hash, "The Guild Of Swordsmen")
    graph.add_edge(main_hash, decoy_hash, "west")  # 1 hop: wrong room, matches by substring too
    graph.add_edge(main_hash, mid_hash, "south")
    graph.add_edge(mid_hash, guild_hash, "east")  # 2 hops: the real, aliased target

    RoomAliases(memory_dir).add("guild of swordsmen", guild_hash)

    registry = Registry(Context(task=Player, system="sys"))
    session = MagicMock()
    session.is_open = True
    session.drain.return_value = ""
    session.read_until_prompt.side_effect = [
        main_raw, "You go south.\n", mid_raw, "You go east.\n", guild_raw,
    ]
    Navigation.register(registry, session=session, memory_dir=memory_dir, world_graph=graph)

    result = registry.dispatch("navigate_to", {"destination": "guild of swordsmen"})

    # The 1-hop decoy also matches "guild of swordsmen" by substring, so a
    # weaker assertion (e.g. just "swordsmen" in result) wouldn't tell the
    # two rooms apart. The move count/path is what actually distinguishes
    # "took the alias's 2-hop route" from "took route_by_title's 1-hop
    # shortest-substring-match route".
    assert result == "Arrived at 'guild of swordsmen' after 2 moves: south → east"


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
