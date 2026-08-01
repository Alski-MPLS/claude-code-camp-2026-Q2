"""navigate_to tool: Python pathfinding + move loop, no LLM per step."""

from __future__ import annotations

from pathlib import Path
from typing import TYPE_CHECKING, Any

from boukensha.memory.parser import RoomParser
from boukensha.memory.room_memory import RoomMemory
from boukensha.memory.world_graph import WorldGraph
from boukensha.memory.pathfinder import Pathfinder, Route, partial_word_matches, text_matches, word_overlap_matches
from boukensha.memory.player_tracker import PlayerTracker
from boukensha.memory.room_aliases import RoomAliases
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
        aliases = RoomAliases(memory_dir)

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
            route: Route | None = None
            landmark_room: str | None = None
            alias_title: str | None = None
            alias_hash = aliases.get(destination)
            if alias_hash and graph.has_room(alias_hash):
                route = pf.route_to(start_hash, alias_hash)
                if route is None:
                    title = graph.graph.nodes[alias_hash].get("title", destination)
                    return (
                        f"'{destination}' is aliased to the known room '{title}', "
                        f"but no walkable path there is currently known from here — "
                        f"likely a one-way passage that was only ever walked in the "
                        f"other direction. Call explore() to find another route out "
                        f"rather than retrying navigate_to with the same destination."
                    )
                alias_title = graph.graph.nodes[alias_hash].get("title", destination)
            if route is None:
                route = pf.route_by_title(start_hash, destination)
            if route is None:
                haystacks = _landmark_haystacks()
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
                all_titles = sorted({t for t in titles.values() if t})
                if all_titles:
                    _MAX_TITLES = 60
                    shown = all_titles[:_MAX_TITLES]
                    suffix = f", plus {len(all_titles) - _MAX_TITLES} more" if len(all_titles) > _MAX_TITLES else ""
                    return (
                        f"No confident match for '{destination}' — it shares no "
                        f"recognizable vocabulary with any mapped room. All "
                        f"currently known room titles: {', '.join(shown)}{suffix}. "
                        f"If one of these is actually your destination, retry "
                        f"navigate_to with its exact title, then call "
                        f"navigate_alias_add(alias='{destination}', "
                        f"destination='<exact title>') so this shorthand resolves "
                        f"directly next time. If the destination truly isn't mapped "
                        f"yet, call explore()."
                    )
                return f"No known path to '{destination}'. Explore more of the area first."
            path = route.directions
            if landmark_room:
                landmark_title = graph.graph.nodes[landmark_room].get("title", "?")
                dest_desc = f"'{destination}' (found in '{landmark_title}')"
            elif alias_title:
                dest_desc = f"'{destination}' (aliased to '{alias_title}')"
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

        def _navigate_alias_add(alias: str, destination: str, **_: Any) -> str:
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
                haystacks = _landmark_haystacks()
                found = _route_by_landmark(pf, start_hash, destination, haystacks)
                if found is not None:
                    route, _landmark_room = found
            if route is None or not route.nodes:
                # No routable match — but the room may still be mapped by
                # name (title or landmark text) and simply unreachable from
                # here right now (e.g. behind a one-way passage). Aliasing
                # only persists a room hash, not a walk, so a route isn't
                # actually required — reuse the same name-only matching
                # navigate_to's own known-but-unreachable branch relies on
                # to find it. Only act on an unambiguous single match; an
                # ambiguous one is worse to guess than to refuse.
                titles = {node: attrs.get("title") or "" for node, attrs in graph.graph.nodes(data=True)}
                known_matches = set(text_matches(destination, titles)) | set(text_matches(destination, haystacks))
                if len(known_matches) == 1:
                    room_hash = next(iter(known_matches))
                    aliases.add(alias, room_hash)
                    title = graph.graph.nodes[room_hash].get("title", destination)
                    return (
                        f"Remembered: '{alias}' now resolves directly to '{title}' "
                        f"(currently unreachable from here — no walkable path is "
                        f"known yet, but the alias is recorded for once one is)."
                    )
                return (
                    f"Could not resolve '{destination}' to a known room to alias — "
                    f"navigate_to it successfully first, then retry navigate_alias_add "
                    f"with its exact title."
                )
            room_hash = route.nodes[-1]
            aliases.add(alias, room_hash)
            title = graph.graph.nodes[room_hash].get("title", destination)
            return f"Remembered: '{alias}' now resolves directly to '{title}'."

        registry.tool(
            "navigate_to",
            description=(
                "Navigate to a known destination using the built room map. "
                "Uses the shortest known path — no LLM needed per move step. "
                "Checks a learned alias first (see navigate_alias_add); if "
                "no alias matches, matches destination against room titles; "
                "if nothing matches, falls back to searching every mapped "
                "room's description/items/npcs, so a landmark like 'the "
                "fountain' or 'the well' resolves to whichever room actually "
                "mentions it. Returns the path taken, or an error if the "
                "destination is unknown. Call navigate_alias_add to teach a "
                "shorthand term a direct alias so future calls resolve it "
                "instantly instead of re-matching."
            ),
            parameters={
                "destination": {
                    "type": "string",
                    "description": "Partial room title, or a landmark/item/npc mentioned inside a room (case-insensitive)",
                },
            },
            block=_navigate_to,
        )

        registry.tool(
            "navigate_alias_add",
            description=(
                "Remember that a shorthand term (e.g. 'bakery', 'your guild', "
                "'the newbie zone') refers to a specific already-known room, so "
                "future navigate_to calls with that term resolve directly instead "
                "of failing or matching ambiguously. Call this once you've "
                "confirmed the exact room — e.g. after navigate_to succeeded "
                "using the room's exact title, or while standing in the room the "
                "shorthand refers to."
            ),
            parameters={
                "alias": {
                    "type": "string",
                    "description": "The shorthand term to remember (case-insensitive), e.g. 'bakery'",
                },
                "destination": {
                    "type": "string",
                    "description": (
                        "The exact room title (or a landmark/item/npc mentioned inside "
                        "a room) identifying which room the alias refers to — same "
                        "matching rules as navigate_to's destination"
                    ),
                },
            },
            block=_navigate_alias_add,
        )
