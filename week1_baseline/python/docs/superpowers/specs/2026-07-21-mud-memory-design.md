# MUD persistent memory (player.md / world.md) — design

Scope: `12_context/` only (the current step folder). Not backported to earlier steps.

## Problem

The MUD tools (`boukensha/tools/mud.py`) fire commands at the CircleMUD server and
return raw text, but nothing is remembered between calls. The agent has no notion
of which rooms connect to which, what's in them, or its own long-term state — it
re-discovers the world from scratch every session and within a session relies
entirely on what's still in the conversation window.

## Goal

Give the agent two persistent markdown files it maintains itself:

- `player.md` — character stats, goals, notes.
- `world.md` — the map: rooms, exits, connections, shops, landmarks.

The feature must be modular: fully removable via a single toggle, with zero
overhead when off.

## Design

### Location

Files live in `~/.boukensha/memory/` by default (alongside the existing
`settings.yaml`/`.env` config dir), configurable via a new `memory.dir` key in
`settings.yaml`. This directory is outside the project repo by default, so the
files are never git-tracked. Since `BOUKENSHA_DIR` can be redirected, add a
defensive `.boukensha/` entry to `12_context/.gitignore` in case someone points
it inside the project.

Both files are shared across all MUD characters (no per-character split) — this
is a single-user local tool and splitting adds path complexity for no real
benefit here.

### New module: `boukensha/tools/memory.py`

Mirrors the shape of `tools/mud.py` and `tools/file_system.py`.

```python
_FILES = {
    "player": ("player.md", "# Player Notes\n\n(nothing recorded yet)\n"),
    "world":  ("world.md",  "# World Map\n\n(nothing recorded yet)\n"),
}
```

- `_ensure_files(memory_dir) -> dict[str, Path]` — creates the directory and any
  missing file with its default template. Used by both registration and prompt
  injection so first-run behavior is identical either way.
- `Memory.register(registry, *, memory_dir)` — registers exactly two tools:
  - `read_memory(file: "player"|"world")` — returns the file's full contents.
  - `write_memory(file: "player"|"world", content: str)` — overwrites the file
    (same overwrite semantics as the existing `write_file` tool — the agent
    rewrites the whole document when it wants to prune or reorganize; no
    diffing/append logic needed).
  Both reject any `file` value outside `{"player", "world"}` with an
  `"error: ..."` string, matching the error style already used in
  `file_system.py` and `mud.py` (return a string, never raise, so a bad
  argument can't crash the agent loop).
- `Memory.prompt_block(memory_dir) -> str` — calls `_ensure_files`, then returns
  a self-contained instructional block with both files' current contents
  inlined:

  ```
  ## Persistent memory
  You maintain two memory files across sessions — player.md (your character:
  stats, goals, notes) and world.md (the map: rooms, exits, shops, landmarks).
  Use read_memory/write_memory to keep them current, especially after entering
  a new room or a notable change to your character. Rewrite rather than let
  them grow unbounded.

  --- player.md ---
  {player_contents}

  --- world.md ---
  {world_contents}
  ```

### Config: `boukensha/config.py`

Two new properties, following the existing `dig()` pattern used for `mud_*`:

- `memory_enabled` — `dig("memory", "enabled")`, default `True`.
- `memory_dir` — `dig("memory", "dir")`, default `str(Path(self.dir) / "memory")`.

### Wiring: `boukensha/__init__.py`

`run()` and `repl()` each get a new `memory: bool | None = None` parameter,
mirroring the existing `mud: dict | bool | None` toggle:

- `None` (default) → use `cfg.memory_enabled` from `settings.yaml`.
- `False` → disabled outright: no tools registered, nothing appended to the
  system prompt, zero overhead.
- `True` → forced on regardless of config.

When enabled:
1. `Memory.prompt_block(memory_dir)` is computed and appended to
   `resolved_system` **before** `Context` is constructed, so the agent starts
   every session already oriented on its current state.
2. `tools.Memory.register(registry, memory_dir=memory_dir)` is called alongside
   the existing `FileSystem`/`Shell`/`Mud` registration — critically,
   **independent of `working_dir`**, so it still works when MUD mode sets
   `working_dir=False` (the current behavior when `MUD_NAME` is set, per
   `boukensha_loader.py`).

### REPL: `boukensha/repl.py`

- Add a `_MEMORY_TOOL_NAMES = frozenset({"read_memory", "write_memory"})` set,
  matching the existing `_MUD_TOOL_NAMES` pattern.
- Add a `/memory` command that lists registered memory tool names, matching the
  existing `/mud` and `/file` commands, and mention it in `HELP`.

## Error handling

- Unknown `file` argument to `read_memory`/`write_memory` → `"error: invalid
  file: ... (expected one of player, world)"`, no disk access attempted.
- Directory/file creation uses `os.makedirs(..., exist_ok=True)` +
  `Path.write_text`, same as `file_system.py`'s `write_file`.
- If `memory=False`, none of the above code paths run at all.

## Testing

`tests/test_tools_memory.py`, mirroring `test_tools_file_system.py`:
- Registration creates the directory and both files with default templates if
  absent.
- `read_memory`/`write_memory` round-trip correctly for both `"player"` and
  `"world"`.
- Invalid `file` value returns an error string and does not touch disk.
- `prompt_block()` output contains both filenames' markers and current content.

Plus a check at the `run()`/`repl()` wiring level (wherever the existing
`mud=False` toggle is tested) confirming `memory=False` registers no memory
tools and adds nothing to the system prompt.

## Out of scope

- Structured/parsed world-state tracking (auto-parsing `look`/`exits` output
  into a graph). Rejected as fragile (coupled to CircleMUD's exact text
  format) and unnecessary — freeform LLM-authored notes satisfy the stated
  goal more simply.
- Per-character memory files.
- Env-var-only toggle (`BOUKENSHA_MEMORY=...`) — the `memory:` parameter +
  `settings.yaml` already covers this; can be added later if a real need
  shows up.
- Backporting to earlier step folders (01–11).
