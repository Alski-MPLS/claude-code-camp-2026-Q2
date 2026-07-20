from __future__ import annotations

import io
from unittest.mock import MagicMock, patch

import pytest

import boukensha
from boukensha.agent import Agent
from boukensha.context import Context
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

    defaults = dict(
        context=ctx,
        registry=registry,
        builder=mock_builder,
        client=mock_client,
        logger=None,
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
    return Repl(**defaults), ctx


def _run_with_input(repl, lines):
    text = "\n".join(lines) + "\n"
    with patch("sys.stdin", io.StringIO(text)):
        repl.start()


def test_repl_exits_on_exit_command(capsys):
    repl, _ = _make_repl()
    _run_with_input(repl, ["/exit"])
    captured = capsys.readouterr()
    assert "Goodbye" in captured.out


def test_repl_exits_on_quit_command(capsys):
    repl, _ = _make_repl()
    _run_with_input(repl, ["/quit"])
    captured = capsys.readouterr()
    assert "Goodbye" in captured.out


def test_repl_exits_on_eof(capsys):
    repl, _ = _make_repl()
    with patch("sys.stdin", io.StringIO("")):
        repl.start()
    # no exception raised


def test_repl_help_command(capsys):
    repl, _ = _make_repl()
    _run_with_input(repl, ["/help", "/exit"])
    captured = capsys.readouterr()
    assert "/clear" in captured.out
    assert "/exit" in captured.out


def test_repl_clear_command_wipes_history(capsys):
    repl, ctx = _make_repl()
    ctx.add_message("user", "earlier")
    _run_with_input(repl, ["/clear", "/exit"])
    assert ctx.messages == []
    captured = capsys.readouterr()
    assert "cleared" in captured.out


def test_repl_quiet_command_enables_quiet(capsys):
    boukensha._quiet = False
    repl, _ = _make_repl()
    _run_with_input(repl, ["/quiet", "/exit"])
    assert boukensha.is_quiet() is True
    boukensha._quiet = False  # cleanup


def test_repl_loud_command_disables_quiet(capsys):
    boukensha._quiet = True
    repl, _ = _make_repl()
    _run_with_input(repl, ["/loud", "/exit"])
    assert boukensha.is_quiet() is False


def test_repl_runs_agent_for_normal_input(capsys):
    repl, ctx = _make_repl()
    _run_with_input(repl, ["hello world", "/exit"])
    # agent reply "ok" must appear in output
    captured = capsys.readouterr()
    assert "ok" in captured.out


def test_repl_history_accumulates_across_turns():
    repl, ctx = _make_repl()
    _run_with_input(repl, ["first turn", "second turn", "/exit"])
    roles = [m.role for m in ctx.messages]
    # user + assistant for each turn
    assert roles.count("user") == 2
    assert roles.count("assistant") == 2


def test_repl_skips_blank_lines():
    repl, ctx = _make_repl()
    _run_with_input(repl, ["", "   ", "/exit"])
    # No agent messages added for blank input
    user_msgs = [m for m in ctx.messages if m.role == "user"]
    assert user_msgs == []


def test_repl_banner_shows_provider(capsys):
    repl, _ = _make_repl(provider="anthropic", model="claude-haiku-4-5", api_key="key")
    _run_with_input(repl, ["/exit"])
    captured = capsys.readouterr()
    assert "anthropic" in captured.out
    assert "claude-haiku-4-5" in captured.out


def test_repl_api_key_status_in_banner(capsys):
    repl_with_key, _ = _make_repl(api_key="real-key")
    _run_with_input(repl_with_key, ["/exit"])
    out_with = capsys.readouterr().out
    assert "API key set" in out_with

    repl_no_key, _ = _make_repl(api_key=None)
    _run_with_input(repl_no_key, ["/exit"])
    out_without = capsys.readouterr().out
    assert "API key not set" in out_without
