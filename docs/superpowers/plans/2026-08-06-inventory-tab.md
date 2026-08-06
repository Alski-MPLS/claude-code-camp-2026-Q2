# Inventory Dashboard Tab Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add an "Inventory" tab to the Boukensha web dashboard showing each tracked character's equipped items and carried (backpack) items.

**Architecture:** Extend the existing equipment-tracking pattern (parse → persist → surface) to carried inventory. `check(kind="inventory")` output is currently parsed by nothing and discarded; add a parser, a `PlayerTracker` method, and a wiring branch to persist it to `players.json`, exactly mirroring how `equipment` already works. No new API route is needed — `/api/players` and `/api/overview` already spread the full per-player dict. Add a dashboard tab following the Score tab's fetch-on-click + SSE-piggyback pattern.

**Tech Stack:** Python 3.11+, pytest, vanilla JS (no framework), Flask, existing `style.css`.

## Global Constraints

- Follow the exact `None`-vs-empty-dict/list return contract used by `parse_equipment` (spec: "returns `None` when the text isn't inventory output at all... `[]` when it IS inventory output but nothing is carried").
- No new dashboard tab framework or SSE-only pattern — fetch-on-tab-click, matching Score/Overview/Goals/Sessions (spec section 5, non-goals).
- No auto-refresh on `get_item`/`drop_item`/`equip_item` — only on explicit `check(kind="inventory")` (spec non-goals).
- No item-stats/upgrade-advisory logic for carried items in this plan (spec non-goals).

---

### Task 1: `parse_inventory` parser

**Files:**
- Modify: `src/boukensha/memory/equipment_parser.py` (add function, no existing code changes)
- Test: `tests/test_equipment_parser.py` (append tests)

**Interfaces:**
- Consumes: nothing new (pure function, no imports beyond `re` which is already imported in the file)
- Produces: `parse_inventory(text: str) -> list[dict] | None` — each dict is `{"name": str, "count": int}`. `None` for unrelated text, `[]` for a confirmed-empty inventory. Task 3 (tracker) and Task 4 (wiring) depend on this exact signature and return contract.

Stock CircleMUD `inventory` output looks like:
```
You are carrying:
( 2) a Black Pawn's Sword
some Black Pawn Armor
a shiny newbie dagger ..It has a soft glowing aura!
```
- A line optionally starts with `(\s*N\s*)` (count prefix); the rest of the line (trimmed) is the item name, kept as-is including any `..aura` suffix.
- Header line is `"You are carrying:"` (case-insensitive) — its presence is what distinguishes "empty inventory" (`[]`) from "unrelated text" (`None`).
- An empty inventory reads `"You are not carrying anything."` — no header line, no item lines: this must return `[]` too since real CircleMUD servers on this codebase phrase it this way. Treat any text matching `"you are (not carrying anything|carrying:)"` (case-insensitive) as valid inventory output.

- [ ] **Step 1: Write the failing tests**

Append to `tests/test_equipment_parser.py` (add `parse_inventory` to the existing `from boukensha.memory.equipment_parser import parse_equipment, parse_identify` import line at the top, making it `from boukensha.memory.equipment_parser import parse_equipment, parse_identify, parse_inventory`):

```python
def test_parse_inventory_extracts_counted_and_uncounted_items():
    text = (
        "You are carrying:\n"
        "( 2) a Black Pawn's Sword\n"
        "some Black Pawn Armor\n"
        "a shiny newbie dagger ..It has a soft glowing aura!\n"
    )
    assert parse_inventory(text) == [
        {"name": "a Black Pawn's Sword", "count": 2},
        {"name": "some Black Pawn Armor", "count": 1},
        {"name": "a shiny newbie dagger ..It has a soft glowing aura!", "count": 1},
    ]


def test_parse_inventory_returns_empty_list_for_carrying_nothing():
    assert parse_inventory("You are not carrying anything.\n") == []


def test_parse_inventory_returns_empty_list_for_header_with_no_items():
    assert parse_inventory("You are carrying:\n") == []


def test_parse_inventory_returns_none_for_unrelated_text():
    assert parse_inventory("You aren't holding that item.\n") is None


def test_parse_inventory_returns_none_for_empty_string():
    assert parse_inventory("") is None


def test_parse_inventory_strips_trailing_whitespace_from_item_name():
    text = "You are carrying:\n( 3) a torch   \n"
    assert parse_inventory(text) == [{"name": "a torch", "count": 3}]
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `cd week3_capable/agent-exp && uv run pytest tests/test_equipment_parser.py -k parse_inventory -v`
Expected: FAIL with `ImportError` or `NameError: name 'parse_inventory' is not defined`

- [ ] **Step 3: Write the implementation**

Add to `src/boukensha/memory/equipment_parser.py`, after `parse_equipment` (after line 139, before the `# ── 'identify' output` section header):

```python
# ── 'inventory' output ───────────────────────────────────────────────────────

_INVENTORY_HEADER_RE = re.compile(r"you are (carrying:|not carrying anything)", re.IGNORECASE)
_INVENTORY_COUNT_RE = re.compile(r"^\(\s*(\d+)\s*\)\s*(.+)$")


def parse_inventory(text: str) -> list[dict] | None:
    """Parse 'inventory' command output into [{"name": str, "count": int}, ...].

    Returns ``None`` when the text isn't inventory output at all (unrelated
    command), and ``[]`` when it IS inventory output but nothing is carried
    ("You are not carrying anything.") — same None-vs-empty contract as
    ``parse_equipment``.
    """
    if not _INVENTORY_HEADER_RE.search(text):
        return None

    items: list[dict] = []
    for line in text.splitlines():
        stripped = line.strip()
        if not stripped or _INVENTORY_HEADER_RE.search(stripped):
            continue
        m = _INVENTORY_COUNT_RE.match(stripped)
        if m:
            items.append({"name": m.group(2).strip(), "count": int(m.group(1))})
        else:
            items.append({"name": stripped, "count": 1})
    return items
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `cd week3_capable/agent-exp && uv run pytest tests/test_equipment_parser.py -v`
Expected: PASS (all tests in the file, including the pre-existing equipment/identify ones — confirms no regression)

- [ ] **Step 5: Commit**

```bash
cd week3_capable/agent-exp
git add src/boukensha/memory/equipment_parser.py tests/test_equipment_parser.py
git commit -m "feat: add parse_inventory for carried-item text"
```

---

### Task 2: `PlayerTracker.update_inventory`

**Files:**
- Modify: `src/boukensha/memory/player_tracker.py`
- Test: `tests/test_player_tracker.py` (append tests)

**Interfaces:**
- Consumes: nothing new
- Produces: `PlayerTracker.update_inventory(name: str, items: list[dict]) -> None`. Writes `data[name]["inventory"] = items` and `data[name]["inventory_updated_at"] = <iso timestamp>`, merging into the existing per-player record (same as `update_equipment`). Task 3 (wiring) depends on this exact method name and signature.

- [ ] **Step 1: Write the failing tests**

Append to `tests/test_player_tracker.py`:

```python
def test_update_inventory_records_items_for_new_player(tmp_path):
    tracker = PlayerTracker(tmp_path)
    tracker.update_inventory("Hero", [{"name": "a torch", "count": 1}])
    data = tracker.read_all()
    assert data["Hero"]["inventory"] == [{"name": "a torch", "count": 1}]
    assert "inventory_updated_at" in data["Hero"]


def test_update_inventory_preserves_existing_position_stats_and_equipment(tmp_path):
    tracker = PlayerTracker(tmp_path)
    tracker.update("Hero", "abc123", "Temple Square")
    tracker.update_stats("Hero", {"hp": 20, "max_hp": 20})
    tracker.update_equipment("Hero", {"finger": "a gold ring"})
    tracker.update_inventory("Hero", [{"name": "a torch", "count": 1}])
    data = tracker.read_all()
    assert data["Hero"]["room_hash"] == "abc123"
    assert data["Hero"]["stats"]["hp"] == 20
    assert data["Hero"]["equipment"] == {"finger": "a gold ring"}
    assert data["Hero"]["inventory"] == [{"name": "a torch", "count": 1}]


def test_update_inventory_overwrites_previous_snapshot(tmp_path):
    tracker = PlayerTracker(tmp_path)
    tracker.update_inventory("Hero", [{"name": "a torch", "count": 1}])
    tracker.update_inventory("Hero", [{"name": "a sword", "count": 1}])
    data = tracker.read_all()
    assert data["Hero"]["inventory"] == [{"name": "a sword", "count": 1}]
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `cd week3_capable/agent-exp && uv run pytest tests/test_player_tracker.py -k update_inventory -v`
Expected: FAIL with `AttributeError: 'PlayerTracker' object has no attribute 'update_inventory'`

- [ ] **Step 3: Write the implementation**

Add to `src/boukensha/memory/player_tracker.py`, after `update_equipment` (after line 48):

```python
    def update_inventory(self, name: str, items: list[dict[str, Any]]) -> None:
        data = self.read_all()
        existing = data.get(name, {})
        data[name] = {
            **existing,
            "inventory": items,
            "inventory_updated_at": datetime.now(timezone.utc).isoformat(),
        }
        self._write(data)
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `cd week3_capable/agent-exp && uv run pytest tests/test_player_tracker.py -v`
Expected: PASS (all tests in the file)

- [ ] **Step 5: Commit**

```bash
cd week3_capable/agent-exp
git add src/boukensha/memory/player_tracker.py tests/test_player_tracker.py
git commit -m "feat: add PlayerTracker.update_inventory"
```

---

### Task 3: Wire `check(kind="inventory")` to persist via `_check_and_record`

**Files:**
- Modify: `src/boukensha/tools/mud.py:69` (import), `src/boukensha/tools/mud.py:557-588` (`_check_and_record`)
- Test: `tests/test_tools_mud.py` (append tests)

**Interfaces:**
- Consumes: `parse_inventory` (Task 1), `PlayerTracker.update_inventory` (Task 2)
- Produces: `check(kind="inventory")` now persists to `players.json` under the `inventory` key. Nothing downstream in this plan depends on this beyond the dashboard reading `players.json` (Task 5), which needs no code change since `/api/players`/`/api/overview` already pass through the full dict.

- [ ] **Step 1: Write the failing tests**

Append to `tests/test_tools_mud.py` (near the existing `test_check_equipment_*` tests around line 1061 — same file, same `_make_registry`/`Mud._register_with_session` helpers already used throughout):

```python
def test_check_inventory_persists_items_to_player_tracker(tmp_path):
    registry = _make_registry()
    mock_session = MagicMock()
    mock_session.is_open = True
    mock_session.drain.return_value = ""
    mock_session.read_until_prompt.return_value = (
        "You are carrying:\n"
        "( 2) a Black Pawn's Sword\n"
        "a shiny newbie dagger\n"
        "> "
    )
    Mud._register_with_session(
        registry, mock_session, name="Tester", password="secret", memory_dir=tmp_path
    )
    registry.dispatch("check", {"kind": "inventory"})

    from boukensha.memory.player_tracker import PlayerTracker
    data = PlayerTracker(tmp_path).read_all()
    assert data["Tester"]["inventory"] == [
        {"name": "a Black Pawn's Sword", "count": 2},
        {"name": "a shiny newbie dagger", "count": 1},
    ]


def test_check_inventory_without_memory_dir_does_not_crash():
    registry = _make_registry()
    mock_session = MagicMock()
    mock_session.is_open = True
    mock_session.drain.return_value = ""
    mock_session.read_until_prompt.return_value = "You are carrying:\na torch\n> "
    Mud._register_with_session(registry, mock_session, name="Tester", password="secret")
    result = registry.dispatch("check", {"kind": "inventory"})
    assert "a torch" in result


def test_check_inventory_with_nothing_carried_records_empty_list(tmp_path):
    from boukensha.memory.player_tracker import PlayerTracker
    # A previously recorded snapshot must be cleared, not left stale.
    PlayerTracker(tmp_path).update_inventory("Tester", [{"name": "a torch", "count": 1}])

    registry = _make_registry()
    mock_session = MagicMock()
    mock_session.is_open = True
    mock_session.drain.return_value = ""
    mock_session.read_until_prompt.return_value = "You are not carrying anything.\n> "
    Mud._register_with_session(
        registry, mock_session, name="Tester", password="secret", memory_dir=tmp_path
    )
    result = registry.dispatch("check", {"kind": "inventory"})
    assert "not carrying" in result
    assert PlayerTracker(tmp_path).read_all()["Tester"]["inventory"] == []


def test_check_non_inventory_output_does_not_clobber_recorded_snapshot(tmp_path):
    from boukensha.memory.player_tracker import PlayerTracker
    PlayerTracker(tmp_path).update_inventory("Tester", [{"name": "a torch", "count": 1}])

    registry = _make_registry()
    mock_session = MagicMock()
    mock_session.is_open = True
    mock_session.drain.return_value = ""
    mock_session.read_until_prompt.return_value = "Huh?!?\n> "
    Mud._register_with_session(
        registry, mock_session, name="Tester", password="secret", memory_dir=tmp_path
    )
    registry.dispatch("check", {"kind": "inventory"})
    assert PlayerTracker(tmp_path).read_all()["Tester"]["inventory"] == [
        {"name": "a torch", "count": 1}
    ]
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `cd week3_capable/agent-exp && uv run pytest tests/test_tools_mud.py -k inventory -v`
Expected: FAIL — `data["Tester"]` has no `"inventory"` key (KeyError), since nothing persists it yet.

- [ ] **Step 3: Write the implementation**

In `src/boukensha/tools/mud.py:69`, change:
```python
from boukensha.memory.equipment_parser import _item_lookup_key, parse_equipment, parse_identify
```
to:
```python
from boukensha.memory.equipment_parser import _item_lookup_key, parse_equipment, parse_identify, parse_inventory
```

In `_check_and_record` (`src/boukensha/tools/mud.py:557-588`), add an `elif` branch after the existing `equipment` branch (after line 587, before the `return raw` on line 588):

```python
            elif k == "inventory" and not raw.startswith("error:"):
                items = parse_inventory(raw)
                if items is not None and tracker is not None:
                    tracker.update_inventory(name, items)
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `cd week3_capable/agent-exp && uv run pytest tests/test_tools_mud.py -v`
Expected: PASS (all tests in the file — confirms no regression to the score/equipment branches)

- [ ] **Step 5: Commit**

```bash
cd week3_capable/agent-exp
git add src/boukensha/tools/mud.py tests/test_tools_mud.py
git commit -m "feat: persist check(kind=inventory) results to PlayerTracker"
```

---

### Task 4: Full test suite sanity check

**Files:** none (verification only)

**Interfaces:**
- Consumes: Tasks 1-3 combined
- Produces: confirmation the whole suite is green before touching the dashboard.

- [ ] **Step 1: Run the full test suite**

Run: `cd week3_capable/agent-exp && uv run pytest tests/ -v`
Expected: PASS, 0 failures (this repo's existing suite plus the new tests from Tasks 1-3)

- [ ] **Step 2: Commit**

Nothing to commit (verification-only task) — if this step reveals a failure, fix it and fold the fix into whichever of Tasks 1-3 it belongs to, then re-run.

---

### Task 5: Inventory tab — HTML + nav

**Files:**
- Modify: `src/boukensha/dashboard/templates/index.html`

**Interfaces:**
- Consumes: nothing (static markup)
- Produces: `<button class="tab-btn" data-tab="inventory">Inventory</button>` in `<nav id="tabs">`, and `<section id="tab-inventory" class="tab-pane"><div id="inventory-cards"></div></section>`. Task 6 (JS) depends on the exact ids `tab-inventory` and `inventory-cards`.

This is a markup-only task with no automated test (the existing dashboard has no HTML/JS test harness — Score/Map/Waterfall tabs were added the same way, verified by manual browser check). Manual verification happens in Task 7 once the JS is wired up.

- [ ] **Step 1: Add the nav button**

In `src/boukensha/dashboard/templates/index.html`, in `<nav id="tabs">` (lines 11-19), add a new button after the Score button:

```html
    <button class="tab-btn" data-tab="score">Score</button>
    <button class="tab-btn" data-tab="inventory">Inventory</button>
```
(replacing just the `<button class="tab-btn" data-tab="score">Score</button>` line with both lines)

- [ ] **Step 2: Add the tab section**

After the `<section id="tab-score" class="tab-pane">...</section>` block (lines 27-29), add:

```html
  <section id="tab-inventory" class="tab-pane">
    <div id="inventory-cards"></div>
  </section>
```

- [ ] **Step 3: Commit**

```bash
cd week3_capable/agent-exp
git add src/boukensha/dashboard/templates/index.html
git commit -m "feat: add Inventory tab markup to dashboard"
```

---

### Task 6: Inventory tab — JS + CSS

**Files:**
- Modify: `src/boukensha/dashboard/static/app.js`
- Modify: `src/boukensha/dashboard/static/style.css`

**Interfaces:**
- Consumes: `/api/players` (existing endpoint, now includes `equipment` and `inventory` keys per player after Task 3), `escapeHtml` (existing helper, `app.js:1`)
- Produces: `loadInventory()` function, wired into the tab-click dispatcher and the SSE `check`-result handler. Task 7 (manual verification) depends on this being called correctly.

- [ ] **Step 1: Add the tab-click dispatch line**

In `src/boukensha/dashboard/static/app.js`, in the tab-click handler (lines 10-22), add a line after the `score` dispatch:

```javascript
    if (btn.dataset.tab === 'score') loadScore();
    if (btn.dataset.tab === 'inventory') loadInventory();
```
(insert the `inventory` line right after the existing `score` line)

- [ ] **Step 2: Add `loadInventory()`**

After the `loadScore()` function (after line 172, before the `// Goals tab` comment on line 174), add:

```javascript
// Inventory tab
function equipmentList(equipment) {
  const entries = Object.entries(equipment || {});
  if (!entries.length) return '<p class="overview-empty">Nothing equipped.</p>';
  return '<ul class="inventory-list">' + entries.map(([slot, item]) =>
    `<li><span class="inventory-slot">${escapeHtml(slot)}</span> ${escapeHtml(item)}</li>`
  ).join('') + '</ul>';
}

function carriedList(inventory) {
  if (inventory == null) return '<p class="overview-empty">Inventory not yet checked.</p>';
  if (!inventory.length) return '<p class="overview-empty">Not carrying anything.</p>';
  return '<ul class="inventory-list">' + inventory.map(item =>
    `<li>${escapeHtml(item.name)}${item.count > 1 ? ` <span class="inventory-count">×${item.count}</span>` : ''}</li>`
  ).join('') + '</ul>';
}

async function loadInventory() {
  const el = document.getElementById('inventory-cards');
  const r = await fetch('/api/players');
  const players = await r.json();
  if (!players.length) {
    el.innerHTML = '<p class="overview-empty">No players tracked yet.</p>';
    return;
  }
  el.innerHTML = players.map(p => `<div class="score-card">
    <div class="score-card-header"><span class="score-card-name">${escapeHtml(p.name)}</span></div>
    <div class="inventory-columns">
      <div>
        <div class="inventory-column-label">Equipped</div>
        ${equipmentList(p.equipment)}
      </div>
      <div>
        <div class="inventory-column-label">Carrying</div>
        ${carriedList(p.inventory)}
      </div>
    </div>
  </div>`).join('');
}
```

- [ ] **Step 3: Piggyback on the SSE `check`-result refresh**

In `src/boukensha/dashboard/static/app.js`, in the SSE handler's Score-tab refresh block (lines 78-83), extend it to also refresh Inventory:

Replace:
```javascript
  if (event.phase === 'tool_result' && event.name === 'check') {
    const scoreTab = document.getElementById('tab-score');
    if (scoreTab && scoreTab.classList.contains('active')) {
      loadScore();
    }
  }
```
with:
```javascript
  if (event.phase === 'tool_result' && event.name === 'check') {
    const scoreTab = document.getElementById('tab-score');
    if (scoreTab && scoreTab.classList.contains('active')) {
      loadScore();
    }
    const inventoryTab = document.getElementById('tab-inventory');
    if (inventoryTab && inventoryTab.classList.contains('active')) {
      loadInventory();
    }
  }
```

- [ ] **Step 4: Add CSS for the two-column layout**

In `src/boukensha/dashboard/static/style.css`, after the existing `.score-flags` rule (line 139), add:

```css
.inventory-columns { display: flex; gap: 24px; margin-top: 4px; }
.inventory-columns > div { flex: 1; min-width: 0; }
.inventory-column-label { color: #888; font-size: 11px; text-transform: uppercase; letter-spacing: 0.05em; margin-bottom: 6px; }
.inventory-list { list-style: none; margin: 0; padding: 0; color: #ccc; font-size: 13px; line-height: 1.6; }
.inventory-slot { color: #4af; text-transform: capitalize; margin-right: 6px; }
.inventory-count { color: #888; }
```

- [ ] **Step 5: Commit**

```bash
cd week3_capable/agent-exp
git add src/boukensha/dashboard/static/app.js src/boukensha/dashboard/static/style.css
git commit -m "feat: render Inventory tab (equipped + carried items)"
```

---

### Task 7: Manual verification against the live dashboard

**Files:** none (verification only)

**Interfaces:**
- Consumes: Tasks 5-6 combined, plus a running `boukensha --web` instance
- Produces: confirmation the feature actually works end-to-end, not just unit-tested.

- [ ] **Step 1: Start the dashboard**

Run: `cd week3_capable/agent-exp && uv run python bin/boukensha --web --no-tui` (or attach to whatever session is already running with `--web`) and open `http://localhost:4568`.

- [ ] **Step 2: Trigger an inventory check**

If a live MUD session is connected, have the agent (or send manually via REPL) run `check(kind="inventory")` for the tracked character. If no live session is available, seed data directly:

```bash
cd week3_capable/agent-exp
uv run python -c "
from boukensha.memory.player_tracker import PlayerTracker
import os
t = PlayerTracker(os.path.expanduser('PATH_TO_.boukensha/memory'))
t.update_equipment('dummy', {'wield': 'a small sword', 'body': 'a breast plate'})
t.update_inventory('dummy', [{'name': 'a torch', 'count': 1}, {'name': \"a Black Pawn's Sword\", 'count': 2}])
"
```
(substitute the real `.boukensha/memory` path for the running instance)

- [ ] **Step 3: Click the Inventory tab and verify**

Confirm:
- The "Inventory" button appears in the nav, between Score and Live.
- Clicking it shows a card per tracked player with "Equipped" and "Carrying" columns.
- Equipped shows slot names and item descriptions; Carrying shows item names with `×N` counts for count > 1 and no count suffix for count == 1.
- No JS console errors (open browser devtools).

- [ ] **Step 4: Verify live SSE refresh**

With the Inventory tab open and a live agent session running, trigger another `check(kind="inventory")` from the agent and confirm the tab's contents update without a manual click/refresh.

- [ ] **Step 5: Report result**

No commit for this task (verification only). If any check in Steps 3-4 fails, fix the issue in whichever of Tasks 5-6 it belongs to and re-run this task.
