"""Resolves which step folder's ``boukensha`` package to load, then boots its REPL.

This module lives *outside* the ``boukensha`` package on purpose — it is the
piece that decides which ``boukensha`` gets imported, so it can't itself be
part of the thing it's choosing between.

Resolution order:
  1. BOUKENSHA_PATH environment variable (selects which *step* src/boukensha to load)
  2. ~/.boukensharc  (a file containing a single step-folder path)
  3. The src/boukensha bundled inside this installed distribution (the latest step)

Config directory (settings.yaml, .env, system.md) is separate:
  BOUKENSHA_DIR=~/.boukensha  (default, set in env to override)

Examples:
  boukensha                                                              # uses bundled lib + ~/.boukensha
  BOUKENSHA_PATH=~/Sites/boukensha/04_api_client boukensha                # loads step 4
  BOUKENSHA_DIR=~/projects/mybot/.boukensha boukensha                    # custom config dir
  echo ~/Sites/boukensha/09_global_executable > ~/.boukensharc && boukensha  # permanent step default
"""

from __future__ import annotations

import os
import sys
from pathlib import Path

# Absolute path to this distribution's own bundled src/ directory.
BUNDLED_SRC_DIR = str(Path(__file__).parent)


def _src_dir_for(step_dir: Path) -> str:
    return str(step_dir / "src")


def _has_package(src_dir: str) -> bool:
    return (Path(src_dir) / "boukensha" / "__init__.py").is_file()


def resolve() -> str:
    """Return the src/ directory containing the ``boukensha`` package to load."""
    path_env = os.environ.get("BOUKENSHA_PATH")
    if path_env:
        step_dir = Path(path_env).expanduser().resolve()
        src_dir = _src_dir_for(step_dir)
        if _has_package(src_dir):
            return src_dir
        raise SystemExit(
            "boukensha: BOUKENSHA_PATH is set but no src/boukensha/__init__.py found at:\n"
            f"       {step_dir}\n"
            "       Make sure BOUKENSHA_PATH points to a step folder, e.g.:\n"
            "       BOUKENSHA_PATH=~/Sites/boukensha/08_the_repl_loop boukensha"
        )

    rc_file = Path.home() / ".boukensharc"
    if rc_file.is_file():
        rc_value = rc_file.read_text().strip()
        if rc_value:
            step_dir = Path(rc_value).expanduser().resolve()
            src_dir = _src_dir_for(step_dir)
            if _has_package(src_dir):
                return src_dir
            raise SystemExit(
                f"boukensha: ~/.boukensharc points to {step_dir}\n"
                "       but no src/boukensha/__init__.py was found there.\n"
                "       Update ~/.boukensharc or remove it to use the bundled default."
            )

    return BUNDLED_SRC_DIR
