from unittest.mock import MagicMock

from boukensha.context import Context
from boukensha.registry import Registry
from boukensha.tasks.player import Player
from boukensha.memory.world_graph import WorldGraph
from boukensha.memory.room_memory import RoomMemory
from boukensha.memory.blocked_exits import BlockedExits
from boukensha.memory.parser import RoomParser
from boukensha.tools.exploration import Exploration


def _make_registry() -> Registry:
    ctx = Context(task=Player, system="sys")
    return Registry(ctx)


def _make_session(*responses: str) -> MagicMock:
    session = MagicMock()
    session.is_open = True
    session.drain.return_value = ""
    session.read_until_prompt.side_effect = list(responses)
    return session


def test_explore_discovers_new_room_via_unwalked_exit(tmp_path):
    """The exact scenario reported: a room has an exit the agent has seen
    but never walked through (no edge recorded for it), and asking to
    explore should go find what's through it — without specifying a
    destination."""
    memory_dir = tmp_path / "memory"
    graph = WorldGraph(memory_dir)
    registry = _make_registry()
    session = _make_session(
        "Room A\n   Desc A.\n[ Exits: n ]\n",
        "You go north.\n",
        "Room B\n   Desc B.\n[ Exits: s ]\n",
    )
    Exploration.register(registry, session=session, memory_dir=memory_dir, world_graph=graph)

    result = registry.dispatch("explore", {})

    assert "discovered 'room b'" in result.lower()
    sent = [c.args[0] for c in session.send_command.call_args_list]
    assert sent == ["look", "north", "look"]


def test_explore_skips_already_blocked_exit(tmp_path):
    """An exit already confirmed to need a key/be locked must not be
    retried on every explore() call — it should move on to the next
    unexplored exit instead."""
    memory_dir = tmp_path / "memory"
    graph = WorldGraph(memory_dir)
    mem = RoomMemory(memory_dir)
    blocked = BlockedExits(memory_dir)

    raw = "Room A\n   Desc A.\n[ Exits: n e ]\n"
    room = RoomParser.parse(raw)
    room_hash, _ = mem.record(room)
    graph.add_room(room_hash, room["title"])
    blocked.mark_blocked(room_hash, "north")

    registry = _make_registry()
    session = _make_session(
        raw,
        "You go east.\n",
        "Room C\n   Desc C.\n[ Exits: w ]\n",
    )
    Exploration.register(registry, session=session, memory_dir=memory_dir, world_graph=graph)

    result = registry.dispatch("explore", {})

    assert "discovered 'room c'" in result.lower()
    sent = [c.args[0] for c in session.send_command.call_args_list]
    assert "north" not in sent
    assert sent.count("east") == 1


def test_explore_opens_closed_door_and_retries(tmp_path):
    """A move that doesn't change rooms might just be a closed (not locked)
    door — explore should try opening it once before giving up on the exit."""
    memory_dir = tmp_path / "memory"
    graph = WorldGraph(memory_dir)
    registry = _make_registry()
    room_a = "Room A\n   Desc A.\n[ Exits: s ]\n"
    session = _make_session(
        room_a,               # initial look
        "The door is closed.\n",  # failed move south
        room_a,                # look again, still in Room A
        "You open the door.\n",   # open south
        "You go south.\n",         # retried move south
        "Room E\n   Desc E.\n[ Exits: n ]\n",  # look, now in Room E
    )
    Exploration.register(registry, session=session, memory_dir=memory_dir, world_graph=graph)

    result = registry.dispatch("explore", {})

    assert "closed" in result.lower()
    assert "discovered 'room e'" in result.lower()
    sent = [c.args[0] for c in session.send_command.call_args_list]
    assert sent == ["look", "south", "look", "open south", "south", "look"]


def test_explore_marks_exit_blocked_when_still_stuck_after_opening(tmp_path):
    """If the exit is still blocked even after trying to open it (locked,
    needs a key), explore must mark it blocked rather than fail silently or
    loop on it again next time."""
    memory_dir = tmp_path / "memory"
    graph = WorldGraph(memory_dir)
    registry = _make_registry()
    room_a = "Room A\n   Desc A.\n[ Exits: s ]\n"
    session = _make_session(
        room_a,
        "The door is closed.\n",
        room_a,
        "It seems to be locked.\n",
        "The door is closed.\n",
        room_a,
    )
    Exploration.register(registry, session=session, memory_dir=memory_dir, world_graph=graph)

    result = registry.dispatch("explore", {})

    assert "blocked" in result.lower()

    room_hash = next(iter(graph.graph.nodes))
    blocked = BlockedExits(memory_dir)
    assert blocked.get(room_hash) == {"south"}


def test_explore_reports_fully_mapped_area(tmp_path):
    """Once every known exit either has an edge or is blocked, explore must
    say so rather than claiming there's nowhere left to look by accident."""
    memory_dir = tmp_path / "memory"
    graph = WorldGraph(memory_dir)
    mem = RoomMemory(memory_dir)

    raw = "Room A\n   Desc A.\n[ Exits: n ]\n"
    room = RoomParser.parse(raw)
    a_hash, _ = mem.record(room)
    graph.add_room(a_hash, room["title"])
    graph.add_room("bbb", "Room B")
    graph.add_edge(a_hash, "bbb", "north")

    registry = _make_registry()
    session = _make_session(raw)
    Exploration.register(registry, session=session, memory_dir=memory_dir, world_graph=graph)

    result = registry.dispatch("explore", {})

    assert "fully mapped" in result.lower()
    sent = [c.args[0] for c in session.send_command.call_args_list]
    assert sent == ["look"]
