import json
from pathlib import Path
from boukensha.memory.world_graph import WorldGraph


def test_add_room_creates_node(tmp_path):
    g = WorldGraph(tmp_path)
    g.add_room("aabbcc001122", "Temple Square")
    assert g.has_room("aabbcc001122")


def test_add_edge_creates_connection(tmp_path):
    g = WorldGraph(tmp_path)
    g.add_room("aabbcc001122", "Room A")
    g.add_room("ddeeff334455", "Room B")
    g.add_edge("aabbcc001122", "ddeeff334455", "north")
    neighbors = g.get_neighbors("aabbcc001122")
    assert neighbors.get("north") == "ddeeff334455"


def test_save_and_reload(tmp_path):
    g = WorldGraph(tmp_path)
    g.add_room("aabbcc001122", "Room A")
    g.add_room("ddeeff334455", "Room B")
    g.add_edge("aabbcc001122", "ddeeff334455", "east")
    g.save()

    g2 = WorldGraph(tmp_path)
    g2.load()
    assert g2.has_room("aabbcc001122")
    assert g2.get_neighbors("aabbcc001122").get("east") == "ddeeff334455"


def test_get_neighbors_unknown_room_returns_empty(tmp_path):
    g = WorldGraph(tmp_path)
    assert g.get_neighbors("deadbeefcafe") == {}


def test_has_room_false_for_unknown(tmp_path):
    g = WorldGraph(tmp_path)
    assert not g.has_room("deadbeefcafe")


def test_duplicate_add_room_is_idempotent(tmp_path):
    g = WorldGraph(tmp_path)
    g.add_room("aabbcc001122", "Temple Square")
    g.add_room("aabbcc001122", "Temple Square")
    # No error, node count still 1
    assert g.has_room("aabbcc001122")


def test_add_edge_fills_in_reverse_direction(tmp_path):
    """CircleMUD exits are almost always bidirectional, but edges are only
    ever recorded in the direction actually walked. A room only approached
    from one side must still be pathfinding-reachable from the other, so
    add_edge should optimistically fill in the reverse direction too."""
    g = WorldGraph(tmp_path)
    g.add_room("a", "Room A")
    g.add_room("b", "Room B")
    g.add_edge("a", "b", "north")
    assert g.get_neighbors("b").get("south") == "a"


def test_add_edge_does_not_overwrite_observed_reverse_edge(tmp_path):
    """If the reverse direction has already been observed leading somewhere
    else (a one-way passage, a maze, a different connecting room), the
    optimistic fill-in must never clobber that real, previously-recorded
    edge."""
    g = WorldGraph(tmp_path)
    g.add_room("a", "Room A")
    g.add_room("b", "Room B")
    g.add_room("c", "Room C — the real destination south of B")
    # B's south exit was already observed to lead to C, not back to A.
    g.add_edge("b", "c", "south")
    # Now A -> B north is recorded (e.g. approached from a different room).
    g.add_edge("a", "b", "north")
    assert g.get_neighbors("b").get("south") == "c"
