# Inventory dashboard tab — design

**Scope:** `week3_capable/agent-exp` (Boukensha)

## Problem

The dashboard already shows a Score tab (HP/mana/moves/exp/gold) and, since
`2026-08-03-equipment-tracking-design.md`, tracks worn/wielded equipment in
`players.json`. There is still no visibility into what the character is
*carrying* (unequipped inventory) — items sit in the backpack until the agent
decides to equip, drop, or use them, and the user watching the dashboard has
no way to see that state.

Worse: `check(kind="inventory")` is already a supported tool call
(`src/boukensha/tools/mud.py:557`, `_check_and_record`), but its raw text
result is only ever returned to the agent — it is never parsed or persisted,
unlike `score` and `equipment`, which both update `PlayerTracker`. This is a
straightforward gap, not a new capability: the same three-step pattern used
for equipment (parse → persist → surface) just hasn't been extended to
inventory yet.

## Non-goals

- No auto-refresh on every `get_item`/`drop_item`/`equip_item` call. Like
  equipment, the tracked snapshot only updates when the agent calls
  `check(kind="inventory")`. Matches existing convention; revisit only if
  staleness turns out to be a real problem in practice.
- No item-stats/upgrade-advisory logic for carried items — that already
  exists for equipped items via `ItemStatsStore` (equipment-tracking design)
  and is out of scope here. This tab is a passive viewer, not a decision aid.
- No new dashboard tab framework/pattern — reuse the existing fetch-on-tab-click
  convention (Score/Overview/Goals/Sessions tabs), not the SSE-only pattern
  used by the Live tab.

## Design

### 1. Parser — `src/boukensha/memory/equipment_parser.py`

Add `parse_inventory(text: str) -> list[dict] | None`, same style and file as
`parse_equipment`/`parse_identify`. Stock CircleMUD `inventory` output:

```
You are carrying:
( 2) a Black Pawn's Sword
some Black Pawn Armor
a shiny newbie dagger ..It has a soft glowing aura!
```

Each line optionally starts with a `(\s*N\s*)` count prefix; the rest of the
line is the item's short description (including any aura/flag suffix, kept
as-is — no need to strip it the way `_item_lookup_key` does for equipment
matching, since inventory items aren't looked up by name here).

Parse into `[{"name": str, "count": int}, ...]`, one entry per line, count
defaulting to 1 when there's no `(N)` prefix. Returns `None` when the text
isn't inventory output at all (e.g. an `error:` string), and `[]` when it IS
inventory output but nothing is carried ("You are not carrying anything.") —
same None-vs-empty contract as `parse_equipment`, so callers can distinguish
"unrelated text" from "legitimately empty."

### 2. Storage — `src/boukensha/memory/player_tracker.py`

Add `update_inventory(name: str, items: list[dict]) -> None`, mirroring
`update_equipment` exactly: merges into the per-player record in
`players.json` under an `inventory` key with an `inventory_updated_at`
timestamp.

### 3. Wiring — `src/boukensha/tools/mud.py`

In `_check_and_record` (line 557), add an `elif k == "inventory"` branch
alongside the existing `score`/`equipment` branches: run `parse_inventory` on
the raw result; if it returns non-`None` and a tracker is present, call
`tracker.update_inventory(name, items)`.

### 4. API — no changes needed

`/api/players` and `/api/overview` (`src/boukensha/dashboard/app.py:98-107`,
`109-133`) both already spread the full per-player dict read from
`players.json` (`{"name": name, **info}`). Once `update_inventory` starts
writing the `inventory` key, both endpoints expose it automatically.

### 5. Frontend

- `src/boukensha/dashboard/templates/index.html`: add an `Inventory` button
  to `<nav id="tabs">` and a `<section id="tab-inventory" class="tab-pane">`,
  sized like the existing Score section (`index.html:27-29`).
- `src/boukensha/dashboard/static/app.js`: add `loadInventory()` following
  `loadScore()`'s shape (~lines 127-172) — fetch `/api/players`, render two
  lists per player:
  - **Equipped** — reuse the existing `equipment` field (slot → item),
    same data the Score tab already has access to.
  - **Carrying** — the new `inventory` field (`name` + `count`, count only
    shown when > 1).
  Wire into the tab-click dispatcher (`app.js:16-20`) alongside the other
  fetch-on-click tabs.
- Piggyback on the existing SSE-triggered Score refresh (`app.js:74-83`,
  where `es.onmessage` calls `loadScore()` after a `check` tool result
  streams by): extend that same handler to also call `loadInventory()` when
  it's the visible tab, so an open Inventory tab updates live the next time
  the agent calls `check(kind="inventory")`, without requiring a manual
  re-click.
- `src/boukensha/dashboard/static/style.css`: reuse `.score-card`-style
  classes rather than introducing a new visual language; add only what's
  needed for a two-column (equipped / carrying) layout.

### 6. Tests

- `tests/test_equipment_parser.py` (existing file): add cases for
  `parse_inventory` — counted items, uncounted items, aura/flag suffixes,
  empty inventory, non-inventory text → `None`.
- Extend the `PlayerTracker` test file for `update_inventory`.
- Extend the `tools/mud.py` test suite: `check(kind="inventory")` persists
  parsed items to the tracker, mirroring the existing equipment-persistence
  test.

## Open questions / follow-ups

- None — this closely mirrors the already-implemented and validated
  equipment-tracking design, so the main risk (parser format mismatch)
  is low; confirm against a live `check(kind="inventory")` transcript
  during implementation the same way other parsers here were validated.
