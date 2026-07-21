from __future__ import annotations

import os
import tempfile
from pathlib import Path
from unittest.mock import MagicMock, patch

import yaml

from boukensha.run_dsl import RunDSL
from boukensha.context import Context
from boukensha.registry import Registry
from boukensha.tasks.player import Player
import boukensha


def _make_registry() -> Registry:
    ctx = Context(task=Player, system="sys")
    return Registry(ctx)


def test_run_dsl_registers_tool():
    registry = _make_registry()
    dsl = RunDSL(registry)
    dsl.tool("greet", description="Say hello", parameters={"name": {"type": "string"}}, block=lambda name: f"Hi {name}")
    assert "greet" in registry._context.tools


def test_run_dsl_tool_is_callable():
    registry = _make_registry()
    dsl = RunDSL(registry)
    dsl.tool("double", description="Double a number", parameters={"n": {"type": "integer"}}, block=lambda n: n * 2)
    result = registry.dispatch("double", {"n": 5})
    assert result == 10


def test_run_dsl_tool_no_parameters():
    registry = _make_registry()
    dsl = RunDSL(registry)
    dsl.tool("ping", description="Ping", block=lambda: "pong")
    result = registry.dispatch("ping", {})
    assert result == "pong"


def test_run_is_callable():
    assert callable(boukensha.run)


def test_run_dsl_exported():
    from boukensha import RunDSL
    assert RunDSL is not None


def test_run_returns_text(monkeypatch):
    """boukensha.run() must return the agent's final text without error."""
    # Provide a minimal .boukensha config so Config() doesn't fail
    with tempfile.TemporaryDirectory() as tmp:
        monkeypatch.setenv("BOUKENSHA_DIR", tmp)

        # Write a minimal settings.yaml
        settings = {
            "tasks": {
                "player": {
                    "provider": "anthropic",
                    "model": "claude-haiku-4-5",
                }
            }
        }
        with open(f"{tmp}/settings.yaml", "w") as f:
            yaml.dump(settings, f)

        with open(f"{tmp}/.env", "w") as f:
            f.write("ANTHROPIC_API_KEY=test-key\n")

        # Patch the Agent so no real HTTP call is made
        fake_agent = MagicMock()
        fake_agent.run.return_value = "mocked result"

        with patch("boukensha.Agent", return_value=fake_agent):
            result = boukensha.run(
                task="What is 2+2?",
                log=f"{tmp}/test-session.jsonl",
            )

        assert result == "mocked result"
        fake_agent.run.assert_called_once()


def test_repl_is_callable():
    assert callable(boukensha.repl)


def test_repl_exported():
    from boukensha import Repl
    assert Repl is not None


def test_repl_starts_and_exits_immediately(monkeypatch):
    """boukensha.repl() must start the REPL and exit cleanly on EOF."""
    import io

    with tempfile.TemporaryDirectory() as tmp:
        monkeypatch.setenv("BOUKENSHA_DIR", tmp)

        settings = {
            "tasks": {
                "player": {
                    "provider": "anthropic",
                    "model": "claude-haiku-4-5",
                }
            }
        }
        with open(f"{tmp}/settings.yaml", "w") as f:
            yaml.dump(settings, f)
        with open(f"{tmp}/.env", "w") as f:
            f.write("ANTHROPIC_API_KEY=test-key\n")

        with patch("sys.stdin", io.StringIO("")):
            boukensha.repl(tui=False, log=f"{tmp}/test-repl.jsonl")


def _make_boukensha_dir(tmp_path):
    tmp_path.mkdir(parents=True, exist_ok=True)
    settings = {
        "tasks": {"player": {"provider": "anthropic", "model": "claude-haiku-4-5"}}
    }
    with open(f"{tmp_path}/settings.yaml", "w") as f:
        yaml.dump(settings, f)
    with open(f"{tmp_path}/.env", "w") as f:
        f.write("ANTHROPIC_API_KEY=test-key\n")
    return tmp_path


def test_run_registers_filesystem_tools_when_working_dir_set(monkeypatch, tmp_path):
    bdir = _make_boukensha_dir(tmp_path / "bdir")
    wdir = tmp_path / "wdir"
    wdir.mkdir()
    monkeypatch.setenv("BOUKENSHA_DIR", str(bdir))

    captured_registry = []

    def fake_agent_init(**kwargs):
        captured_registry.append(kwargs["registry"])
        m = MagicMock()
        m.run.return_value = "done"
        return m

    with patch("boukensha.Agent", side_effect=fake_agent_init):
        import boukensha
        boukensha.run(
            task="test",
            working_dir=str(wdir),
            log=f"{tmp_path}/test.jsonl",
        )

    registry = captured_registry[0]
    tool_names = set(registry._context.tools.keys())
    assert "pwd" in tool_names
    assert "list_directory" in tool_names
    assert "read_file" in tool_names
    assert "write_file" in tool_names
    assert "delete_file" in tool_names
    assert "search_files" in tool_names
    assert "run_command" in tool_names


def test_run_skips_tools_when_working_dir_false(monkeypatch, tmp_path):
    bdir = _make_boukensha_dir(tmp_path / "bdir")
    monkeypatch.setenv("BOUKENSHA_DIR", str(bdir))

    captured_registry = []

    def fake_agent_init(**kwargs):
        captured_registry.append(kwargs["registry"])
        m = MagicMock()
        m.run.return_value = "done"
        return m

    with patch("boukensha.Agent", side_effect=fake_agent_init):
        import boukensha
        boukensha.run(
            task="test",
            working_dir=False,
            log=f"{tmp_path}/test.jsonl",
        )

    registry = captured_registry[0]
    assert "pwd" not in registry._context.tools
    assert "run_command" not in registry._context.tools


def test_run_defaults_working_dir_to_cwd(monkeypatch, tmp_path):
    bdir = _make_boukensha_dir(tmp_path / "bdir")
    monkeypatch.setenv("BOUKENSHA_DIR", str(bdir))

    captured_ctx = []

    def fake_agent_init(**kwargs):
        captured_ctx.append(kwargs["context"])
        m = MagicMock()
        m.run.return_value = "done"
        return m

    with patch("boukensha.Agent", side_effect=fake_agent_init):
        import boukensha
        boukensha.run(task="test", log=f"{tmp_path}/test.jsonl")

    assert captured_ctx[0].working_dir == os.getcwd()


def test_tools_exported():
    import boukensha
    assert hasattr(boukensha, "tools")
    assert hasattr(boukensha.tools, "FileSystem")
    assert hasattr(boukensha.tools, "Shell")


def test_tui_exported():
    import boukensha
    assert hasattr(boukensha, "Tui")
    from boukensha.tui import Tui
    assert boukensha.Tui is Tui


def test_repl_tui_false_calls_repl_start(monkeypatch, tmp_path):
    import yaml, os
    bdir = tmp_path / "bdir"
    bdir.mkdir()
    settings = {"tasks": {"player": {"provider": "anthropic", "model": "claude-haiku-4-5"}}}
    (bdir / "settings.yaml").write_text(yaml.dump(settings))
    (bdir / ".env").write_text("ANTHROPIC_API_KEY=test-key\n")
    monkeypatch.setenv("BOUKENSHA_DIR", str(bdir))

    started = []

    import boukensha
    from boukensha.repl import Repl as _Repl

    def fake_start(self):
        started.append(True)

    monkeypatch.setattr(_Repl, "start", fake_start)
    try:
        boukensha.repl(tui=False)
    except Exception:
        pass

    assert started, "Repl.start() was not called when tui=False"


def test_memory_enabled_helper_defaults_to_config():
    import boukensha
    from boukensha.config import Config

    mock_cfg = MagicMock(spec=Config)
    mock_cfg.memory_enabled = True
    assert boukensha._memory_enabled(mock_cfg, None) is True

    mock_cfg.memory_enabled = False
    assert boukensha._memory_enabled(mock_cfg, None) is False


def test_memory_enabled_helper_explicit_override_wins():
    import boukensha
    from boukensha.config import Config

    mock_cfg = MagicMock(spec=Config)
    mock_cfg.memory_enabled = False
    assert boukensha._memory_enabled(mock_cfg, True) is True

    mock_cfg.memory_enabled = True
    assert boukensha._memory_enabled(mock_cfg, False) is False


def test_run_registers_memory_tools_and_injects_prompt_by_default(monkeypatch):
    """memory=None (default) reads config (defaults to enabled) and wires everything."""
    with tempfile.TemporaryDirectory() as tmp:
        monkeypatch.setenv("BOUKENSHA_DIR", tmp)

        settings = {
            "tasks": {"player": {"provider": "anthropic", "model": "claude-haiku-4-5"}}
        }
        with open(f"{tmp}/settings.yaml", "w") as f:
            yaml.dump(settings, f)
        with open(f"{tmp}/.env", "w") as f:
            f.write("ANTHROPIC_API_KEY=test-key\n")

        fake_agent = MagicMock()
        fake_agent.run.return_value = "mocked result"

        captured_ctx = {}

        def _capture_agent(**kwargs):
            captured_ctx["context"] = kwargs["context"]
            return fake_agent

        with patch("boukensha.Agent", side_effect=_capture_agent):
            boukensha.run(task="hello", log=f"{tmp}/session.jsonl", working_dir=False)

        ctx = captured_ctx["context"]
        assert "read_memory" in ctx.tools
        assert "write_memory" in ctx.tools
        assert "player.md" in ctx.system
        assert "world.md" in ctx.system
        assert (Path(tmp) / "memory" / "player.md").exists()


def test_run_memory_false_disables_memory_entirely(monkeypatch):
    with tempfile.TemporaryDirectory() as tmp:
        monkeypatch.setenv("BOUKENSHA_DIR", tmp)

        settings = {
            "tasks": {"player": {"provider": "anthropic", "model": "claude-haiku-4-5"}}
        }
        with open(f"{tmp}/settings.yaml", "w") as f:
            yaml.dump(settings, f)
        with open(f"{tmp}/.env", "w") as f:
            f.write("ANTHROPIC_API_KEY=test-key\n")

        fake_agent = MagicMock()
        fake_agent.run.return_value = "mocked result"

        captured_ctx = {}

        def _capture_agent(**kwargs):
            captured_ctx["context"] = kwargs["context"]
            return fake_agent

        with patch("boukensha.Agent", side_effect=_capture_agent):
            boukensha.run(
                task="hello", log=f"{tmp}/session.jsonl", working_dir=False, memory=False
            )

        ctx = captured_ctx["context"]
        assert "read_memory" not in ctx.tools
        assert "write_memory" not in ctx.tools
        assert not (Path(tmp) / "memory").exists()


def test_repl_registers_memory_tools_and_injects_prompt_by_default(monkeypatch):
    """repl()'s memory wiring must match run()'s: memory=None reads config
    (defaults to enabled) and wires tools + prompt injection the same way."""
    import boukensha
    from boukensha.repl import Repl as _Repl

    with tempfile.TemporaryDirectory() as tmp:
        monkeypatch.setenv("BOUKENSHA_DIR", tmp)

        settings = {
            "tasks": {"player": {"provider": "anthropic", "model": "claude-haiku-4-5"}}
        }
        with open(f"{tmp}/settings.yaml", "w") as f:
            yaml.dump(settings, f)
        with open(f"{tmp}/.env", "w") as f:
            f.write("ANTHROPIC_API_KEY=test-key\n")

        captured_ctx = {}
        real_init = _Repl.__init__

        def fake_init(self, **kwargs):
            captured_ctx["context"] = kwargs["context"]
            real_init(self, **kwargs)

        monkeypatch.setattr(_Repl, "__init__", fake_init)
        monkeypatch.setattr(_Repl, "start", lambda self: None)

        boukensha.repl(tui=False, log=f"{tmp}/repl-session.jsonl", working_dir=False)

        ctx = captured_ctx["context"]
        assert "read_memory" in ctx.tools
        assert "write_memory" in ctx.tools
        assert "player.md" in ctx.system
        assert "world.md" in ctx.system
