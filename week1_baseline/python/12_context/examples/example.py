#!/usr/bin/env python
"""Step 12 — Context Management demo.

Launches the Textual TUI by default.  Pass --no-tui for the plain REPL.
"""

from __future__ import annotations

import os
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

os.environ.setdefault(
    "BOUKENSHA_DIR",
    str(Path(__file__).parent.parent.parent.parent.parent / ".boukensha"),
)

import boukensha

use_tui = "--no-tui" not in sys.argv

boukensha.repl(
    tui=use_tui,
    working_dir=str(Path(__file__).parent),
)
