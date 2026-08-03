"""Parses the MUD's 'score' command output into structured player stats."""

from __future__ import annotations

import re

_SCORE_RE = re.compile(
    r"You have (\d+)\((\d+)\) hit,\s*(\d+)\((\d+)\) mana and\s*(\d+)\((\d+)\) movement points",
    re.IGNORECASE,
)

# CircleMUD only prints these lines when the condition is true — there's no
# "You are not hungry." counterpart, so absence means fine, not unknown.
_HUNGRY_RE = re.compile(r"You are hungry\.", re.IGNORECASE)
_THIRSTY_RE = re.compile(r"You are thirsty\.", re.IGNORECASE)

_LEVEL_RE = re.compile(r"This ranks you as (.+?)\s*\(level (\d+)\)", re.IGNORECASE)
_EXP_GOLD_RE = re.compile(
    r"You have (\d+) exp,\s*(\d+) gold coins", re.IGNORECASE
)
_EXP_NEXT_RE = re.compile(r"You need (\d+) exp to reach your next level", re.IGNORECASE)


class PlayerStats:
    @staticmethod
    def parse_score(text: str) -> dict[str, int | str | bool] | None:
        m = _SCORE_RE.search(text)
        if not m:
            return None
        hp, max_hp, mana, max_mana, move, max_move = (int(g) for g in m.groups())
        stats: dict[str, int | str | bool] = {
            "hp": hp, "max_hp": max_hp,
            "mana": mana, "max_mana": max_mana,
            "move": move, "max_move": max_move,
            "hungry": bool(_HUNGRY_RE.search(text)),
            "thirsty": bool(_THIRSTY_RE.search(text)),
        }

        level_m = _LEVEL_RE.search(text)
        if level_m:
            stats["title"] = level_m.group(1).strip()
            stats["level"] = int(level_m.group(2))

        exp_gold_m = _EXP_GOLD_RE.search(text)
        if exp_gold_m:
            stats["exp"] = int(exp_gold_m.group(1))
            stats["gold"] = int(exp_gold_m.group(2))

        exp_next_m = _EXP_NEXT_RE.search(text)
        if exp_next_m:
            stats["exp_to_next"] = int(exp_next_m.group(1))

        return stats
