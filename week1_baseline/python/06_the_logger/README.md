# Step 6: The Logger

Python port of `ruby/06_the_logger`. Adds `Logger` — captures events throughout the agent loop and writes a structured JSONL session log.

## New Files

| File | Description |
|---|---|
| `src/boukensha/logger.py` | `Logger` — session logging with JSONL output and execution metadata |

## Updated Files

| File | Change |
|---|---|
| `src/boukensha/__init__.py` | Added `Logger` export |
| `src/boukensha/agent.py` | Added `logger` kwarg; calls `logger.session_start()`, `logger.iteration()`, `logger.prompt()`, `logger.tool_call()`, `logger.tool_result()`, `logger.response()`, `logger.limit_reached()`, `logger.turn_end()` |
| `src/boukensha/backends/*.py` | All backends gain execution metadata: provider, model, tokens, cost_usd |

## Logger API

| Method | Description |
|---|---|
| `Logger(dir=None, log=None, session_id=None, snapshot=None)` | Construct the logger; default dir is `.boukensha/sessions`, session_id auto-generated as `YYYYMMDDTHHMMSSZ-<hex>` |
| `logger.path` | Read-only property: full path to the session log file (e.g., `.boukensha/sessions/20260720T121530Z-abc123.jsonl`) |
| `logger.session_id` | Read-only property: session identifier |
| `logger.session_start(task, backend, timestamp)` | Called when Agent starts; writes `session_start` event with snapshot and metadata |
| `logger.iteration(number, timestamp)` | Called at the start of each iteration |
| `logger.prompt(text, timestamp)` | Called after prompt is sent |
| `logger.tool_call(name, input, id, timestamp)` | Called when a tool is invoked |
| `logger.tool_result(name, result, ok, error, timestamp)` | Called with the tool result |
| `logger.response(text, usage, stop_reason, task, backend, timestamp)` | Called when the model responds |
| `logger.limit_reached(reason, timestamp)` | Called when iteration or token limit is reached |
| `logger.turn_end(timestamp)` | Called at the end of the agent loop |
| `logger.close()` | Closes the session log file |

## Task Configuration (~/.boukensha/settings.yaml)

    tasks:
      player:
        provider: anthropic
        model: claude-haiku-4-5
        max_iterations: 25
        max_output_tokens: 1024

## Run Example

    cd week1_baseline/python/06_the_logger
    uv sync
    uv run python examples/example.py

Requires the API key for whichever provider is configured in `~/.boukensha/settings.yaml` (e.g. `ANTHROPIC_API_KEY`). Writes a structured JSONL session log to `~/.boukensha/sessions/<session-id>.jsonl`.

## Run Tests

    cd week1_baseline/python/06_the_logger
    uv sync
    uv run pytest tests/ -v
