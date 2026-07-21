"""Shell tool module: registers a sandboxed run_command tool."""

from __future__ import annotations

import shlex
import subprocess
from pathlib import Path
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from boukensha.registry import Registry


class Shell:
    @staticmethod
    def register(
        registry: Registry,
        *,
        working_dir: str,
        timeout: int = 30,
        allowed_commands: list[str] | None = None,
    ) -> None:
        root = str(Path(working_dir).expanduser().resolve())

        def _oops(msg: str) -> str:
            return f"error: {msg}"

        allowed_note = (
            f" Allowed executables: {', '.join(allowed_commands)}."
            if allowed_commands
            else ""
        )
        description = (
            f"Run a shell command inside the working directory and return its combined "
            f"stdout+stderr output. Commands run with a {timeout}-second timeout.{allowed_note}"
        )

        def run_command(command: str) -> str:
            if allowed_commands is not None:
                try:
                    parts = shlex.split(command)
                except ValueError:
                    parts = command.strip().split()
                executable = parts[0] if parts else ""
                if executable not in allowed_commands:
                    return _oops(
                        f"'{executable}' is not in the allowed-commands list "
                        f"({', '.join(allowed_commands)})"
                    )

            try:
                result = subprocess.run(
                    command,
                    shell=True,
                    cwd=root,
                    stdout=subprocess.PIPE,
                    stderr=subprocess.STDOUT,
                    text=True,
                    timeout=timeout,
                )
                output = result.stdout.strip()
                exit_note = "" if result.returncode == 0 else f"\n[exit {result.returncode}]"
                return f"(no output){exit_note}" if not output else f"{output}{exit_note}"
            except subprocess.TimeoutExpired:
                return _oops(f"command timed out after {timeout}s: {command}")
            except FileNotFoundError as e:
                return _oops(f"command not found: {e}")
            except Exception as e:
                return _oops(str(e))

        registry.tool(
            "run_command",
            description,
            {"command": {"type": "string", "description": "The shell command to execute (e.g. 'python script.py', 'ls -la', 'git status')"}},
            block=run_command,
        )
