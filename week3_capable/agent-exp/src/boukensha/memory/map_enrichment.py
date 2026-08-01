"""Derived, read-only enrichment of the world graph for the dashboard Map
tab: edge confidence (walked vs. inferred), per-room frontier counts, alias
reverse-lookup, and zone clustering. All functions are pure and recompute
from WorldGraph/RoomMemory/RoomAliases on every call — nothing here is
persisted, mirroring world_stats.py's existing pattern."""

from __future__ import annotations

from collections import Counter

from networkx.algorithms.community import greedy_modularity_communities

from .pathfinder import significant_words, words
from .room_aliases import RoomAliases
from .room_memory import RoomMemory
from .world_graph import WorldGraph

_ZONE_PALETTE = [
    "#3a5f8a", "#8a3a5f", "#5f8a3a", "#8a6a3a",
    "#3a8a7a", "#6a3a8a", "#8a3a3a", "#3a8a3a",
]


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


def node_aliases(aliases: RoomAliases) -> dict[str, list[str]]:
    """Invert RoomAliases (alias -> room_hash) into room_hash -> [aliases]."""
    result: dict[str, list[str]] = {}
    for alias, room_hash in aliases.read_all().items():
        result.setdefault(room_hash, []).append(alias)
    return result


def assign_zones(graph: WorldGraph) -> dict[str, dict]:
    """Cluster rooms into zones via greedy modularity community detection on
    the undirected graph, and label each zone with its most common
    significant title word. Recomputed fresh every call — no persisted zone
    state, so it self-corrects as the map grows."""
    undirected = graph.graph.to_undirected()
    result: dict[str, dict] = {}
    if undirected.number_of_nodes() == 0:
        return result
    communities = list(greedy_modularity_communities(undirected))
    for zone_id, members in enumerate(communities):
        word_counts: Counter[str] = Counter()
        for member in members:
            title = graph.graph.nodes[member].get("title", "")
            title_words = significant_words(words(title)) or words(title)
            # `words`/`significant_words` return sets, whose iteration order
            # is hash-randomized per process — feed Counter.update a sorted
            # list so tie-breaking in most_common() below is deterministic
            # across runs instead of flipping randomly on every server
            # restart.
            word_counts.update(sorted(title_words))
        zone_label = word_counts.most_common(1)[0][0].title() if word_counts else f"Zone {zone_id}"
        for member in members:
            result[member] = {
                "zone_id": zone_id,
                "zone_label": zone_label,
                "zone_color": _ZONE_PALETTE[zone_id % len(_ZONE_PALETTE)],
            }
    return result
