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
