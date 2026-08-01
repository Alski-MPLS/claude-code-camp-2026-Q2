"""Stateless HP threshold check — triggers flee goal update when HP is low."""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from .goal_manager import GoalManager


class CombatMonitor:
    @staticmethod
    def check(hp: int, goal: dict[str, Any]) -> str | None:
        threshold = int(goal.get("hp_flee_threshold", 5))
        if hp <= threshold:
            return (
                f"HP is {hp} (at or below flee threshold {threshold}). "
                "You must FLEE immediately and find a safe place to recover."
            )
        return None

    @staticmethod
    def update_on_low_hp(hp: int, goal_manager: "GoalManager") -> str | None:
        goal = goal_manager.read()
        directive = CombatMonitor.check(hp, goal)
        if directive is not None:
            goal_manager.update(status="flee")
        return directive
