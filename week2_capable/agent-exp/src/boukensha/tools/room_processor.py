"""process_room tool: parse current room, diff vs memory, return only new info."""

from __future__ import annotations

from pathlib import Path
from typing import TYPE_CHECKING, Any

from boukensha.memory.parser import RoomParser
from boukensha.memory.room_memory import RoomMemory
from boukensha.memory.world_graph import WorldGraph

if TYPE_CHECKING:
    from boukensha.registry import Registry


class RoomProcessor:
    @classmethod
    def register(
        cls,
        registry: "Registry",
        *,
        session: Any,
        memory_dir: str | Path,
        prev_hash_ref: list[str | None] | None = None,
        world_graph: WorldGraph | None = None,
        last_direction_ref: list[str | None] | None = None,
    ) -> None:
        memory_dir = Path(memory_dir)
        mem = RoomMemory(memory_dir)
        graph = world_graph if world_graph is not None else WorldGraph(memory_dir)
        if world_graph is None:
            graph.load()
        _prev: list[str | None] = prev_hash_ref if prev_hash_ref is not None else [None]

        def _process_room(**_: Any) -> str:
            if not session.is_open:
                return "error: not connected"
            session.drain()
            session.send_command("look")
            raw = session.read_until_prompt()
            room = RoomParser.parse(raw)
            if not room["title"]:
                return raw  # fallback: return raw if parse failed

            h, diff = mem.record(room)
            graph.add_room(h, room["title"])

            # Link from previous room if the 'move' tool recorded which direction got us here.
            if _prev[0] and _prev[0] != h and last_direction_ref is not None and last_direction_ref[0]:
                graph.add_edge(_prev[0], h, last_direction_ref[0])
            if last_direction_ref is not None:
                last_direction_ref[0] = None

            _prev[0] = h
            graph.save()

            if not diff:
                return f"[known room: {room['title']}] Nothing new observed."

            parts = [f"Room: {room['title']}"]
            if diff.get("description"):
                parts.append(f"Description: {diff['description']}")
            if diff.get("exits"):
                exits_str = ", ".join(diff["exits"].keys())
                parts.append(f"Exits: {exits_str}")
            if diff.get("npcs"):
                parts.append(f"NPCs: {', '.join(diff['npcs'])}")
            if diff.get("items"):
                parts.append(f"Items: {', '.join(diff['items'])}")
            return "\n".join(parts)

        registry.tool(
            "process_room",
            description=(
                "Look at the current room and return ONLY new or changed information vs stored memory. "
                "Returns an empty observation string if nothing has changed since last visit. "
                "Use this instead of raw 'look' to minimize token usage."
            ),
            parameters={},
            block=_process_room,
        )
