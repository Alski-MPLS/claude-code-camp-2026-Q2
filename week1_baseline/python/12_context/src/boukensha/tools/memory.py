"""Memory tool module: two persistent markdown files the agent maintains
itself — player.md (character state) and world.md (the map).

Modular by design: nothing in this module is imported or invoked unless the
caller opts in via ``Memory.register`` / ``Memory.prompt_block``. See
boukensha/__init__.py's ``memory`` parameter on run()/repl().
"""

from __future__ import annotations

from pathlib import Path
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from boukensha.registry import Registry

_FILES: dict[str, tuple[str, str]] = {
    "player": ("player.md", "# Player Notes\n\n(nothing recorded yet)\n"),
    "world":  ("world.md",  "# World Map\n\n(nothing recorded yet)\n"),
}

_PROMPT_HEADER = (
    "## Persistent memory\n"
    "You maintain two memory files across sessions — player.md (your character: "
    "stats, goals, notes) and world.md (the map: rooms, exits, shops, landmarks). "
    "Use read_memory/write_memory to keep them current, especially after entering "
    "a new room or a notable change to your character. Rewrite rather than let "
    "them grow unbounded."
)


def _ensure_files(memory_dir: str) -> dict[str, Path]:
    root = Path(memory_dir).expanduser()
    root.mkdir(parents=True, exist_ok=True)
    paths: dict[str, Path] = {}
    for key, (filename, template) in _FILES.items():
        path = root / filename
        if not path.exists():
            path.write_text(template, encoding="utf-8")
        paths[key] = path
    return paths


class Memory:
    """Registers read_memory/write_memory tools against a registry."""

    @staticmethod
    def register(registry: "Registry", *, memory_dir: str) -> None:
        paths = _ensure_files(memory_dir)

        def read_memory(file: str) -> str:
            path = paths.get(file.strip().lower())
            if path is None:
                return f"error: invalid file: {file!r} (expected one of {', '.join(sorted(_FILES))})"
            try:
                return path.read_text(encoding="utf-8")
            except Exception as e:
                return f"error: {e}"

        registry.tool(
            "read_memory",
            "Read the current contents of a persistent memory file.",
            {"file": {"type": "string", "description": "player | world"}},
            block=read_memory,
        )

        def write_memory(file: str, content: str) -> str:
            path = paths.get(file.strip().lower())
            if path is None:
                return f"error: invalid file: {file!r} (expected one of {', '.join(sorted(_FILES))})"
            try:
                path.write_text(content, encoding="utf-8")
                return f"ok: wrote {len(content.encode('utf-8'))} bytes to {path.name}"
            except Exception as e:
                return f"error: {e}"

        registry.tool(
            "write_memory",
            "Overwrite a persistent memory file with new content.",
            {
                "file": {"type": "string", "description": "player | world"},
                "content": {"type": "string", "description": "Full new contents of the file"},
            },
            block=write_memory,
        )

    @staticmethod
    def prompt_block(memory_dir: str) -> str:
        paths = _ensure_files(memory_dir)
        sections = "\n\n".join(
            f"--- {path.name} ---\n{path.read_text(encoding='utf-8')}"
            for path in paths.values()
        )
        return f"{_PROMPT_HEADER}\n\n{sections}"
