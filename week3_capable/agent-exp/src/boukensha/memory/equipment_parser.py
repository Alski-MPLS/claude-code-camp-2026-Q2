"""Parses raw CircleMUD 'equipment' and 'identify' output into structured data."""

from __future__ import annotations

import re

_EQUIP_LINE_RE = re.compile(r"<([^>]+)>\s*(.+)")
_WORN_PREFIXES = ("worn on ", "used as ", "worn as ")


def _normalize_slot(label: str) -> str:
    label = label.strip().lower()
    for prefix in _WORN_PREFIXES:
        if label.startswith(prefix):
            return label[len(prefix):].strip()
    return label


def parse_equipment(text: str) -> dict[str, str] | None:
    """Parse 'equipment' command output into {slot_key: item_description}."""
    slots: dict[str, str] = {}
    for line in text.splitlines():
        m = _EQUIP_LINE_RE.search(line)
        if not m:
            continue
        slot = _normalize_slot(m.group(1))
        item = m.group(2).strip()
        if item:
            slots[slot] = item
    return slots or None


_IDENTIFY_OBJECT_RE = re.compile(r"Object '([^']+)'")
_IDENTIFY_WEAR_RE = re.compile(r"can be worn on:\s*(\w+)", re.IGNORECASE)
_IDENTIFY_WEAPON_RE = re.compile(r"Item type:\s*WEAPON", re.IGNORECASE)
_IDENTIFY_AFFECT_RE = re.compile(r"Affects:\s*(\w+)\s*By\s*(-?\d+)", re.IGNORECASE)


def parse_identify(text: str) -> dict | None:
    """Parse 'identify' spell/scroll output into name, wear slot, and stat affects."""
    obj_m = _IDENTIFY_OBJECT_RE.search(text)
    if not obj_m:
        return None

    name = obj_m.group(1)

    wear_m = _IDENTIFY_WEAR_RE.search(text)
    if wear_m:
        wear_slot: str | None = wear_m.group(1).strip().lower()
    elif _IDENTIFY_WEAPON_RE.search(text):
        wear_slot = "wielded"
    else:
        wear_slot = None

    affects = {
        m.group(1).lower(): int(m.group(2))
        for m in _IDENTIFY_AFFECT_RE.finditer(text)
    }

    return {"name": name, "wear_slot": wear_slot, "affects": affects}
