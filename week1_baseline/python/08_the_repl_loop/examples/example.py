import os
from pathlib import Path

os.environ.setdefault(
    "BOUKENSHA_DIR",
    str((Path(__file__).parent.parent.parent.parent.parent / ".boukensha").resolve()),
)

import boukensha
from boukensha import Config

# The step 07 folder makes a good playground — it already has source files.
base_dir = Path(__file__).parent.parent.parent / "07_the_run_dsl"

print(f"Config: {Config()}")
print()


def register_tools(dsl):
    dsl.tool(
        "read_file",
        description="Read the contents of a file from disk",
        parameters={"path": {"type": "string", "description": "File path relative to the working directory"}},
        block=lambda path: (base_dir / path).read_text(),
    )
    dsl.tool(
        "list_directory",
        description="List the files in a directory",
        parameters={"path": {"type": "string", "description": "Directory path relative to the working directory, or '.' for root"}},
        block=lambda path: ", ".join(
            f for f in os.listdir(base_dir / path) if not f.startswith(".")
        ),
    )


boukensha.repl(tool_registrar=register_tools)
