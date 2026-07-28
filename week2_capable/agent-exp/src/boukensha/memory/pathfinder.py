"""Dijkstra shortest path over a WorldGraph."""

from __future__ import annotations

from dataclasses import dataclass, field

import networkx as nx

from .world_graph import WorldGraph


@dataclass
class Route:
    """A planned route: the directions to walk, and the room hash the graph
    expects to land in after each one (``nodes[0]`` is the start room, so
    ``len(nodes) == len(directions) + 1``). Callers that execute the route
    step by step can compare the room actually reached against ``nodes[i+1]``
    to detect a graph that doesn't match reality, rather than only noticing
    a move that fails outright."""

    directions: list[str] = field(default_factory=list)
    nodes: list[str] = field(default_factory=list)


class Pathfinder:
    def __init__(self, graph: WorldGraph) -> None:
        self._graph = graph

    def _route(self, start_hash: str, end_hash: str) -> Route | None:
        g = self._graph.graph
        if start_hash not in g or end_hash not in g:
            return None
        if start_hash == end_hash:
            return Route(directions=[], nodes=[start_hash])
        try:
            node_path = nx.shortest_path(g, start_hash, end_hash)
        except nx.NetworkXNoPath:
            return None
        directions: list[str] = []
        for a, b in zip(node_path, node_path[1:]):
            edge_data = g.get_edge_data(a, b) or {}
            directions.append(edge_data.get("direction", "?"))
        return Route(directions=directions, nodes=node_path)

    def find_path(self, start_hash: str, end_hash: str) -> list[str] | None:
        route = self._route(start_hash, end_hash)
        return route.directions if route is not None else None

    def route_by_title(self, start_hash: str, title_fragment: str) -> Route | None:
        # Titles aren't unique (CircleMUD reuses e.g. "The Great Field Of
        # Midgaard" across several distinct rooms along a road), so a
        # fragment can match multiple nodes. Picking the first match in
        # graph-iteration order can send the player to an arbitrary, possibly
        # far-away room instead of the one actually reachable/intended.
        # Evaluate every match and take the shortest real route.
        g = self._graph.graph
        fragment_lower = title_fragment.lower()
        best: Route | None = None
        for node, attrs in g.nodes(data=True):
            if fragment_lower not in (attrs.get("title") or "").lower():
                continue
            route = self._route(start_hash, node)
            if route is None:
                continue
            if best is None or len(route.directions) < len(best.directions):
                best = route
        return best

    def find_path_by_title(
        self, start_hash: str, title_fragment: str
    ) -> list[str] | None:
        route = self.route_by_title(start_hash, title_fragment)
        return route.directions if route is not None else None
