# Step 10 — A Standard Tool Library

Boukensha now ships two built-in tool modules. Instead of manually registering tools, the framework gives the agent a standard library of capabilities out of the box when `working_dir` is set.

## What's new

### `boukensha.tools.FileSystem`

Registers automatically when `working_dir` is set:

| Tool | Description |
|------|-------------|
| `pwd` | Return the working directory |
| `list_directory` | List files at a path (default `.`) |
| `read_file` | Read a file's contents |
| `write_file` | Write (or create) a file |
| `delete_file` | Delete a file |
| `search_files` | Grep for a regex pattern across the working tree, returns `path:line:content` matches |

All paths are **relative to the working directory**. Absolute paths and `..` traversals that escape the root are rejected with an error string.

### `boukensha.tools.Shell`

Registers automatically when `working_dir` is set:

| Tool | Description |
|------|-------------|
| `run_command` | Run a shell command inside the working directory |

Commands run with a configurable timeout and an optional allow-list of permitted executables.

### New `boukensha.run` / `boukensha.repl` keyword arguments

```python
boukensha.run(
    task="...",
    working_dir="/my/project",          # None (default) = os.getcwd(); False = no tools
    allowed_commands=["python", "git"], # None = allow all (default)
    shell_timeout=30                    # seconds, default 30
)
```

`allowed_commands=None` permits any executable. Pass an explicit list to lock the agent down:

```python
# Only allow python and git — rm, curl, etc. will be rejected
boukensha.run(task="...", allowed_commands=["python", "git"])
```

### Direct registration

Both modules can be registered manually for finer control:

```python
from boukensha.tools import FileSystem, Shell

FileSystem.register(registry, working_dir="/my/project")
Shell.register(registry, working_dir="/my/project", timeout=10, allowed_commands=["python"])
```

## Run the example

```sh
cd week1_baseline/python/10_standard_tool_library
uv sync
uv run python examples/example.py

# or via the global executable pointed at this step:
BOUKENSHA_PATH=~/Sites/boukensha/python/10_standard_tool_library boukensha
```

## Running the tests

```sh
uv run pytest tests/ -v
```
