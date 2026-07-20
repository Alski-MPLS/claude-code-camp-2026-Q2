# 02 · The Tool Registry (Python)

Python port of `ruby/02_the_registry`. The Registry is how BOUKENSHA manages
what capabilities the agent can use — it stores tools and dispatches calls to
them by name. Carries `Config`, `Base`, `Player`, `Tool`, `Message`, `Context`
forward from `01_struct_skeleton` **unchanged** (confirmed byte-identical
against the Ruby source: `diff -rq ruby/01_struct_skeleton/lib
ruby/02_the_registry/lib` shows only two files added, nothing modified). This
step adds `boukensha.errors.UnknownToolError` and `boukensha.registry.Registry`.

## How it works

The agent never calls a tool directly. It emits a structured request (name +
args) and the `Registry` looks up the tool and runs it:

```
Agent:     "Hey registry, call move with direction='north'"
Registry:  looks up "move" in the tool table
Registry:  found it, calls the block with the provided args
Registry:  here's the result
```

## Requirements

- Python 3.11+
- [`uv`](https://docs.astral.sh/uv/) for dependency management

## Install

```bash
cd python/02_the_registry
uv sync
```

## Package layout

```
python/02_the_registry/
  pyproject.toml         # project metadata + deps, managed via uv
  src/boukensha/
    __init__.py            # re-exports Config, Context, Message, Tool, Registry, UnknownToolError, tasks
    config.py              # Config class (unchanged from 01_struct_skeleton)
    tool.py                # Tool dataclass (unchanged)
    message.py             # Message dataclass (unchanged)
    context.py             # Context class (unchanged)
    errors.py              # UnknownToolError
    registry.py            # Registry class
    tasks/
      __init__.py
      base.py               # Base task class
      player.py              # Player(Base), TASK_NAME = "player"
  examples/
    example.py              # runnable smoke-test
```

## `Registry`

| Method | Description |
|---|---|
| `Registry(context)` | wraps a `Context`; tools registered through the registry are still stored on that context |
| `.tool(name, description, parameters=None, *, block)` | constructs a `Tool` and registers it on the context; returns the `Tool` |
| `.dispatch(name, args=None)` | looks up a tool by name and calls `tool.block(**args)`; raises `UnknownToolError` if no tool is registered under that name |

## `UnknownToolError`

Raised when `dispatch` is called with a name that has no registered tool. A
harness needs explicit error boundaries — an unrecognised tool name should
never silently fail.

```
UnknownToolError: No tool registered as 'flee'
```

## Design note: no key-transformation step in `dispatch`

Ruby's `dispatch` calls `args.transform_keys(&:to_sym)` before invoking the
block, because Ruby blocks with keyword parameters require **symbol** keys,
while the args arrive **string**-keyed (as they would from parsed JSON). This
is called out in the Ruby README as a deliberate, visible gotcha.

Python has no such gap: keyword arguments are already matched by string name
(`tool.block(**args)` works directly on a string-keyed dict), so there is
nothing to transform. This is a language difference, not a dropped feature.

## Run example

```bash
uv run examples/example.py
```

Expected output (`Config` line's directory depends on your `.boukensha/`
location; the two `Tool` description fields are truncated by `Tool.__repr__`
to a fixed width):

```
=== BOUKENSHA Step 2: Tool Registry ===

Config:  Config(dir=..., tasks=player)
Context: #<Context task=player turns=0 tools=2>
Tools:
  #<Tool name=move description=Move the player in a direction (north, so params=['direction']>
  #<Tool name=shout description=Shout a message so everyone in the zone c params=['message']>

Dispatching 'shout' with message='dragon spotted'...
Result: DRAGON SPOTTED

Dispatching 'move' with direction='north'...
Result: You move north into a torch-lit corridor.

UnknownToolError caught: No tool registered as 'flee'
```
