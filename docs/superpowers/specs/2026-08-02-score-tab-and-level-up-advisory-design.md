# Score Dashboard Tab & Level-Up Advisory — Design Spec

**Date:** 2026-08-02
**Project:** boukensha (week3_capable/agent-exp)
**Status:** Approved

---

## Problem

Two related gaps surfaced while running the agent live and watching it farm:

1. There's no way to watch character stats (HP/mana/move, level, exp, gold) update
   live without reading raw SSE log lines on the Live tab. A dedicated Score tab
   would make it easy to glance at character progress.
2. The agent just leveled up (level 2 → 3) mid-session with no acknowledgement —
   nothing tells it to seek out a guildmaster and train (`practice`) newly
   available skills. Left alone, it will keep farming indefinitely without ever
   training.

## Constraints

- The agent does not yet know where the guild/guildmaster is — `room_aliases.json`
  only has `"the newbie zone"` mapped. Auto-navigation to the guild is not
  reliably possible yet, so the level-up handling must be an advisory nudge, not
  a hard navigation trigger.
- `check(kind='score')` is already called regularly by the agent and its raw
  text already contains everything needed (HP/mana/move, level, title, exp,
  exp-to-next, gold) — no new MUD command is required.
- The dashboard's Live tab already receives every tool_call/tool_result event
  over SSE (`EventBus` in `dashboard/event_bus.py`, fed from the session logger).
  The Score tab should reuse this existing stream rather than open a new one.

---

## Design

### 1. Extend `PlayerStats.parse_score` (`src/boukensha/memory/player_stats.py`)

Add regexes for the remaining lines always present in `score` output:

```
This ranks you as Dummy the Sentry (level 3).
You have 5829 exp, 130 gold coins, and 0 questpoints.
You need 2171 exp to reach your next level.
```

New fields added to the existing stats dict (alongside `hp`/`max_hp`/`mana`/
`max_mana`/`move`/`max_move`/`hungry`/`thirsty`):

- `level: int`
- `title: str` (e.g. `"Dummy the Sentry"`)
- `exp: int`
- `exp_to_next: int`
- `gold: int`

If the level/title/exp lines are missing (unexpected score format), those keys
are simply omitted rather than raising — `parse_score` keeps returning `None`
only when the core HP/mana/move line fails to match, exactly as it does today.

These fields flow into `players.json` for free via the existing
`tracker.update_stats()` call in `mud.py` — no changes needed to
`PlayerTracker`.

### 2. Level-up advisory (`src/boukensha/tools/mud.py`, `_check_and_record`)

Before calling `tracker.update_stats(name, stats)`, read the player's
previously recorded level:

```python
previous = (tracker.read_all().get(name) or {}).get("stats") or {}
previous_level = previous.get("level")
```

After parsing the new stats, if `previous_level is not None and stats.get("level", 0) > previous_level`,
append a `_level_up_advisory(previous_level, stats)` string to the raw score
text — same pattern and tone as the existing `_sustenance_advisory`:

```python
def _level_up_advisory(previous_level: int, stats: dict) -> str:
    level = stats.get("level")
    title = stats.get("title", "")
    return (
        f"\n\n[Level up!] You are now level {level}"
        f"{f' ({title})' if title else ''} — up from level {previous_level}. "
        "Consider finding a guildmaster and using practice to train any new "
        "skills before continuing to farm. If you haven't located a "
        "guildmaster yet, explore toward one; navigate_to it once it's mapped. "
        "Not urgent enough to interrupt a fight in progress."
    )
```

First-ever score check for a character (`previous_level is None`) never fires
this — that's a baseline read, not a level gain.

This is purely advisory text appended to the tool result, matching the
existing architecture: tools surface actionable information, the LLM decides
what to do with it. No goal-file mutation, no forced navigation.

### 3. Score dashboard tab

**`templates/index.html`** — new nav button and pane, following the existing
Overview/Goals structure:

```html
<button class="tab-btn" data-tab="score">Score</button>
...
<section id="tab-score" class="tab-pane">
  <div id="score-cards"></div>
</section>
```

**`static/app.js`** — a `loadScore()` function fetching the existing
`/api/players` endpoint (already returns the new level/exp/gold fields once
part 1 lands) and rendering one card per tracked player:

- Level + title as the card heading
- HP / mana / move as labeled bars (reusing `.overview-card` styling)
- Exp progress: `exp` vs `exp + exp_to_next`
- Gold
- Hungry/thirsty flags if set

Wired into the existing tab-click router (`if (btn.dataset.tab === 'score') loadScore();`).

**Live updates** reuse the existing SSE handler in `es.onmessage`: when a
`tool_result` for `name === 'check'` arrives and the Score tab is currently
active, call `loadScore()` again — the same debounce-by-active-tab pattern
already used for the Map tab's `MAP_REFRESH_TOOLS` set. No new SSE event type,
no new backend endpoint.

### 4. Testing

- `tests/test_player_stats.py`: parse the real sample score text captured
  from a session log (level 2 and level 3 examples) and assert all new fields
  (`level`, `title`, `exp`, `exp_to_next`, `gold`).
- `tests/test_tools_mud.py` (or wherever `check`/score advisory tests
  currently live): a level-up test asserting the advisory text is appended
  when the new level exceeds the previously recorded one, and a
  no-advisory test for both the first-ever check and a same/lower level
  reading.

---

## Out of scope

- Auto-navigating to the guild or auto-calling `practice` — deferred until the
  guild location is actually known and mapped.
- Persisting a "training completed" flag — the advisory just nudges every
  level-up; the agent isn't tracked on whether it acted on it.
