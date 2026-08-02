"""explore tool: find the nearest unexplored exit and go investigate it —
no LLM call needed to decide *where* to explore next.

An exit counts as "unexplored" when a room's own ``look`` output listed it
(``[ Exits: n e s w ]``) but the world graph has no edge recorded for it yet
— i.e. the agent has seen the exit exists but never actually walked through
it. Exits already confirmed to need something the agent doesn't have (a
locked door, a key) are skipped via BlockedExits, rather than retried on
every call.
"""

from __future__ import annotations

from pathlib import Path
from typing import TYPE_CHECKING, Any

from boukensha.memory.parser import RoomParser
from boukensha.memory.room_memory import RoomMemory
from boukensha.memory.world_graph import WorldGraph, OPPOSITE_DIRECTION
from boukensha.memory.pathfinder import Pathfinder, Route
from boukensha.memory.player_tracker import PlayerTracker
from boukensha.memory.blocked_exits import BlockedExits
from boukensha.memory.darkness import DARK_ROOM_REASON, is_dark_room
from ._walk import walk_route

if TYPE_CHECKING:
    from boukensha.registry import Registry


class Exploration:
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
        blocked = BlockedExits(memory_dir)
        tracker = PlayerTracker(memory_dir)

        def _real_exits(room_hash: str) -> set[str] | None:
            room = mem.get(room_hash)
            return set(room.get("exits") or {}) if room else None

        def _current_room_hash() -> str | None:
            """Send 'look' and return the hash of the current room.

            Also keeps prev_hash_ref/last_direction_ref (shared with the raw
            move/process_room tools) in sync with wherever explore()
            actually leaves the character — see navigation.py's identical
            comment for why: without it, those tools would wire a bogus
            edge from a stale "last known room" the next time they're used.
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

        def _nearest_frontier(start_hash: str, max_hops: int | None = None) -> tuple[Route, str, str] | None:
            """The closest (room, direction) where a known exit has no
            corresponding edge in the graph yet and isn't marked blocked.

            Search is global across the whole known map by design — this is
            what makes explore() a cheap "map everything" tool without the
            LLM having to plan routes itself. The tradeoff: once the area
            right around the current position is fully mapped, "nearest"
            can jump to some leftover unexplored exit anywhere else already
            visited (e.g. back near a hub like a town square), which reads
            as backtracking when the actual intent was "push further out
            from here." ``max_hops`` lets a caller opt into a local-only
            search for that case, at the cost of possibly reporting nothing
            found even though the map has frontier elsewhere.
            """
            pf = Pathfinder(graph)
            best: tuple[Route, str, str] | None = None
            for node in list(graph.graph.nodes):
                room = mem.get(node)
                if not room:
                    continue
                known_exits = set((room.get("exits") or {}).keys())
                if not known_exits:
                    continue
                mapped = set(graph.get_neighbors(node).keys())
                unblocked = sorted(known_exits - mapped - blocked.get(node))
                if not unblocked:
                    continue
                route = pf.route_to(start_hash, node)
                if route is None:
                    continue
                if max_hops is not None and len(route.directions) > max_hops:
                    continue
                if best is None or len(route.directions) < len(best[0].directions):
                    best = (route, node, unblocked[0])
            return best

        def _explore(max_hops: int | None = None, **_: Any) -> str:
            if not session.is_open:
                return "error: not connected"
            if world_graph is None:
                graph.load()
            start_hash = _current_room_hash()
            if start_hash is None:
                return "error: could not determine current room"

            found = _nearest_frontier(start_hash, max_hops)
            if found is None:
                if max_hops is not None:
                    return (
                        f"No unexplored exit within {max_hops} hop(s) of here — "
                        "the immediate area is fully mapped. Call explore() again "
                        "without max_hops to search the whole known map (this may "
                        "route you somewhere far away, including back near "
                        "already-visited hubs), or navigate_to a specific known "
                        "room/landmark instead."
                    )
                return (
                    "No unexplored exits reachable — this area appears fully "
                    "mapped, or every remaining exit is already marked blocked."
                )
            route, frontier_hash, direction = found

            approach = ""
            if route.directions:
                outcome = walk_route(
                    session=session, graph=graph, mem=mem, current_room_hash=_current_room_hash, route=route
                )
                if outcome.status != "arrived":
                    graph.save()
                    return outcome.message + " Call explore again to replan."
                approach = f"Walked {len(route.directions)} move(s) to the frontier room. "

            before_hash = frontier_hash

            def _retreat_from_darkness() -> None:
                # Best-effort: step back out the way we came so the
                # character isn't left standing somewhere it can't see.
                opposite = OPPOSITE_DIRECTION.get(direction)
                if opposite:
                    session.drain()
                    session.send_command(opposite)
                    session.read_until_prompt()

            def _mark_dark_and_report() -> str:
                blocked.mark_blocked(before_hash, direction, reason=DARK_ROOM_REASON)
                graph.save()
                return (
                    f"{approach}Exit {direction} leads into darkness — marked "
                    f"it blocked until a light source is available. Call "
                    f"explore again to try the next unexplored exit."
                )

            # Peek before committing to the move at all, where the game
            # supports it — avoids ever walking blind into a dark room.
            session.drain()
            session.send_command(f"look {direction}")
            peek_raw = session.read_until_prompt()
            if is_dark_room(peek_raw):
                return _mark_dark_and_report()

            session.drain()
            session.send_command(direction)
            move_raw = session.read_until_prompt()
            if is_dark_room(move_raw):
                # The peek didn't catch it (e.g. through a closed door) —
                # we're actually standing in the dark now. Retreat rather
                # than leave the character somewhere it can't see to fight
                # or find its way out.
                _retreat_from_darkness()
                return _mark_dark_and_report()

            new_hash = _current_room_hash()

            if new_hash is not None and new_hash != before_hash:
                graph.add_edge(before_hash, new_hash, direction, to_room_exits=_real_exits(new_hash))
                graph.save()
                new_title = graph.graph.nodes[new_hash].get("title", "?")
                return f"{approach}Explored {direction}: discovered '{new_title}'."

            # Didn't move — could just be a closed (not locked) door. Try
            # opening it once and retry before giving up on this exit.
            session.drain()
            session.send_command(f"open door {direction}")
            session.read_until_prompt()
            session.drain()
            session.send_command(direction)
            retry_raw = session.read_until_prompt()
            if is_dark_room(retry_raw):
                _retreat_from_darkness()
                return _mark_dark_and_report()
            retried_hash = _current_room_hash()

            if retried_hash is not None and retried_hash != before_hash:
                graph.add_edge(before_hash, retried_hash, direction, to_room_exits=_real_exits(retried_hash))
                graph.save()
                new_title = graph.graph.nodes[retried_hash].get("title", "?")
                return f"{approach}Exit {direction} was closed; opened it and discovered '{new_title}'."

            blocked.mark_blocked(before_hash, direction)
            graph.save()
            return (
                f"{approach}Exit {direction} appears to need something else "
                f"(locked door, key, etc.) — marked it blocked and will skip "
                f"it in future exploration. Call explore again to try the "
                f"next unexplored exit."
            )

        registry.tool(
            "explore",
            description=(
                "Find the nearest room with a known-but-unwalked exit and go "
                "investigate it — no need to specify a destination. The search "
                "is GLOBAL across the whole known map, not just nearby: once the "
                "area right around you is fully mapped, the 'nearest' unwalked "
                "exit anywhere can be back near an already-visited hub (e.g. "
                "town), which will walk you all the way back there — that is "
                "expected behavior for 'map everything', not a bug, but it is "
                "almost never what you want when you're trying to push further "
                "out from your current spot (e.g. deeper into a dungeon/zone "
                "to find more mobs). For that, pass max_hops (e.g. 3-5) to "
                "restrict the search to nearby unexplored exits only — it will "
                "report nothing found rather than teleport you back to a hub. "
                "Skips exits already confirmed to be locked/blocked, and "
                "refuses to walk into a dark room (marks it blocked instead) "
                "rather than risk getting stuck somewhere it can't see. Call "
                "repeatedly to keep expanding the map outward."
            ),
            parameters={
                "max_hops": {
                    "type": "integer",
                    "description": (
                        "Only consider unwalked exits reachable within this many "
                        "moves of your current room. Omit for the default "
                        "whole-map search (can route you far away, including "
                        "back near already-mapped hubs)."
                    ),
                },
            },
            block=_explore,
        )
