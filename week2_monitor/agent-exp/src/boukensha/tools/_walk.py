"""Shared step-by-step route walker used by navigate_to and explore.

Factored out so both tools get the same drift/blocked-exit detection: a move
can fail outright (room doesn't change) or succeed into the wrong room (a
stale/incorrect graph edge) — either way the caller must stop rather than
keep walking a plan computed against a room it's no longer actually in.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Callable

from boukensha.memory.pathfinder import Route
from boukensha.memory.room_memory import RoomMemory
from boukensha.memory.world_graph import WorldGraph


@dataclass
class WalkOutcome:
    status: str  # "arrived" | "blocked" | "drifted" | "lost"
    taken: list[str] = field(default_factory=list)
    final_hash: str | None = None
    message: str = ""


def walk_route(
    *,
    session: Any,
    graph: WorldGraph,
    mem: RoomMemory,
    current_room_hash: Callable[[], str | None],
    route: Route,
) -> WalkOutcome:
    def _real_exits(room_hash: str) -> set[str] | None:
        room = mem.get(room_hash)
        return set(room.get("exits") or {}) if room else None

    current_hash = route.nodes[0]
    taken: list[str] = []
    total = len(route.directions)
    for step, direction in enumerate(route.directions):
        session.drain()
        session.send_command(direction)
        session.read_until_prompt()
        new_hash = current_room_hash()
        if new_hash is None:
            return WalkOutcome(
                status="lost",
                taken=taken,
                final_hash=current_hash,
                message=(
                    f"Move interrupted after {len(taken)}/{total} moves "
                    f"({' → '.join(taken) or 'none'}): could not determine "
                    f"current room after moving {direction}."
                ),
            )
        if new_hash == current_hash:
            return WalkOutcome(
                status="blocked",
                taken=taken,
                final_hash=current_hash,
                message=(
                    f"Move interrupted after {len(taken)}/{total} moves "
                    f"({' → '.join(taken) or 'none'}): moving {direction} "
                    f"didn't leave the current room (blocked exit?). "
                    f"Check what's blocking it and retry."
                ),
            )
        expected_hash = route.nodes[step + 1]
        if new_hash != expected_hash:
            # The room changed, but not to the room the graph expected for
            # this step — record the edge we actually just observed (ground
            # truth) so the graph self-heals for next time.
            graph.add_edge(current_hash, new_hash, direction, to_room_exits=_real_exits(new_hash))
            return WalkOutcome(
                status="drifted",
                taken=taken,
                final_hash=new_hash,
                message=(
                    f"Move interrupted after {len(taken)}/{total} moves "
                    f"({' → '.join(taken) or 'none'}): moving {direction} led "
                    f"to an unexpected room — the map doesn't match reality "
                    f"here. Corrected that edge; replan from where you "
                    f"actually are."
                ),
            )
        graph.add_edge(current_hash, new_hash, direction, to_room_exits=_real_exits(new_hash))
        current_hash = new_hash
        taken.append(direction)
    return WalkOutcome(status="arrived", taken=taken, final_hash=current_hash)
