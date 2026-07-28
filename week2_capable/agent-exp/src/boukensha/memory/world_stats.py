"""Aggregate read-only stats over the world graph and room memory, for the
dashboard's Overview tab. Pure functions — no I/O beyond what the passed-in
WorldGraph/RoomMemory objects already provide."""

from __future__ import annotations

from .room_memory import RoomMemory
from .world_graph import WorldGraph


def frontier_stats(graph: WorldGraph, mem: RoomMemory) -> dict[str, int]:
    """Known exits vs. exits actually walked (has a graph edge), across
    every room the agent has recorded. 'Frontier' is known-but-unwalked —
    it deliberately does not exclude exits marked blocked in
    BlockedExits, since those are still known frontier, just not
    currently pursuable."""
    known_exits = 0
    walked = 0
    for node in graph.graph.nodes:
        room = mem.get(node)
        if not room:
            continue
        room_known = set((room.get("exits") or {}).keys())
        mapped = set(graph.get_neighbors(node).keys())
        known_exits += len(room_known)
        walked += len(room_known & mapped)
    return {"known_exits": known_exits, "walked": walked, "frontier": known_exits - walked}


def entity_stats(graph: WorldGraph, mem: RoomMemory) -> dict[str, int]:
    """Unique mob and object names seen across every known room (the same
    name appearing in multiple rooms counts once)."""
    mobs: set[str] = set()
    objects: set[str] = set()
    for node in graph.graph.nodes:
        room = mem.get(node)
        if not room:
            continue
        mobs.update(room.get("npcs") or [])
        objects.update(room.get("items") or [])
    return {"mobs": len(mobs), "objects": len(objects), "total": len(mobs) + len(objects)}
