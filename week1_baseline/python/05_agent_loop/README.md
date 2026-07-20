# Python 05 Agent Loop

Python port of `ruby/05_agent_loop`. Adds `Agent` — drives the tool-call loop until the model signals `end_turn` or the iteration ceiling is reached.

## New Files

| File | Description |
|---|---|
| `src/boukensha/agent.py` | `Agent` — the loop, tool dispatch, and wind-down logic |

## Updated Files

| File | Change |
|---|---|
| `src/boukensha/errors.py` | Added `LoopError` for runaway agents |
| `src/boukensha/client.py` | `call()` now accepts a `tools` kwarg (empty list disables tools for wind-down) |
| `src/boukensha/prompt_builder.py` | Added `parse_response()`; `to_api_payload()` accepts `tools` kwarg |
| `src/boukensha/tasks/base.py` | Added `max_iterations()` and `max_output_tokens()` classmethods |
| `src/boukensha/message.py` | `content` widened to `Any` (stores normalised content blocks for assistant turns) |
| `src/boukensha/backends/*.py` | Every backend gains `parse_response()`; OpenAI/Gemini/Ollama/OllamaCloud add inverse helpers |

## How It Works

    send messages to API
            |
    stop_reason == "tool_use"?
        yes -> extract tool calls
            -> store assistant message (must precede tool_result)
            -> dispatch each tool via Registry
            -> inject results as tool_result messages
            -> go back to top
        no  -> return final text response

## Normalised Response Shape

Every backend's `parse_response` converts its provider-specific wire format into:

    {
        "stop_reason": "tool_use" | "end_turn",
        "content": [
            {"type": "text", "text": "..."},
            {"type": "tool_use", "id": "...", "name": "...", "input": {...}},
        ]
    }

`Agent` never inspects a raw provider response.

## `Agent` API

| Method | Description |
|---|---|
| `Agent(context, registry, builder, client, task_settings=None, max_iterations=None, max_output_tokens=None)` | Construct the agent |
| `agent.run()` | Run the loop; returns the final text string |

## Task Configuration (~/.boukensha/settings.yaml)

    tasks:
      player:
        provider: anthropic
        model: claude-haiku-4-5
        max_iterations: 25
        max_output_tokens: 1024

## Run Example

    cd week1_baseline/python/05_agent_loop
    uv sync
    uv run python examples/example.py

Requires the API key for whichever provider is configured in `~/.boukensha/settings.yaml` (e.g. `ANTHROPIC_API_KEY`).

## Run Tests

    cd week1_baseline/python/05_agent_loop
    uv sync
    uv run pytest tests/ -v
