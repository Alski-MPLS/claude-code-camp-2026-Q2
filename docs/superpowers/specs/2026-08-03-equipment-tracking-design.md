# Equipment tracking & upgrade advisories — design

**Scope:** `week3_capable/agent-exp` (Boukensha)

## Problem

CircleMUD equipment is managed via wear slots (head, body, legs, hands, shield,
finger, wielded, etc.), and items vary widely in quality — AC, hitroll,
damroll, and stat bonuses are set per-item by zone builders. Boukensha
already has:

- `equip_item` — wear/wield/hold/grab/remove, a raw pass-through
- `check(kind="equipment")` and `check(kind="score")` — raw pass-throughs
- `cast_spell` / `use_magic_item` — already capable of casting/reciting
  `identify`, the in-game command that reveals an item's hidden stats
  (AC, HITROLL, DAMROLL, stat modifiers)

but nothing parses any of this output or remembers it. This is a logged gap
(`game_findings.md`, "No equipment/light-source tracking yet"). The agent
currently has no way to know whether an item it just picked up is better than
what it's already wearing.

## Non-goals

- No new tool for casting `identify` — `cast_spell`/`use_magic_item` already
  cover it.
- No auto-equip. The agent decides; the system only surfaces information.
- No dashboard UI in this pass — data model only. A dashboard tab is a
  natural follow-up once this exists.

## Design

### 1. Parsers — `src/boukensha/memory/equipment_parser.py`

Two pure functions, same style as `PlayerStats.parse_score`:

- `parse_equipment(text: str) -> dict[str, str] | None`
  Parses `equipment` command output. Stock CircleMUD format:
  ```
  You are using:
  <used as light>       a small candle
  <worn on finger>      a gold ring
  <worn on body>        a suit of leather armor
  <wielded>              a long sword
  ```
  Regex over `<([^>]+)>\s+(.+)` per line. Normalize the bracketed label into
  a short slot key (`"worn on finger"` → `"finger"`, `"wielded"` →
  `"wielded"`, `"used as light"` → `"light"`, etc.) mapped to the item
  description. Returns `None` if the text doesn't look like equipment output
  (e.g. it's an `error:` string from `_guard`).

- `parse_identify(text: str) -> dict | None`
  Parses `identify` spell/scroll output. Stock CircleMUD format includes
  lines like:
  ```
  Object 'a gold ring', Item type: WORN
  This item can be worn on: FINGER
  Can affect you as :
     Affects: HITROLL By 2
     Affects: DAMROLL By 1
     Affects: AC By -10
  ```
  Extract the object name, wear-slot line (normalized to the same slot key
  vocabulary as `parse_equipment`), and every `Affects: <NAME> By <value>`
  line via one generic regex into `{affect_name.lower(): int(value)}` — this
  uniformly captures hitroll, damroll, AC, and stat mods (STR/DEX/CON/...)
  without needing a separate stats parser. Returns `None` if the text
  doesn't match (e.g. "You are not holding that item" failure output).

  Built against the stock CircleMUD identify format. This server's actual
  output hasn't been captured yet — the regexes may need adjusting once
  validated against a live `identify` cast, the same way other parsers in
  this codebase (e.g. `PlayerStats`) were refined against real transcripts.
  Note this as an open item in `game_findings.md` if a live session shows
  a mismatch.

### 2. Storage

**Item stats — world-scoped.** An item's stats are a property of the item
type, not of who's wearing it — same lifetime/sharing model as
`KnowledgeManager` (quest hints, NPC secrets). New
`src/boukensha/memory/item_stats.py`:

```python
class ItemStatsStore:
    def __init__(self, base_dir: str | Path) -> None: ...
    def save(self, item_name: str, stats: dict) -> None: ...
    def get(self, item_name: str) -> dict | None: ...
    def read_all(self) -> dict[str, dict]: ...
```

Persisted to `.boukensha/item_stats.yaml`, keyed by lowercased item name,
same load/save-via-tempfile pattern as `KnowledgeManager`. Excluded from git
(add to `.gitignore` alongside `knowledge.yaml`, if not already covered by a
wildcard).

**Current loadout — player-scoped.** Extend `PlayerTracker`
(`src/boukensha/memory/player_tracker.py`) with:

```python
def update_equipment(self, name: str, slots: dict[str, str]) -> None: ...
```

Same pattern as the existing `update_stats` — merges into the per-player
record in `players.json` under an `equipment` key with an
`equipment_updated_at` timestamp.

### 3. Wiring — `src/boukensha/tools/mud.py`

- `check(kind="equipment")`: after getting the raw response, run
  `parse_equipment`; on success, call `tracker.update_equipment(name, slots)`.
  Mirrors the existing `_check_and_record` handling of `kind="score"`.

- `cast_spell` and `use_magic_item`: when the spell name / item mode
  indicates `identify` (spell text or `mode="recite"`/`"use"` where the
  action string contains "identify"), run `parse_identify` on the result.
  On success:
  1. Save to `ItemStatsStore`.
  2. If the parsed wear slot is known, look up what's currently in that
     slot from the tracker's last equipment snapshot for this player, and
     look up *that* item's stats from `ItemStatsStore` (only available if
     it too was previously identified).
  3. If both the new and current item's stats are known, append an
     advisory comparing them — same shape as `_sustenance_advisory` /
     `_level_up_advisory` in `tools/mud.py`: informational text appended to
     the tool result, not a gate, silent (no advisory) when there's
     nothing to compare against (current slot empty or never identified).

  Example advisory: `"[Equipment] 'a gold ring' (AC -10, hitroll +2) is
  stronger than what's currently worn in your finger slot ('a copper
  ring', AC -2). Consider equip_item(item=\"gold ring\", action=\"wear\")."`

### 4. Tests

New test files following existing conventions (`tests/test_player_stats.py`
style):

- `tests/test_equipment_parser.py` — `parse_equipment`/`parse_identify`
  against stock-format fixture strings, including malformed/error input.
- `tests/test_item_stats.py` — `ItemStatsStore` save/get/read_all round-trip.
- Extend `tests/test_player_tracker.py` (or equivalent) for
  `update_equipment`.
- Extend the `tools/mud.py` test suite for the advisory wiring: identify two
  items in the same slot, assert the second identify's result contains the
  comparison text; assert silence when only one item in the slot has been
  identified.

## Open questions / follow-ups

- Exact `identify` output format for this server is unverified — first live
  test after implementation should confirm the regexes, per the existing
  `game_findings.md` "Open" → "Implemented" workflow.
- Dashboard visualization of equipment/AC is out of scope here; a natural
  follow-up once this data exists (mirrors how the Waterfall/Sessions tabs
  were added incrementally).
</content>
