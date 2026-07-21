from __future__ import annotations

from pathlib import Path

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


def test_context_working_dir_resolves_path(tmp_path):
    ctx = Context(task=Player, system="sys", working_dir=str(tmp_path))
    assert ctx.working_dir == str(tmp_path.resolve())


def test_context_working_dir_none_by_default():
    ctx = Context(task=Player, system="sys")
    assert ctx.working_dir is None


def test_context_working_dir_expands_tilde(monkeypatch, tmp_path):
    monkeypatch.setenv("HOME", str(tmp_path))
    ctx = Context(task=Player, system="sys", working_dir="~")
    assert ctx.working_dir == str(tmp_path.resolve())
