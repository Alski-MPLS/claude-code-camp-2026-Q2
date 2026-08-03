# Score Dashboard Tab & Level-Up Advisory Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add a live-updating "Score" tab to the boukensha web dashboard, and make `check(kind='score')` append an advisory when the character's level increases.

**Architecture:** Extend the existing `PlayerStats.parse_score` regex parser with level/title/exp/gold fields (they flow into `players.json` for free via the existing `PlayerTracker.update_stats`). Add a level-up comparison + advisory string inside `mud.py`'s `_check_and_record`, following the existing `_sustenance_advisory` pattern exactly. Add a new dashboard tab that fetches `/api/players` (already returns the new fields once parsing is extended) and re-fetches on relevant SSE events, following the existing Map-tab live-refresh pattern.

**Tech Stack:** Python 3.11+ (stdlib `re`, pytest), vanilla JS (no framework) + Flask SSE, existing `EventBus`.

## Global Constraints

- Working directory for all Python/test commands: `week3_capable/agent-exp` (repo root for `git` commands is the monorepo root, `claude-code-camp-2026-Q2`).
- Run tests with the project's own venv, not any other week's: `.venv/bin/python -m pytest ...` (do not rely on `uv run` — it has previously resolved to the wrong venv in this environment).
- `PlayerStats.parse_score` must keep returning exactly the same dict shape as before when the level/exp/gold lines are absent from the input text — several existing tests assert exact dict equality (`tests/test_player_stats.py`, `tests/test_tools_mud.py::test_check_score_persists_stats_to_player_tracker`). New keys must only appear when their source line is present in the text.
- No auto-navigation or auto-`practice` calls — level-up handling is advisory text only (see spec, "Out of scope").
- Follow existing code patterns exactly: `_sustenance_advisory` is the template for the level-up advisory; the Map tab's `MAP_REFRESH_TOOLS` set is the template for the Score tab's live refresh.

---

### Task 1: Extend `PlayerStats.parse_score` with level/title/exp/gold

**Files:**
- Modify: `src/boukensha/memory/player_stats.py`
- Test: `tests/test_player_stats.py`

**Interfaces:**
- Consumes: nothing new (pure regex parsing of `score` command text).
- Produces: `PlayerStats.parse_score(text: str) -> dict[str, int | str | bool] | None` — same as before, but the returned dict gains optional keys `level: int`, `title: str`, `exp: int`, `exp_to_next: int`, `gold: int` **only when the corresponding line is present** in `text`. These keys are read by Task 2 (`mud.py`) and Task 3 (dashboard `/api/players` consumers).

- [ ] **Step 1: Write the failing tests**

Add to `tests/test_player_stats.py`:

```python
def test_parse_score_extracts_level_title_exp_and_gold():
    text = (
        "You are 17 years old.\n"
        "You have 50(50) hit, 100(100) mana and 88(88) movement points.\n"
        "Your armor class is 29/10, and your alignment is 164.\n"
        "You have 5829 exp, 130 gold coins, and 0 questpoints.\n"
        "You need 2171 exp to reach your next level.\n"
        "You have earned 0 quest points.\n"
        "You have completed 0 quests, and you are not on a quest at the moment.\n"
        "You have been playing for 0 days and 3 hours.\n"
        "This ranks you as Dummy the Sentry (level 3).\n"
        "You are standing.\n"
    )
    stats = PlayerStats.parse_score(text)
    assert stats["level"] == 3
    assert stats["title"] == "Dummy the Sentry"
    assert stats["exp"] == 5829
    assert stats["exp_to_next"] == 2171
    assert stats["gold"] == 130


def test_parse_score_omits_level_fields_when_lines_absent():
    text = "You have 37(37) hit, 100(100) mana and 87(87) movement points.\n"
    stats = PlayerStats.parse_score(text)
    assert "level" not in stats
    assert "title" not in stats
    assert "exp" not in stats
    assert "exp_to_next" not in stats
    assert "gold" not in stats
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `cd week3_capable/agent-exp && .venv/bin/python -m pytest tests/test_player_stats.py -v`
Expected: the two new tests FAIL with `KeyError` (keys not present yet); all pre-existing tests in this file still PASS.

- [ ] **Step 3: Implement the new regexes**

In `src/boukensha/memory/player_stats.py`, add below the existing `_HUNGRY_RE`/`_THIRSTY_RE`:

```python
_LEVEL_RE = re.compile(r"This ranks you as (.+?)\s*\(level (\d+)\)", re.IGNORECASE)
_EXP_GOLD_RE = re.compile(
    r"You have (\d+) exp,\s*(\d+) gold coins", re.IGNORECASE
)
_EXP_NEXT_RE = re.compile(r"You need (\d+) exp to reach your next level", re.IGNORECASE)
```

Update `parse_score` to merge these in before returning:

```python
    @staticmethod
    def parse_score(text: str) -> dict[str, int | str | bool] | None:
        m = _SCORE_RE.search(text)
        if not m:
            return None
        hp, max_hp, mana, max_mana, move, max_move = (int(g) for g in m.groups())
        stats: dict[str, int | str | bool] = {
            "hp": hp, "max_hp": max_hp,
            "mana": mana, "max_mana": max_mana,
            "move": move, "max_move": max_move,
            "hungry": bool(_HUNGRY_RE.search(text)),
            "thirsty": bool(_THIRSTY_RE.search(text)),
        }

        level_m = _LEVEL_RE.search(text)
        if level_m:
            stats["title"] = level_m.group(1).strip()
            stats["level"] = int(level_m.group(2))

        exp_gold_m = _EXP_GOLD_RE.search(text)
        if exp_gold_m:
            stats["exp"] = int(exp_gold_m.group(1))
            stats["gold"] = int(exp_gold_m.group(2))

        exp_next_m = _EXP_NEXT_RE.search(text)
        if exp_next_m:
            stats["exp_to_next"] = int(exp_next_m.group(1))

        return stats
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `cd week3_capable/agent-exp && .venv/bin/python -m pytest tests/test_player_stats.py -v`
Expected: all tests PASS (7 total: 5 pre-existing + 2 new).

- [ ] **Step 5: Commit**

```bash
cd /Users/alanw/code/github/ai/claude-code-camp-2026-Q2
git add week3_capable/agent-exp/src/boukensha/memory/player_stats.py week3_capable/agent-exp/tests/test_player_stats.py
git commit -m "Parse level, title, exp, and gold from score output"
```

---

### Task 2: Level-up advisory in `check(kind='score')`

**Files:**
- Modify: `src/boukensha/tools/mud.py:311-329` (advisory helpers) and `:452-460` (`_check_and_record`)
- Test: `tests/test_tools_mud.py`

**Interfaces:**
- Consumes: `PlayerStats.parse_score` from Task 1 (dict may now contain `level`/`title`), `PlayerTracker.read_all() -> dict[str, Any]` and `PlayerTracker.update_stats(name, stats)` (both already exist, unchanged).
- Produces: `_level_up_advisory(previous_level: int, stats: dict) -> str`, called from `_check_and_record`. The `check` tool's return string gains an appended `[Level up!]` block when applicable — consumed by no other code (advisory text only, per spec).

- [ ] **Step 1: Write the failing tests**

Add to `tests/test_tools_mud.py` (same file already has `Mud._register_with_session` helper usage and a `_make_registry` helper — follow the existing tests immediately after `test_check_score_omits_sustenance_advisory_when_neither` for placement):

```python
def test_check_score_appends_level_up_advisory_when_level_increased(tmp_path):
    from boukensha.memory.player_tracker import PlayerTracker
    PlayerTracker(tmp_path).update_stats("Tester", {
        "hp": 37, "max_hp": 37, "mana": 100, "max_mana": 100,
        "move": 87, "max_move": 87, "hungry": False, "thirsty": False,
        "level": 2, "title": "Dummy the Recruit",
    })

    registry = _make_registry()
    mock_session = MagicMock()
    mock_session.is_open = True
    mock_session.drain.return_value = ""
    mock_session.read_until_prompt.return_value = (
        "You have 50(50) hit, 100(100) mana and 88(88) movement points.\n"
        "You have 5829 exp, 130 gold coins, and 0 questpoints.\n"
        "You need 2171 exp to reach your next level.\n"
        "This ranks you as Dummy the Sentry (level 3). > "
    )
    Mud._register_with_session(
        registry, mock_session, name="Tester", password="secret", memory_dir=tmp_path
    )

    result = registry.dispatch("check", {"kind": "score"})

    assert "[Level up!]" in result
    assert "level 3" in result
    assert "Dummy the Sentry" in result
    assert "level 2" in result  # mentions the previous level


def test_check_score_omits_level_up_advisory_on_first_ever_check(tmp_path):
    registry = _make_registry()
    mock_session = MagicMock()
    mock_session.is_open = True
    mock_session.drain.return_value = ""
    mock_session.read_until_prompt.return_value = (
        "You have 20(20) hit, 100(100) mana and 85(85) movement points.\n"
        "This ranks you as Dummy the Recruit (level 2). > "
    )
    Mud._register_with_session(
        registry, mock_session, name="Tester", password="secret", memory_dir=tmp_path
    )

    result = registry.dispatch("check", {"kind": "score"})

    assert "[Level up!]" not in result


def test_check_score_omits_level_up_advisory_when_level_unchanged(tmp_path):
    from boukensha.memory.player_tracker import PlayerTracker
    PlayerTracker(tmp_path).update_stats("Tester", {
        "hp": 37, "max_hp": 37, "mana": 100, "max_mana": 100,
        "move": 87, "max_move": 87, "hungry": False, "thirsty": False,
        "level": 3, "title": "Dummy the Sentry",
    })

    registry = _make_registry()
    mock_session = MagicMock()
    mock_session.is_open = True
    mock_session.drain.return_value = ""
    mock_session.read_until_prompt.return_value = (
        "You have 45(50) hit, 100(100) mana and 88(88) movement points.\n"
        "This ranks you as Dummy the Sentry (level 3). > "
    )
    Mud._register_with_session(
        registry, mock_session, name="Tester", password="secret", memory_dir=tmp_path
    )

    result = registry.dispatch("check", {"kind": "score"})

    assert "[Level up!]" not in result
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `cd week3_capable/agent-exp && .venv/bin/python -m pytest tests/test_tools_mud.py -k level_up -v`
Expected: all three FAIL (`[Level up!]` never appears yet).

- [ ] **Step 3: Implement `_level_up_advisory` and wire it into `_check_and_record`**

In `src/boukensha/tools/mud.py`, add a new function directly after `_sustenance_advisory` (which ends at line 329, right before `_no_living_target_message` at line 332):

```python
def _level_up_advisory(previous_level: int, stats: dict[str, int | str | bool]) -> str:
    level = stats.get("level")
    title = stats.get("title", "")
    title_part = f" ({title})" if title else ""
    return (
        f"\n\n[Level up!] You are now level {level}{title_part} — up from level "
        f"{previous_level}. Consider finding a guildmaster and using practice to "
        "train any new skills before continuing to farm. If you haven't located "
        "a guildmaster yet, explore toward one; navigate_to it once it's mapped. "
        "Not urgent enough to interrupt a fight in progress."
    )
```

Then update `_check_and_record` (currently lines 452-460):

```python
        def _check_and_record(kind: str) -> str:
            raw = _check_info(session, kind)
            if kind.strip().lower() == "score" and not raw.startswith("error:"):
                stats = PlayerStats.parse_score(raw)
                if stats:
                    previous_level = None
                    if tracker is not None:
                        previous = (tracker.read_all().get(name) or {}).get("stats") or {}
                        previous_level = previous.get("level")
                        tracker.update_stats(name, stats)
                    raw += _sustenance_advisory(stats)
                    new_level = stats.get("level")
                    if (
                        previous_level is not None
                        and new_level is not None
                        and new_level > previous_level
                    ):
                        raw += _level_up_advisory(previous_level, stats)
            return raw
```

Note: `tracker.read_all()` must be called **before** `tracker.update_stats(name, stats)` in the same branch, since `update_stats` overwrites the stored stats — reversing the order would make `previous_level` always equal the new level.

- [ ] **Step 4: Run tests to verify they pass**

Run: `cd week3_capable/agent-exp && .venv/bin/python -m pytest tests/test_tools_mud.py -v`
Expected: all tests in the file PASS, including the 3 new ones and all pre-existing `check`/score tests (`test_check_score_persists_stats_to_player_tracker`, `test_check_non_score_kind_does_not_touch_player_tracker`, `test_check_score_without_memory_dir_does_not_crash`, `test_check_score_appends_sustenance_advisory_when_hungry_and_thirsty`, `test_check_score_omits_sustenance_advisory_when_neither`).

- [ ] **Step 5: Commit**

```bash
cd /Users/alanw/code/github/ai/claude-code-camp-2026-Q2
git add week3_capable/agent-exp/src/boukensha/tools/mud.py week3_capable/agent-exp/tests/test_tools_mud.py
git commit -m "Add level-up advisory to check(kind=score)"
```

---

### Task 3: Score dashboard tab — HTML + CSS

**Files:**
- Modify: `src/boukensha/dashboard/templates/index.html`
- Modify: `src/boukensha/dashboard/static/style.css`

**Interfaces:**
- Produces: DOM elements `#tab-score` (pane) and `#score-cards` (container the JS in Task 4 renders into), plus CSS classes `.score-card`, `.score-card-header`, `.score-card-level`, `.score-bar-row`, `.score-bar-label`, `.score-bar-track`, `.score-bar-fill`, `.score-bar-fill.hp`, `.score-bar-fill.mana`, `.score-bar-fill.move`, `.score-exp-row`, `.score-gold`, `.score-flags` — consumed by Task 4's JS.

- [ ] **Step 1: Add the nav button and pane to `index.html`**

In `src/boukensha/dashboard/templates/index.html`, add the nav button right after the Overview button (currently line 12):

```html
    <button class="tab-btn" data-tab="overview">Overview</button>
    <button class="tab-btn" data-tab="score">Score</button>
```

Add the pane right after `</section>` closing `tab-overview` (currently line 24), before `<section id="tab-live"` (currently line 26):

```html
  <section id="tab-score" class="tab-pane">
    <div id="score-cards"></div>
  </section>
```

- [ ] **Step 2: Add CSS for the score cards**

In `src/boukensha/dashboard/static/style.css`, add after the existing `.overview-empty` rule (currently line 122):

```css

.score-card { background: #1a1a1a; border: 1px solid #333; border-radius: 6px; padding: 16px; margin-bottom: 12px; max-width: 420px; }
.score-card-header { display: flex; justify-content: space-between; align-items: baseline; margin-bottom: 12px; }
.score-card-name { color: #fff; font-size: 16px; font-weight: bold; }
.score-card-level { color: #4af; font-size: 13px; }
.score-bar-row { margin-bottom: 8px; }
.score-bar-label { color: #888; font-size: 11px; text-transform: uppercase; letter-spacing: 0.05em; margin-bottom: 3px; display: flex; justify-content: space-between; }
.score-bar-track { background: #222; border-radius: 4px; height: 8px; overflow: hidden; }
.score-bar-fill { height: 100%; border-radius: 4px; }
.score-bar-fill.hp { background: #f66; }
.score-bar-fill.mana { background: #6af; }
.score-bar-fill.move { background: #6f6; }
.score-bar-fill.exp { background: #fa4; }
.score-exp-row { color: #ccc; font-size: 12px; margin-top: 10px; }
.score-gold { color: #fd4; font-size: 12px; margin-top: 4px; }
.score-flags { color: #f96; font-size: 12px; margin-top: 8px; }
```

- [ ] **Step 3: Manually verify the pane renders (no data yet)**

This task has no Python/JS logic to unit test — verify visually once Task 4 is done. No commit yet; combine with Task 4's commit since an empty pane with no JS wiring isn't independently meaningful. Proceed directly to Task 4.

---

### Task 4: Score dashboard tab — JS rendering + live refresh

**Files:**
- Modify: `src/boukensha/dashboard/static/app.js`

**Interfaces:**
- Consumes: `GET /api/players` (existing endpoint, `src/boukensha/dashboard/app.py:99-107`) returning `[{name, stats: {hp, max_hp, mana, max_mana, move, max_move, hungry, thirsty, level?, title?, exp?, exp_to_next?, gold?}, title, room_hash, ...}]` (the outer `title` is room title from `PlayerTracker.update`; the character's rank title lives inside `stats.title` from Task 1 — do not confuse the two). DOM elements from Task 3 (`#score-cards`).
- Produces: `loadScore()` function, called from the tab router and from the SSE handler.

- [ ] **Step 1: Add `loadScore()` and wire it into the tab router**

In `src/boukensha/dashboard/static/app.js`, update the tab-click router (currently lines 10-21) to add:

```javascript
    if (btn.dataset.tab === 'score') loadScore();
```

Add the function anywhere after `escapeHtml` is defined (e.g. right after the `loadOverview` function, which ends at line 88):

```javascript
// Score tab
function scoreBar(label, value, max, cls) {
  const pct = max > 0 ? Math.round((value / max) * 100) : 0;
  return `<div class="score-bar-row">
    <div class="score-bar-label"><span>${escapeHtml(label)}</span><span>${value}/${max}</span></div>
    <div class="score-bar-track"><div class="score-bar-fill ${cls}" style="width:${pct}%"></div></div>
  </div>`;
}

async function loadScore() {
  const el = document.getElementById('score-cards');
  const r = await fetch('/api/players');
  const players = await r.json();
  if (!players.length) {
    el.innerHTML = '<p class="overview-empty">No players tracked yet.</p>';
    return;
  }
  el.innerHTML = players.map(p => {
    const s = p.stats || {};
    if (!('hp' in s)) {
      return `<div class="score-card">
        <div class="score-card-header"><span class="score-card-name">${escapeHtml(p.name)}</span></div>
        <p class="overview-empty">Stats not yet checked (no score command run).</p>
      </div>`;
    }
    const levelPart = 'level' in s
      ? `Level ${s.level}${s.title ? ' — ' + escapeHtml(s.title) : ''}`
      : 'Level unknown';
    const expRow = 'exp' in s && 'exp_to_next' in s
      ? scoreBar('Exp to next level', s.exp_to_next > 0 ? Math.max(0, s.exp_to_next - s.exp_to_next) : 0, 0, 'exp') // placeholder replaced below
      : '';
    const flags = [];
    if (s.hungry) flags.push('hungry');
    if (s.thirsty) flags.push('thirsty');
    return `<div class="score-card">
      <div class="score-card-header">
        <span class="score-card-name">${escapeHtml(p.name)}</span>
        <span class="score-card-level">${levelPart}</span>
      </div>
      ${scoreBar('HP', s.hp, s.max_hp, 'hp')}
      ${scoreBar('Mana', s.mana, s.max_mana, 'mana')}
      ${scoreBar('Move', s.move, s.max_move, 'move')}
      ${'exp' in s && 'exp_to_next' in s
        ? `<div class="score-exp-row">${s.exp} exp — ${s.exp_to_next} to next level</div>`
        : ''}
      ${'gold' in s ? `<div class="score-gold">${s.gold} gold</div>` : ''}
      ${flags.length ? `<div class="score-flags">${flags.join(', ')}</div>` : ''}
    </div>`;
  }).join('');
}
```

Note: the `expRow` variable in the draft above is dead/unused — remove it. The exp line is rendered directly in the template literal via the ternary right below the move bar. Do not include the `scoreBar('Exp to next level', ...)` placeholder line at all; it was a false start. The corrected function body has no `expRow` variable.

- [ ] **Step 2: Wire live refresh into the existing SSE handler**

In `src/boukensha/dashboard/static/app.js`, the SSE handler already has a `MAP_REFRESH_TOOLS` block (currently lines 44-50):

```javascript
  const MAP_REFRESH_TOOLS = new Set(['move', 'navigate_to', 'process_room']);
  if (event.phase === 'tool_result' && MAP_REFRESH_TOOLS.has(event.name)) {
    const mapTab = document.getElementById('tab-map');
    if (mapTab && mapTab.classList.contains('active')) {
      window.loadMap && window.loadMap();
    }
  }
```

Add directly after that block, inside the same `es.onmessage` handler:

```javascript

  // Refresh the Score tab whenever a `check` call resolves (covers score,
  // but also harmless to refresh on inventory/equipment/etc. checks — the
  // underlying /api/players data only changes when it was actually a score
  // check, so a no-op refresh is cheap and simpler than inspecting args).
  if (event.phase === 'tool_result' && event.name === 'check') {
    const scoreTab = document.getElementById('tab-score');
    if (scoreTab && scoreTab.classList.contains('active')) {
      loadScore();
    }
  }
```

- [ ] **Step 3: Manual verification**

Run: `cd week3_capable/agent-exp && .venv/bin/python -m pytest tests/ -q` (confirm no regressions; this task has no new Python tests — it's front-end only).
Expected: same pass/fail counts as the pre-existing baseline (405 passed, 4 pre-existing unrelated failures in `test_room_parser.py` — do not attempt to fix those, they're out of scope).

Then manually verify in a browser:
1. Start the dashboard: `cd week3_capable/agent-exp && .venv/bin/python bin/boukensha --web` (or via the already-running tmux session if one exists).
2. Open `http://localhost:4568`, click the "Score" tab.
3. Confirm it shows a card per tracked player with HP/mana/move bars, level+title, exp, and gold (or "Stats not yet checked" if no `score` has run yet in `.boukensha/memory/players.json`).
4. While a `check(kind='score')` call is in flight in the agent's session, confirm the Score tab updates without a manual page refresh (leave the Score tab active, trigger a score check, watch the bars update).

- [ ] **Step 4: Commit**

```bash
cd /Users/alanw/code/github/ai/claude-code-camp-2026-Q2
git add week3_capable/agent-exp/src/boukensha/dashboard/templates/index.html week3_capable/agent-exp/src/boukensha/dashboard/static/style.css week3_capable/agent-exp/src/boukensha/dashboard/static/app.js
git commit -m "Add live-updating Score tab to the web dashboard"
```

---

## Self-Review Notes

- **Spec coverage:** Task 1 covers spec §1, Task 2 covers spec §2, Tasks 3-4 cover spec §3, tests are embedded per-task per spec §4. All spec sections have a corresponding task.
- **Placeholder scan:** removed a false-start `expRow` line from the Task 4 draft — corrected inline in Step 1's note rather than leaving it as a "TODO"; the actual code block to type has no dead code.
- **Type consistency:** `PlayerStats.parse_score` return type used consistently as `dict[str, int | str | bool] | None` across Task 1 and Task 2. `_level_up_advisory(previous_level: int, stats: dict) -> str` signature matches its call site in Task 2 Step 3. `loadScore()` (Task 4) matches the `window.loadMap`-style pattern already used for other tabs — no `window.` prefix needed since it's called from within `app.js` itself, same file as the router (unlike `loadMap`, which lives in `map.js` and needs `window.loadMap` to cross the file boundary).
