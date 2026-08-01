"""Dijkstra shortest path over a WorldGraph."""

from __future__ import annotations

import re
from dataclasses import dataclass, field

import networkx as nx

from .world_graph import WorldGraph

_STOPWORDS = {"the", "a", "an", "of", "to", "at", "in", "on"}


def words(text: str) -> set[str]:
    """Lowercased, stopword-filtered tokens — shared by any matcher that
    needs to compare a fragment against room text without requiring an
    exact substring (room titles, descriptions, item/npc lists)."""
    return {w for w in re.findall(r"[a-z0-9]+", text.lower()) if w not in _STOPWORDS}


def significant_words(word_set: set[str]) -> set[str]:
    # Short words ("room", "hall", "gate") recur across many unrelated MUD
    # room titles/descriptions and make weak evidence of a match on their
    # own; only longer, more distinctive words count toward the overlap
    # fallback used when no substring match exists.
    return {w for w in word_set if len(w) >= 5}


def word_overlap_matches(fragment: str, texts: dict[str, str]) -> list[str]:
    """Candidate ids from ``texts`` (id -> title/description text) whose text
    contains every significant word of ``fragment``.

    Deliberately an all-or-nothing subset check, not a majority-overlap
    score: a partial match on a single shared word is exactly how a generic
    word that recurs across many unrelated rooms produces a false positive.
    Live bug this guards against: asking for "Guild of Swordsmen" (not yet
    mapped) matched "The Entrance To The Clerics' Guild" because both share
    the word "guild" and the old fallback only required 50% overlap —
    "guild" recurs across every guild in the game and is zero evidence of
    *which* one. Requiring every significant word to match ("guild" AND
    "swordsmen") means a fragment only matches a candidate that actually
    mentions all of it — still handling a paraphrase like "newbie area" vs.
    "...Newbie Zone" (its one significant word, "newbie", both is required
    and matches), but never a wrong guess based on a single generic word in
    common."""
    significant = significant_words(words(fragment))
    if not significant:
        return []
    return [
        node_id for node_id, text in texts.items()
        if significant <= words(text)
    ]


def text_matches(fragment: str, texts: dict[str, str]) -> list[str]:
    """Candidate ids whose text matches ``fragment`` by substring or full
    word-overlap — the same "is this actually the room being asked for"
    check route_by_title uses to pick a route, but without attaching any
    pathfinding. Lets a caller tell apart "this name doesn't match any known
    room" from "it matches a known room, but no route to it is known" —
    those need very different messages: the first is a naming/ambiguity
    problem, the second means the room is mapped but currently unreachable
    (e.g. behind a one-way passage that was only ever walked one way)."""
    fragment_lower = fragment.lower()
    substring = [node_id for node_id, text in texts.items() if fragment_lower in text.lower()]
    if substring:
        return substring
    return word_overlap_matches(fragment, texts)


def partial_word_matches(fragment: str, texts: dict[str, str]) -> list[str]:
    """Candidate ids that share at least one significant word with
    ``fragment`` but don't qualify as a real match under
    ``word_overlap_matches``'s stricter all-or-nothing rule.

    Never route anywhere based on this — it exists purely so a caller that
    failed to resolve a destination can surface "did you mean one of these
    already-known rooms?" to the LLM instead of silently guessing wrong or
    silently giving up. The LLM has context (the current room's own exit
    descriptions, the player's original instructions) that the matcher
    doesn't, so let it make the final call."""
    significant = significant_words(words(fragment))
    if not significant:
        return []
    exact = set(word_overlap_matches(fragment, texts))
    return [
        node_id for node_id, text in texts.items()
        if node_id not in exact and significant & words(text)
    ]


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

    def route_to(self, start_hash: str, end_hash: str) -> Route | None:
        """Like find_path, but also returns the expected node hash after
        each step — needed by callers (navigate_to, explore) that verify the
        room actually reached matches what the graph predicted."""
        return self._route(start_hash, end_hash)

    def route_by_title(self, start_hash: str, title_fragment: str) -> Route | None:
        # Titles aren't unique (CircleMUD reuses e.g. "The Great Field Of
        # Midgaard" across several distinct rooms along a road), so a
        # fragment can match multiple nodes. Picking the first match in
        # graph-iteration order can send the player to an arbitrary, possibly
        # far-away room instead of the one actually reachable/intended.
        # Evaluate every match and take the shortest real route. Substring
        # matches are tried first; only if none exist do we fall back to
        # word-overlap matching, so an exact/near-exact title (e.g. "Room B")
        # isn't shadowed by an unrelated room that merely shares one common
        # word (e.g. "Room A").
        g = self._graph.graph
        fragment_lower = title_fragment.lower()

        def _best_route(matching_nodes: list[str]) -> Route | None:
            best: Route | None = None
            for node in matching_nodes:
                route = self._route(start_hash, node)
                if route is None:
                    continue
                if best is None or len(route.directions) < len(best.directions):
                    best = route
            return best

        substring_matches = [
            node for node, attrs in g.nodes(data=True)
            if fragment_lower in (attrs.get("title") or "").lower()
        ]
        best = _best_route(substring_matches)
        if best is not None:
            return best
        # Fall back to a distinctive shared word (e.g. "newbie" in "newbie
        # area" vs. "...Newbie Zone") — see word_overlap_matches for why this
        # requires the word to be unique across all known titles, not just a
        # majority overlap.
        texts = {node: attrs.get("title") or "" for node, attrs in g.nodes(data=True)}
        return _best_route(word_overlap_matches(title_fragment, texts))

    def find_path_by_title(
        self, start_hash: str, title_fragment: str
    ) -> list[str] | None:
        route = self.route_by_title(start_hash, title_fragment)
        return route.directions if route is not None else None
