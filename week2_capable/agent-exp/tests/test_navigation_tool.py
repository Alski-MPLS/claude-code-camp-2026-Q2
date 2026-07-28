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
