from __future__ import annotations

import sys
from pathlib import Path

import pytest

from boukensha.context import Context
from boukensha.registry import Registry
from boukensha.tasks.player import Player
from boukensha.tools.shell import Shell


def _make_registry(tmp_path: Path) -> Registry:
    ctx = Context(task=Player, system="sys")
    return Registry(ctx)


@pytest.mark.skipif(sys.platform == "win32", reason="Unix shell commands")
def test_run_command_basic(tmp_path):
    registry = _make_registry(tmp_path)
    Shell.register(registry, working_dir=str(tmp_path))
    result = registry.dispatch("run_command", {"command": "echo hello"})
    assert "hello" in result


@pytest.mark.skipif(sys.platform == "win32", reason="Unix shell commands")
def test_run_command_merges_stderr(tmp_path):
    registry = _make_registry(tmp_path)
    Shell.register(registry, working_dir=str(tmp_path))
    result = registry.dispatch("run_command", {"command": "echo err >&2"})
    assert "err" in result


@pytest.mark.skipif(sys.platform == "win32", reason="Unix shell commands")
def test_run_command_nonzero_exit_noted(tmp_path):
    registry = _make_registry(tmp_path)
    Shell.register(registry, working_dir=str(tmp_path))
    result = registry.dispatch("run_command", {"command": "exit 1"})
    assert "[exit 1]" in result


@pytest.mark.skipif(sys.platform == "win32", reason="Unix shell commands")
def test_run_command_no_output(tmp_path):
    registry = _make_registry(tmp_path)
    Shell.register(registry, working_dir=str(tmp_path))
    result = registry.dispatch("run_command", {"command": "true"})
    assert result.startswith("(no output)")


@pytest.mark.skipif(sys.platform == "win32", reason="Unix shell commands")
def test_run_command_allowed_commands_permits(tmp_path):
    registry = _make_registry(tmp_path)
    Shell.register(registry, working_dir=str(tmp_path), allowed_commands=["echo"])
    result = registry.dispatch("run_command", {"command": "echo hi"})
    assert "hi" in result


@pytest.mark.skipif(sys.platform == "win32", reason="Unix shell commands")
def test_run_command_allowed_commands_blocks(tmp_path):
    registry = _make_registry(tmp_path)
    Shell.register(registry, working_dir=str(tmp_path), allowed_commands=["echo"])
    result = registry.dispatch("run_command", {"command": "rm -rf /"})
    assert result.startswith("error:")
    assert "allowed-commands" in result


@pytest.mark.skipif(sys.platform == "win32", reason="Unix shell commands")
def test_run_command_timeout(tmp_path):
    registry = _make_registry(tmp_path)
    Shell.register(registry, working_dir=str(tmp_path), timeout=1)
    result = registry.dispatch("run_command", {"command": "sleep 10"})
    assert result.startswith("error:")
    assert "timed out" in result


@pytest.mark.skipif(sys.platform == "win32", reason="Unix shell commands")
def test_run_command_runs_in_working_dir(tmp_path):
    (tmp_path / "probe.txt").write_text("probed")
    registry = _make_registry(tmp_path)
    Shell.register(registry, working_dir=str(tmp_path))
    result = registry.dispatch("run_command", {"command": "cat probe.txt"})
    assert "probed" in result


def test_run_command_description_includes_timeout(tmp_path):
    registry = _make_registry(tmp_path)
    Shell.register(registry, working_dir=str(tmp_path), timeout=45)
    tool = registry._context.tools["run_command"]
    assert "45" in tool.description


def test_run_command_description_includes_allowed_list(tmp_path):
    registry = _make_registry(tmp_path)
    Shell.register(registry, working_dir=str(tmp_path), allowed_commands=["python", "git"])
    tool = registry._context.tools["run_command"]
    assert "python" in tool.description
    assert "git" in tool.description
