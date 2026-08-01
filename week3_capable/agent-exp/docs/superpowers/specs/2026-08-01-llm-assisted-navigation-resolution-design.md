# LLM-assisted destination resolution + learned aliases — design

## Problem

`navigate_to` (`src/boukensha/tools/navigation.py`) resolves a free-text
`destination` against the known map purely deterministically: substring
match on room titles, then all-significant-words-must-match overlap
(`memory/pathfinder.py::word_overlap_matches`), then a landmark search over
room descriptions/items/npcs (`_route_by_landmark`), then partial-word
near-misses for the error message.

This works well when the destination shares distinctive vocabulary with the
mapped room text, but fails in two related ways, all observed live:

1. **No shared vocabulary at all.** "Go find the bakery" fails outright with
   `"No known path to 'bakery'. Explore more of the area first."` if the
   room is actually titled something that shares no word with "bakery" —
   zero information for the agent to act on, even though the agent (an LLM
   with its own memory of what it has seen) may well know exactly which
   room that is.
2. **Ambiguous shared vocabulary.** `pathfinder.py`'s own comments document
   a live bug: "Guild of Swordsmen" (not yet mapped) matched "The Entrance
   To The Clerics' Guild" because both share the word "guild," which recurs
   across every guild in the game and is not real evidence of *which* one.
   "Go train at your guild" or "go find the newbie zone" are the same
   failure mode — a generic or paraphrased term that either matches nothing
   distinctive, or matches the wrong thing.

The fix is **not** destination-specific (not "special-case bakery" or
"special-case guild"). It generalizes: when deterministic matching fails or
is unreliable, give the agent — which already reasons over the whole
conversation and already knows what it is looking for — enough information
about the known map to resolve it itself, and let it persist that
resolution so the same term resolves deterministically and correctly next
time without repeating the reasoning.

## Design

### 1. Richer failure message when nothing at all matches

In `_navigate_to`, the final "nothing matched" branch (today: `"No known
path to '{destination}'. Explore more of the area first."`) is extended to
include the full list of currently known room titles, so the agent can pick
the right one from its own knowledge of the game rather than getting a dead
end. Capped/truncated for very large maps, in the same spirit as
`_knowledge_injection.py`'s token cap on injected knowledge. Only this
branch changes — the existing substring/word-overlap/landmark/near-miss
logic, which already resolves plenty of cases correctly (e.g. "the
fountain"), is untouched.

### 2. `RoomAliases` store + `navigate_alias_add` tool

New `src/boukensha/memory/room_aliases.py`, following the same pattern as
`BlockedExits`/`KnowledgeManager` (atomic write via `.tmp` + `os.replace`):
persists a map of lowercased alias → room hash to
`.boukensha/memory/room_aliases.json`.

New tool `navigate_alias_add(alias, destination)` registered alongside
`navigate_to` in `Navigation.register`: resolves `destination` through the
same matching pipeline `navigate_to` uses (so the alias always points at a
real, currently-known room), then stores `alias → room_hash`.

`_navigate_to`'s matching pipeline checks the alias store **first**, before
title substring/word-overlap/landmark search. This means:

- Once "bakery" is aliased, it resolves in one deterministic lookup, no
  reasoning required.
- Once "guild of swordsmen" is aliased to the correct guild room, the
  ambiguous word-overlap match against "guild" is bypassed entirely for
  that term going forward — the alias wins before the ambiguous fallback
  ever runs.

### 3. System prompt guidance

`prompts/system.md` gets a short instruction: if `navigate_to` fails but its
error message (near-misses, or the full title list from part 1) reveals the
right room, retry `navigate_to` with the exact title; once that succeeds,
call `navigate_alias_add(alias=<original term>, destination=<exact
title>)` so the same shorthand resolves directly next time.

### 4. Documentation updates

- `architecture.md`: add `RoomAliases` to the component table; add
  `navigate_alias_add` to the `navigate_to` tool's row (or its own row);
  mention the alias-first lookup order in the "Exploration & Route-Walking
  Reliability" section; add `ALIASFILE`/`ROOMALIASES` to the data-flow
  diagram alongside the existing memory files.
- `game_findings.md`: new "Implemented" entry in the existing voice/format,
  using the bakery/guild/newbie-zone cases as the motivating examples,
  same as the existing fountain/landmark entry.

## Out of scope

- No nested/extra LLM call inside `navigate_to` itself — resolution stays
  in the existing agent loop (the conversational LLM), keeping the tool
  pure Python and free of hidden cost/latency.
- No changes to `explore()`, combat, or the dashboard.
- No automatic/inferred aliasing (e.g. guessing that a failed call followed
  by a successful one must be related) — aliasing is always an explicit
  `navigate_alias_add` call, avoiding false aliases from unrelated
  back-to-back `navigate_to` calls.

## Testing

- `tests/test_room_aliases.py`: store round-trip, atomic write, case
  insensitivity.
- `tests/test_navigation_tool.py` additions:
  - an aliased destination resolves via the alias, bypassing title/landmark
    search entirely (including the ambiguous-guild-style case).
  - the full known-title list appears in the error message only when no
    substring/word-overlap/landmark/near-miss match exists at all.
  - `navigate_alias_add` resolves its `destination` the same way
    `navigate_to` does and persists the alias.

## File changes

```
src/boukensha/memory/room_aliases.py       # new: RoomAliases store
src/boukensha/tools/navigation.py          # alias-first lookup, navigate_alias_add tool,
                                            # richer no-match error message
src/boukensha/__init__.py                  # wire RoomAliases into Navigation.register (both call sites)
prompts/system.md                          # guidance: retry with exact title, then alias it
architecture.md                            # document RoomAliases + navigate_alias_add
game_findings.md                           # new Implemented entry
tests/test_room_aliases.py                 # new
tests/test_navigation_tool.py              # additions
```
