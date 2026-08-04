"""Stateless gold threshold check — advises depositing gold at the ATM."""

from __future__ import annotations

from typing import Any


class GoldMonitor:
    @staticmethod
    def check(gold: int, goal: dict[str, Any]) -> str | None:
        threshold = int(goal.get("gold_deposit_threshold", 200))
        if gold < threshold:
            return None
        half = gold // 2
        return (
            f"\n\n[Bank] You're carrying {gold} gold — at or above your "
            f"{threshold} deposit threshold. Once it's safe (not mid-combat, "
            f"not mid-travel), deposit half ({half}) at the ATM via "
            f"bank(action='deposit', amount={half}). Known ATM location: "
            "The Entrance Hall To The Guild Of Swordsmen — navigate_to it "
            "if not already there."
        )
