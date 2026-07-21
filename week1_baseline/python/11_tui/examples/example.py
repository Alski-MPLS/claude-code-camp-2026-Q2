#!/usr/bin/env python
"""Step 10 — A Standard Tool Library demo.

Demonstrates auto-registration of FileSystem and Shell tools via working_dir.
"""

from __future__ import annotations

import os
from pathlib import Path

import sys
sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

os.environ.setdefault(
    "BOUKENSHA_DIR",
    str(Path(__file__).parent.parent.parent.parent.parent / ".boukensha"),
)

import boukensha

cfg = boukensha.Config()
print(f"Config: {cfg}")
print(f"API key set? {bool(os.environ.get('ANTHROPIC_API_KEY'))}")
print()

boukensha.run(
    task=(
        "List the files in the current working directory, read one of them, "
        "then tell me what you found."
    ),
    working_dir=str(Path(__file__).parent),
)
