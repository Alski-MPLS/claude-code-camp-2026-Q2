# Architecture — `boukensha` Config (Python)

Code review summary and architecture diagram for `src/boukensha/`.

## Component overview

| Component | Responsibility |
|---|---|
| **`Config`** (`config.py`) | Resolves the `.boukensha` directory, loads `.env` into the process environment, parses `settings.yaml`, and exposes typed accessors (`tasks()`, `dig()`, `mud_*`). It is the single entry point consumers construct. |
| **`Base`** (`tasks/base.py`) | Stateless task contract. Every method is a `classmethod`/`staticmethod` operating on an explicit `settings` dict — no task instances are created. Resolves `provider`, `model`, and system-prompt overrides (user file vs. shipped default). |
| **`Player`** (`tasks/player.py`) | Concrete task (`TASK_NAME = "player"`); currently adds nothing beyond `Base`. |
| **`examples/example.py`** | Smoke-test / reference consumer: builds a `Config`, pulls the `player` task settings, and prints resolved values. |

Design note: `Config` owns *where things live and what's configured*; `Base`/`Player` own *how a task interprets its own settings slice* — the two never reach into each other's internals, they only pass a `settings: dict` and directory strings across the boundary.

## Data flow diagram

```mermaid
flowchart TB
    subgraph inputs["Inputs (external state)"]
        ENV["Environment variable\nBOUKENSHA_DIR (optional)"]
        DOTENV[".boukensha/.env\n(secrets: API keys)"]
        YAML[".boukensha/settings.yaml\n(tasks, mud config)"]
        USERPROMPT[".boukensha/prompts/&lt;task&gt;/system.md\n(optional override)"]
        DEFAULTPROMPT["prompts/system.md\n(shipped default)"]
    end

    ENV -->|"1. resolve dir\n(fallback ~/.boukensha)"| CFG
    DOTENV -->|"2. load_dotenv()\ninjects into os.environ"| CFG
    YAML -->|"3. yaml.safe_load()"| CFG

    subgraph core["boukensha package"]
        CFG["Config\n._resolve_dir / ._load_env / ._load_settings"]
        BASE["Base (tasks/base.py)\nprovider() · model() · prompt_override()\nprompt() · system_prompt()"]
        PLAYER["Player(Base)\nTASK_NAME = 'player'"]
    end

    CFG -->|"config.tasks('player') -> settings dict"| BASE
    CFG -->|"config.user_prompts_dir\nConfig.PROMPTS_DIR"| BASE
    BASE --> PLAYER
    USERPROMPT -.->|"read if prompt_override.system == true"| BASE
    DEFAULTPROMPT -.->|"read as fallback"| BASE

    subgraph outputs["Outputs (consumed by caller)"]
        O1["config.dir, config.settings\nconfig.tasks(), config.dig()"]
        O2["config.mud_host / mud_port\nmud_username / mud_password"]
        O3["Player.provider() / .model()\n(raises ValueError if missing)"]
        O4["Player.system_prompt()\n-> resolved prompt text | None"]
    end

    CFG --> O1
    CFG --> O2
    PLAYER --> O3
    PLAYER --> O4

    O1 --> CALLER["Caller\n(examples/example.py today;\nfuture agentic loop)"]
    O2 --> CALLER
    O3 --> CALLER
    O4 --> CALLER

    classDef input fill:#e8f0fe,stroke:#4a7ad4;
    classDef output fill:#e6f7e6,stroke:#3a9a3a;
    class ENV,DOTENV,YAML,USERPROMPT,DEFAULTPROMPT input;
    class O1,O2,O3,O4 output;
```

## Prompt resolution sequence

Zooms in on `Base.prompt()`, the one non-trivial control-flow path in the module.

```mermaid
sequenceDiagram
    participant C as Caller
    participant B as Base/Player
    participant U as user_prompts_dir file
    participant D as default_prompts_dir file

    C->>B: system_prompt(settings, user_prompts_dir, default_prompts_dir)
    B->>B: prompt_override(settings, "system")?
    alt override is true
        B->>U: read <user_prompts_dir>/player/system.md
        alt file exists
            U-->>B: text
            B-->>C: return text
        else file missing
            B->>D: read <default_prompts_dir>/system.md
            D-->>B: text or None
            B-->>C: return text or None
        end
    else override is false/absent
        B->>D: read <default_prompts_dir>/system.md
        D-->>B: text or None
        B-->>C: return text or None
    end
```

## Notes from review

- **Fail-fast on required config**: `Base.provider()` / `Base.model()` raise `ValueError` immediately when missing from `settings.yaml`, rather than silently defaulting — appropriate since a task can't run without them.
- **Graceful fallback elsewhere**: `.env` and `settings.yaml` are optional (missing files just yield `{}` / no-op), and MUD host/port fall back to `localhost:4000` — sensible defaults for local development.
- **Stateless task classes**: `Base`/`Player` never instantiate; every call takes `settings` explicitly, which keeps task logic pure and easy to unit test without constructing a `Config`.
- **Directory resolution is env-var-first**: `BOUKENSHA_DIR` must be set *before* `Config()` loads `.env`, since `.env` lives inside the directory being resolved — a deliberate ordering constraint worth keeping in mind if it's ever refactored.
