# Step 13 — Memory

When you call an LLM directly you are responsible for the context window. There is no auto-compacting. This step adds proper token tracking, visual warnings, and automatic compaction so the agent never silently blows past the limit.

## What's new

### Accurate context tracking

`Context` now maintains two distinct token counts:

| Attribute | What it measures |
|-----------|-----------------|
| `context_window` | The model's maximum input token capacity (default 200,000 for Anthropic) |
| `current_tokens` | Tokens actually used in the most recent API call (`usage.input_tokens` from the response) |

Previously `token_budget` (8,192) was displayed as the limit — that was the *output* `max_tokens`, not the context window. And the cumulative session token sum was shown as usage, which grew without bound even after `/clear`. Both are fixed.

The Agent updates `current_tokens` after every API response (including mid-turn tool-use calls), so the display always reflects what the next call will actually send.

### Context colour coding

The progress and status lines now colour the context indicator based on how full the window is:

| Usage | Colour | Meaning |
|-------|--------|---------|
| < 70% | Grey | Normal |
| 70–84% | Yellow | Approaching limit |
| ≥ 85% | Red | Compaction imminent |

A `⚠` symbol also appears in the status bar at 85%+.

### Auto-compaction

At the start of each agent turn, if `current_tokens / context_window >= 0.85`, the Agent automatically compacts the context before making any API call:

```
[context compacted — 12 messages dropped to free space]
```

Compaction drops the oldest 40% of messages (keeping at least 2) and resets `current_tokens` to 0. The first API call after compaction will report the true new size.

### `Context.compact_messages()`

```python
dropped = context.compact_messages(target_fraction=0.60)
# => 12  (number of messages dropped)
```

### `/compact` command

Manual compaction from the REPL or TUI:

```
boukensha> /compact
(compacted context — 12 messages dropped)
```

### Logger `compaction` event

```json
{"phase": "compaction", "before": 172000, "dropped": 12, "context_window": 200000}
```

Emitted whenever auto- or manual compaction runs. The TUI subscribes to this event to display the compaction notice in the conversation view.

### `boukensha.repl()` — `context_window=` parameter

`token_budget` is replaced by `context_window` (default `200_000`):

```python
boukensha.repl(context_window=128_000)  # for a smaller model
```

## Smart navigation and vitals

### Affordance tags

Each room carries a set of capability tags that describe what the agent can do there: `can_drink`, `can_eat`, `can_rest`, and `can_heal`. Tags are inferred automatically from the room description when it is first observed — keywords like "fountain", "well", or "stream" imply `can_drink`; "bakery", "inn", or "tavern" imply `can_eat`; and so on. When the agent successfully drinks or eats in a room, the relevant tag is confirmed and persisted to the map file so that future sessions start with it already set.

### `map_find_capability` tool

A new navigation tool finds the nearest room matching a capability keyword:

```
map_find_capability("drink")   # => "Go north, then west to reach the Fountain Plaza"
map_find_capability("eat")     # => "You are already in a room where you can eat"
```

`map_path_to` also falls back to capability matching when no room name exactly matches the requested destination — so `map_path_to("fountain")` will route to the nearest `can_drink` room if no room is literally named "fountain".

### Loop detection

`map_here` tracks the last several rooms visited. If the agent revisits the same room too many times in a short window, the output includes a `⚠ loop warning` notice so the agent knows to try a different route.

### VitalsTracker and hint injection

`VitalsTracker` (in `src/boukensha/tools/vitals.py`) passively monitors every MUD response for thirst/hunger phrases and for HP values from `score` output. When HP is low or the character is thirsty or hungry, it returns a one-line hint string.

The `Agent` injects this hint as a synthetic `tool_result` message immediately after each tool batch, before the next model call. The system prompt instructs the agent to treat `[vitals]` hints as highest-priority directives: call `map_find_capability` with the suggested capability, navigate there, and address the need before resuming other activity.

## Run the demo

```sh
cd week1_baseline/python/13_memory
uv sync

# TUI (default):
uv run python examples/example.py

# Plain REPL:
uv run python examples/example.py --no-tui
```

## Tests

```sh
uv run pytest tests/ -v
```
