"""Parse raw CircleMUD 'look' output into a structured dict."""

from __future__ import annotations

import re

_DIRECTION_RE = re.compile(
    r"^Exits:\s*(.+)$", re.IGNORECASE | re.MULTILINE
)
_EXIT_NAMES = {"north", "south", "east", "west", "up", "down"}


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

            # Exits line
            m = _DIRECTION_RE.match(stripped)
            if m:
                in_desc = False
                for part in m.group(1).split(","):
                    d = part.strip().lower()
                    if d in _EXIT_NAMES:
                        exits[d] = None
                continue

            # Description ends at the first blank line after content
            if in_desc:
                desc_lines.append(stripped)
                continue

            # After exits: classify non-empty lines as NPC or item heuristic
            if stripped:
                low = stripped.lower()
                # Items end in "is here." or "lies here." — simplified heuristic
                if low.endswith("is here.") or low.endswith("lies here.") or low.endswith("here."):
                    # NPC or item: if line starts with capital A/An/The and ends with "is here."
                    # treat as NPC; if ends with "lies here." treat as item
                    if "lies here" in low:
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
