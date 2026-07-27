"""Parse raw CircleMUD 'look' output into a structured dict."""

from __future__ import annotations

import re

# CircleMUD renders exits as "[ Exits: n e s w ]" (bracketed, single-letter
# abbreviations, space-separated) — not the "Exits: north, east" format this
# parser originally targeted.
_EXITS_RE = re.compile(r"^\[\s*Exits:\s*([^\]]*)\]\s*$", re.IGNORECASE)
_DIR_ABBR = {"n": "north", "s": "south", "e": "east", "w": "west", "u": "up", "d": "down"}

# The vitals/prompt line CircleMUD appends after every command, e.g.
# "34H 100M 87V (news) (motd) >" — never part of the room itself.
_STATUS_RE = re.compile(r"^\d+H\s+\d+M\s+\d+V\b")


class RoomParser:
    @staticmethod
    def parse(raw: str) -> dict:
        """Parse raw MUD look output.

        Returns:
            {
                "title": str,
                "description": str,
                "exits": {direction: None, ...},
                "npcs": [str, ...],
                "items": [str, ...],
            }
        """
        lines = raw.splitlines()
        title = lines[0].strip() if lines else ""

        exits: dict[str, None] = {}
        npcs: list[str] = []
        items: list[str] = []
        desc_lines: list[str] = []
        in_desc = True

        for line in lines[1:]:
            stripped = line.strip()
            if not stripped or _STATUS_RE.match(stripped):
                continue

            # Exits line
            m = _EXITS_RE.match(stripped)
            if m:
                in_desc = False
                for token in m.group(1).split():
                    d = _DIR_ABBR.get(token.strip().lower())
                    if d:
                        exits[d] = None
                continue

            # Description is everything before the exits line
            if in_desc:
                desc_lines.append(stripped)
                continue

            # After exits: classify remaining lines as NPC or item (heuristic)
            low = stripped.lower()
            if low.endswith("is here.") or low.endswith("lies here.") or low.endswith("here.") or low.endswith("."):
                if "lies here" in low or "is lying here" in low:
                    items.append(stripped)
                elif re.match(r"^[A-Z]", stripped):
                    # Simple heuristic: short lines are likely NPCs/items
                    if len(stripped.split()) <= 4:
                        npcs.append(stripped)
                    else:
                        items.append(stripped)

        description = " ".join(l for l in desc_lines if l)

        return {
            "title": title,
            "description": description,
            "exits": exits,
            "npcs": npcs,
            "items": items,
        }
