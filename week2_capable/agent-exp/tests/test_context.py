from __future__ import annotations

from pathlib import Path

from boukensha.context import Context
from boukensha.registry import Registry
from boukensha.run_dsl import RunDSL
from boukensha.tasks.player import Player


def _make_ctx(**kw) -> Context:
    return Context(task=Player, system="sys", **kw)


# ── existing tests (keep) ────────────────────────────────────────────────────

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


# ── new token-tracking tests ─────────────────────────────────────────────────

def test_context_default_context_window():
    ctx = _make_ctx()
    assert ctx.context_window == 200_000


def test_context_custom_context_window():
    ctx = _make_ctx(context_window=128_000)
    assert ctx.context_window == 128_000


def test_context_current_tokens_starts_zero():
    ctx = _make_ctx()
    assert ctx.current_tokens == 0


def test_context_turn_tokens_starts_zero():
    ctx = _make_ctx()
    assert ctx.turn_tokens == 0


def test_context_update_tokens():
    ctx = _make_ctx()
    ctx.update_tokens(5000)
    assert ctx.current_tokens == 5000


def test_context_update_tokens_accepts_string():
    ctx = _make_ctx()
    ctx.update_tokens("3000")
    assert ctx.current_tokens == 3000


def test_context_reset_turn_tokens():
    ctx = _make_ctx()
    ctx.add_turn_tokens(100, 50)
    ctx.reset_turn_tokens()
    assert ctx.turn_tokens == 0


def test_context_add_turn_tokens_accumulates():
    ctx = _make_ctx()
    ctx.add_turn_tokens(100, 50)
    ctx.add_turn_tokens(200, 75)
    assert ctx.turn_tokens == 425


def test_context_usage_fraction_zero_when_no_tokens():
    ctx = _make_ctx()
    assert ctx.usage_fraction == 0.0


def test_context_usage_fraction():
    ctx = _make_ctx(context_window=200_000)
    ctx.update_tokens(100_000)
    assert ctx.usage_fraction == 0.5


def test_context_usage_pct():
    ctx = _make_ctx(context_window=200_000)
    ctx.update_tokens(170_000)
    assert ctx.usage_pct == 85


def test_context_usage_fraction_zero_when_context_window_zero():
    ctx = _make_ctx(context_window=0)
    assert ctx.usage_fraction == 0.0


def test_context_needs_compaction_false_below_threshold():
    ctx = _make_ctx(context_window=200_000)
    ctx.update_tokens(100_000)  # 50 %
    assert ctx.needs_compaction() is False


def test_context_needs_compaction_true_at_threshold():
    ctx = _make_ctx(context_window=200_000, compaction_threshold=0.85)
    ctx.update_tokens(170_000)  # exactly 85 %
    assert ctx.needs_compaction() is True


def test_context_needs_compaction_custom_threshold():
    ctx = _make_ctx(context_window=200_000)
    ctx.update_tokens(140_000)  # 70 %
    assert ctx.needs_compaction(threshold=0.70) is True
    assert ctx.needs_compaction(threshold=0.71) is False


def test_context_compact_messages_drops_oldest_40_pct():
    ctx = _make_ctx()
    for i in range(10):
        ctx.add_message("user", f"msg {i}")
    dropped = ctx.compact_messages()
    # ceil(10 * 0.40) = 4 dropped
    assert dropped == 4
    assert len(ctx.messages) == 6


def test_context_compact_messages_keeps_at_least_2():
    ctx = _make_ctx()
    ctx.add_message("user", "a")
    ctx.add_message("user", "b")
    ctx.add_message("user", "c")
    # ceil(3 * 0.40) = 2, but that would leave only 1 — capped to keep 2
    dropped = ctx.compact_messages()
    assert len(ctx.messages) >= 2


def test_context_compact_messages_resets_current_tokens():
    ctx = _make_ctx()
    ctx.update_tokens(170_000)
    for i in range(5):
        ctx.add_message("user", f"msg {i}")
    ctx.compact_messages()
    assert ctx.current_tokens == 0


def test_context_compact_messages_returns_zero_for_empty():
    ctx = _make_ctx()
    dropped = ctx.compact_messages()
    assert dropped == 0


def test_context_compact_messages_custom_target_fraction():
    ctx = _make_ctx()
    for i in range(10):
        ctx.add_message("user", f"msg {i}")
    # target_fraction=0.30 → drop_fraction=0.70 → ceil(10*0.70)=7
    dropped = ctx.compact_messages(target_fraction=0.30)
    assert dropped == 7
    assert len(ctx.messages) == 3


def test_context_clear_messages_resets_current_tokens():
    ctx = _make_ctx()
    ctx.update_tokens(5000)
    ctx.add_message("user", "hi")
    ctx.clear_messages()
    assert ctx.current_tokens == 0
    assert ctx.messages == []
