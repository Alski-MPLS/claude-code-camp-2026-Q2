"""Tests for the RoomGraph and Map tool registration."""

from __future__ import annotations

import json
from pathlib import Path
from unittest.mock import MagicMock

import pytest

from boukensha.tools.map import Map, RoomGraph, _node_key, _parse_room


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

LOOK_ROOM_A = """\
The Town Square
A wide cobblestone plaza.  A fountain burbles in the center.
Obvious exits: north, east, south
"""

LOOK_ROOM_B = """\
A Dark Alley
Shadows cling to the walls here.  You smell something unpleasant.
Obvious exits: south, west
"""

LOOK_ROOM_C = """\
The Blacksmith
Hammers ring out as the smith works the forge.
Obvious exits: east
"""

NO_EXITS_RESPONSE = "You see nothing special."


@pytest.fixture()
def tmp_save(tmp_path: Path) -> Path:
    return tmp_path / "maps" / "testchar.json"


@pytest.fixture()
def graph(tmp_save: Path) -> RoomGraph:
    return RoomGraph(tmp_save)


# ---------------------------------------------------------------------------
# _node_key
# ---------------------------------------------------------------------------

def test_node_key_is_stable():
    k1 = _node_key("Town Square", "A plaza.", ["north", "east"])
    k2 = _node_key("Town Square", "A plaza.", ["north", "east"])
    assert k1 == k2


def test_node_key_exit_order_independent():
    k1 = _node_key("Town Square", "A plaza.", ["north", "east"])
    k2 = _node_key("Town Square", "A plaza.", ["east", "north"])
    assert k1 == k2


def test_node_key_differs_on_title():
    k1 = _node_key("Room A", "desc", ["north"])
    k2 = _node_key("Room B", "desc", ["north"])
    assert k1 != k2


def test_node_key_is_12_hex_chars():
    k = _node_key("x", "y", [])
    assert len(k) == 12
    assert all(c in "0123456789abcdef" for c in k)


# ---------------------------------------------------------------------------
# _parse_room
# ---------------------------------------------------------------------------

def test_parse_room_extracts_title_exits():
    result = _parse_room(LOOK_ROOM_A)
    assert result is not None
    title, _desc, exits = result
    assert title == "The Town Square"
    assert set(exits) == {"north", "east", "south"}


def test_parse_room_returns_none_without_exits_line():
    assert _parse_room(NO_EXITS_RESPONSE) is None


def test_parse_room_strips_ansi():
    ansi_response = "\x1b[1mThe Arena\x1b[0m\nBlood stains the sand.\nObvious exits: west\n"
    result = _parse_room(ansi_response)
    assert result is not None
    assert result[0] == "The Arena"


# ---------------------------------------------------------------------------
# RoomGraph.observe — node creation
# ---------------------------------------------------------------------------

def test_observe_adds_node(graph: RoomGraph):
    graph.observe(LOOK_ROOM_A, "look")
    assert graph._graph.number_of_nodes() == 1


def test_observe_sets_current_node(graph: RoomGraph):
    graph.observe(LOOK_ROOM_A, "look")
    assert graph._current is not None


def test_observe_unrecognised_response_is_noop(graph: RoomGraph):
    graph.observe(NO_EXITS_RESPONSE, "look")
    assert graph._graph.number_of_nodes() == 0
    assert graph._current is None


def test_observe_idempotent_same_room(graph: RoomGraph):
    graph.observe(LOOK_ROOM_A, "look")
    graph.observe(LOOK_ROOM_A, "look")
    assert graph._graph.number_of_nodes() == 1


# ---------------------------------------------------------------------------
# RoomGraph.observe — edge creation
# ---------------------------------------------------------------------------

def test_observe_move_adds_directed_edge(graph: RoomGraph):
    graph.observe(LOOK_ROOM_A, "look")
    graph.observe(LOOK_ROOM_B, "north")
    assert graph._graph.number_of_edges() == 1
    edges = list(graph._graph.edges(data=True))
    assert edges[0][2]["direction"] == "north"


def test_observe_non_direction_cmd_no_edge(graph: RoomGraph):
    graph.observe(LOOK_ROOM_A, "look")
    graph.observe(LOOK_ROOM_B, "look")
    assert graph._graph.number_of_edges() == 0


def test_observe_edge_direction_preserved(graph: RoomGraph):
    graph.observe(LOOK_ROOM_A, "look")
    graph.observe(LOOK_ROOM_B, "east")
    graph.observe(LOOK_ROOM_C, "south")
    assert graph._graph.number_of_edges() == 2


# ---------------------------------------------------------------------------
# map_here
# ---------------------------------------------------------------------------

def test_map_here_no_location(graph: RoomGraph):
    result = graph.map_here()
    assert "No location" in result


def test_map_here_shows_title(graph: RoomGraph):
    graph.observe(LOOK_ROOM_A, "look")
    result = graph.map_here()
    assert "Town Square" in result


def test_map_here_marks_unexplored_exits(graph: RoomGraph):
    graph.observe(LOOK_ROOM_A, "look")
    result = graph.map_here()
    assert "unexplored" in result


def test_map_here_marks_mapped_exit_after_move(graph: RoomGraph):
    graph.observe(LOOK_ROOM_A, "look")
    graph.observe(LOOK_ROOM_B, "north")
    # go back to A
    graph.observe(LOOK_ROOM_A, "south")
    result = graph.map_here()
    assert "mapped" in result


# ---------------------------------------------------------------------------
# map_path_to
# ---------------------------------------------------------------------------

def test_map_path_to_no_current(graph: RoomGraph):
    result = graph.map_path_to("Town Square")
    assert "unknown" in result.lower()


def test_map_path_to_already_here(graph: RoomGraph):
    graph.observe(LOOK_ROOM_A, "look")
    result = graph.map_path_to("Town Square")
    assert "already" in result.lower()


def test_map_path_to_direct_path(graph: RoomGraph):
    graph.observe(LOOK_ROOM_A, "look")
    graph.observe(LOOK_ROOM_B, "north")
    graph.observe(LOOK_ROOM_A, "south")   # back at A
    result = graph.map_path_to("Dark Alley")
    assert "north" in result


def test_map_path_to_no_match(graph: RoomGraph):
    graph.observe(LOOK_ROOM_A, "look")
    result = graph.map_path_to("Nonexistent Dungeon")
    assert "No room matching" in result


def test_map_path_to_unreachable(graph: RoomGraph):
    # Two isolated rooms with no edges between them
    graph.observe(LOOK_ROOM_A, "look")
    key_a = graph._current          # save A's key
    graph._current = None           # break the chain so no edge is recorded
    graph.observe(LOOK_ROOM_B, "look")   # B is added as an island
    graph._current = key_a          # restore current to A (which IS in the graph)
    result = graph.map_path_to("Dark Alley")
    assert "no navigable path" in result.lower()


# ---------------------------------------------------------------------------
# map_summary
# ---------------------------------------------------------------------------

def test_map_summary_empty(graph: RoomGraph):
    result = graph.map_summary()
    assert "empty" in result.lower()


def test_map_summary_counts_rooms(graph: RoomGraph):
    graph.observe(LOOK_ROOM_A, "look")
    graph.observe(LOOK_ROOM_B, "north")
    result = graph.map_summary()
    assert "2 room" in result


def test_map_summary_marks_current_room(graph: RoomGraph):
    graph.observe(LOOK_ROOM_A, "look")
    result = graph.map_summary()
    assert "you are here" in result.lower()


# ---------------------------------------------------------------------------
# JSON persistence round-trip
# ---------------------------------------------------------------------------

def test_save_creates_file(graph: RoomGraph, tmp_save: Path):
    graph.observe(LOOK_ROOM_A, "look")
    assert tmp_save.exists()


def test_round_trip_preserves_nodes(tmp_save: Path):
    g1 = RoomGraph(tmp_save)
    g1.observe(LOOK_ROOM_A, "look")
    g1.observe(LOOK_ROOM_B, "north")

    g2 = RoomGraph(tmp_save)
    assert g2._graph.number_of_nodes() == 2
    assert g2._graph.number_of_edges() == 1
    assert g2._current == g1._current


def test_round_trip_preserves_edge_direction(tmp_save: Path):
    g1 = RoomGraph(tmp_save)
    g1.observe(LOOK_ROOM_A, "look")
    g1.observe(LOOK_ROOM_B, "east")

    g2 = RoomGraph(tmp_save)
    edges = list(g2._graph.edges(data=True))
    assert edges[0][2]["direction"] == "east"


def test_load_corrupt_json_is_noop(tmp_save: Path):
    tmp_save.parent.mkdir(parents=True, exist_ok=True)
    tmp_save.write_text("{not valid json")
    g = RoomGraph(tmp_save)   # should not raise
    assert g._graph.number_of_nodes() == 0


# ---------------------------------------------------------------------------
# Map.register — tool wiring
# ---------------------------------------------------------------------------

def test_map_register_returns_room_graph(tmp_save: Path):
    registry = MagicMock()
    result = Map.register(registry, save_path=tmp_save)
    assert isinstance(result, RoomGraph)


def test_map_register_registers_four_tools_complete(tmp_save: Path):
    registry = MagicMock()
    Map.register(registry, save_path=tmp_save)
    assert registry.tool.call_count == 4
    names = {call.args[0] for call in registry.tool.call_args_list}
    assert names == {"map_here", "map_path_to", "map_summary", "map_find_capability"}


# ---------------------------------------------------------------------------
# Affordance tagging
# ---------------------------------------------------------------------------

LOOK_FOUNTAIN_ROOM = """\
The Town Square
A wide cobblestone plaza.  A stone fountain gurgles in the center.
Obvious exits: north, east, south
"""

LOOK_BAKERY_ROOM = """\
The Bakery
The smell of fresh bread fills the air.  A vendor sells loaves here.
Obvious exits: west
"""

LOOK_TEMPLE_ROOM = """\
The Temple of Healing
A cleric tends to the wounded at the shrine.
Obvious exits: south
"""

LOOK_PLAIN_ROOM = """\
A Dark Corridor
Damp stone walls.  Nothing of note here.
Obvious exits: north, south
"""


def test_affordance_can_drink_inferred_from_description(graph: RoomGraph):
    graph.observe(LOOK_FOUNTAIN_ROOM, "look")
    node_data = graph._graph.nodes[graph._current]
    assert "can_drink" in node_data.get("affordances", [])


def test_affordance_can_eat_inferred_from_description(graph: RoomGraph):
    graph.observe(LOOK_BAKERY_ROOM, "look")
    node_data = graph._graph.nodes[graph._current]
    assert "can_eat" in node_data.get("affordances", [])


def test_affordance_can_heal_inferred_from_description(graph: RoomGraph):
    graph.observe(LOOK_TEMPLE_ROOM, "look")
    node_data = graph._graph.nodes[graph._current]
    assert "can_heal" in node_data.get("affordances", [])


def test_affordance_can_rest_inferred_from_description(graph: RoomGraph):
    graph.observe(LOOK_TEMPLE_ROOM, "look")
    node_data = graph._graph.nodes[graph._current]
    assert "can_rest" in node_data.get("affordances", [])


def test_no_affordance_on_plain_room(graph: RoomGraph):
    graph.observe(LOOK_PLAIN_ROOM, "look")
    node_data = graph._graph.nodes[graph._current]
    assert node_data.get("affordances", []) == []


def test_rooms_with_affordance_returns_matching_keys(graph: RoomGraph):
    graph.observe(LOOK_FOUNTAIN_ROOM, "look")
    fountain_key = graph._current
    graph.observe(LOOK_PLAIN_ROOM, "north")
    results = graph.rooms_with_affordance("can_drink")
    assert fountain_key in results
    assert graph._current not in results


def test_confirm_affordance_adds_to_confirmed(graph: RoomGraph):
    graph.observe(LOOK_FOUNTAIN_ROOM, "look")
    key = graph._current
    graph.confirm_affordance(key, "can_drink")
    node_data = graph._graph.nodes[key]
    assert "can_drink" in node_data.get("affordances_confirmed", [])


def test_confirm_affordance_also_ensures_inferred(graph: RoomGraph):
    graph.observe(LOOK_PLAIN_ROOM, "look")
    key = graph._current
    graph.confirm_affordance(key, "can_drink")
    node_data = graph._graph.nodes[key]
    assert "can_drink" in node_data.get("affordances", [])


def test_affordances_survive_round_trip(tmp_save: Path):
    g1 = RoomGraph(tmp_save)
    g1.observe(LOOK_FOUNTAIN_ROOM, "look")
    g2 = RoomGraph(tmp_save)
    node_data = g2._graph.nodes[g2._current]
    assert "can_drink" in node_data.get("affordances", [])


# ---------------------------------------------------------------------------
# map_find_capability
# ---------------------------------------------------------------------------

def test_map_find_capability_no_current(graph: RoomGraph):
    result = graph.map_find_capability("can_drink")
    assert "unknown" in result.lower()


def test_map_find_capability_no_matching_rooms(graph: RoomGraph):
    graph.observe(LOOK_PLAIN_ROOM, "look")
    result = graph.map_find_capability("can_drink")
    assert "no known" in result.lower()


def test_map_find_capability_already_here(graph: RoomGraph):
    graph.observe(LOOK_FOUNTAIN_ROOM, "look")
    result = graph.map_find_capability("can_drink")
    assert "already" in result.lower()


def test_map_find_capability_finds_nearest(graph: RoomGraph):
    graph.observe(LOOK_PLAIN_ROOM, "look")          # start: plain
    graph.observe(LOOK_FOUNTAIN_ROOM, "north")      # north → fountain
    graph.observe(LOOK_PLAIN_ROOM, "south")         # back to plain
    result = graph.map_find_capability("can_drink")
    assert "north" in result
    assert "can_drink" in result or "fountain" in result.lower()


def test_map_find_capability_unreachable(graph: RoomGraph):
    graph.observe(LOOK_PLAIN_ROOM, "look")
    key_plain = graph._current
    graph._current = None
    graph.observe(LOOK_FOUNTAIN_ROOM, "look")   # island node
    graph._current = key_plain
    result = graph.map_find_capability("can_drink")
    assert "no navigable" in result.lower() or "no known" in result.lower()


# ---------------------------------------------------------------------------
# map_path_to — capability fallback
# ---------------------------------------------------------------------------

def test_map_path_to_falls_back_to_capability(graph: RoomGraph):
    graph.observe(LOOK_PLAIN_ROOM, "look")
    graph.observe(LOOK_FOUNTAIN_ROOM, "north")
    graph.observe(LOOK_PLAIN_ROOM, "south")
    # "fountain" matches no room title but IS a can_drink keyword
    result = graph.map_path_to("fountain")
    assert "north" in result


# ---------------------------------------------------------------------------
# Loop detection in map_here
# ---------------------------------------------------------------------------

def test_map_here_no_loop_warning_normally(graph: RoomGraph):
    graph.observe(LOOK_ROOM_A, "look")
    graph.observe(LOOK_ROOM_B, "north")
    result = graph.map_here()
    assert "loop" not in result.lower()


def test_map_here_warns_on_loop(graph: RoomGraph):
    # Visit same room 3 times in last 6 moves
    graph.observe(LOOK_ROOM_A, "look")
    graph.observe(LOOK_ROOM_B, "north")
    graph.observe(LOOK_ROOM_A, "south")
    graph.observe(LOOK_ROOM_B, "north")
    graph.observe(LOOK_ROOM_A, "south")
    result = graph.map_here()
    assert "loop" in result.lower()


# ---------------------------------------------------------------------------
# Map.register — now 4 tools
# ---------------------------------------------------------------------------

def test_map_register_registers_four_tools(tmp_save: Path):
    registry = MagicMock()
    Map.register(registry, save_path=tmp_save)
    assert registry.tool.call_count == 4
    names = {call.args[0] for call in registry.tool.call_args_list}
    assert "map_find_capability" in names
