"""Parses raw CircleMUD 'equipment' and 'identify' output into structured data."""

from __future__ import annotations

import re

# ── Canonical wear-slot vocabulary ───────────────────────────────────────────
#
# Single source of truth shared by BOTH parsers. The two commands name the same
# physical slot differently:
#
#   * 'equipment' prints CircleMUD's wear_where[] labels inside <...>, e.g.
#     "<worn around neck>", "<worn about body>", "<wielded>", "<held>".
#     (See MobEquipSlot in circlemud_world_parser/constants.py: LIGHT, RING_R/L,
#     NECK_1/2, BODY, HEAD, LEGS, FEET, HANDS, ARMS, SHIELD, ABOUT_BODY, WAIST,
#     WRIST_R/L, WIELD, HOLD.)
#   * 'identify' prints the ObjectWear bit names via sprintbit, e.g.
#     "TAKE FINGER", "TAKE NECK", "TAKE ABOUT", "WIELD", "HOLD".
#     (See ObjectWear in constants.py: WEAR_TAKE/FINGER/NECK/BODY/HEAD/LEGS/
#     FEET/HANDS/ARMS/SHIELD/ABOUT/WAIST/WRIST/WIELD/HOLD.)
#
# Canonical keys follow the short ObjectWear bit names (finger, neck, body,
# head, legs, feet, hands, arms, shield, about, waist, wrist, wield, hold) plus
# 'light' for the light slot, which has no wear bit but does have a
# MobEquipSlot.LIGHT ("used as light") equipment label.
#
# 'about' is deliberately distinct from 'body': WEAR_ABOUT (a cloak) and
# WEAR_BODY (body armor) are separate slots and must never collide.
_CANONICAL_SLOTS: dict[str, str] = {
    # --- 'equipment' wear_where[] labels -------------------------------------
    "used as light": "light",
    "worn on finger": "finger",
    "worn around neck": "neck",
    "worn on body": "body",
    "worn on head": "head",
    "worn on legs": "legs",
    "worn on feet": "feet",
    "worn on hands": "hands",
    "worn on arms": "arms",
    "worn as shield": "shield",
    "worn about body": "about",
    "worn around waist": "waist",
    "worn around wrist": "wrist",
    "wielded": "wield",
    "held": "hold",
    # --- 'identify' ObjectWear bit names (sprintbit output) ------------------
    "light": "light",
    "finger": "finger",
    "neck": "neck",
    "body": "body",
    "head": "head",
    "legs": "legs",
    "feet": "feet",
    "hands": "hands",
    "arms": "arms",
    "shield": "shield",
    "about": "about",
    "waist": "waist",
    "wrist": "wrist",
    "wield": "wield",
    "hold": "hold",
    # --- common phrasings / partial forms ------------------------------------
    "about body": "about",
    "around neck": "neck",
    "around waist": "waist",
    "around wrist": "wrist",
    "on finger": "finger",
    "on body": "body",
    "on head": "head",
    "on legs": "legs",
    "on feet": "feet",
    "on hands": "hands",
    "on arms": "arms",
    "as shield": "shield",
    "as light": "light",
    "hands (2)": "hands",
    "finger (2)": "finger",
}

_SLOT_PREFIXES = ("worn on ", "worn around ", "worn as ", "used as ", "worn ")


def canonical_slot(label: str) -> str:
    """Map any recognized wear-location name variant to one canonical slot key."""
    key = " ".join(label.strip().lower().split())
    if key in _CANONICAL_SLOTS:
        return _CANONICAL_SLOTS[key]
    for prefix in _SLOT_PREFIXES:
        if key.startswith(prefix):
            rest = key[len(prefix):].strip()
            return _CANONICAL_SLOTS.get(rest, rest)
    return key


_PAREN_SUFFIX_RE = re.compile(r"\s*\.*\s*\(.*$", re.DOTALL)


def _item_lookup_key(name: str) -> str:
    """Strip CircleMUD's magic-item flag suffixes so names match identify's name.

    The 'equipment'/'inventory' listings append flags to an item's short
    description — "a gold ring ..(Yellow Aura)" under detect magic, plus
    "(invisible)", "(Glowing)", "(Humming)" — while ItemStatsStore is keyed by
    the clean ``Object '<short desc>'`` name printed by identify. Drop
    everything from the first '(' onward (and any '..' right before it).
    """
    return _PAREN_SUFFIX_RE.sub("", name).strip()


# ── 'equipment' output ───────────────────────────────────────────────────────

_EQUIP_LINE_RE = re.compile(r"<([^>]+)>\s*(.+)")
_EQUIP_HEADER_RE = re.compile(r"You are using:", re.IGNORECASE)


def parse_equipment(text: str) -> dict[str, str] | None:
    """Parse 'equipment' command output into {canonical_slot: item_description}.

    Returns ``None`` when the text isn't equipment output at all (unrelated
    command), and ``{}`` when it IS equipment output but nothing is worn
    ("You are using: nothing.") — callers rely on that distinction to clear a
    stale loadout snapshot.
    """
    slots: dict[str, str] = {}
    for line in text.splitlines():
        m = _EQUIP_LINE_RE.search(line)
        if not m:
            continue
        slot = canonical_slot(m.group(1))
        item = m.group(2).strip()
        if item:
            # Known limitation (last-one-wins): CircleMUD has genuinely dual
            # slots — RING_R/RING_L, NECK_1/NECK_2, WRIST_R/WRIST_L — that all
            # print the same label, so two worn rings collapse to a single
            # "finger" entry and the second overwrites the first.
            slots[slot] = item
    if slots:
        return slots
    return {} if _EQUIP_HEADER_RE.search(text) else None


# ── 'identify' output ────────────────────────────────────────────────────────

# Non-greedy up to the literal "', Item type:" so item names containing an
# apostrophe ("a mage's staff") aren't truncated at the first quote.
_IDENTIFY_OBJECT_RE = re.compile(r"Object '(.+?)', Item type:")
# sprintbit prints EVERY set wear bit space-separated, and WEAR_TAKE is set on
# virtually every wearable item — so grab the whole rest of the line and filter.
_IDENTIFY_WEAR_RE = re.compile(r"can be worn on:\s*(.*)", re.IGNORECASE)
_IDENTIFY_WEAPON_RE = re.compile(r"Item type:\s*WEAPON", re.IGNORECASE)
_IDENTIFY_AFFECT_RE = re.compile(r"Affects:\s*(\w+)\s*By\s*(-?\d+)", re.IGNORECASE)


def _identify_wear_slot(text: str) -> str | None:
    m = _IDENTIFY_WEAR_RE.search(text)
    if m:
        tokens = [t for t in m.group(1).split() if t.upper() != "TAKE"]
        if tokens:
            return canonical_slot(tokens[0])
    if _IDENTIFY_WEAPON_RE.search(text):
        return "wield"
    return None


def parse_identify(text: str) -> dict | None:
    """Parse 'identify' spell/scroll output into name, wear slot, and stat affects."""
    obj_m = _IDENTIFY_OBJECT_RE.search(text)
    if not obj_m:
        return None

    name = obj_m.group(1)
    affects = {
        m.group(1).lower(): int(m.group(2))
        for m in _IDENTIFY_AFFECT_RE.finditer(text)
    }

    return {"name": name, "wear_slot": _identify_wear_slot(text), "affects": affects}
