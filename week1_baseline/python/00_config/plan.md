# 00 · Configuration (Python port)

Port of `ruby/00_config` to Python. Same behavior, same config schema, same
directory conventions — only the language and its idioms change.

We want to be able to manage all configuration from an external file eg.
`~/.boukensha/settings.yaml`. We want a dedicated class to handle
configuration, eg. `boukensha.Config`. Configuration will keep evolving in
later iterations, so the schema and class will grow — no hardcoding of
configurable values, defaults are fine to hardcode.

Configuration is organised by **task** — a role in the agentic loop bound to
its own LLM. week1_baseline only drives a single `player` task (the main
loop), but a more advanced loop will assign different LLMs to different
tasks. A task is either a "single-task" or a "multi-task" — the latter being
a full agent.

## Design Considerations

Ruby's stdlib ships `yaml`, so the original only needed to add the `dotenv`
gem. Python's stdlib has no YAML parser, so this port necessarily depends on
two third-party packages: `pyyaml` (settings file) and `python-dotenv` (`.env`
loading). Beyond those two, prefer the standard library (`os`, `pathlib`)
over extra dependencies.

Dependency management uses `pyproject.toml` managed with `uv` — the current
standard for new Python projects (fast installs, lockfile, no separate
virtualenv bootstrapping step).

`Config.dig()` in Ruby defensively checks both string and symbol keys because
Ruby YAML/hash access can involve either. `PyYAML` always loads mapping keys
as plain `str`, so the Python port's `dig()` simplifies to a straight
string-key traversal — no symbol-checking branch to port, since it would be
dead code.

Task classes (`Base`, `Player`) stay classes with `@classmethod`/
`@staticmethod` methods, mirroring the Ruby design 1:1: no instances are
created, every method takes a `settings` dict explicitly. This preserves the
stateless-by-design intent called out in the Ruby README.

## Code Changes

| File | Purpose |
|------|---------|
| `pyproject.toml` | project metadata + deps (`pyyaml`, `python-dotenv`), managed via `uv` |
| `src/boukensha/config.py` | `boukensha.Config` class |
| `src/boukensha/tasks/base.py` | abstract `boukensha.tasks.Base` (provider/model + prompt resolution) |
| `src/boukensha/tasks/player.py` | concrete `boukensha.tasks.Player` (the main loop) |
| `src/boukensha/__init__.py` | top-level package init, re-exports `Config`, `tasks.Player` |
| `prompts/system.md` | default system prompt shipped with the library |
| `examples/example.py` | runnable smoke-test |

---

## Config directory resolution

The class looks for a `.boukensha/` directory in this order:

1. **`BOUKENSHA_DIR` env var** — set this to point at any directory you like.
2. **`~/.boukensha`** — the default location for a real install.

## Config directory structure

The class expects the following:

```
.boukensha/
  .env                 # stores credentials eg. LLMs APIs (never committed to repo)
  settings.yaml        # all non-secret settings
  prompts/
    <task>/
      system.md        # per-task override for the default system prompt (optional)
```

---

## Tasks

`boukensha.tasks.Base` is an abstract stateless class. All behaviour is
expressed as classmethods/staticmethods that accept a `settings` dict — no
instances are created. Concrete subclasses define `TASK_NAME`. For now only
`boukensha.tasks.Player` exists; future steps add per-turn ceilings
(`max_iterations`, `max_turn_tokens`, `max_output_tokens`,
`compaction_threshold`) — these are **not** read yet.

`Config.tasks()` returns the raw dict from `settings.yaml` under `tasks:`.
Pass a name to look up a specific task's settings dict, then pass it to the
stateless class:

```python
from boukensha import Config
from boukensha.tasks import Player

config = Config()
Player.provider(config.tasks("player"))
Player.system_prompt(
    config.tasks("player"),
    user_prompts_dir=config.user_prompts_dir,
    default_prompts_dir=Config.PROMPTS_DIR,
)
```

## System prompt resolution

Per task, `Player.system_prompt` is resolved in this order:

1. **`.boukensha/prompts/<task>/system.md`** — used when the task's
   `prompt_override.system` is `true` and the file exists.
2. **`prompts/system.md`** — the default system prompt shipped with the
   library.

## Configuration Schema

The following properties so far:
- `tasks`: a map of task name → task config (provider, model, prompt_override).
- `tasks.<name>.prompt_override.system`: when `true`, the task's
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

---

## API mapping (Ruby → Python)

| Ruby | Python |
|------|--------|
| `Boukensha::Config.new` | `Config()` |
| `config.dir` | `config.dir` (property) |
| `config.settings` | `config.settings` (property) |
| `config.tasks(name = nil)` | `config.tasks(name: str \| None = None)` |
| `config.user_prompts_dir` | `config.user_prompts_dir` (property) |
| `config.mud_host` / `mud_port` / `mud_username` / `mud_password` | same, as properties |
| `config.dig(*keys)` | `config.dig(*keys)` — string-key traversal only |
| `Boukensha::Config::PROMPTS_DIR` | `Config.PROMPTS_DIR` (class attribute) |
| `Boukensha::Tasks::Base.task_name` (raises if undefined) | `Base.TASK_NAME` (class attribute; `NotImplementedError` if unset) |
| `.provider(settings)` / `.model(settings)` | same, raise `ValueError` (not `ArgumentError`) if missing |
| `.prompt_override?(settings, prompt = :system)` | `.prompt_override(settings, prompt="system") -> bool` |
| `.prompt(settings, name = :system, ...)` | `.prompt(settings, name="system", ...)` |
| `.system_prompt(settings, ...)` | `.system_prompt(settings, ...)` |
| `config.to_s` / `inspect` | `config.__repr__` |

## Dependencies

```toml
[project]
dependencies = [
    "pyyaml",
    "python-dotenv",
]
```

Managed with `uv`:

```bash
uv sync
```

## Run Example

```bash
uv run examples/example.py
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

## Testing

Ruby version has no test suite; match that scope for the port. If tests are
added later, use `pytest` with fixtures for a temp `.boukensha/` dir rather
than touching the real `~/.boukensha`.

## Implementation order

1. `pyproject.toml` + `uv sync` (dependencies only, empty package yet)
2. `prompts/system.md` (copy verbatim from Ruby)
3. `src/boukensha/config.py` (`Config` class: dir resolution, `.env` load, YAML load, `dig`, `tasks`, `mud_*`, `__repr__`)
4. `src/boukensha/tasks/base.py` (`Base`: `provider`, `model`, `prompt_override`, `prompt`, `system_prompt`)
5. `src/boukensha/tasks/player.py` (`Player(Base)`, `TASK_NAME = "player"`)
6. `src/boukensha/__init__.py` (re-export `Config`, `tasks.Player`)
7. `examples/example.py` (smoke test, output matches Ruby's format exactly)
8. Manual run: `uv run examples/example.py` against a real `.boukensha/` dir, diff output against the Ruby example's expected output
