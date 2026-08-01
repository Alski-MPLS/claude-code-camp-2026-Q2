from boukensha.memory.world_graph import WorldGraph
from boukensha.memory.room_memory import RoomMemory
from boukensha.memory.map_enrichment import classify_edges, node_frontier


def _room(title, exits, npcs=None, items=None):
    return {"title": title, "description": "d", "exits": exits, "npcs": npcs or [], "items": items or []}


def test_classify_edges_walked_vs_inferred(tmp_path):
    graph = WorldGraph(tmp_path)
    mem = RoomMemory(tmp_path)

    room_a = _room("Room A", {"north": "a corridor"})
    hash_a, _ = mem.record(room_a)
    graph.add_room(hash_a, "Room A")

    room_b = _room("Room B", {})  # B's own exits don't mention south — the reverse edge is inferred
    hash_b, _ = mem.record(room_b)
    graph.add_room(hash_b, "Room B")

    # to_room_exits omitted (defaults to None = "unknown yet") so WorldGraph
    # optimistically auto-fills the south reverse edge — passing an empty
    # set here would instead tell it "confirmed no such exit" and suppress
    # the reverse edge entirely, which is not what we're testing.
    graph.add_edge(hash_a, hash_b, "north")

    classification = classify_edges(graph, mem)
    assert classification[(hash_a, hash_b)] == "walked"
    assert classification[(hash_b, hash_a)] == "inferred"


def test_classify_edges_empty_graph(tmp_path):
    graph = WorldGraph(tmp_path)
    mem = RoomMemory(tmp_path)
    assert classify_edges(graph, mem) == {}


def test_node_frontier_counts_unmapped_known_exits(tmp_path):
    graph = WorldGraph(tmp_path)
    mem = RoomMemory(tmp_path)

    room_a = _room("Room A", {"north": "a corridor", "east": "a door"})
    hash_a, _ = mem.record(room_a)
    graph.add_room(hash_a, "Room A")

    room_b = _room("Room B", {"south": "back to room a"})
    hash_b, _ = mem.record(room_b)
    graph.add_room(hash_b, "Room B")

    graph.add_edge(hash_a, hash_b, "north", to_room_exits={"south"})

    frontier = node_frontier(graph, mem)
    assert frontier[hash_a] == 1  # east is known but unmapped
    assert frontier[hash_b] == 0  # south is walked (auto reverse edge)


def test_node_frontier_skips_node_with_no_room_memory_record(tmp_path):
    graph = WorldGraph(tmp_path)
    mem = RoomMemory(tmp_path)
    graph.add_room("orphan", "Orphan Room")
    assert node_frontier(graph, mem) == {"orphan": 0}
