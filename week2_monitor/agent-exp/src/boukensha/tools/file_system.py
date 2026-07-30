"""FileSystem tool module: registers six sandboxed file-operation tools."""

from __future__ import annotations

import glob as _glob
import os
import re
from pathlib import Path
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from boukensha.registry import Registry


class FileSystem:
    @staticmethod
    def register(registry: Registry, *, working_dir: str) -> None:
        root = str(Path(working_dir).expanduser().resolve())

        def _resolve(path: str) -> str:
            absolute = str(Path(os.path.join(root, path)).resolve())
            if absolute == root or absolute.startswith(root + os.sep):
                return absolute
            return f"error: path '{path}' escapes the working directory"

        def _oops(msg: str) -> str:
            return f"error: {msg}"

        def pwd() -> str:
            return root

        registry.tool(
            "pwd",
            "Return the working directory — the root that all file paths are relative to.",
            {},
            block=pwd,
        )

        def list_directory(path: str = ".") -> str:
            target = _resolve(path)
            if target.startswith("error:"):
                return target
            if not os.path.isdir(target):
                return _oops(f"'{path}' is not a directory")
            entries = sorted(os.listdir(target))
            entries = [
                f"{e}/" if os.path.isdir(os.path.join(target, e)) else e
                for e in entries
            ]
            return "(empty)" if not entries else "\n".join(entries)

        registry.tool(
            "list_directory",
            "List files and subdirectories at a path relative to the working directory. Defaults to the working directory itself.",
            {"path": {"type": "string", "description": "Relative path to list (default '.')"}},
            block=list_directory,
        )

        def read_file(path: str) -> str:
            target = _resolve(path)
            if target.startswith("error:"):
                return target
            if not os.path.isfile(target):
                return _oops(f"'{path}' is not a file")
            try:
                return Path(target).read_text(encoding="utf-8")
            except Exception as e:
                return _oops(str(e))

        registry.tool(
            "read_file",
            "Read and return the full contents of a file. Path is relative to the working directory.",
            {"path": {"type": "string", "description": "Relative path to the file"}},
            block=read_file,
        )

        def write_file(path: str, content: str) -> str:
            target = _resolve(path)
            if target.startswith("error:"):
                return target
            try:
                os.makedirs(os.path.dirname(target), exist_ok=True)
                Path(target).write_text(content, encoding="utf-8")
                byte_count = len(content.encode("utf-8"))
                rel = target.removeprefix(root + os.sep)
                return f"ok: wrote {byte_count} bytes to {rel}"
            except Exception as e:
                return _oops(str(e))

        registry.tool(
            "write_file",
            "Write content to a file, creating it (and any missing parent directories) if needed, overwriting if it exists. Path is relative to the working directory.",
            {
                "path": {"type": "string", "description": "Relative path to the file"},
                "content": {"type": "string", "description": "Text content to write"},
            },
            block=write_file,
        )

        def delete_file(path: str) -> str:
            target = _resolve(path)
            if target.startswith("error:"):
                return target
            if not os.path.isfile(target):
                return _oops(f"'{path}' is not a file")
            try:
                os.remove(target)
                return f"ok: deleted {path}"
            except Exception as e:
                return _oops(str(e))

        registry.tool(
            "delete_file",
            "Delete a file. Directories are not deleted. Path is relative to the working directory.",
            {"path": {"type": "string", "description": "Relative path to the file to delete"}},
            block=delete_file,
        )

        def search_files(pattern: str, path: str = ".", glob: str = "*") -> str:
            target = _resolve(path)
            if target.startswith("error:"):
                return target

            if os.path.isfile(target):
                file_pattern = target
            else:
                file_pattern = os.path.join(target, "**", glob)

            try:
                regex = re.compile(pattern)
            except re.error as e:
                return _oops(f"invalid pattern: {e}")

            matches: list[str] = []
            for file in sorted(_glob.glob(file_pattern, recursive=True)):
                if not os.path.isfile(file):
                    continue
                rel = file.removeprefix(root + os.sep)
                try:
                    with open(file, encoding="utf-8", errors="replace") as f:
                        for lineno, line in enumerate(f, 1):
                            if regex.search(line):
                                matches.append(f"{rel}:{lineno}:{line.rstrip()}")
                except Exception as e:
                    matches.append(f"{rel}: error reading file: {e}")

            return "no matches" if not matches else "\n".join(matches)

        registry.tool(
            "search_files",
            "Search for a text pattern (literal string or Python regex) across all files in the working directory tree. Returns matching lines in 'path:line_number:content' format.",
            {
                "pattern": {"type": "string", "description": "The text or regex pattern to search for"},
                "path": {"type": "string", "description": "Subdirectory or file to search within (default '.' = entire working directory)"},
                "glob": {"type": "string", "description": "File glob to restrict which files are searched, e.g. '*.py' (default '*')"},
            },
            block=search_files,
        )
