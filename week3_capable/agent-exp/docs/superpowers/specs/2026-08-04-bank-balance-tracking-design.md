# Track and display bank balance alongside on-hand gold

## Problem

The dashboard's Overview tab shows on-hand gold (`s.gold`, from `score`)
but nothing about how much is banked at the ATM. Since the gold-deposit
advisory ([[2026-08-04-gold-deposit-advisory-design]]) started nudging
the agent to bank half its gold once it crosses a threshold, there's no
way to see from the dashboard whether that's actually happening or how
much has accumulated in the bank.

CircleMUD's `deposit`/`withdraw` replies don't include the new bank
total ("You deposit 135 coins." — just the transacted amount); only
`balance` does ("Current balance: 200 coins." — confirmed by the
existing `test_bank_balance_ignores_amount` fixture).

## Scope

- Track a `bank_gold` figure per character, persisted the same way
  `hp`/`gold`/`level` etc. already are (`PlayerTracker.update_stats`).
- Show it on the Overview tab's score card, next to on-hand gold.
- `deposit`/`withdraw` automatically trigger a follow-up `balance` query
  so the tracked figure is always the server's authoritative number,
  never inferred/added-up client-side.

## Design

### 1. `_parse_bank_balance` (`src/boukensha/tools/mud.py`)

```python
_BANK_BALANCE_RE = re.compile(r"balance:?\s*([\d,]+)\s*coins?", re.IGNORECASE)

def _parse_bank_balance(text: str) -> int | None:
    m = _BANK_BALANCE_RE.search(text)
    if not m:
        return None
    return int(m.group(1).replace(",", ""))
```

### 2. `_bank` becomes a closure with tracker access

Currently `_bank(session, action, amount)` is a free module-level
function with no access to `tracker`/`name`. Add a closure
`_bank_and_record` inside `Mud._register_with_session` (same pattern as
the existing `_check_and_record`), and register the `bank` tool against
it instead of the bare `_bank`:

```python
def _bank_and_record(action: str, amount: int | None) -> str:
    result = _bank(session, action, amount)
    if result.startswith("error:"):
        return result
    act = action.strip().lower()
    if act == "balance":
        balance_text = result
    else:
        # deposit/withdraw replies don't carry the new total — ask.
        balance_text = _bank(session, "balance", None)
    balance = _parse_bank_balance(balance_text)
    if balance is not None and tracker is not None:
        previous = (tracker.read_all().get(name) or {}).get("stats") or {}
        tracker.update_stats(name, {**previous, "bank_gold": balance})
        if act != "balance":
            result += f"\n\n[Bank balance] You now have {balance} coins in the bank."
    return result
```

Register: `block=lambda action, amount=None, **_: _bank_and_record(action, amount)`.

`_bank` itself is unchanged — still the raw send/guard/enum-check logic,
just no longer registered directly.

### 3. Dashboard (`src/boukensha/dashboard/static/app.js`)

In `loadScore()`, next to the existing gold line:

```js
${'gold' in s ? `<div class="score-gold">${s.gold} gold${'bank_gold' in s ? ` · ${s.bank_gold} banked` : ''}</div>` : ''}
```

No backend/API changes — `/api/players` already passes the `stats`
dict straight through.

### 4. Style

No new CSS class needed; reuses `.score-gold`.

## Testing

- `_parse_bank_balance`: matches `"Current balance: 200 coins."` → 200;
  handles comma-thousands (`"1,500 coins"`) → 1500; returns `None` on
  no match.
- `bank(action="balance")` persists `bank_gold` to the tracker and does
  NOT append the extra `[Bank balance]` line (the raw response already
  said it).
- `bank(action="deposit", amount=100)` triggers a second `send_command`
  call (`"balance"`), persists the parsed `bank_gold`, and appends the
  `[Bank balance]` line to the result.
- `bank` without a `memory_dir`/tracker configured still works
  unchanged (no crash, no persistence attempted).

## Non-goals

- Adding a bank balance to the raw `score` command's output (CircleMUD
  doesn't include it there; only a live `balance` query has it).
- Reconciling/inferring bank_gold from deposit/withdraw amounts instead
  of querying — always ask the server for ground truth.
