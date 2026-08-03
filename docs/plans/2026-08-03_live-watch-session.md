# 2026-08-03 — Live-watch session: bank/ATM, combat_loop, wait tool, danger detection

## Goal for the session

Start `boukensha` (`week3_capable/agent-exp`) with `--web`, watch it play live via
tmux + the dashboard Live tab, and check it against a checklist:

- Keep leveling up.
- Go back to town when thirsty/hungry.
- Train at its guild on level-up.
- Deposit excess gold at an ATM.
- Explore fully — notice and record "interesting" details the MUD calls out.
- Find a light source for dark areas.
- Eventually fight a Minotaur, but only once level 7+ with good equipment.
- Keep an eye on Anthropic API spend.

Two things were flagged up front as likely missing from the codebase: gold
banking, and reasoning toward finding the Minotaur. Both turned out to be
real gaps, confirmed by reading `prompts/system.md` and `src/boukensha/tools/`
before making any change.

## Changes made, in the order they came up

### 1. Added a `bank` tool + prompt guidance (gold/ATM)

No banking tool existed at all. Added `bank(action="deposit"|"withdraw"|"balance",
amount=...)` in `src/boukensha/tools/mud.py`, mapped directly to CircleMUD's
`deposit <amount>` / `withdraw <amount>` / `balance` commands. Added a new
"Carrying too much gold" section to `prompts/system.md`.

**Correction mid-session:** the user pointed out there's probably no dedicated
bank *room*. Checked the actual world data in
`week0_explore/circlemud-world-parser/assets/` and confirmed it: object
`#3034` ("an automatic teller machine") is placed as a wall fixture in six
ordinary rooms — the Temple, Reception, and each guild's entrance hall — not
a destination of its own. Rewrote the prompt section and the tool's own
description to say so explicitly ("no separate bank room — watch for an ATM
mentioned in room text, especially at your own guild"). Sent a live
correction to the running agent, which had already started planning to
`explore()`/`navigate_to` a nonexistent "bank." Next attempt, it found the
ATM in its guild's entrance hall and deposited correctly.

### 2. Added prompt guidance for light sources, noticing details, resting, and the Minotaur

`prompts/system.md` additions:
- **Dark rooms and light sources** — `explore`/`navigate_to` already refused
  to walk into dark rooms and marked them blocked, but nothing told the
  agent *why*, or that buying/equipping a torch from a shop resolves it.
- **Noticing interesting details** — the `examine` and `knowledge_add` tools
  already existed but nothing prompted the agent to use them proactively
  when room text calls out something notable.
- **Resting to recover HP and movement** — `set_position(position="rest"/"sleep")`
  existed but was never mentioned in the prompt at all.
- **Long-term goal: the Minotaur** — told the agent to defer any Minotaur
  fight until level 7+ with good equipment, and (per user feedback) to
  actively reason toward finding it: get a light source early, then treat
  newly-opened dark areas as the likely search target, following any
  in-game clues (signs, NPC hints).

Confirmed working live: the agent found and equipped a torch, pushed into a
previously dark stairway, and discovered an in-game sign confirming the
level-7 requirement — recorded via `knowledge_add`.

### 3. Fixed `combat_loop`'s false "target fled" bug

**Symptom seen on the Live tab:** the agent attacked a mob, `combat_loop`
reported "no combat activity — it likely fled," but a subsequent `move`
got `"No way! You're fighting for your life!"` — i.e. it was still actually
fighting. The agent misdiagnosed this as a stale-cache issue and got stuck.

**Root cause** (confirmed from the raw session JSONL transcript): the
quiet-round heuristic in `src/boukensha/tools/combat.py` only recognized a
fixed list of hit/miss/dodge keyword phrases as "activity." This particular
mob's round text didn't match any of them, so after 3 "quiet" reads the loop
assumed the mob had fled — while the fight was still genuinely ongoing.

**Fix:** before declaring "fled," the loop now re-issues the attack and
reads the MUD server's own unambiguous answer: `"You're fighting the best
you can!"` means it's a false alarm (keep going); anything else (dead, or
"don't see them") is trusted. This uses the game's own ground truth instead
of a keyword guess. Added a regression test for the false-positive case and
updated the existing "really did flee" test to include the new probe step.

### 4. Added a `wait` tool (missing capability)

**Symptom:** the agent got stuck at 0 movement, tried `rest`/`sleep`, and
kept calling `check(kind="score")` — which showed *zero* recovery across
several calls — and concluded it was soft-locked, asking for user help.

**Root cause:** there was no way for the agent to intentionally let real
wall-clock time pass. Tool calls return almost instantly, so several
`check` calls in a row can easily happen inside a single MUD server regen
tick, showing no change — not because regen is broken, but because no real
time actually elapsed between checks.

**Fix:** added `wait(seconds=1-90, default 30)` to `src/boukensha/tools/mud.py` —
sleeps for real time, then automatically reports fresh `score`. Added prompt
guidance explaining regen is server-clock-based, not tool-call-based. Added
3 new tests (mocking `time.sleep` so the suite stays fast).

Confirmation this was the right read: by the time the app was restarted
minutes later, the character's HP/movement had *already* fully regenerated
on their own from the server's background ticks — proving it was never a
soft lock, just no way for the agent to choose to wait.

### 5. Fixed a real safety gap in `combat_loop`'s danger detection

**Symptom:** HP dropped to -9 ("You are in a pretty bad shape, unable to do
anything!"), gold went to 0, and the entire inventory was wiped — a death
or near-death, not a normal fight.

**Root cause:** the agent attacked a "gelatinous blob" that `consider`
answered with `"You ARE mad!"` — stock CircleMUD's single most severe
consider-danger response (`diff <= 100` tier in `do_consider`). The
`_DANGER_PATTERNS` safety-gate list in `combat.py` covered several danger
phrases (`"do you feel lucky"`, `"certain death"`, etc.) but not CircleMUD's
own top two tiers (`"Are you mad!?"` / `"You ARE mad!"`), so the gate let
the fight through.

**Fix:** added `"mad!"` to `_DANGER_PATTERNS` (matches both stock strings).
Added a regression test. This is the most safety-relevant fix from the
session — everything else was efficiency/correctness, this one was actual
character harm.

## Test results

Full suite after all changes: **436 passed**, same 4 pre-existing failures
in `tests/test_room_parser.py` (unrelated to anything touched today — not
investigated further this session).

## Operational notes

- The Textual TUI's text input can lose keyboard focus after the app stops
  a turn on its own (hitting the auto-continue cap, or the `stuck_repetition`
  guard) — typed input silently drops until you press `Tab` to refocus.
  Worth fixing or at least documenting for anyone driving it by hand.
- A code fix doesn't apply to an already-running process — after the
  `combat_loop` and `wait` fixes, the app was restarted (`tmux kill-session`
  + relaunch) to pick up the change. MUD character state (HP, position,
  gold, inventory) lives on the CircleMUD server, so restarting the local
  process is safe and just reconnects the same character where it left off.
- Total Anthropic spend across all historical sessions by the end of this
  session: **~$3.83** (claude-haiku-4-5). Cost tracking via the dashboard's
  `/api/sessions` and `/api/overview` endpoints was useful for watching this
  in near-real-time.

## State at end of session

Stopped intentionally (`tmux kill-session -t boukensha`) for later testing.
Character was alive but wounded (17/66 HP) at "The Tournament And Practice
Yard" after the near-death fight above, before HP guidance had it back out
resting. Level 4, 7280 exp, 0 gold (lost in the death/near-death), 123 rooms
known. Next session should pick up from there — HP will have regenerated
further on the server's own clock in the meantime.
