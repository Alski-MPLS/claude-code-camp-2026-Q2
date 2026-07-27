"""NetworkX DiGraph of rooms connected by exit edges."""

from __future__ import annotations

import json
import os
from pathlib import Path

import networkx as nx


class WorldGraph:
    def __init__(self, base_dir: str | Path) -> None:
        self._base_dir = Path(base_dir)
        self._base_dir.mkdir(parents=True, exist_ok=True)
        self._path = self._base_dir / "world_graph.json"
        self._g: nx.DiGraph = nx.DiGraph()

    def add_room(self, room_hash: str, title: str) -> None:
        if room_hash not in self._g:
            self._g.add_node(room_hash, title=title)

    def add_edge(self, from_hash: str, to_hash: str, direction: str) -> None:
        self._g.add_edge(from_hash, to_hash, direction=direction)

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
