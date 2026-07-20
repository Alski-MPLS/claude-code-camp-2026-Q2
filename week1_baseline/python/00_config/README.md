# 00 · Configuration (Python)

Python port of `ruby/00_config`. Manages all Boukensha configuration from an
external file, eg. `~/.boukensha/settings.yaml`, via a dedicated `Config`
class. Configuration will keep growing across iterations — hardcode defaults,
never hardcode configurable values.

Configuration is organised by **task** — a role in the agentic loop bound to
its own LLM. week1_baseline only drives a single `player` task (the main
loop); a more advanced loop will assign different LLMs to different tasks. A
task is either a "single-task" or a "multi-task" — the latter being a full
agent.

See [`plan.md`](plan.md) for the design rationale and the Ruby→Python
mapping this port followed.

## Requirements

- Python 3.11+
- [`uv`](https://docs.astral.sh/uv/) for dependency management

## Install

```bash
cd python/00_config
uv sync
```

This creates a `.venv` and installs the two runtime dependencies:
`pyyaml` (settings file) and `python-dotenv` (`.env` loading) — Python's
standard library has neither, unlike Ruby's.

## Package layout

```
python/00_config/
  pyproject.toml         # project metadata + deps, managed via uv
  src/boukensha/
    __init__.py            # re-exports Config, tasks.Player
    config.py              # Config class
    tasks/
      __init__.py
      base.py               # Base task class (provider/model + prompt resolution)
      player.py             # Player(Base), TASK_NAME = "player"
  prompts/
    system.md               # default system prompt shipped with the library
  examples/
    example.py              # runnable smoke-test
```

## Config directory resolution

`Config()` looks for a `.boukensha/` directory in this order:

1. **`BOUKENSHA_DIR` env var** — set this to point at any directory you like.
2. **`~/.boukensha`** — the default location for a real install.

## Config directory structure

```
.boukensha/
  .env                 # stores credentials eg. LLM API keys (never commit this)
  settings.yaml        # all non-secret settings
  prompts/
    <task>/
      system.md        # per-task override for the default system prompt (optional)
```

## Usage

```python
from boukensha import Config
from boukensha.tasks import Player

config = Config()

player_settings = config.tasks("player")  # or config.tasks() for all tasks

Player.provider(player_settings)   # "anthropic"
Player.model(player_settings)      # "claude-haiku-4-5"
Player.prompt_override(player_settings, "system")  # True / False

Player.system_prompt(
    player_settings,
    user_prompts_dir=config.user_prompts_dir,
    default_prompts_dir=Config.PROMPTS_DIR,
)

config.mud_host       # "localhost"
config.mud_port       # 4000
config.mud_username   # "dummy"
config.mud_password   # "helloworld"
```

### `Config`

| Member | Description |
|--------|--------------|
| `Config()` | resolves `.boukensha` dir, loads `.env`, loads `settings.yaml` |
| `.dir` | resolved absolute path to the config directory |
| `.settings` | raw dict parsed from `settings.yaml` |
| `.tasks(name=None)` | full `tasks:` dict, or one task's dict by name |
| `.user_prompts_dir` | `<config dir>/prompts`, for per-task prompt overrides |
| `.mud_host` / `.mud_port` / `.mud_username` / `.mud_password` | MUD connection settings, with `host`/`port` defaults |
| `.dig(*keys)` | fetch a nested key path, e.g. `dig("mud", "host")` |
| `Config.PROMPTS_DIR` | class attribute: path to the default `prompts/` shipped with this package |

### `Base` / `Player` tasks

`boukensha.tasks.Base` is an abstract stateless class: every method is a
`@classmethod`/`@staticmethod` that takes a `settings` dict explicitly — no
instances are created. `Player` is the only concrete subclass so far, with
`TASK_NAME = "player"`.

| Method | Description |
|--------|--------------|
| `.provider(settings)` | task's provider name; raises `ValueError` if missing |
| `.model(settings)` | task's model name; raises `ValueError` if missing |
| `.prompt_override(settings, prompt="system")` | `True` if that prompt is configured to use the user override |
| `.prompt(settings, name="system", user_prompts_dir=None, default_prompts_dir=None)` | resolves a named prompt |
| `.system_prompt(settings, user_prompts_dir=None, default_prompts_dir=None)` | shortcut for `.prompt(settings, "system", ...)` |

Future steps add per-turn ceilings (`max_iterations`, `max_turn_tokens`,
`max_output_tokens`, `compaction_threshold`) to `Base` — not read yet.

## System prompt resolution

Per task, `system_prompt` is resolved in this order:

1. **`.boukensha/prompts/<task>/system.md`** — used when the task's
   `prompt_override.system` is `true` and the file exists.
2. **`prompts/system.md`** (this package's `Config.PROMPTS_DIR`) — the
   default system prompt shipped with the library.

## Configuration schema

- `tasks`: a map of task name → task config (`provider`, `model`, `prompt_override`).
- `tasks.<name>.prompt_override.system`: when `true`, that task's
  `.boukensha/prompts/<name>/system.md` overrides the default system prompt.
- `mud`: MUD connection information for the main player.

```yaml
tasks:
  player:
    provider: anthropic        # provider name (string)
    model: claude-haiku-4-5
    prompt_override:
      system: true
mud:
  host: localhost
  port: 4000
  username: dummy
  password: helloworld
```

## Run example

```bash
uv run examples/example.py
```

By default the example points `BOUKENSHA_DIR` at the repo root's
`.boukensha/` so it works out of the box from a checkout. Point it elsewhere
to use a different config:

```bash
BOUKENSHA_DIR=/path/to/.boukensha uv run examples/example.py
```

Expected output (values from your `.boukensha/`):

```
=== Boukensha Step 0: Configuration ===

Config dir:     /home/andrew/Sites/Claude-Code-Camp/.boukensha
Tasks:          player

-- player task --
Provider:       anthropic
Model:          claude-haiku-4-5
Prompt override?True
System prompt:  You are a MUD player assistant. Use the tools available to y...

MUD host:       localhost:4000
MUD user:       dummy

API key set?    True

Config(dir=/home/andrew/Sites/Claude-Code-Camp/.boukensha, tasks=player)
```
