"""combat_loop tool: Python fight loop with HP monitoring."""

from __future__ import annotations

import re
import time
from pathlib import Path
from typing import TYPE_CHECKING, Any

from boukensha.goals.goal_manager import GoalManager
from boukensha.goals.combat_monitor import CombatMonitor
from boukensha.tools.mud import _match_npc, _no_living_target_message, _get_item

if TYPE_CHECKING:
    from boukensha.registry import Registry

_HP_RE = re.compile(r"(\d+)/(\d+)H", re.IGNORECASE)
_DEAD_PATTERNS = ["is dead!", "you receive", "experience points"]

# Generic diku/circle-family combat-round text. Used to detect that a fight
# is still actually happening — a target that flees or wanders off mid-fight
# often doesn't trigger any of the other end-of-combat checks (no "is dead",
# no HP-threshold flee, and servers don't always print an explicit
# "you stop fighting"/"no one is fighting" line), so the loop would otherwise
# spin all the way to max_rounds waiting on a fight that already ended.
_COMBAT_ACTIVITY_PATTERNS = [
    "you hit", "you miss", "you kick", "you punch", "you claw", "you bite",
    "you sting", "you clobber", "you slash", "you pierce",
    "hits you", "misses you", "bites you", "claws you", "stings you",
    "you parry", "parries", "dodge",
]
_QUIET_ROUND_LIMIT = 3

# CircleMUD/tbaMUD-family 'consider' responses for a wildly outmatched
# opponent. Wording varies per server, so this is a heuristic substring
# match, not an exhaustive list — extend it if a server uses other phrasing.
_DANGER_PATTERNS = [
    "do you feel lucky",
    "miracle to win",
    "miracle to survive",
    "certain death",
    "would be suicide",
    "no chance",
    "hopelessly outmatched",
    "far superior",
]


def _too_dangerous(consider_text: str) -> str | None:
    low = consider_text.lower()
    for phrase in _DANGER_PATTERNS:
        if phrase in low:
            return phrase
    return None


class Combat:
    @classmethod
    def register(
        cls,
        registry: "Registry",
        *,
        session: Any,
        goals_dir: str | Path,
        current_npcs_ref: list[list[str]] | None = None,
    ) -> None:
        goals_dir = Path(goals_dir)
        gm = GoalManager(goals_dir)
        _npcs: list[list[str]] = current_npcs_ref if current_npcs_ref is not None else [[]]

        def _parse_hp(text: str) -> int | None:
            m = _HP_RE.search(text)
            if m:
                return int(m.group(1))
            return None

        def _combat_loop(
            target: str,
            flee_hp: int = 5,
            force: bool = False,
            auto_loot: bool = True,
            **_: Any,
        ) -> str:
            if not session.is_open:
                return "error: not connected"

            gm.update(hp_flee_threshold=flee_hp)

            if not force and not _match_npc(target, _npcs[0]):
                return _no_living_target_message(target, _npcs[0])

            # Hard safety gate: always consider the target ourselves before
            # ever attacking, regardless of whether the caller already did.
            # An LLM told to "find easy monsters" can still misjudge or just
            # push through a dangerous consider result — this can't be
            # skipped or argued past unless force=True is passed explicitly.
            if not force:
                session.drain()
                session.send_command(f"consider {target}")
                consider_resp = session.read_until_prompt()
                danger = _too_dangerous(consider_resp)
                if danger:
                    gm.update(status="flee", notes=f"Refused fight vs '{target}': {danger!r}")
                    return (
                        f"Refused to attack '{target}' — consider warned: "
                        f"{consider_resp.strip()!r} (matched danger phrase: {danger!r}). "
                        "This target is far too strong. Flee this area or find a weaker "
                        "target instead. Pass force=true only if you deliberately want to "
                        "fight anyway."
                    )

            goal = gm.read()

            # Initiate attack
            session.drain()
            session.send_command(f"kill {target}")
            response = session.read_until_prompt()

            rounds = 0
            max_rounds = 30
            quiet_rounds = 0

            while rounds < max_rounds:
                rounds += 1
                response_lower = response.lower()

                # Check if target is dead
                if any(p in response_lower for p in _DEAD_PATTERNS):
                    result = f"Combat complete: {target} defeated after {rounds} round(s)."
                    if auto_loot:
                        loot_resp = _get_item(session, "all", "corpse", None)
                        result += f"\nLoot: {loot_resp}"
                    return result

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

                # No sign of an actual exchange this round (no hit/miss/dodge
                # text either way) — after a few of these in a row, the
                # target most likely fled or wandered off mid-fight. Bail
                # out early instead of spinning to max_rounds.
                if any(p in response_lower for p in _COMBAT_ACTIVITY_PATTERNS):
                    quiet_rounds = 0
                else:
                    quiet_rounds += 1
                    if quiet_rounds >= _QUIET_ROUND_LIMIT:
                        return (
                            f"No combat activity for {quiet_rounds} rounds after attacking "
                            f"'{target}' — it likely fled or wandered off. Re-check the room "
                            "with look/consider before trying again."
                        )

                time.sleep(0.5)
                response = session.read_until_prompt(timeout=3.0)

            return f"Combat loop reached {max_rounds} rounds — check status manually."

        registry.tool(
            "combat_loop",
            description=(
                "Fight a target in a Python loop, checking HP each round. "
                "Always considers the target first and refuses to attack if it looks far "
                "too dangerous (e.g. \"Do you feel lucky, punk?\") — pass force=true to "
                "attack anyway. Otherwise automatically flees if HP drops to or below flee_hp. "
                "On a kill, automatically loots the corpse (get all corpse) and includes the "
                "loot result in the response — pass auto_loot=false to skip this and inspect "
                "the corpse yourself first. "
                "Returns when target dies, you flee, or the round limit is reached. "
                "No LLM call per round — only use this for straightforward fights."
            ),
            parameters={
                "target": {"type": "string", "description": "Name of the mob to attack"},
                "flee_hp": {"type": "integer", "description": "Flee if HP drops to this value or below (default: 5)"},
                "force": {"type": "boolean", "description": "Skip the pre-fight danger check and attack even if consider looks dangerous (default: false)"},
                "auto_loot": {"type": "boolean", "description": "Automatically loot the corpse on a kill (default: true)"},
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
