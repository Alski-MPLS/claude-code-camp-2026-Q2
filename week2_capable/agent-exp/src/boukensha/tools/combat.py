"""combat_loop tool: Python fight loop with HP monitoring."""

from __future__ import annotations

import re
import time
from pathlib import Path
from typing import TYPE_CHECKING, Any

from boukensha.goals.goal_manager import GoalManager
from boukensha.goals.combat_monitor import CombatMonitor

if TYPE_CHECKING:
    from boukensha.registry import Registry

_HP_RE = re.compile(r"(\d+)/(\d+)H", re.IGNORECASE)
_DEAD_PATTERNS = [b"is dead!", b"You receive", b"experience points"]


class Combat:
    @classmethod
    def register(
        cls,
        registry: "Registry",
        *,
        session: Any,
        goals_dir: str | Path,
    ) -> None:
        goals_dir = Path(goals_dir)
        gm = GoalManager(goals_dir)

        def _parse_hp(text: str) -> int | None:
            m = _HP_RE.search(text)
            if m:
                return int(m.group(1))
            return None

        def _combat_loop(target: str, flee_hp: int = 5, **_: Any) -> str:
            if not session.is_open:
                return "error: not connected"

            gm.update(hp_flee_threshold=flee_hp)
            goal = gm.read()

            # Initiate attack
            session.drain()
            session.send_command(f"kill {target}")
            response = session.read_until_prompt()

            rounds = 0
            max_rounds = 30

            while rounds < max_rounds:
                rounds += 1
                response_lower = response.lower()

                # Check if target is dead
                if any(p.decode().lower() in response_lower for p in _DEAD_PATTERNS):
                    return f"Combat complete: {target} defeated after {rounds} round(s)."

                # Check HP from prompt if present
                hp = _parse_hp(response)
                if hp is not None:
                    directive = CombatMonitor.update_on_low_hp(hp, gm)
                    if directive:
                        session.drain()
                        session.send_command("flee")
                        flee_resp = session.read_until_prompt()
                        return f"Fled combat: {directive}\n{flee_resp}"

                # Check if we're no longer in combat
                if "you stop fighting" in response_lower or "no one is fighting" in response_lower:
                    return f"Combat ended after {rounds} round(s)."

                time.sleep(0.5)
                response = session.read_until_prompt(timeout=3.0)

            return f"Combat loop reached {max_rounds} rounds — check status manually."

        registry.tool(
            "combat_loop",
            description=(
                "Fight a target in a Python loop, checking HP each round. "
                "Automatically flees if HP drops to or below flee_hp. "
                "Returns when target dies, you flee, or the round limit is reached. "
                "No LLM call per round — only use this for straightforward fights."
            ),
            parameters={
                "target": {"type": "string", "description": "Name of the mob to attack"},
                "flee_hp": {"type": "integer", "description": "Flee if HP drops to this value or below (default: 5)"},
            },
            block=_combat_loop,
        )

        registry.tool(
            "goal_read",
            description="Read the current goal YAML and return it as a formatted string.",
            parameters={},
            block=lambda **_: _format_goal(gm.read()),
        )

        registry.tool(
            "goal_update",
            description=(
                "Update the agent's current goal. Fields: current_goal (str), "
                "priority (explore|fight|heal|flee|idle), status (active|paused|completed|flee), notes (str)."
            ),
            parameters={
                "current_goal": {"type": "string", "description": "New goal description (optional)"},
                "priority": {"type": "string", "description": "explore | fight | heal | flee | idle (optional)"},
                "status": {"type": "string", "description": "active | paused | completed | flee (optional)"},
                "notes": {"type": "string", "description": "Additional notes (optional)"},
            },
            block=lambda **kwargs: _do_goal_update(gm, kwargs),
        )


def _format_goal(goal: dict[str, Any]) -> str:
    lines = [
        f"current_goal: {goal.get('current_goal', '')}",
        f"priority: {goal.get('priority', '')}",
        f"status: {goal.get('status', '')}",
        f"hp_flee_threshold: {goal.get('hp_flee_threshold', 5)}",
        f"notes: {goal.get('notes', '')}",
    ]
    return "\n".join(lines)


def _do_goal_update(gm: GoalManager, kwargs: dict[str, Any]) -> str:
    filtered = {k: v for k, v in kwargs.items() if v is not None and k in (
        "current_goal", "priority", "status", "notes", "hp_flee_threshold"
    )}
    if filtered:
        gm.update(**filtered)
        return "Goal updated: " + ", ".join(f"{k}={v}" for k, v in filtered.items())
    return "No fields to update."
