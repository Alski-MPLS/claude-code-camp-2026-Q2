"""navigate_to tool: Python pathfinding + move loop, no LLM per step."""

from __future__ import annotations

from pathlib import Path
from typing import TYPE_CHECKING, Any

from boukensha.memory.parser import RoomParser
from boukensha.memory.room_memory import RoomMemory
from boukensha.memory.world_graph import WorldGraph
from boukensha.memory.pathfinder import Pathfinder
from boukensha.memory.player_tracker import PlayerTracker

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
        world_graph: WorldGraph | None = None,
        character_name: str | None = None,
    ) -> None:
        memory_dir = Path(memory_dir)
        mem = RoomMemory(memory_dir)
        graph = world_graph if world_graph is not None else WorldGraph(memory_dir)
        if world_graph is None:
            graph.load()
        tracker = PlayerTracker(memory_dir)

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
            if character_name:
                tracker.update(character_name, h, room["title"])
            return h

        def _navigate_to(destination: str, **_: Any) -> str:
            if not session.is_open:
                return "error: not connected"
            start_hash = _current_room_hash()
            if start_hash is None:
                return "error: could not determine current room"
            if world_graph is None:
                graph.load()
            pf = Pathfinder(graph)
            route = pf.route_by_title(start_hash, destination)
            if route is None:
                return f"No known path to '{destination}'. Explore more of the area first."
            path = route.directions
            if not path:
                return f"Already at '{destination}'."
            current_hash = start_hash
            taken: list[str] = []
            for step, direction in enumerate(path):
                session.drain()
                session.send_command(direction)
                session.read_until_prompt()
                new_hash = _current_room_hash()
                if new_hash is None:
                    graph.save()
                    return (
                        f"Move interrupted after {len(taken)}/{len(path)} moves "
                        f"({' → '.join(taken) or 'none'}): could not determine "
                        f"current room after moving {direction}."
                    )
                if new_hash == current_hash:
                    # The move didn't change rooms (closed door, blocked exit,
                    # mob in the way, etc). Continuing down the precomputed
                    # path from here would walk it from the wrong room —
                    # abort so the caller can look around and retry instead
                    # of wandering off in an unintended direction.
                    graph.save()
                    return (
                        f"Move interrupted after {len(taken)}/{len(path)} moves "
                        f"({' → '.join(taken) or 'none'}): moving {direction} "
                        f"didn't leave the current room (blocked exit?). "
                        f"Check what's blocking it and retry navigate_to."
                    )
                expected_hash = route.nodes[step + 1]
                if new_hash != expected_hash:
                    # The room changed, but not to the room the graph expected
                    # for this step — some earlier edge in the graph doesn't
                    # match reality (recorded against the wrong room, a stale
                    # entry from before a parser fix, etc). Walking the rest
                    # of the precomputed path from here would compound the
                    # drift, so stop now. Record the edge we actually just
                    # observed — it's ground truth — so the graph self-heals
                    # for next time instead of repeating the same bad route.
                    graph.add_edge(current_hash, new_hash, direction)
                    graph.save()
                    return (
                        f"Move interrupted after {len(taken)}/{len(path)} moves "
                        f"({' → '.join(taken) or 'none'}): moving {direction} led "
                        f"to an unexpected room — the map doesn't match reality "
                        f"here. Corrected that edge; call navigate_to again to "
                        f"replan from where you actually are."
                    )
                graph.add_edge(current_hash, new_hash, direction)
                current_hash = new_hash
                taken.append(direction)
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
