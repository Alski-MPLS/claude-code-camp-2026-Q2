# Boukensha Web Dashboard

A five-tab Flask application that shows what the agent is doing in real time.

## Starting the dashboard

Pass `--web` when launching the agent:

```sh
python bin/boukensha --web
```

The dashboard starts in a background daemon thread and is available immediately:

```
http://localhost:4568
```

Use `--port` to change the port:

```sh
python bin/boukensha --web --port 4569
```

## Tabs

### Overview

Landing tab. Summary cards for rooms known, frontier exits (known-but-unmapped), and unique entities (mobs/objects) seen across every recorded room, plus each tracked player's last-known HP/mana/move and current location (with where they came from).

Data endpoint: `GET /api/overview`

```json
{
  "rooms_known": 26,
  "frontier": {"known_exits": 73, "walked": 32, "frontier": 41},
  "entities": {"mobs": 16, "objects": 3, "total": 19},
  "players": [
    {
      "name": "Hero",
      "room_hash": "abc123",
      "title": "Temple Square",
      "updated_at": "2026-07-27T22:10:00+00:00",
      "prev_room_hash": "def456",
      "stats": {"hp": 20, "max_hp": 20, "mana": 100, "max_mana": 100, "move": 85, "max_move": 85},
      "stats_updated_at": "2026-07-27T22:10:05+00:00"
    }
  ]
}
```

`stats`/`stats_updated_at` are only present once the agent has called `check(kind="score")` at least once — they reflect what the agent last saw, not necessarily the player's true current state (see the CDC/journal caveat below: this is a snapshot of agent-observed state, not ground truth).

### Live

Real-time event stream delivered via Server-Sent Events (SSE). Each event is appended as a coloured line as it arrives. Styled by phase:

| CSS class | Phase | What it shows |
|---|---|---|
| `phase-response` | `response` | The agent's text reply |
| `phase-tool_call` | `tool_call` | Tool name and arguments |
| `phase-tool_result` | `tool_result` | First 200 chars of the tool output |
| `phase-compaction` | `compaction` | Number of messages dropped |
| `phase-iteration` | `iteration` | Current iteration counter |

### Map

Compass-anchored layout of every room the agent has visited, built from `.boukensha/memory/world_graph.json`. Nodes are room IDs; edges are directional connections (north/south/etc). Click a node to see its title and details. Each character's current room is marked with a colored star that moves as they do, polled from `.boukensha/memory/players.json`.

Data endpoint: `GET /api/map`

```json
{
  "nodes": [{"id": "abc123", "title": "Temple Square"}, ...],
  "links": [{"source": "abc123", "target": "def456", "direction": "north"}, ...]
}
```

Data endpoint: `GET /api/players`

```json
[
  {"name": "Hero", "room_hash": "abc123", "title": "Temple Square", "updated_at": "2026-07-27T22:10:00+00:00"},
  ...
]
```

### Waterfall

Timeline of each agent turn broken into phases. Events are forwarded from the Live SSE stream via `window.addWaterfallEvent`. Shows relative timing of prompt, tool calls, and response within each iteration.

### Goals

Displays the content of `.boukensha/goals/current.yaml` as key-value pairs. Refreshes when you click the tab.

Data endpoint: `GET /api/goal`

```json
{
  "current_goal": "Explore the city",
  "priority": "normal",
  "status": "active",
  "hp_flee_threshold": 30,
  "notes": ""
}
```

### Sessions

Table of all past sessions found in `.boukensha/sessions/`. Shows session ID, start time, model, and total input/output token counts. Click a row to expand the full transcript.

Data endpoints:

- `GET /api/sessions` — list of session summaries
- `GET /api/sessions/<session_id>` — full JSONL entries for one session

## SSE event types

All events are JSON objects with a `phase` field. The Logger emits these phases:

| Phase | Key fields | Description |
|---|---|---|
| `session_start` | `at`, `model`, `provider`, `max_iterations`, `max_output_tokens` | Emitted once when the agent starts |
| `turn` | `n` | User turn number |
| `iteration` | `n`, `max` | Agent iteration within a turn |
| `prompt` | `messages`, `tokens` | Full message list sent to the LLM |
| `response` | `text`, `usage` | LLM text reply with token usage |
| `tool_call` | `name`, `args` | Tool the agent invoked |
| `tool_result` | `name`, `result` | Return value from the tool |
| `compaction` | `before`, `dropped`, `context_window` | Context compaction event |
| `reasoning` | `text` | Extended thinking content (Anthropic only) |
| `turn_end` | `n` | Turn completed |

## Adding a new tab

1. Add a button in `src/boukensha/dashboard/templates/index.html`:
   ```html
   <button class="tab-btn" data-tab="mytab">My Tab</button>
   ```

2. Add a pane div in the same template:
   ```html
   <div id="tab-mytab" class="tab-pane">
     <div id="mytab-content"></div>
   </div>
   ```

3. Create `src/boukensha/dashboard/static/mytab.js`:
   ```js
   export function loadMyTab() {
     fetch('/api/mytab')
       .then(r => r.json())
       .then(data => {
         document.getElementById('mytab-content').textContent = JSON.stringify(data);
       });
   }
   window.loadMyTab = loadMyTab;
   ```

4. Add the `<script>` tag to `index.html` and call `window.loadMyTab && window.loadMyTab()` in the tab routing block in `app.js`.

5. Optionally add an API endpoint in `src/boukensha/dashboard/app.py`:
   ```python
   @app.route("/api/mytab")
   def api_mytab():
       return jsonify({"hello": "world"})
   ```

## Troubleshooting

| Problem | Fix |
|---|---|
| `Address already in use` (port 4568) | Use `--port 4569` (or any free port) |
| Map tab shows blank | Agent has not visited any rooms yet; complete at least one turn |
| Live tab shows nothing | Check that `--web` was passed; reload the page |
| Goals tab shows empty | Create `.boukensha/goals/current.yaml` manually or let the agent create it |
| Dashboard does not start | Ensure Flask is installed: `uv sync` from `week2_capable/agent-exp/` |
</content>
</invoke>