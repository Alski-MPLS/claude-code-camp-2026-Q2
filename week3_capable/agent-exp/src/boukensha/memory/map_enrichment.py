"""Derived, read-only enrichment of the world graph for the dashboard Map
tab: edge confidence (walked vs. inferred), per-room frontier counts, alias
reverse-lookup, and zone clustering. All functions are pure and recompute
from WorldGraph/RoomMemory/RoomAliases on every call — nothing here is
persisted, mirroring world_stats.py's existing pattern."""

from __future__ import annotations

from .room_memory import RoomMemory
from .world_graph import WorldGraph


def classify_edges(graph: WorldGraph, mem: RoomMemory) -> dict[tuple[str, str], str]:
    """For every edge (u, v, direction) in the graph: "walked" if `direction`
    is among the source room's own recorded exits (the agent actually saw
    and walked it), else "inferred" (WorldGraph.add_edge auto-filled the
    opposite direction of some other walked edge)."""
    result: dict[tuple[str, str], str] = {}
    for u, v, data in graph.graph.edges(data=True):
        direction = data.get("direction")
        room = mem.get(u)
        known_exits = set((room or {}).get("exits") or {})
        result[(u, v)] = "walked" if direction in known_exits else "inferred"
    return result


def node_frontier(graph: WorldGraph, mem: RoomMemory) -> dict[str, int]:
    """Per room: count of exits the room is known to have (from RoomMemory)
    that have no corresponding graph edge yet — the same known-minus-mapped
    computation world_stats.frontier_stats already does in aggregate, keyed
    per room instead of summed."""
    result: dict[str, int] = {}
    for node in graph.graph.nodes:
        room = mem.get(node)
        if not room:
            result[node] = 0
            continue
        room_known = set((room.get("exits") or {}).keys())
        mapped = set(graph.get_neighbors(node).keys())
        result[node] = len(room_known - mapped)
    return result
