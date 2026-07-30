from __future__ import annotations

import boukensha


def setup_function():
    boukensha._quiet = False


def teardown_function():
    boukensha._quiet = False


def test_quiet_starts_false():
    assert boukensha.is_quiet() is False


def test_enable_quiet():
    boukensha.enable_quiet()
    assert boukensha.is_quiet() is True


def test_disable_quiet():
    boukensha.enable_quiet()
    boukensha.disable_quiet()
    assert boukensha.is_quiet() is False


def test_agent_suppresses_prints_when_quiet(capsys):
    from unittest.mock import MagicMock
    from boukensha.agent import Agent
    from boukensha.context import Context
    from boukensha.registry import Registry
    from boukensha.tasks.player import Player

    boukensha.enable_quiet()

    ctx = Context(task=Player, system="sys")
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
    ctx.add_message("user", "hi")

    agent = Agent(context=ctx, registry=registry, builder=mock_builder, client=mock_client)
    agent.run()

    captured = capsys.readouterr()
    assert "[iteration" not in captured.out
