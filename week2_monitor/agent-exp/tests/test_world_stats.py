from boukensha.memory.world_graph import WorldGraph
from boukensha.memory.room_memory import RoomMemory
from boukensha.memory.world_stats import frontier_stats, entity_stats


def _room(title, exits, npcs=None, items=None):
    return {"title": title, "description": "d", "exits": exits, "npcs": npcs or [], "items": items or []}


def test_frontier_stats_empty_graph(tmp_path):
    graph = WorldGraph(tmp_path)
    mem = RoomMemory(tmp_path)
    assert frontier_stats(graph, mem) == {"known_exits": 0, "walked": 0, "frontier": 0}


def test_frontier_stats_counts_walked_and_unwalked_exits(tmp_path):
    graph = WorldGraph(tmp_path)
    mem = RoomMemory(tmp_path)

    room_a = _room("Room A", {"north": "a corridor", "east": "a door"})
    hash_a, _ = mem.record(room_a)
    graph.add_room(hash_a, "Room A")

    room_b = _room("Room B", {"south": "back to room a"})
    hash_b, _ = mem.record(room_b)
    graph.add_room(hash_b, "Room B")

    graph.add_edge(hash_a, hash_b, "north", to_room_exits={"south"})

    stats = frontier_stats(graph, mem)
    # Room A: north walked, east unwalked. Room B: south walked (auto reverse edge).
    assert stats == {"known_exits": 3, "walked": 2, "frontier": 1}


def test_frontier_stats_skips_graph_node_with_no_room_memory_record(tmp_path):
    graph = WorldGraph(tmp_path)
    mem = RoomMemory(tmp_path)
    graph.add_room("orphan", "Orphan Room")  # node exists in graph, never recorded via RoomMemory
    assert frontier_stats(graph, mem) == {"known_exits": 0, "walked": 0, "frontier": 0}


def test_entity_stats_counts_unique_mobs_and_objects_across_rooms(tmp_path):
    graph = WorldGraph(tmp_path)
    mem = RoomMemory(tmp_path)

    room_a = _room("Room A", {}, npcs=["a peacekeeper"], items=["a small sign"])
    hash_a, _ = mem.record(room_a)
    graph.add_room(hash_a, "Room A")

    room_b = _room("Room B", {}, npcs=["a peacekeeper", "the baker"], items=[])
    hash_b, _ = mem.record(room_b)
    graph.add_room(hash_b, "Room B")

    stats = entity_stats(graph, mem)
    # "a peacekeeper" appears in both rooms but counts once.
    assert stats == {"mobs": 2, "objects": 1, "total": 3}


def test_entity_stats_empty_graph(tmp_path):
    graph = WorldGraph(tmp_path)
    mem = RoomMemory(tmp_path)
    assert entity_stats(graph, mem) == {"mobs": 0, "objects": 0, "total": 0}
