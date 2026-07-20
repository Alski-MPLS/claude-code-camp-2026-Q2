from __future__ import annotations

from unittest.mock import MagicMock

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
