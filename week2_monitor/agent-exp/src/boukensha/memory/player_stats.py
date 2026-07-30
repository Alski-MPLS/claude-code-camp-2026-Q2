"""Parses the MUD's 'score' command output into structured player stats."""

from __future__ import annotations

import re

_SCORE_RE = re.compile(
    r"You have (\d+)\((\d+)\) hit,\s*(\d+)\((\d+)\) mana and\s*(\d+)\((\d+)\) movement points",
    re.IGNORECASE,
)


class PlayerStats:
    @staticmethod
    def parse_score(text: str) -> dict[str, int] | None:
        m = _SCORE_RE.search(text)
        if not m:
            return None
        hp, max_hp, mana, max_mana, move, max_move = (int(g) for g in m.groups())
        return {
            "hp": hp, "max_hp": max_hp,
            "mana": mana, "max_mana": max_mana,
            "move": move, "max_move": max_move,
        }
