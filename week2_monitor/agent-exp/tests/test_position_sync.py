"""Regression tests for the exact live bug reported: navigate_to/explore
moved the character without updating prev_hash_ref (shared with the raw
move/process_room tools' edge-recording), so a later raw `move` call wired
a bogus edge from a stale "last known room" instead of the real one —
producing impossible double connections like a room having two different
"south" exits in the map."""

from unittest.mock import MagicMock

from boukensha.context import Context
from boukensha.registry import Registry
from boukensha.tasks.player import Player
from boukensha.memory.world_graph import WorldGraph
from boukensha.memory.room_memory import RoomMemory
from boukensha.memory.parser import RoomParser
from boukensha.tools.mud import Mud
from boukensha.tools.navigation import Navigation
from boukensha.tools.exploration import Exploration


def _make_registry() -> Registry:
    return Registry(Context(task=Player, system="sys"))


def test_navigate_to_syncs_prev_hash_ref_for_a_later_raw_move(tmp_path):
    memory_dir = tmp_path / "memory"
    mem = RoomMemory(memory_dir)

    bakery_raw = "The Bakery\n   A bakery.\n[ Exits: s ]\n"
    store_raw = "The General Store\n   A store.\n[ Exits: n s ]\n"
    bakery_room = RoomParser.parse(bakery_raw)
    store_room = RoomParser.parse(store_raw)
    bakery_hash, _ = mem.record(bakery_room)
    store_hash, _ = mem.record(store_room)

    graph = WorldGraph(memory_dir)
    graph.add_room(bakery_hash, "The Bakery")
    graph.add_room(store_hash, "The General Store")
    graph.add_edge(bakery_hash, store_hash, "south", to_room_exits={"north", "south"})

    registry = _make_registry()
    session = MagicMock()
    session.is_open = True
    session.drain.return_value = ""

    prev_hash_ref: list[str | None] = [bakery_hash]  # stale: character was here before
    last_direction_ref: list[str | None] = [None]

    Navigation.register(
        registry,
        session=session,
        memory_dir=memory_dir,
        world_graph=graph,
        prev_hash_ref=prev_hash_ref,
        last_direction_ref=last_direction_ref,
    )
    Mud._register_with_session(
        registry,
        session,
        name="Tester",
        password="secret",
        memory_dir=str(memory_dir),
        world_graph=graph,
        prev_hash_ref=prev_hash_ref,
        last_direction_ref=last_direction_ref,
    )

    session.read_until_prompt.side_effect = [bakery_raw, "You go south.\n", store_raw]
    registry.dispatch("navigate_to", {"destination": "General Store"})

    # navigate_to must have updated the shared pointer to where it actually left off.
    assert prev_hash_ref[0] == store_hash

    # Now a raw move south from the General Store (a real exit, per its own
    # recorded data) must record an edge FROM the General Store — not from
    # the stale Bakery — regardless of what room that move actually lands in.
    session.read_until_prompt.side_effect = ["Main Street\n   A street.\n[ Exits: n ]\n"]
    registry.dispatch("move", {"direction": "south"})

    main_street_hash = next(
        h for h, a in graph.graph.nodes(data=True) if a.get("title") == "Main Street"
    )
    edge = graph.graph.get_edge_data(store_hash, main_street_hash)
    assert edge is not None
    assert edge["direction"] == "south"
    # The bogus edge this bug produced live: Bakery gaining a second,
    # impossible "south" exit to wherever the raw move actually landed.
    assert graph.graph.get_edge_data(bakery_hash, main_street_hash) is None


def test_explore_syncs_prev_hash_ref_for_a_later_raw_move(tmp_path):
    memory_dir = tmp_path / "memory"
    graph = WorldGraph(memory_dir)

    registry = _make_registry()
    session = MagicMock()
    session.is_open = True
    session.drain.return_value = ""

    prev_hash_ref: list[str | None] = [None]
    last_direction_ref: list[str | None] = [None]

    Exploration.register(
        registry,
        session=session,
        memory_dir=memory_dir,
        world_graph=graph,
        prev_hash_ref=prev_hash_ref,
        last_direction_ref=last_direction_ref,
    )
    Mud._register_with_session(
        registry,
        session,
        name="Tester",
        password="secret",
        memory_dir=str(memory_dir),
        world_graph=graph,
        prev_hash_ref=prev_hash_ref,
        last_direction_ref=last_direction_ref,
    )

    session.read_until_prompt.side_effect = [
        "Room A\n   Desc A.\n[ Exits: n ]\n",
        "You see a corridor.\n",  # peek
        "You go north.\n",
        "Room B\n   Desc B.\n[ Exits: s ]\n",
    ]
    registry.dispatch("explore", {})

    room_b_hash = next(
        h for h, a in graph.graph.nodes(data=True) if a.get("title") == "Room B"
    )
    assert prev_hash_ref[0] == room_b_hash

    session.read_until_prompt.side_effect = ["Room C\n   Desc C.\n[ Exits: n ]\n"]
    registry.dispatch("move", {"direction": "south"})

    room_c_hash = next(
        h for h, a in graph.graph.nodes(data=True) if a.get("title") == "Room C"
    )
    edge = graph.graph.get_edge_data(room_b_hash, room_c_hash)
    assert edge is not None
    assert edge["direction"] == "south"
