# First-Time Setup

Step-by-step guide for getting Boukensha running on a machine that has never had it installed.

## Requirements

- Python 3.11 or newer (`python3 --version`)
- [uv](https://docs.astral.sh/uv/) — install with `curl -LsSf https://astral.sh/uv/install.sh | sh`
- A running CircleMUD server, or access to the test one

## Steps

### 1. Install dependencies

```sh
cd week2_capable/agent-exp
uv sync
```

This installs everything listed in `pyproject.toml` into an isolated virtual environment. No system-wide pip changes.

### 2. Configure `.boukensha/`

Create the directories:

```sh
mkdir -p .boukensha/goals .boukensha/memory
```

Create `.boukensha/settings.yaml`:

```yaml
mud:
  host: localhost       # change to your MUD server hostname
  port: 4000            # change if your server uses a different port
  username: yourcharacter
  password: yourpassword

model: claude-opus-4-5
provider: anthropic
```

Create `.boukensha/.env` with your API key and MUD credentials:

```
ANTHROPIC_API_KEY=sk-ant-...
MUD_HOST=localhost
MUD_PORT=4000
MUD_NAME=yourcharacter
MUD_PASSWORD=yourpassword
```

Settings in `.env` override `settings.yaml` when both are present.

### 3. Run

```sh
cd week2_capable/agent-exp
python bin/boukensha --web
```

The agent starts, connects to the MUD, and launches the dashboard in a background thread.

### 4. Open the dashboard

```
http://localhost:4568
```

You should see the Live tab showing the agent's first turn.

## Verify the install (no MUD needed)

```sh
uv run pytest tests/ -v
```

All tests should pass. The test suite uses mock sessions so no live MUD connection is required.

## Next steps

- Edit `.boukensha/goals/current.yaml` to set an initial goal before starting the agent
- Use `--no-web` if you only want the TUI and no browser
- Use `--no-web --no-tui` for a plain line-based REPL (useful in scripts)
- See `README.md` for the full configuration reference and troubleshooting guide
</content>
</invoke>