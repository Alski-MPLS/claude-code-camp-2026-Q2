"""NetworkX DiGraph of rooms connected by exit edges."""

from __future__ import annotations

import json
import os
from pathlib import Path

import networkx as nx

OPPOSITE_DIRECTION = {
    "north": "south",
    "south": "north",
    "east": "west",
    "west": "east",
    "up": "down",
    "down": "up",
}


class WorldGraph:
    def __init__(self, base_dir: str | Path) -> None:
        self._base_dir = Path(base_dir)
        self._base_dir.mkdir(parents=True, exist_ok=True)
        self._path = self._base_dir / "world_graph.json"
        self._g: nx.DiGraph = nx.DiGraph()

    def add_room(self, room_hash: str, title: str) -> None:
        if room_hash not in self._g:
            self._g.add_node(room_hash, title=title)

    def add_edge(
        self,
        from_hash: str,
        to_hash: str,
        direction: str,
        *,
        to_room_exits: set[str] | None = None,
    ) -> None:
        self._g.add_edge(from_hash, to_hash, direction=direction)
        # Edges are only ever recorded in the direction actually walked, but
        # CircleMUD exits are almost always bidirectional. Without this, a
        # room only ever approached from one side is pathfinding-unreachable
        # even though it's really one step away — the graph shows the room
        # exists but navigate_to still reports "no known path" to it. Only
        # fill the gap: never touch that direction out of to_hash if it's
        # already claimed by a real observed edge — a room can only have one
        # exit per direction, so an existing one there (even to some other
        # room, e.g. a one-way passage) means the assumption doesn't apply.
        opposite = OPPOSITE_DIRECTION.get(direction)
        if not opposite:
            return
        existing_directions = {data.get("direction") for _, data in self._g[to_hash].items()}
        if opposite in existing_directions:
            return
        # If we already know the destination room's real recorded exits (it's
        # been visited and looked at), never fabricate a return path that
        # isn't actually among them — some passages are genuinely one-way,
        # and inferring a wrong reverse edge just recreates the same class
        # of "map doesn't match reality" bug in a new place. Only fall back
        # to the optimistic assumption when we have no ground truth yet.
        if to_room_exits is not None and opposite not in to_room_exits:
            return
        self._g.add_edge(to_hash, from_hash, direction=opposite)

    def get_neighbors(self, room_hash: str) -> dict[str, str]:
        if room_hash not in self._g:
            return {}
        return {
            data["direction"]: neighbor
            for neighbor, data in self._g[room_hash].items()
            if "direction" in data
        }

    def has_room(self, room_hash: str) -> bool:
        return room_hash in self._g

    def save(self) -> None:
        data = nx.node_link_data(self._g)
        tmp = self._path.with_suffix(".tmp")
        tmp.write_text(json.dumps(data, indent=2, ensure_ascii=False), encoding="utf-8")
        os.replace(tmp, self._path)

    def load(self) -> None:
        if not self._path.exists():
            return
        data = json.loads(self._path.read_text(encoding="utf-8"))
        self._g = nx.node_link_graph(data, directed=True, multigraph=False)

    @property
    def graph(self) -> nx.DiGraph:
        return self._g
