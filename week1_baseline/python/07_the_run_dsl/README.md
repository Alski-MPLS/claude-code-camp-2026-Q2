# Step 7 — The `boukensha.run()` DSL

## What this step adds

A single top-level entry point: `boukensha.run()`.

Every previous step required you to manually create and wire together a `Context`, `Registry`, backend, `PromptBuilder`, `Client`, `Logger`, and `Agent`. Step 7 hides all of that behind one function call and an optional tool-registration callback. It is the "hello world" entry point for the framework.

## The new primitives

### `RunDSL`

A tiny helper object. `boukensha.run()` creates one and passes it to your `tool_registrar` callback, so `self` inside the callback becomes a `RunDSL` — exposing only one method: `tool()`. This keeps the DSL surface intentionally small and prevents callers from reaching internal state.

### `boukensha.run()`

Accepts keyword arguments that describe *what* to do. All plumbing is handled internally.

| Option | Default | Description |
|---|---|---|
| `task` | *(required)* | The user message handed to the agent |
| `system` | Player task system prompt | System prompt |
| `model` | from `settings.yaml` | Model name |
| `backend` | from `settings.yaml` | `"anthropic"`, `"openai"`, `"gemini"`, `"ollama"`, or `"ollama_cloud"` |
| `api_key` | from env var | API key for the chosen backend |
| `ollama_host` | `"http://localhost:11434"` | Ollama base URL |
| `log` | `.boukensha/sessions/<session-id>.jsonl` | Optional JSONL log path override |
| `max_output_tokens` | from `settings.yaml` (1024) | Max tokens per API response |
| `tool_registrar` | `None` | A callable `(dsl: RunDSL) -> None` that registers tools |

## Before and after

**Step 6 — 20+ lines of manual plumbing:**

```python
ctx      = Context(task=Player, system="You are a MUD player assistant.")
registry = Registry(ctx)
backend  = Anthropic(api_key=os.environ["ANTHROPIC_API_KEY"], model="claude-haiku-4-5")
builder  = PromptBuilder(ctx, backend)
client   = Client(builder)
logger   = Logger()
agent    = Agent(context=ctx, registry=registry, builder=builder, client=client, logger=logger)

registry.tool("read_file", description="Read a file", parameters={"path": {"type": "string"}},
              block=lambda path: Path(path).read_text())

ctx.add_message("user", "Read lib/boukensha.rb")
result = agent.run()
logger.close()
```

**Step 7 — just describe what you want:**

```python
def register_tools(dsl):
    dsl.tool(
        "read_file",
        description="Read a file",
        parameters={"path": {"type": "string", "description": "File path"}},
        block=lambda path: Path(path).read_text(),
    )

result = boukensha.run(task="Read src/boukensha/__init__.py", tool_registrar=register_tools)
```

## Running the example

```sh
cd week1_baseline/python/07_the_run_dsl
uv sync
uv run python examples/example.py
```

The example registers two tools (`read_file`, `list_directory`) and asks the agent to read `README.md` and summarise what the framework can do. The logger prints each phase to stdout and writes a session JSONL file under `.boukensha/sessions/`.

## Running the tests

```sh
cd week1_baseline/python/07_the_run_dsl
uv sync --group dev
uv run pytest tests/ -v
```
