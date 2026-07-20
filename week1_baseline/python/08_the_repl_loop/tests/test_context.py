from __future__ import annotations

from boukensha.context import Context
from boukensha.registry import Registry
from boukensha.run_dsl import RunDSL
from boukensha.tasks.player import Player


def _make_ctx() -> Context:
    return Context(task=Player, system="sys")


def test_clear_messages_wipes_history():
    ctx = _make_ctx()
    ctx.add_message("user", "hello")
    ctx.add_message("assistant", "hi")
    ctx.clear_messages()
    assert ctx.messages == []


def test_clear_messages_keeps_tools():
    ctx = _make_ctx()
    registry = Registry(ctx)
    dsl = RunDSL(registry)
    dsl.tool("ping", description="Ping", block=lambda: "pong")
    ctx.add_message("user", "hello")
    ctx.clear_messages()
    assert "ping" in ctx.tools
    assert ctx.messages == []


def test_clear_messages_resets_turn_count():
    ctx = _make_ctx()
    ctx.add_message("user", "one")
    ctx.add_message("user", "two")
    ctx.clear_messages()
    assert ctx.turn_count == 0
