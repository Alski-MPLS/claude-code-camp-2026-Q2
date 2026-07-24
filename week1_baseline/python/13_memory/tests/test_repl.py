from __future__ import annotations

import io
import tempfile
from unittest.mock import MagicMock, patch

import boukensha
from boukensha.context import Context
from boukensha.logger import Logger
from boukensha.repl import Repl
from boukensha.registry import Registry
from boukensha.tasks.player import Player


def _make_repl(responses=None, **kwargs):
    ctx = Context(task=Player, system="sys")
    registry = Registry(ctx)

    mock_builder = MagicMock()
    if responses:
        mock_builder.parse_response.side_effect = responses
    else:
        mock_builder.parse_response.return_value = {
            "stop_reason": "end_turn",
            "content": [{"type": "text", "text": "ok"}],
        }
    mock_builder.to_api_payload.return_value = {}
    mock_builder.backend = None
    mock_client = MagicMock()
    mock_client.call.return_value = {}

    _tmp = tempfile.mkdtemp()
    _logger = Logger(dir=_tmp)

    defaults = dict(
        context=ctx,
        registry=registry,
        builder=mock_builder,
        client=mock_client,
        logger=_logger,
        task_settings={},
        max_iterations=25,
        max_turn_tokens=None,
        max_output_tokens=None,
        config_dir=None,
        provider="anthropic",
        model="claude-haiku-4-5",
        version="0.1.0",
        api_key="test-key",
    )
    defaults.update(kwargs)
    return Repl(**defaults), ctx, _logger


def _run_with_input(repl, lines):
    text = "\n".join(lines) + "\n"
    with patch("sys.stdin", io.StringIO(text)):
        repl.start()


def test_repl_exits_on_exit_command(capsys):
    repl, _, logger = _make_repl()
    try:
        _run_with_input(repl, ["/exit"])
    finally:
        logger.close()
    captured = capsys.readouterr()
    assert "Goodbye" in captured.out


def test_repl_exits_on_quit_command(capsys):
    repl, _, logger = _make_repl()
    try:
        _run_with_input(repl, ["/quit"])
    finally:
        logger.close()
    captured = capsys.readouterr()
    assert "Goodbye" in captured.out


def test_repl_exits_on_eof(capsys):
    repl, _, logger = _make_repl()
    try:
        with patch("sys.stdin", io.StringIO("")):
            repl.start()
    finally:
        logger.close()
    # no exception raised


def test_repl_help_command(capsys):
    repl, _, logger = _make_repl()
    try:
        _run_with_input(repl, ["/help", "/exit"])
    finally:
        logger.close()
    captured = capsys.readouterr()
    assert "/clear" in captured.out
    assert "/exit" in captured.out


def test_repl_clear_command_wipes_history(capsys):
    repl, ctx, logger = _make_repl()
    ctx.add_message("user", "earlier")
    try:
        _run_with_input(repl, ["/clear", "/exit"])
    finally:
        logger.close()
    assert ctx.messages == []
    captured = capsys.readouterr()
    assert "cleared" in captured.out


def test_repl_quiet_command_enables_quiet(capsys):
    boukensha._quiet = False
    repl, _, logger = _make_repl()
    try:
        _run_with_input(repl, ["/quiet", "/exit"])
    finally:
        logger.close()
    assert boukensha.is_quiet() is True
    boukensha._quiet = False  # cleanup


def test_repl_loud_command_disables_quiet(capsys):
    boukensha._quiet = True
    repl, _, logger = _make_repl()
    try:
        _run_with_input(repl, ["/loud", "/exit"])
    finally:
        logger.close()
    assert boukensha.is_quiet() is False


def test_repl_runs_agent_for_normal_input(capsys):
    repl, ctx, logger = _make_repl()
    try:
        _run_with_input(repl, ["hello world", "/exit"])
    finally:
        logger.close()
    # agent reply "ok" must appear in output
    captured = capsys.readouterr()
    assert "ok" in captured.out


def test_repl_history_accumulates_across_turns():
    repl, ctx, logger = _make_repl()
    try:
        _run_with_input(repl, ["first turn", "second turn", "/exit"])
    finally:
        logger.close()
    roles = [m.role for m in ctx.messages]
    # user + assistant for each turn
    assert roles.count("user") == 2
    assert roles.count("assistant") == 2


def test_repl_skips_blank_lines():
    repl, ctx, logger = _make_repl()
    try:
        _run_with_input(repl, ["", "   ", "/exit"])
    finally:
        logger.close()
    # No agent messages added for blank input
    user_msgs = [m for m in ctx.messages if m.role == "user"]
    assert user_msgs == []


def test_repl_banner_shows_provider(capsys):
    repl, _, logger = _make_repl(provider="anthropic", model="claude-haiku-4-5", api_key="key")
    try:
        _run_with_input(repl, ["/exit"])
    finally:
        logger.close()
    captured = capsys.readouterr()
    assert "anthropic" in captured.out
    assert "claude-haiku-4-5" in captured.out


def test_repl_api_key_status_in_banner(capsys):
    repl_with_key, _, logger_with = _make_repl(api_key="real-key")
    try:
        _run_with_input(repl_with_key, ["/exit"])
    finally:
        logger_with.close()
    out_with = capsys.readouterr().out
    assert "API key set" in out_with

    repl_no_key, _, logger_no = _make_repl(api_key=None)
    try:
        _run_with_input(repl_no_key, ["/exit"])
    finally:
        logger_no.close()
    out_without = capsys.readouterr().out
    assert "API key not set" in out_without


def test_repl_on_output_routes_banner():
    repl, _, logger = _make_repl()
    received = []
    repl.on_output(received.append)
    try:
        import io
        with patch("sys.stdin", io.StringIO("/exit\n")):
            repl.start()
    finally:
        logger.close()
    all_output = "\n".join(received)
    assert "BOUKENSHA" in all_output


def test_repl_on_output_routes_agent_reply():
    repl, _, logger = _make_repl()
    received = []
    repl.on_output(received.append)
    try:
        import io
        with patch("sys.stdin", io.StringIO("hello\n/exit\n")):
            repl.start()
    finally:
        logger.close()
    all_output = "\n".join(received)
    assert "ok" in all_output


def test_repl_handle_command_exit_returns_quit():
    repl, _, logger = _make_repl()
    try:
        result = repl.handle_command("/exit")
    finally:
        logger.close()
    assert result == "quit"


def test_repl_handle_command_quit_returns_quit():
    repl, _, logger = _make_repl()
    try:
        result = repl.handle_command("/quit")
    finally:
        logger.close()
    assert result == "quit"


def test_repl_handle_command_clear_wipes_history():
    repl, ctx, logger = _make_repl()
    ctx.add_message("user", "earlier message")
    try:
        result = repl.handle_command("/clear")
    finally:
        logger.close()
    assert result == "command"
    assert ctx.messages == []


def test_repl_handle_command_help_returns_command():
    repl, _, logger = _make_repl()
    try:
        result = repl.handle_command("/help")
    finally:
        logger.close()
    assert result == "command"


def test_repl_handle_command_none_for_non_command():
    repl, _, logger = _make_repl()
    try:
        result = repl.handle_command("hello world")
    finally:
        logger.close()
    assert result is None


def test_repl_run_turn_calls_agent_and_routes_output():
    repl, _, logger = _make_repl()
    received = []
    repl.on_output(received.append)
    try:
        repl.run_turn("say hello")
    finally:
        logger.close()
    all_output = "\n".join(received)
    assert "ok" in all_output


def test_repl_properties_exposed():
    repl, ctx, logger = _make_repl(model="claude-haiku-4-5", version="0.1.0")
    try:
        assert repl.model == "claude-haiku-4-5"
        assert repl.version == "0.1.0"
        assert repl.context is ctx
        assert repl.logger is logger
        assert "BOUKENSHA" in repl.banner
    finally:
        logger.close()


# ── Step 13: /compact command ────────────────────────────────────────────────

def test_repl_compact_command_drops_messages(capsys):
    repl, ctx, logger = _make_repl()
    # Pre-load 10 messages
    for i in range(10):
        ctx.add_message("user", f"msg {i}")
    count_before = len(ctx.messages)
    try:
        result = repl.handle_command("/compact")
    finally:
        logger.close()
    assert result == "command"
    assert len(ctx.messages) < count_before


def test_repl_compact_command_prints_dropped_count(capsys):
    repl, ctx, logger = _make_repl()
    for i in range(10):
        ctx.add_message("user", f"msg {i}")
    try:
        repl.handle_command("/compact")
    finally:
        logger.close()
    captured = capsys.readouterr()
    assert "compacted" in captured.out
    assert "dropped" in captured.out


def test_repl_compact_in_help_text(capsys):
    repl, _, logger = _make_repl()
    try:
        _run_with_input(repl, ["/help", "/exit"])
    finally:
        logger.close()
    captured = capsys.readouterr()
    assert "/compact" in captured.out


def test_repl_compact_via_start(capsys):
    repl, ctx, logger = _make_repl()
    for i in range(6):
        ctx.add_message("user", f"msg {i}")
    try:
        _run_with_input(repl, ["/compact", "/exit"])
    finally:
        logger.close()
    captured = capsys.readouterr()
    assert "compacted" in captured.out


def test_run_turn_writes_new_goal(tmp_path):
    goal_path = tmp_path / "goals" / "hero.md"
    ctx = Context(task=Player, system="sys", goal_path=goal_path)
    registry = Registry(ctx)

    mock_builder = MagicMock()
    mock_builder.parse_response.return_value = {
        "stop_reason": "end_turn",
        "content": [{"type": "text", "text": "ok"}],
    }
    mock_builder.to_api_payload.return_value = {}
    mock_builder.backend = None
    mock_client = MagicMock()
    mock_client.call.return_value = {}

    _tmp = tempfile.mkdtemp()
    logger = Logger(dir=_tmp)
    repl = Repl(
        context=ctx,
        registry=registry,
        builder=mock_builder,
        client=mock_client,
        logger=logger,
        task_settings={},
        max_iterations=25,
        max_turn_tokens=None,
        max_output_tokens=None,
        config_dir=None,
        provider="anthropic",
        model="claude-haiku-4-5",
        version="0.1.0",
        api_key="test-key",
    )
    try:
        repl.run_turn("go find the bakery")
        assert "go find the bakery" in goal_path.read_text()

        repl.run_turn("go drink water instead")
        assert "go drink water instead" in goal_path.read_text()
        assert "go find the bakery" not in goal_path.read_text()
    finally:
        logger.close()
