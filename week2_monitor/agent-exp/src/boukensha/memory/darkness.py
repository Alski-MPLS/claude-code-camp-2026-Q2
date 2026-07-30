"""Detect the MUD's dark-room response.

A room with no light source shows nothing but "It is pitch black..." — no
title, description, or exits — whether you're standing in it or peeking into
it from an adjacent room. See game_findings.md: entering one blind risks
getting stuck somewhere the agent can't see to fight or find its way out.
"""

from __future__ import annotations

import re

DARK_ROOM_REASON = "dark (needs a light source)"

_DARK_ROOM_RE = re.compile(r"pitch black", re.IGNORECASE)


def is_dark_room(raw: str) -> bool:
    return bool(_DARK_ROOM_RE.search(raw))
