# The Prompt Builder (Python)

Because LLM access, cost and quality are constantly changing, we want to be able to switch between multiple LLMs that will drive the agent loop.

There are several SDKs that provide access to many LLMs but in practice we only really need to focus on top-tier models:
- anthropic family
- openai family
- gemini family
- ollama cloud e.g. kimi, minimax, llama

The Prompt Builder serializes `Context` for the exact format each API expects.
The `PromptBuilder` delegates to whichever backend you pass in.

PromptBuilder does not call the API — we are simply preparing the format for API calls.

Configuration is task-based here, carried forward from the registry step. The
`player` task owns its provider, model, and prompt override settings, and the
context records the task that the prompt is being built for.

## Package Layout

```
python/03_prompt_builder/
  pyproject.toml
  README.md
  plan.md
  prompts/
    system.md                 # shipped default system prompt
  src/boukensha/
    __init__.py               # re-exports everything
    config.py                 # MODIFIED — PROMPTS_DIR restored
    tool.py                   # unchanged, carried from 02_the_registry
    message.py                # unchanged, carried from 02_the_registry
    context.py                # unchanged, carried from 02_the_registry
    errors.py                 # MODIFIED — + UnsupportedModelError
    registry.py               # unchanged, carried from 02_the_registry
    prompt_builder.py         # NEW
    backends/
      __init__.py
      base.py
      anthropic.py
      gemini.py
      ollama.py
      ollama_cloud.py
      openai.py
    tasks/
      __init__.py
      base.py
      player.py
  examples/
    example.py
```

## How It Works

```
Context (Python objects)
        ↓
PromptBuilder
        ↓
Backend (Anthropic, OpenAI, Gemini, or Ollama)
        ↓
API Payload (plain dicts and lists)
        ↓
POST to API
```

## `Config.PROMPTS_DIR` Restored

`01_struct_skeleton` and `02_the_registry` dropped `Config.PROMPTS_DIR` because those steps shipped no `prompts/` directory. This step re-adds it — computed as `(Path(__file__).parent.parent.parent / "prompts").resolve()`, which resolves to `python/03_prompt_builder/prompts/` — because it now ships its own `prompts/system.md`. This mirrors the Ruby diff exactly: `config.rb` regains the `PROMPTS_DIR` constant it had dropped in the previous two steps.

## `boukensha.PromptBuilder`

| Method | Description |
|---|---|
| `to_messages()` | Delegates message serialization to the backend |
| `to_tools()` | Delegates tool serialization to the backend |
| `to_api_payload(*, max_output_tokens=1024)` | Assembles the complete payload ready to POST |
| `headers` (property) | Returns the correct headers for the backend |
| `url` (property) | Returns the correct endpoint URL for the backend |

## Backends

Each API has its own conventions for how data is expected. Anthropic and Gemini are the most alike (system prompt as a top-level field), while OpenAI and Ollama share the same `function`-wrapped tool schema.

Backends also own their supported model table. A backend raises `UnsupportedModelError` if initialized with an unknown model name, so `settings.yaml` cannot silently select an unsupported or misspelled model. Each model entry carries:

| Key | Meaning |
|---|---|
| `context_window` | The model's known token context window |
| `cost_per_million["input"]` | USD input token price per million tokens, when known |
| `cost_per_million["output"]` | USD output token price per million tokens, when known |
| `usage_unit` | `"tokens"`, `"local_compute"`, or `"ollama_cloud_usage"` |
| `usage_level` | Ollama Cloud usage tier, when applicable |

Backend instances expose `context_window`, `input_token_cost_per_million`,
`output_token_cost_per_million`, `usage_unit`, `usage_level`, and
`estimate_cost(*, input_tokens, output_tokens)`.
For local Ollama models, token API cost is `0.0`. For Ollama Cloud, public
pricing is plan/usage based rather than token based, so `estimate_cost` returns
`None`.

The prices in this step are static tutorial data, current as of June 16, 2026,
and should be reviewed whenever the selected model set changes.

### `boukensha.backends.Anthropic`

Talks to `https://api.anthropic.com/v1/messages`.
Requires an `ANTHROPIC_API_KEY`. Supported models:

| Model | Context Window | Input $/M | Output $/M |
|---|---|---|---|
| `claude-haiku-4-5` | 200,000 | $1.00 | $5.00 |
| `claude-haiku-4-5-20251001` | 200,000 | $1.00 | $5.00 |
| `claude-sonnet-4-6` | 1,000,000 | $3.00 | $15.00 |
| `claude-opus-4-8` | 1,000,000 | $5.00 | $25.00 |

### `boukensha.backends.Gemini`

Talks to `https://generativelanguage.googleapis.com/v1beta/models/{model}:generateContent`.
Requires a `GEMINI_API_KEY`. Supported models:

| Model | Context Window | Input $/M | Output $/M |
|---|---|---|---|
| `gemini-2.5-flash` | 1,048,576 | $0.30 | $2.50 |
| `gemini-2.5-flash-lite` | 1,048,576 | $0.10 | $0.40 |
| `gemini-2.5-pro` | 1,048,576 | $1.25 | $10.00 |
| `gemini-3.1-flash-lite` | 1,048,576 | $0.25 | $1.50 |
| `gemini-3.5-flash` | 1,048,576 | $1.50 | $9.00 |

### `boukensha.backends.Ollama`

Talks to `http://localhost:11434/api/chat`.
Requires `ollama serve` running locally. No API key needed. Supported models:

| Model | Context Window | Cost |
|---|---|---|
| `deepseek-r1:8b` | 128,000 | local |
| `gemma4` | 128,000 | local |
| `gemma4:12b` | 256,000 | local |
| `gemma4:26b` | 256,000 | local |
| `gemma4:31b` | 256,000 | local |
| `gemma4:e2b` | 128,000 | local |
| `gemma4:e4b` | 128,000 | local |
| `qwen3:30b` | 256,000 | local |
| `qwen3:8b` | 40,000 | local |

### `boukensha.backends.OllamaCloud`

Talks to `https://ollama.com/api/chat`. Requires an `OLLAMA_API_KEY`. Supported models:

| Model | Context Window | Usage Level |
|---|---|---|
| `gemma4:31b-cloud` | 256,000 | medium |
| `kimi-k2.5:cloud` | 256,000 | high |
| `minimax-m3:cloud` | 512,000 | high |

### `boukensha.backends.OpenAI`

Talks to `https://api.openai.com/v1/chat/completions`.
Requires an `OPENAI_API_KEY`. Supported models:

| Model | Context Window | Input $/M | Output $/M |
|---|---|---|---|
| `gpt-5.4` | 1,000,000 | $2.50 | $15.00 |
| `gpt-5.4-mini` | 400,000 | $0.75 | $4.50 |
| `gpt-5.5` | 1,000,000 | $5.00 | $30.00 |

### System Prompt

Anthropic and Gemini send the system prompt as a top-level field, separate from the messages array. Ollama and OpenAI put it inside the messages array as a `role: system` message.

```json
// Anthropic
{ "system": "You are a MUD player assistant.", "messages": [ ... ] }

// Gemini
{ "systemInstruction": { "parts": [{ "text": "You are a MUD player assistant." }] }, "contents": [ ... ] }

// Ollama / OpenAI
{ "messages": [ { "role": "system", "content": "You are a MUD player assistant." }, ... ] }
```

### Tool Results

Anthropic wraps tool results in a user message. Ollama and OpenAI use their own `role: tool` message type (with slightly different identifier fields). Gemini wraps results in a `functionResponse` part on a `user` message.

```json
// Anthropic
{ "role": "user", "content": [{ "type": "tool_result", "tool_use_id": "toolu_01X", "content": "A damp stone corridor stretches north. Torches flicker on the walls." }] }

// Ollama
{ "role": "tool", "tool_name": "look", "content": "A damp stone corridor stretches north. Torches flicker on the walls." }

// OpenAI
{ "role": "tool", "tool_call_id": "toolu_01X", "content": "A damp stone corridor stretches north. Torches flicker on the walls." }

// Gemini
{ "role": "user", "parts": [{ "functionResponse": { "name": "toolu_01X", "response": { "content": "A damp stone corridor stretches north. Torches flicker on the walls." } } }] }
```

### Tool Definitions

Anthropic uses `input_schema`. Ollama and OpenAI wrap everything in a `function` envelope with `parameters`. Gemini wraps tools in a `functionDeclarations` array.

```json
// Anthropic
{ "name": "move", "description": "Move the player in a direction (north, south, east, west, up, down)", "input_schema": { "type": "object", "properties": { "direction": { "type": "string", "description": "The direction to move" } }, "required": ["direction"] } }

// Ollama / OpenAI
{ "type": "function", "function": { "name": "move", "description": "Move the player in a direction (north, south, east, west, up, down)", "parameters": { "type": "object", "properties": { "direction": { "type": "string", "description": "The direction to move" } }, "required": ["direction"] } } }

// Gemini
{ "functionDeclarations": [ { "name": "move", "description": "Move the player in a direction (north, south, east, west, up, down)", "parameters": { "type": "object", "properties": { "direction": { "type": "string", "description": "The direction to move" } }, "required": ["direction"] } } ] }
```

### Message Roles

Anthropic, Ollama, and OpenAI all use `assistant` for the model's turn. Gemini calls it `model`.

```json
// Anthropic / Ollama / OpenAI
{ "role": "assistant", "content": "Let me take a look around first." }

// Gemini
{ "role": "model", "parts": [{ "text": "Let me take a look around first." }] }
```

## Design Note: `model_info` Naming Collision

Ruby's `Backends::Base` defines both a class method `model_info(model)` (metadata lookup by name) and an instance method `model_info` (no args, returns the resolved instance's metadata). This is legal in Ruby because class methods and instance methods live in separate method tables.

Python has no such separation: a `classmethod` and a `property` with the same name on the same class collide — whichever is defined last in the class body wins for all access.

Resolution: `model_info` stays the public **classmethod** (`Anthropic.model_info("claude-haiku-4-5")`). The instance's resolved metadata is stored in `self._model_info` (private by convention), set by `_configure_model`. This is safe because the public instance API — `context_window`, `input_token_cost_per_million`, `output_token_cost_per_million`, `usage_unit`, `usage_level`, `estimate_cost` — never included `model_info` as a direct instance accessor.

## Design Note: `PromptBuilder.to_messages` Arity Quirk

`PromptBuilder.to_messages()` always calls `backend.to_messages(context.messages)` — exactly one argument. This matches `Anthropic` and `Gemini` (whose `to_messages` takes one arg, `messages`), but **not** `Ollama`, `OllamaCloud`, or `OpenAI` (which take two: `system, messages`). Calling `PromptBuilder.to_messages()` directly with an Ollama-family backend will raise a `TypeError`.

This is a real, unaddressed latent bug in the Ruby source, confirmed unaddressed as of `ruby/04_api_client`. It never triggers in practice because `to_api_payload` routes through each backend's own `to_payload`, which calls its own `to_messages` with the correct arity internally.

This is ported as-is rather than fixed — "fixing" it here would silently change behavior beyond this step's scope. Do not paper over it while porting `04_api_client`.

## Considerations

**The conversation is stateless.** The model has no memory between turns. Every API call includes the entire history from the beginning. BOUKENSHA is responsible for carrying that state.

**Tool results are user messages on Anthropic.** This feels counterintuitive — the result came from BOUKENSHA, not the human — but it reflects how the Anthropic API models the conversation. Ollama, OpenAI, and Gemini all handle this with dedicated message/part types instead.

**The agent only sees schemas.** The `description` field on each tool is the only thing the agent uses to decide which tool to call. The actual callable never leaves BOUKENSHA.

**`tool.parameters.keys()` needs no coercion.** Ruby's backends call `tool.parameters.keys.map(&:to_s)` to coerce symbol keys to strings before building the `required` array. Python's `Tool.parameters` has been a `dict[str, Any]` with string keys since `01_struct_skeleton`, so `list(tool.parameters.keys())` works directly — no coercion needed.

## Run Example

```sh
cd week1_baseline/python/03_prompt_builder
ANTHROPIC_API_KEY=test-key uv run examples/example.py
```

Output (with `provider: anthropic`, `model: claude-haiku-4-5` in `.boukensha/settings.yaml`):

```
=== BOUKENSHA Step 3: Prompt Builder ===

Config: Config(dir=/path/to/.boukensha, tasks=player)
Provider: anthropic
Model: claude-haiku-4-5
{
  "model": "claude-haiku-4-5",
  "system": "You are a MUD player assistant. Use the tools available to you to help the player explore, fight, and interact with the world.",
  "max_tokens": 1024,
  "tools": [
    {
      "name": "look",
      "description": "Look around the current room for details",
      "input_schema": {
        "type": "object",
        "properties": {},
        "required": []
      }
    },
    {
      "name": "move",
      "description": "Move the player in a direction (north, south, east, west, up, down)",
      "input_schema": {
        "type": "object",
        "properties": {
          "direction": {
            "type": "string",
            "description": "The direction to move"
          }
        },
        "required": [
          "direction"
        ]
      }
    }
  ],
  "messages": [
    {
      "role": "user",
      "content": "I just arrived in the dungeon. What's around me, and can you move north?"
    },
    {
      "role": "assistant",
      "content": "Let me take a look around first."
    },
    {
      "role": "user",
      "content": [
        {
          "type": "tool_result",
          "tool_use_id": "toolu_01X",
          "content": "A damp stone corridor stretches north. Torches flicker on the walls."
        }
      ]
    }
  ]
}
```
