# Step 11 — A Terminal UI

Boukensha now ships a full terminal UI (TUI) built on [Textual](https://github.com/Textualize/textual). The plain REPL from step 10 is still available with `tui=False`.

## What's new

### `boukensha.Tui`

New class. Wraps a `Repl` instance and replaces its raw `print`/`input` I/O with a structured four-zone display:

```
┌──────────────────────────────────────────────┐
│  conversation viewport (scrollable)           │
├──────────────────────────────────────────────┤
│  ⟳ live progress line (idle when not running) │
├──────────────────────────────────────────────┤
│  boukensha> input box                         │
├──────────────────────────────────────────────┤
│  status line (always-on)                      │
└──────────────────────────────────────────────┘
```

The **progress line** shows a spinner, current action, iteration counter (`n/MAX`), elapsed seconds, token counts (↑ in / ↓ out), and tool call count while the agent is running. When idle it shows context usage and turn count.

The **status line** always shows: version · model · context tokens used · registered tool count · wall-clock time.

**Keyboard shortcuts:**

| Key | Action |
|-----|--------|
| `Enter` | Submit input or slash command |
| `Esc` | Interrupt the running agent turn |
| `Ctrl+L` | Clear conversation history |
| `PgUp` / `PgDn` | Scroll conversation viewport |
| `Ctrl+C` / `Ctrl+D` | Quit |

### `boukensha.repl()` — new `tui:` keyword

```python
boukensha.repl(tui=True)   # default — launches Textual TUI
boukensha.repl(tui=False)  # falls back to plain terminal REPL
```

### `Repl` refactored for composability

`Repl` now exposes three methods so `Tui` (or any other front-end) can drive it:

| Method | Purpose |
|--------|---------|
| `on_output(callback)` | Route all REPL output through a callback instead of stdout |
| `handle_command(text)` | Process a slash command; returns `"quit"`, `"command"`, or `None` |
| `run_turn(text)` | Run one agent turn and route the result through `on_output` |

`banner`, `logger`, `context`, `model`, and `version` are also exposed as properties.

### `Logger.subscribe()`

```python
logger.subscribe(lambda event: ...)
```

Every structured log event is now broadcast to all registered subscribers. `Tui` uses this to update the live progress line in real time.

## Run

```sh
cd week1_baseline/python/11_tui
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
