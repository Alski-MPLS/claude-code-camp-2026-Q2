from __future__ import annotations

from boukensha.run_dsl import RunDSL
from boukensha.context import Context
from boukensha.registry import Registry
from boukensha.tasks.player import Player


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


import boukensha


def test_run_is_callable():
    assert callable(boukensha.run)


def test_run_dsl_exported():
    from boukensha import RunDSL
    assert RunDSL is not None


def test_run_returns_text(monkeypatch):
    """boukensha.run() must return the agent's final text without error."""
    import os
    import tempfile
    from unittest.mock import MagicMock, patch

    # Provide a minimal .boukensha config so Config() doesn't fail
    with tempfile.TemporaryDirectory() as tmp:
        monkeypatch.setenv("BOUKENSHA_DIR", tmp)

        # Write a minimal settings.yaml
        import yaml
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
    import tempfile
    import yaml
    from unittest.mock import MagicMock, patch

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
            boukensha.repl(log=f"{tmp}/test-repl.jsonl")
