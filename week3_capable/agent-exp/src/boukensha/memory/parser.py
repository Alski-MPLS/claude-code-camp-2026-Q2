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

        # Real room titles are short and don't end in sentence punctuation
        # ("Main Street", "The Dirt Path"). Zone banners ("This zone is above
        # the level of most zones. Here be dragons.") and command failures
        # ("Alas, you cannot go that way...") always do — skip past any such
        # leading lines (and blank ones) to find the actual title, if any.
        idx = 0
        while idx < len(lines) and (
            not lines[idx].strip()
            or lines[idx].strip().endswith((".", "!", "?"))
            or _STATUS_RE.match(lines[idx].strip())
        ):
            idx += 1
        title = lines[idx].strip() if idx < len(lines) else ""

        exits: dict[str, None] = {}
        npcs: list[str] = []
        items: list[str] = []
        desc_lines: list[str] = []
        in_desc = True

        for line in lines[idx + 1:]:
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
            if low.endswith(("is here.", "lies here.", "here.", ".", "!", "?")):
                if "lies here" in low or "is lying here" in low:
                    items.append(stripped)
                elif low.endswith("is here.") and re.match(r"^[A-Z]", stripped):
                    # CircleMUD's auto-generated mob line is always exactly
                    # "<name> is here." — trust it regardless of name length
                    # (a combat-safety consumer of npcs[] must not miss a
                    # real, longer-named mob just because it has more words).
                    npcs.append(stripped)
                elif re.match(r"^[A-Z]", stripped):
                    # Custom mob long-descriptions and item lines both just
                    # end in "...here." with no reliable marker, and a
                    # word-count split doesn't work: real mobs routinely get
                    # long flavor-text descriptions too (e.g. "A creepy
                    # little crawling thing is scuttling along the floor at
                    # your feet."). Default to npcs — the same reasoning as
                    # the "is here." branch above: a combat-safety consumer
                    # of npcs[] must not miss a real mob just because its
                    # description is long. Misclassifying a genuinely static
                    # item as an npc only costs a harmless rejected
                    # `consider`/`attack` from the live game; the reverse
                    # (a real mob filed under items) makes it permanently
                    # unattackable through these tools, since nothing else
                    # ever queries the live game to check.
                    npcs.append(stripped)

        description = " ".join(l for l in desc_lines if l)

        return {
            "title": title,
            "description": description,
            "exits": exits,
            "npcs": npcs,
            "items": items,
        }
