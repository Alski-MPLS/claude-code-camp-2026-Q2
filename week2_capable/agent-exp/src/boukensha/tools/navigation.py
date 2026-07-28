"""navigate_to tool: Python pathfinding + move loop, no LLM per step."""

from __future__ import annotations

from pathlib import Path
from typing import TYPE_CHECKING, Any

from boukensha.memory.parser import RoomParser
from boukensha.memory.room_memory import RoomMemory
from boukensha.memory.world_graph import WorldGraph
from boukensha.memory.pathfinder import Pathfinder, Route
from boukensha.memory.player_tracker import PlayerTracker
from ._walk import walk_route

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

        def _route_by_landmark(pf: Pathfinder, start_hash: str, fragment: str) -> tuple[Route, str] | None:
            """Fall back to searching each known room's description/items/
            npcs for the fragment — a destination like "the fountain" or
            "the well" is usually a feature INSIDE a room, not a room
            title, and the LLM has no other reliable way to recall which
            room that was once the fact scrolls out of context."""
            fragment_lower = fragment.lower()
            best: tuple[Route, str] | None = None
            for node in list(graph.graph.nodes):
                room = mem.get(node)
                if not room:
                    continue
                haystack = " ".join(
                    [room.get("description", ""), *(room.get("items") or []), *(room.get("npcs") or [])]
                ).lower()
                if fragment_lower not in haystack:
                    continue
                route = pf.route_to(start_hash, node)
                if route is None:
                    continue
                if best is None or len(route.directions) < len(best[0].directions):
                    best = (route, node)
            return best

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
            landmark_room: str | None = None
            if route is None:
                found = _route_by_landmark(pf, start_hash, destination)
                if found is not None:
                    route, landmark_room = found
            if route is None:
                return f"No known path to '{destination}'. Explore more of the area first."
            path = route.directions
            if landmark_room:
                landmark_title = graph.graph.nodes[landmark_room].get("title", "?")
                dest_desc = f"'{destination}' (found in '{landmark_title}')"
            else:
                dest_desc = f"'{destination}'"
            if not path:
                return f"Already at {dest_desc}."
            outcome = walk_route(
                session=session, graph=graph, mem=mem, current_room_hash=_current_room_hash, route=route
            )
            graph.save()
            if outcome.status != "arrived":
                return outcome.message + " Call navigate_to again to replan."
            return f"Arrived at {dest_desc} after {len(path)} moves: {' → '.join(path)}"

        registry.tool(
            "navigate_to",
            description=(
                "Navigate to a known destination using the built room map. "
                "Uses the shortest known path — no LLM needed per move step. "
                "Matches destination against room titles first; if nothing "
                "matches, falls back to searching every mapped room's "
                "description/items/npcs, so a landmark like 'the fountain' "
                "or 'the well' resolves to whichever room actually mentions "
                "it. Returns the path taken, or an error if the destination "
                "is unknown."
            ),
            parameters={
                "destination": {
                    "type": "string",
                    "description": "Partial room title, or a landmark/item/npc mentioned inside a room (case-insensitive)",
                },
            },
            block=_navigate_to,
        )
