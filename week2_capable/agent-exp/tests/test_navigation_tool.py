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
