"""navigate_to tool: Python pathfinding + move loop, no LLM per step."""

from __future__ import annotations

from pathlib import Path
from typing import TYPE_CHECKING, Any

from boukensha.memory.parser import RoomParser
from boukensha.memory.room_memory import RoomMemory
from boukensha.memory.world_graph import WorldGraph
from boukensha.memory.pathfinder import Pathfinder

if TYPE_CHECKING:
    from boukensha.registry import Registry


class Navigation:
    @classmethod
    def register(
        cls,
        registry: "Registry",
        *,
        session: Any,
        memory_dir: str | Path,
    ) -> None:
        memory_dir = Path(memory_dir)
        mem = RoomMemory(memory_dir)
        graph = WorldGraph(memory_dir)
        graph.load()

        def _current_room_hash() -> str | None:
            """Send 'look' and return the hash of the current room."""
            session.drain()
            session.send_command("look")
            raw = session.read_until_prompt()
            room = RoomParser.parse(raw)
            if not room["title"]:
                return None
            h, _ = mem.record(room)
            graph.add_room(h, room["title"])
            return h

        def _navigate_to(destination: str, **_: Any) -> str:
            if not session.is_open:
                return "error: not connected"
            start_hash = _current_room_hash()
            if start_hash is None:
                return "error: could not determine current room"
            graph.load()
            pf = Pathfinder(graph)
            path = pf.find_path_by_title(start_hash, destination)
            if path is None:
                return f"No known path to '{destination}'. Explore more of the area first."
            if not path:
                return f"Already at '{destination}'."
            for direction in path:
                session.drain()
                session.send_command(direction)
                session.read_until_prompt()
            graph.save()
            return f"Arrived at destination after {len(path)} moves: {' → '.join(path)}"

        registry.tool(
            "navigate_to",
            description=(
                "Navigate to a known destination using the built room map. "
                "Uses the shortest known path — no LLM needed per move step. "
                "Returns the path taken, or an error if the destination is unknown."
            ),
            parameters={
                "destination": {"type": "string", "description": "Partial room title to navigate to (case-insensitive)"},
            },
            block=_navigate_to,
        )
