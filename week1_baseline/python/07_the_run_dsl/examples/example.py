import os
from pathlib import Path

os.environ.setdefault(
    "BOUKENSHA_DIR",
    str((Path(__file__).parent.parent.parent.parent.parent / ".boukensha").resolve()),
)

import boukensha
from boukensha import Config

base_dir = Path(__file__).parent.parent.resolve()

print("=== BOUKENSHA Step 7: The Boukensha.run DSL ===")
print()
print(f"Config: {Config()}")
print()


def register_tools(dsl):
    dsl.tool(
        "read_file",
        description="Read the contents of a file from disk",
        parameters={"path": {"type": "string", "description": "The file path to read"}},
        block=lambda path: (base_dir / path).read_text(),
    )
    dsl.tool(
        "list_directory",
        description="List the files in a directory",
        parameters={"path": {"type": "string", "description": "The directory path to list"}},
        block=lambda path: ", ".join(
            f for f in os.listdir(base_dir / path) if not f.startswith(".")
        ),
    )


result = boukensha.run(
    task="Read the README.md file and summarise what this MUD player assistant framework can do.",
    tool_registrar=register_tools,
)

print()
print("=== FINAL RESPONSE ===")
print(result)
