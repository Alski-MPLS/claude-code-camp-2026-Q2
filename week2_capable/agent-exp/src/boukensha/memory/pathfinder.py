"""Dijkstra shortest path over a WorldGraph."""

from __future__ import annotations

import networkx as nx

from .world_graph import WorldGraph


class Pathfinder:
    def __init__(self, graph: WorldGraph) -> None:
        self._graph = graph

    def find_path(self, start_hash: str, end_hash: str) -> list[str] | None:
        g = self._graph.graph
        if start_hash not in g or end_hash not in g:
            return None
        if start_hash == end_hash:
            return []
        try:
            node_path = nx.shortest_path(g, start_hash, end_hash)
        except nx.NetworkXNoPath:
            return None
        directions: list[str] = []
        for a, b in zip(node_path, node_path[1:]):
            edge_data = g.get_edge_data(a, b) or {}
            directions.append(edge_data.get("direction", "?"))
        return directions

    def find_path_by_title(
        self, start_hash: str, title_fragment: str
    ) -> list[str] | None:
        # Titles aren't unique (CircleMUD reuses e.g. "The Great Field Of
        # Midgaard" across several distinct rooms along a road), so a
        # fragment can match multiple nodes. Picking the first match in
        # graph-iteration order can send the player to an arbitrary, possibly
        # far-away room instead of the one actually reachable/intended.
        # Evaluate every match and take the shortest real path.
        g = self._graph.graph
        fragment_lower = title_fragment.lower()
        best_path: list[str] | None = None
        for node, attrs in g.nodes(data=True):
            if fragment_lower not in (attrs.get("title") or "").lower():
                continue
            path = self.find_path(start_hash, node)
            if path is None:
                continue
            if best_path is None or len(path) < len(best_path):
                best_path = path
        return best_path
