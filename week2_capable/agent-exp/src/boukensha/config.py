"""Boukensha::Config port: resolves the ``.boukensha`` config directory and
loads its ``.env`` and ``settings.yaml`` files.
"""

from __future__ import annotations

import os
from pathlib import Path
from typing import Any

import yaml
from dotenv import load_dotenv


def _find_git_root(start: Path) -> Path | None:
    """Walk upward from ``start`` looking for a ``.git`` directory."""
    for candidate in (start, *start.parents):
        if (candidate / ".git").exists():
            return candidate
    return None


class Config:
    # The package root, i.e. the parent of the ``src`` directory this file lives under.
    # Used for locating library assets (prompts) shipped alongside the code.
    PACKAGE_ROOT = Path(__file__).parent.parent.parent

    # The monorepo root (nearest ancestor containing .git), so a single shared
    # .boukensha config directory can serve every step/week folder underneath it.
    # Falls back to PACKAGE_ROOT if no .git is found (e.g. running outside a clone).
    REPO_ROOT = _find_git_root(PACKAGE_ROOT) or PACKAGE_ROOT

    # The .boukensha config directory is resolved in this order:
    #   1. BOUKENSHA_DIR environment variable (set before loading .env)
    #   2. <repo_root>/.boukensha (default)
    DEFAULT_DIR = str(REPO_ROOT / ".boukensha")

    # Default prompts shipped alongside the library code.
    PROMPTS_DIR = str((PACKAGE_ROOT / "prompts").resolve())

    def __init__(self) -> None:
        self.dir = self._resolve_dir()
        self._load_env()
        self.settings: dict[str, Any] = self._load_settings()

    # ---------- tasks -----------------------------------------------------

    def tasks(self, name: str | None = None) -> dict[str, Any]:
        """With no argument: returns the full tasks dict from settings.yaml.
        With a name: returns that task's settings dict, e.g. tasks("player").
        """
        all_tasks = self.dig("tasks") or {}
        return (all_tasks.get(name) or {}) if name else all_tasks

    @property
    def user_prompts_dir(self) -> str:
        """The user's prompts directory for task prompt overrides."""
        return str(Path(self.dir) / "prompts")

    # ---------- MUD connection ----------------------------------------------

    @property
    def mud_host(self) -> str:
        return self.dig("mud", "host") or "localhost"

    @property
    def mud_port(self) -> int:
        return self.dig("mud", "port") or 4000

    @property
    def mud_username(self) -> str | None:
        return self.dig("mud", "username")

    @property
    def mud_password(self) -> str | None:
        return self.dig("mud", "password")

    # ---------- low-level helpers -------------------------------------------

    def dig(self, *keys: str) -> Any:
        """Fetch a nested key path from settings, e.g. dig("mud", "host")."""
        node: Any = self.settings
        for key in keys:
            if isinstance(node, dict):
                node = node.get(key)
            else:
                return None
        return node

    def __repr__(self) -> str:
        return f"Config(dir={self.dir}, tasks={','.join(self.tasks().keys())})"

    # ---------- private -----------------------------------------------------

    def _resolve_dir(self) -> str:
        raw = os.environ.get("BOUKENSHA_DIR") or self.DEFAULT_DIR
        return str(Path(raw).expanduser().resolve())

    def _load_env(self) -> None:
        env_file = Path(self.dir) / ".env"
        if env_file.exists():
            load_dotenv(env_file)

    def _load_settings(self) -> dict[str, Any]:
        settings_file = Path(self.dir) / "settings.yaml"
        if settings_file.exists():
            return yaml.safe_load(settings_file.read_text()) or {}
        return {}
