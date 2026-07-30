# Auto-loot corpse after combat

## Problem

Killing a monster currently requires a second, manual tool call (`get_item`
with `item="all", container="corpse"`) to loot the corpse. The agent has to
remember to do this every time, and forgetting it silently leaves gold/items
behind. We want `combat_loop` to loot automatically on a kill so the agent
gets kill confirmation and loot in a single tool call, matching the manual
transcript:

```
> kill newbie monster
...you have slain the newbie monster...
> get all corpse
You get a handful of gold coins from the corpse of the newbie monster.
...
```

## Scope

- Auto-loot the corpse immediately after a kill inside `combat_loop`.
- Do NOT auto-handle hunger/thirst.
- Do NOT auto-match keys to doors — looted keys just appear in the loot
  text (like the vest did in the transcript); the agent decides when to
  use `door` with a found key.
- Looting only happens on the death branch. The flee branch (HP threshold
  reached) never loots, since there is no corpse yet.

## Design

`src/boukensha/tools/combat.py`, function `_combat_loop`:

1. Add a new parameter `auto_loot: bool = True` to `combat_loop`.
2. When the death patterns are detected (existing `_DEAD_PATTERNS` check),
   and `auto_loot` is true, send `get all corpse` via the existing
   `_get_item` helper from `boukensha.tools.mud` (already imported into
   this module for `_match_npc` / `_no_living_target_message`), then
   append its response to the returned string:

   ```
   Combat complete: {target} defeated after {rounds} round(s).
   Loot: {loot_response}
   ```

3. If `auto_loot=False`, return the existing message unchanged (no loot
   attempt) — for cases where the agent wants to `look in corpse` first
   before deciding what to grab.
4. No special-casing of "nothing to loot" / "already looted" responses —
   the MUD's own response text (e.g. "You didn't find anything.") passes
   through as-is.

## Testing

- Existing `combat_loop` tests should continue to pass unchanged (default
  `auto_loot=True` must not break tests that don't expect a loot step —
  if any do, update their session mocks to also handle `get all corpse`).
- New test: on a kill, verify `get all corpse` is sent and its response is
  included in the returned string.
- New test: `auto_loot=False` suppresses the loot attempt entirely (no
  `get all corpse` command sent).

## Non-goals

- Hunger/thirst automation.
- Auto key-to-door matching.
- Looting from anything other than the freshly-killed target's corpse.
