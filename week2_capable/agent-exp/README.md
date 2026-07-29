# Boukensha — Enhanced MUD Agent (v0.12.0)

An autonomous AI agent that plays CircleMUD. It keeps room memory, plans routes, tracks goals, fights mobs automatically, and shows everything in a live web dashboard — while spending as few tokens as possible per action.

## What Boukensha does

| Feature | How it works |
|---|---|
| Room memory | Hashes every room by content; stores exits, NPCs, and items to disk |
| World map | Builds a graph of visited rooms; uses Dijkstra pathfinding for `navigate_to` |
| Goal tracking | Reads/writes `.boukensha/goals/current.yaml`; agent calls `goal_read`/`goal_update` |
| Combat automation | `combat_loop` runs a Python fight loop with automatic HP-flee threshold |
| Token minimization | `process_room` diffs against stored memory and returns nothing when unchanged |
| Web dashboard | Six-tab Flask app — Overview (default), live SSE stream, map, waterfall, goals, and session history |
| World knowledge | Agent discovers facts (quest hints, NPC secrets, locked door requirements) and saves them to `.boukensha/knowledge.yaml`; injected into every future session automatically |

## Prerequisites

- Python 3.11 or newer
- [uv](https://docs.astral.sh/uv/) — fast Python package manager
- A running CircleMUD server (default `localhost:4000`)
- An Anthropic API key (or another supported LLM backend)

## Setup

### 1. Clone and enter the folder

```sh
git clone <repo-url>
cd week2_capable/agent-exp
```

### 2. Install dependencies

```sh
uv sync
```

### 3. Create the config directory

```sh
mkdir -p .boukensha/goals .boukensha/memory
```

Create `.boukensha/settings.yaml`:

```yaml
mud:
  host: localhost
  port: 4000
  username: yourcharacter
  password: yourpassword

tasks:
  player:
    provider: anthropic
    model: claude-opus-4-5
```

To use a local model via [Ollama](https://ollama.com) instead (no API key needed, just `ollama serve` running):

```yaml
tasks:
  player:
    provider: ollama
    model: qwen2.5-coder:14b   # any model you've pulled with `ollama pull`
```

Create `.boukensha/.env` (or export these in your shell):

```
ANTHROPIC_API_KEY=sk-ant-...
MUD_HOST=localhost
MUD_PORT=4000
MUD_NAME=yourcharacter
MUD_PASSWORD=yourpassword
```

## Configuration reference

### settings.yaml

The config directory defaults to `.boukensha/` inside the repo (override with `BOUKENSHA_DIR`).

| Key | Default | Description |
|---|---|---|
| `mud.host` | `localhost` | CircleMUD hostname |
| `mud.port` | `4000` | CircleMUD telnet port |
| `mud.username` | — | Character name |
| `mud.password` | — | Character password |
| `tasks.player.model` | — (required) | LLM model name for the player task |
| `tasks.player.provider` | — (required) | Backend: `anthropic`, `openai`, `gemini`, `ollama`, `ollama_cloud` |

### Environment variables

| Variable | Purpose |
|---|---|
| `ANTHROPIC_API_KEY` | Anthropic API key |
| `OPENAI_API_KEY` | OpenAI API key |
| `GEMINI_API_KEY` | Google Gemini API key |
| `MUD_HOST` | Overrides `mud.host` |
| `MUD_PORT` | Overrides `mud.port` |
| `MUD_NAME` | Overrides `mud.username` |
| `MUD_PASSWORD` | Overrides `mud.password` |

### Goal file: `.boukensha/goals/current.yaml`

```yaml
current_goal: Explore the city
priority: normal         # low / normal / high
status: active           # active / completed / paused
hp_flee_threshold: 30    # flee combat when HP drops to this value
notes: ""
```

## Running the agent

```sh
# Web dashboard + TUI (recommended)
uv run python bin/boukensha --web

# TUI only (no browser needed)
uv run python bin/boukensha --no-web

# Headless / plain REPL (scriptable)
uv run python bin/boukensha --no-web --no-tui

# Custom dashboard port
uv run python bin/boukensha --web --port 4569
```

Once started with `--web`, open your browser to:

```
http://localhost:4568
```

## Web dashboard tabs

| Tab | What it shows |
|---|---|
| **Overview** | Default landing tab — summary cards for rooms known, frontier exits, and unique entities seen, plus each tracked player's last-known stats and location |
| **Live** | Real-time SSE event stream — every agent turn, tool call, and response |
| **Map** | Force-directed graph of visited rooms built from world memory |
| **Waterfall** | Timing breakdown of each turn: prompt, tool calls, response |
| **Goals** | Current goal YAML with status and priority |
| **Sessions** | History of all past sessions with token usage totals |

## Memory files

| Path | Contents |
|---|---|
| `.boukensha/memory/` | Room JSON files, world graph (`world_graph.json`), player position + stats (`players.json`) |
| `.boukensha/goals/current.yaml` | Active goal |
| `.boukensha/knowledge.yaml` | World knowledge — facts the agent has discovered (quest hints, NPC secrets, item locations). World-scoped; shared across all characters. Excluded from git. |
| `.boukensha/sessions/` | JSONL log files, one per session |

## Running tests

```sh
uv run pytest tests/ -v
```

## Token minimization

Three tools reduce LLM token usage on every turn:

- **process_room** — sends `look`, hashes the result, and returns an empty observation if the room hash matches what is already in memory. A repeated `look` in the same room costs near zero tokens.
- **navigate_to(destination)** — computes the shortest path through the world graph and sends each `move` command automatically. The LLM makes one tool call regardless of path length.
- **combat_loop(target, flee_hp)** — runs a Python attack loop and only returns to the LLM when the fight ends or HP drops below the threshold.

## Troubleshooting

| Problem | Fix |
|---|---|
| `ConnectionRefusedError` on start | CircleMUD server is not running on the configured host/port |
| `tasks.player.model is required in settings.yaml` | Add `tasks.player.model` / `tasks.player.provider` to `.boukensha/settings.yaml` (nested under `tasks.player`, not top-level) |
| `ANTHROPIC_API_KEY not set` | Export the variable or add it to `.boukensha/.env` |
| `Address already in use` (port 4568) | Use `uv run python bin/boukensha --web --port 4569` |
| Map tab shows empty graph | Agent has not visited any rooms yet; play a turn first |
| Goals tab shows defaults | Create `.boukensha/goals/current.yaml` or let the agent write it |
</content>
</invoke>