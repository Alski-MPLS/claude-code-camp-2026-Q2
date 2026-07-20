# Step 8 — The REPL Loop

## What this step adds

An interactive multi-turn session: `boukensha.repl()`.

Step 7 introduced `boukensha.run()` as a single-shot entry point — one task, one response, done. Step 8 wraps the same primitives in a loop that stays alive, reads user input from stdin on each turn, and accumulates the full conversation in a shared `Context`. Tools registered at startup remain available for the entire session.

## New primitives

### `Repl`

The class that drives the loop. `boukensha.repl()` wires up all the plumbing and calls `Repl.start()`, which reads lines from stdin and dispatches each turn to a fresh `Agent` that shares the persistent `Context`.

**Built-in slash commands:**

| Command | Effect |
|---|---|
| `/help` | Print the command list |
| `/quiet` | Suppress agent iteration output |
| `/loud` | Re-enable agent iteration output |
| `/clear` | Wipe conversation history (registered tools stay) |
| `/exit` / `/quit` | Leave the REPL |

The REPL also exits cleanly on EOF (Ctrl-D) or `KeyboardInterrupt` (Ctrl-C).

### `boukensha.repl()`

Accepts the same keyword arguments as `boukensha.run()`, minus `task`.

| Option | Default | Description |
|---|---|---|
| `system` | Player task system prompt | System prompt |
| `model` | from `settings.yaml` | Model name |
| `backend` | from `settings.yaml` | `"anthropic"`, `"openai"`, `"gemini"`, `"ollama"`, or `"ollama_cloud"` |
| `api_key` | from env var | API key for the chosen backend |
| `ollama_host` | `"http://localhost:11434"` | Ollama base URL |
| `log` | `.boukensha/sessions/<session-id>.jsonl` | Optional JSONL log path override |
| `max_output_tokens` | from `settings.yaml` (1024) | Max tokens per API response |
| `tool_registrar` | `None` | A callable `(dsl: RunDSL) -> None` that registers tools |

### Quiet mode

Three new functions on the `boukensha` module toggle noisy iteration output:

```python
boukensha.enable_quiet()   # suppress [iteration N/M] and tool-call prints
boukensha.disable_quiet()  # re-enable them
boukensha.is_quiet()       # -> bool
```

The `/quiet` and `/loud` REPL commands call these internally.

### `Context.clear_messages()`

Wipes the message history while leaving registered tools intact. Called by `/clear`.

### `Logger.turn(n)`

Writes a `{"phase": "turn", "n": <n>}` entry to the JSONL session log at the start of each REPL turn.

## Before and after

**Step 7 — one shot:**

```python
result = boukensha.run(task="What files are in src/?", tool_registrar=register_tools)
print(result)
```

**Step 8 — stays alive:**

```python
boukensha.repl(tool_registrar=register_tools)
# Prints a banner, then:
# boukensha> What files are in src/?
# ... agent reply ...
# boukensha> Summarise the main module
# ... agent reply, full history intact ...
# boukensha> /exit
# Goodbye.
```

## Running the example

```sh
cd week1_baseline/python/08_the_repl_loop
uv sync
uv run python examples/example.py
```

The example registers `read_file` and `list_directory` tools pointing at the step 07 directory and drops you into an interactive session. Type any question about the codebase, use `/quiet` to silence the iteration logs, `/clear` to reset history, or `/exit` to quit.

## Running the tests

```sh
cd week1_baseline/python/08_the_repl_loop
uv sync --group dev
uv run pytest tests/ -v
```
