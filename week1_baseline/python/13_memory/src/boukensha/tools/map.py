"""Persistent room-graph for MUD navigation memory.

Intercepts look/move responses and builds a directed graph of visited rooms.
The graph lives outside the LLM context and is queried via three tools:
  map_here()         — current room + explored/unexplored exits
  map_path_to(dest)  — shortest-path direction sequence to a named room
  map_summary()      — compact dump of the known world

Graph is persisted as JSON at ~/.boukensha/maps/<character>.json and survives
process restarts. Uses networkx.DiGraph for BFS/shortest-path.
"""

from __future__ import annotations

import hashlib
import json
import re
from pathlib import Path
from typing import TYPE_CHECKING, Any

import networkx as nx

if TYPE_CHECKING:
    from boukensha.registry import Registry

_DIRECTIONS = {"north", "east", "south", "west", "up", "down"}
_EXITS_RE = re.compile(r"obvious exits\s*[:\-]\s*(.+)", re.IGNORECASE)
_ANSI_RE = re.compile(r"\x1b\[[0-9;]*[a-zA-Z]")


def _strip_ansi(text: str) -> str:
    return _ANSI_RE.sub("", text)


def _parse_room(response: str) -> tuple[str, str, list[str]] | None:
    """Extract (title, description, exits) from a look response.

    Returns None if the response doesn't look like a room description.
    """
    lines = [l.rstrip() for l in _strip_ansi(response).splitlines()]
    # Drop blank leading lines
    while lines and not lines[0].strip():
        lines.pop(0)
    if not lines:
        return None

    # Find the exits line — it anchors the parse
    exits_idx = None
    for i, line in enumerate(lines):
        if _EXITS_RE.search(line):
            exits_idx = i
            break
    if exits_idx is None:
        return None

    title = lines[0].strip()
    description = " ".join(l.strip() for l in lines[1:exits_idx] if l.strip())
    exits_line = lines[exits_idx]
    exits_match = _EXITS_RE.search(exits_line)
    exits: list[str] = []
    if exits_match:
        raw = exits_match.group(1)
        # "north, east, west." or "north east west"
        exits = [
            w.strip(" .,;").lower()
            for w in re.split(r"[,\s]+", raw)
            if w.strip(" .,;").lower() in _DIRECTIONS
        ]

    return title, description, exits


def _node_key(title: str, description: str, exits: list[str]) -> str:
    """Stable composite key: first 12 hex chars of SHA-256."""
    payload = title + "\x00" + description + "\x00" + ",".join(sorted(exits))
    return hashlib.sha256(payload.encode()).hexdigest()[:12]


class RoomGraph:
    def __init__(self, save_path: Path) -> None:
        self._save_path = save_path
        self._graph: nx.DiGraph = nx.DiGraph()
        self._current: str | None = None  # node key of current room
        self._load()

    # ------------------------------------------------------------------
    # Public observation API (called by mud.py tool wrappers)
    # ------------------------------------------------------------------

    def observe(self, response: str, last_cmd: str | None) -> None:
        """Parse a socket response and update the graph."""
        parsed = _parse_room(response)
        if parsed is None:
            return
        title, description, exits = parsed
        key = _node_key(title, description, exits)

        if not self._graph.has_node(key):
            self._graph.add_node(key, title=title, description=description, exits=exits)
        else:
            # Refresh exits in case the room state changed (doors, etc.)
            self._graph.nodes[key]["exits"] = exits

        prev = self._current
        self._current = key

        # Record the traversal edge if we just moved here via a direction
        if (
            prev is not None
            and prev != key
            and last_cmd is not None
            and last_cmd.lower() in _DIRECTIONS
        ):
            self._graph.add_edge(prev, key, direction=last_cmd.lower())

        self._save()

    # ------------------------------------------------------------------
    # Tool implementations
    # ------------------------------------------------------------------

    def map_here(self) -> str:
        if self._current is None or not self._graph.has_node(self._current):
            return "No location recorded yet — try 'look' first."
        data = self._graph.nodes[self._current]
        title = data.get("title", self._current)
        all_exits = data.get("exits", [])
        # Which exits have a recorded onward edge?
        mapped = {
            d["direction"]
            for _, _, d in self._graph.out_edges(self._current, data=True)
        }
        lines = [f"You are in: {title}"]
        if all_exits:
            exit_parts = []
            for e in all_exits:
                tag = " [mapped]" if e in mapped else " [unexplored]"
                exit_parts.append(e + tag)
            lines.append("Exits: " + ", ".join(exit_parts))
        else:
            lines.append("No obvious exits.")
        lines.append(f"Known rooms: {self._graph.number_of_nodes()}")
        return "\n".join(lines)

    def map_path_to(self, destination: str) -> str:
        if self._current is None:
            return "Current location unknown — try 'look' first."
        dest_lower = destination.lower()
        # Find all nodes whose title matches (case-insensitive substring)
        candidates = [
            n for n, d in self._graph.nodes(data=True)
            if dest_lower in d.get("title", "").lower()
        ]
        if not candidates:
            return f"No room matching '{destination}' in the map."
        # Try each candidate, take the shortest path
        best_directions: list[str] | None = None
        best_title = ""
        for target in candidates:
            if target == self._current:
                return f"You are already in '{self._graph.nodes[target]['title']}'."
            try:
                path = nx.shortest_path(self._graph, self._current, target)
            except nx.NetworkXNoPath:
                continue
            directions = []
            for a, b in zip(path, path[1:]):
                edge_data = self._graph.edges[a, b]
                directions.append(edge_data.get("direction", "?"))
            if best_directions is None or len(directions) < len(best_directions):
                best_directions = directions
                best_title = self._graph.nodes[target].get("title", target)
        if best_directions is None:
            return f"No navigable path to '{destination}' from current location."
        return f"Path to '{best_title}': {' → '.join(best_directions)}"

    def map_summary(self) -> str:
        n_rooms = self._graph.number_of_nodes()
        n_edges = self._graph.number_of_edges()
        if n_rooms == 0:
            return "Map is empty — explore some rooms first."
        lines = [f"Known map: {n_rooms} room(s), {n_edges} connection(s)"]
        for node, data in self._graph.nodes(data=True):
            marker = " ← you are here" if node == self._current else ""
            lines.append(f"  • {data.get('title', node)}{marker}")
        return "\n".join(lines)

    # ------------------------------------------------------------------
    # Persistence
    # ------------------------------------------------------------------

    def _save(self) -> None:
        self._save_path.parent.mkdir(parents=True, exist_ok=True)
        data: dict[str, Any] = {
            "current": self._current,
            "nodes": [
                {"id": n, **d}
                for n, d in self._graph.nodes(data=True)
            ],
            "edges": [
                {"source": u, "target": v, **d}
                for u, v, d in self._graph.edges(data=True)
            ],
        }
        self._save_path.write_text(json.dumps(data, indent=2, ensure_ascii=False))

    def _load(self) -> None:
        if not self._save_path.exists():
            return
        try:
            data = json.loads(self._save_path.read_text())
        except (json.JSONDecodeError, OSError):
            return
        self._current = data.get("current")
        for node in data.get("nodes", []):
            nid = node.pop("id")
            self._graph.add_node(nid, **node)
        for edge in data.get("edges", []):
            src = edge.pop("source")
            tgt = edge.pop("target")
            self._graph.add_edge(src, tgt, **edge)


class Map:
    """Registers the three map query tools against a registry."""

    @classmethod
    def register(cls, registry: "Registry", *, save_path: Path) -> RoomGraph:
        graph = RoomGraph(save_path)

        registry.tool(
            "map_here",
            description=(
                "Show your current room and which exits are already mapped vs. unexplored. "
                "Call this when re-orienting after context compaction or a long session."
            ),
            parameters={},
            block=lambda **_: graph.map_here(),
        )

        registry.tool(
            "map_path_to",
            description=(
                "Return the shortest known direction sequence to reach a named room. "
                "Use when you need to return somewhere you've visited before."
            ),
            parameters={
                "destination": {
                    "type": "string",
                    "description": "Room name or partial name to navigate to",
                },
            },
            block=lambda destination, **_: graph.map_path_to(destination),
        )

        registry.tool(
            "map_summary",
            description=(
                "Dump a compact list of all known rooms and connections. "
                "Use for re-orientation when the map has grown large."
            ),
            parameters={},
            block=lambda **_: graph.map_summary(),
        )

        return graph
