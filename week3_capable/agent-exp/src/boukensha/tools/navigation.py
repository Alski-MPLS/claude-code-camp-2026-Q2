"""navigate_to tool: Python pathfinding + move loop, no LLM per step."""

from __future__ import annotations

from pathlib import Path
from typing import TYPE_CHECKING, Any

from boukensha.memory.parser import RoomParser
from boukensha.memory.room_memory import RoomMemory
from boukensha.memory.world_graph import WorldGraph
from boukensha.memory.pathfinder import Pathfinder, Route, partial_word_matches, text_matches, word_overlap_matches
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
        prev_hash_ref: list[str | None] | None = None,
        last_direction_ref: list[str | None] | None = None,
    ) -> None:
        memory_dir = Path(memory_dir)
        mem = RoomMemory(memory_dir)
        graph = world_graph if world_graph is not None else WorldGraph(memory_dir)
        if world_graph is None:
            graph.load()
        tracker = PlayerTracker(memory_dir)

        def _current_room_hash() -> str | None:
            """Send 'look' and return the hash of the current room.

            Also keeps prev_hash_ref/last_direction_ref (shared with the raw
            move/process_room tools) in sync with wherever navigate_to
            actually leaves the character. Without this, those tools' own
            "last known room" pointer goes stale the moment navigate_to
            moves the character, and a later raw `move` call would wire a
            bogus edge from the old room instead of the real current one.
            """
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
            if prev_hash_ref is not None:
                prev_hash_ref[0] = h
            if last_direction_ref is not None:
                last_direction_ref[0] = None
            return h

        def _landmark_haystacks() -> dict[str, str]:
            haystacks: dict[str, str] = {}
            for node in list(graph.graph.nodes):
                room = mem.get(node)
                if not room:
                    continue
                haystacks[node] = " ".join(
                    [room.get("description", ""), *(room.get("items") or []), *(room.get("npcs") or [])]
                ).lower()
            return haystacks

        def _route_by_landmark(
            pf: Pathfinder, start_hash: str, fragment: str, haystacks: dict[str, str]
        ) -> tuple[Route, str] | None:
            """Fall back to searching each known room's description/items/
            npcs for the fragment — a destination like "the fountain" or
            "the well" is usually a feature INSIDE a room, not a room
            title, and the LLM has no other reliable way to recall which
            room that was once the fact scrolls out of context.

            Substring match is tried first; only if nothing matches do we
            fall back to a distinctive shared word (see
            pathfinder.word_overlap_matches) — a paraphrase like "the blob"
            should still resolve to a room whose description says
            "gelatinous blob" even though the fragment isn't a literal
            substring, but a generic word shared across many rooms' text
            (e.g. "guard", "sign") must never be enough on its own."""
            fragment_lower = fragment.lower()

            def _best_route(matching_nodes: list[str]) -> tuple[Route, str] | None:
                best: tuple[Route, str] | None = None
                for node in matching_nodes:
                    route = pf.route_to(start_hash, node)
                    if route is None:
                        continue
                    if best is None or len(route.directions) < len(best[0].directions):
                        best = (route, node)
                return best

            substring_matches = [n for n, haystack in haystacks.items() if fragment_lower in haystack]
            best = _best_route(substring_matches)
            if best is not None:
                return best
            return _best_route(word_overlap_matches(fragment, haystacks))

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
            haystacks = _landmark_haystacks()
            if route is None:
                found = _route_by_landmark(pf, start_hash, destination, haystacks)
                if found is not None:
                    route, landmark_room = found
            if route is None:
                titles = {node: attrs.get("title") or "" for node, attrs in graph.graph.nodes(data=True)}
                known_matches = text_matches(destination, titles) or text_matches(destination, haystacks)
                if known_matches:
                    matched_titles = ", ".join(sorted({titles.get(n, n) for n in known_matches}))
                    return (
                        f"'{destination}' matches an already-mapped room ({matched_titles}), "
                        f"but no walkable path there is currently known from here — likely a "
                        f"one-way passage that was only ever walked in the other direction. "
                        f"Call explore() to find another route out rather than retrying "
                        f"navigate_to with the same destination."
                    )
                near_misses = partial_word_matches(destination, titles)
                if near_misses:
                    suggestions = ", ".join(sorted({titles[n] for n in near_misses}))
                    return (
                        f"No confident match for '{destination}'. Similarly named rooms "
                        f"already mapped (none matched closely enough to route to "
                        f"automatically): {suggestions}. If one of these is actually what "
                        f"you meant, navigate_to its exact title. If the real destination "
                        f"hasn't been visited yet but is named in the CURRENT room's own "
                        f"description/exits, just move that direction directly instead of "
                        f"calling navigate_to."
                    )
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
