"""Persistent room-graph for MUD navigation memory.

Intercepts look/move responses and builds a directed graph of visited rooms.
The graph lives outside the LLM context and is queried via four tools:
  map_here()                  — current room + explored/unexplored exits + loop warning
  map_path_to(dest)           — shortest-path direction sequence to a named room
  map_summary()               — compact dump of the known world
  map_find_capability(cap)    — nearest room where you can drink/eat/rest/heal

Graph is persisted as JSON at ~/.boukensha/maps/<character>.json and survives
process restarts. Uses networkx.DiGraph for BFS/shortest-path.
"""

from __future__ import annotations

import hashlib
import json
import re
from collections import deque
from pathlib import Path
from typing import TYPE_CHECKING, Any

import networkx as nx

if TYPE_CHECKING:
    from boukensha.registry import Registry

_DIRECTIONS = {"north", "east", "south", "west", "up", "down"}
_DIR_ABBREV = {"n": "north", "e": "east", "s": "south", "w": "west", "u": "up", "d": "down"}
# Matches both "Obvious exits: north, east" and the bracketed brief form
# emitted by this MUD, "[ Exits: s ]".
_EXITS_RE = re.compile(r"exits\s*[:\-]\s*([^\]\r\n]+)", re.IGNORECASE)
_ANSI_RE = re.compile(r"\x1b\[[0-9;]*[a-zA-Z]")

# Matches a verbose exits line: "North - Town Square" or "East - [CLOSED] A Dark Alley".
# Separator is one of: " - ", ": ", " to ", or bare whitespace between the
# direction word and the rest — written as alternation to avoid a character
# class that would accidentally consume leading letters of the room name.
_EXIT_LINE_RE = re.compile(
    r"^\s*(north|south|east|west|up|down)"
    r"\s*(?:-+|:|(?=\s))\s*"          # separator: dash(es), colon, or whitespace
    r"((?:\[[^\]]*\]\s*)*)"           # optional door flags: [CLOSED], [LOCKED], etc.
    r"(.*?)\s*$",
    re.IGNORECASE,
)
_DOOR_FLAGS_RE = re.compile(r"\[([^\]]+)\]", re.IGNORECASE)

# Affordance keyword sets — matched against title + description (case-insensitive)
_AFFORDANCE_KEYWORDS: dict[str, list[str]] = {
    "can_drink": [
        "fountain", "well", "spring", "pool", "brook", "stream",
        "water", "pitcher", "tap", "cistern",
    ],
    "can_eat": [
        "bakery", "tavern", "inn", "kitchen", "food", "meal",
        "feast", "bread", "vendor", "market",
    ],
    "can_rest": [
        "inn", "tavern", "safe", "peaceful", "quiet",
        "sanctuary", "temple", "chapel",
    ],
    "can_heal": [
        "temple", "chapel", "shrine", "healer", "cleric", "priest", "medic",
    ],
}


def _infer_affordances(title: str, description: str) -> list[str]:
    text = (title + " " + description).lower()
    return [
        tag
        for tag, keywords in _AFFORDANCE_KEYWORDS.items()
        if any(kw in text for kw in keywords)
    ]


def _strip_ansi(text: str) -> str:
    return _ANSI_RE.sub("", text)


def _parse_exits_detail(response: str) -> dict[str, dict[str, str]] | None:
    """Parse a verbose 'exits' command response into per-direction detail.

    Handles CircleMUD verbose format::

        North - Town Square
        East  - [CLOSED] The Iron Gate
        South - The Dark Alley

    Returns a dict mapping direction → {room_name, door_state, raw} for each
    matched line, or None if no direction lines were found at all.  When a room
    name cannot be parsed the entry still carries the raw text so the caller
    can persist it without losing data.

    door_state is one of: "open", "closed", "locked", or "" (unknown/open).
    """
    lines = _strip_ansi(response).splitlines()
    result: dict[str, dict[str, str]] = {}
    for line in lines:
        m = _EXIT_LINE_RE.match(line)
        if not m:
            continue
        direction = m.group(1).lower()
        flags_raw = m.group(2)
        room_raw = m.group(3).strip()
        flags = [f.lower() for f in _DOOR_FLAGS_RE.findall(flags_raw)]
        if "locked" in flags:
            door_state = "locked"
        elif "closed" in flags:
            door_state = "closed"
        elif flags:
            door_state = flags[0]
        else:
            door_state = "open"
        result[direction] = {
            "room_name": room_raw,
            "door_state": door_state,
            "raw": line.strip(),
        }
    return result if result else None


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
        # "north, east, west." or "north east west" or brief "n e w"
        for w in re.split(r"[,\s]+", raw):
            token = w.strip(" .,;").lower()
            if token in _DIRECTIONS:
                exits.append(token)
            elif token in _DIR_ABBREV:
                exits.append(_DIR_ABBREV[token])

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
        self._visit_history: deque[str] = deque(maxlen=6)

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

        affordances = _infer_affordances(title, description)
        if not self._graph.has_node(key):
            self._graph.add_node(
                key,
                title=title,
                description=description,
                exits=exits,
                affordances=affordances,
                affordances_confirmed=[],
                exits_detail={},
                exits_scanned=False,
            )
        else:
            self._graph.nodes[key]["exits"] = exits
            # Merge any newly inferred affordances (don't drop confirmed ones)
            existing = self._graph.nodes[key].get("affordances", [])
            merged = list(dict.fromkeys(existing + affordances))
            self._graph.nodes[key]["affordances"] = merged

        prev = self._current
        self._current = key
        self._visit_history.append(key)

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
        mapped = {
            d["direction"]
            for _, _, d in self._graph.out_edges(self._current, data=True)
        }
        affordances = data.get("affordances", []) + data.get("affordances_confirmed", [])
        exits_detail = data.get("exits_detail", {})
        exits_scanned = data.get("exits_scanned", False)
        lines = [f"You are in: {title}"]
        if affordances:
            lines.append("Capabilities: " + ", ".join(dict.fromkeys(affordances)))
        if all_exits:
            lines.append("Exits:")
            for e in all_exits:
                nav_tag = " [mapped]" if e in mapped else " [unexplored]"
                if e in exits_detail:
                    detail = exits_detail[e]
                    room_name = detail.get("room_name", "")
                    door_state = detail.get("door_state", "")
                    door_tag = f" [{door_state.upper()}]" if door_state and door_state != "open" else ""
                    name_part = f" → {room_name}" if room_name else ""
                    lines.append(f"  {e}{name_part}{door_tag}{nav_tag}")
                else:
                    lines.append(f"  {e}{nav_tag}")
        else:
            lines.append("No obvious exits.")
        if not exits_scanned:
            lines.append(
                "[exits not scanned] Run map_scan_exits to record room names "
                "and door states for each exit."
            )
        lines.append(f"Known rooms: {self._graph.number_of_nodes()}")
        # Loop detection: warn if current room appeared 3+ times in last 6 visits
        if self._visit_history.count(self._current) >= 3:
            lines.append(
                "[navigation warning] Possible loop detected — you have visited this room "
                f"{self._visit_history.count(self._current)} times recently."
            )
        return "\n".join(lines)

    def map_path_to(self, destination: str) -> str:
        if self._current is None:
            return "Current location unknown — try 'look' first."
        dest_lower = destination.lower()
        # Title match: exact first, then substring
        exact = [
            n for n, d in self._graph.nodes(data=True)
            if dest_lower == d.get("title", "").lower()
        ]
        substring = [
            n for n, d in self._graph.nodes(data=True)
            if dest_lower in d.get("title", "").lower()
        ]
        candidates = exact or substring
        # Capability fallback: if no title match, check if destination is a capability keyword
        if not candidates:
            # Check all affordance keyword lists for a match
            for tag, keywords in _AFFORDANCE_KEYWORDS.items():
                if dest_lower in keywords or dest_lower == tag:
                    return self.map_find_capability(tag)
            return f"No room matching '{destination}' in the map."
        best_directions: list[str] | None = None
        best_title = ""
        for target in candidates:
            if target == self._current:
                return f"You are already in '{self._graph.nodes[target]['title']}'."
            try:
                path = nx.shortest_path(self._graph, self._current, target)
            except nx.NetworkXNoPath:
                continue
            directions = [
                self._graph.edges[a, b].get("direction", "?")
                for a, b in zip(path, path[1:])
            ]
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

    def map_find_capability(self, capability: str) -> str:
        """Return shortest path to nearest room tagged with capability."""
        if self._current is None:
            return "Current location unknown — try 'look' first."
        candidates = self.rooms_with_affordance(capability)
        if not candidates:
            return f"No known rooms with '{capability}' capability in the map."
        best_directions: list[str] | None = None
        best_title = ""
        for target in candidates:
            if target == self._current:
                data = self._graph.nodes[target]
                return f"You are already in a room with {capability}: '{data.get('title', target)}'."
            try:
                path = nx.shortest_path(self._graph, self._current, target)
            except nx.NetworkXNoPath:
                continue
            directions = [
                self._graph.edges[a, b].get("direction", "?")
                for a, b in zip(path, path[1:])
            ]
            if best_directions is None or len(directions) < len(best_directions):
                best_directions = directions
                best_title = self._graph.nodes[target].get("title", target)
        if best_directions is None:
            return f"No navigable path to any {capability} room from current location."
        hops = len(best_directions)
        return (
            f"Nearest {capability} room: '{best_title}' — "
            f"{' → '.join(best_directions)} ({hops} hop{'s' if hops != 1 else ''})"
        )

    def rooms_with_affordance(self, tag: str) -> list[str]:
        """Return node keys for all rooms tagged with the given affordance."""
        return [
            n for n, d in self._graph.nodes(data=True)
            if tag in d.get("affordances", []) or tag in d.get("affordances_confirmed", [])
        ]

    def confirm_affordance(self, node_key: str, tag: str) -> None:
        """Mark an affordance as confirmed (successful action) on a node."""
        if not self._graph.has_node(node_key):
            return
        node = self._graph.nodes[node_key]
        # Ensure inferred list also has it
        inferred = node.get("affordances", [])
        if tag not in inferred:
            node["affordances"] = inferred + [tag]
        confirmed = node.get("affordances_confirmed", [])
        if tag not in confirmed:
            node["affordances_confirmed"] = confirmed + [tag]
        self._save()

    def update_exits_detail(self, node_key: str, response: str) -> str:
        """Parse an 'exits' command response and persist it on the node.

        Always marks the room as scanned (exits_scanned=True) so the
        map_here hint disappears, even when parsing finds no structured
        detail — this prevents pointless retries on rooms that genuinely
        return nothing useful.

        Returns a human-readable summary of what was stored.
        """
        if not self._graph.has_node(node_key):
            return "error: current room not in map — try 'look' first"
        detail = _parse_exits_detail(response)
        node = self._graph.nodes[node_key]
        if detail:
            # Merge: preserve any previously stored detail for directions not
            # present in this response (e.g. a partial exits listing).
            existing = node.get("exits_detail", {})
            existing.update(detail)
            node["exits_detail"] = existing
        node["exits_scanned"] = True
        self._save()

        if not detail:
            return (
                "Exits scanned — no structured detail found in response "
                "(room marked as scanned so this won't be retried).\n"
                f"Raw response stored:\n{response.strip()}"
            )
        lines = ["Exits detail recorded:"]
        for direction, d in sorted(detail.items()):
            door = f" [{d['door_state'].upper()}]" if d["door_state"] and d["door_state"] != "open" else ""
            name = d["room_name"] or "(unknown)"
            lines.append(f"  {direction} → {name}{door}")
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
    """Registers the four map query tools against a registry."""

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

        registry.tool(
            "map_find_capability",
            description=(
                "Find the nearest room where you can perform a specific action. "
                "Use capability='can_drink' when thirsty, 'can_eat' when hungry, "
                "'can_rest' to recover HP/mana, 'can_heal' for a healer. "
                "Returns the direction sequence to get there."
            ),
            parameters={
                "capability": {
                    "type": "string",
                    "description": "can_drink | can_eat | can_rest | can_heal",
                },
            },
            block=lambda capability, **_: graph.map_find_capability(capability),
        )

        return graph
