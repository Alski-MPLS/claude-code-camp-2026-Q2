"""Tests for boukensha.tools.Mud — all run without a live MUD server."""
from __future__ import annotations

import socket
import threading
import time
from unittest.mock import patch, MagicMock

import pytest

from boukensha.context import Context
from boukensha.registry import Registry
from boukensha.tasks.player import Player
from boukensha.tools.mud import Mud, MudSession


def _make_registry() -> Registry:
    ctx = Context(task=Player, system="sys")
    return Registry(ctx)


# ---------------------------------------------------------------------------
# MudSession unit tests (no live server — mock the socket)
# ---------------------------------------------------------------------------

def test_mud_session_open_sets_open_flag():
    session = MudSession(host="localhost", port=4000)
    mock_sock = MagicMock()
    mock_sock.recv.return_value = b""
    with patch("socket.create_connection", return_value=mock_sock):
        session.open()
    assert session.is_open


def test_mud_session_close_clears_flag():
    session = MudSession(host="localhost", port=4000)
    mock_sock = MagicMock()
    mock_sock.recv.return_value = b""
    with patch("socket.create_connection", return_value=mock_sock):
        session.open()
        session.close()
    assert not session.is_open


def test_mud_session_send_command_raises_when_closed():
    session = MudSession(host="localhost", port=4000)
    with pytest.raises(RuntimeError, match="not open"):
        session.send_command("look")


# ---------------------------------------------------------------------------
# Mud.register tool registration tests (mock session entirely)
# ---------------------------------------------------------------------------

def _registered_session(registry, session):
    """Register Mud tools against registry with a pre-built session."""
    Mud._register_with_session(registry, session, name="Tester", password="secret")


def test_mud_register_adds_expected_tools():
    registry = _make_registry()
    mock_session = MagicMock()
    mock_session.is_open = False
    Mud._register_with_session(registry, mock_session, name="Tester", password="secret")

    expected = [
        "mud_connect", "mud_disconnect", "mud_status",
        "look", "examine", "check",
        "move", "flee", "set_position", "track",
        "attack", "skill_strike", "consider",
        "say", "tell", "channel_say",
        "get_item", "drop_item", "put_item", "equip_item", "consume_item",
        "cast_spell", "use_magic_item",
        "shop", "practice", "save_character", "send_raw",
    ]
    for name in expected:
        assert registry.get(name) is not None, f"tool {name!r} not registered"


def test_mud_status_returns_disconnected_when_closed():
    registry = _make_registry()
    mock_session = MagicMock()
    mock_session.is_open = False
    Mud._register_with_session(registry, mock_session, name="Tester", password="secret")
    result = registry.dispatch("mud_status", {})
    assert "disconnected" in result


def test_mud_status_returns_connected_when_open():
    registry = _make_registry()
    mock_session = MagicMock()
    mock_session.is_open = True
    mock_session.host = "localhost"
    mock_session.port = 4000
    Mud._register_with_session(registry, mock_session, name="Tester", password="secret")
    result = registry.dispatch("mud_status", {})
    assert "connected" in result


def test_tool_returns_error_when_not_connected():
    registry = _make_registry()
    mock_session = MagicMock()
    mock_session.is_open = False
    Mud._register_with_session(registry, mock_session, name="Tester", password="secret")
    result = registry.dispatch("look", {})
    assert result.startswith("error:")


def test_look_sends_look_command_when_connected():
    registry = _make_registry()
    mock_session = MagicMock()
    mock_session.is_open = True
    mock_session.drain.return_value = ""
    mock_session.read_until_prompt.return_value = "You are in a room. > "
    Mud._register_with_session(registry, mock_session, name="Tester", password="secret")
    result = registry.dispatch("look", {})
    mock_session.send_command.assert_called_once_with("look")
    assert "room" in result


def test_move_sends_direction():
    registry = _make_registry()
    mock_session = MagicMock()
    mock_session.is_open = True
    mock_session.drain.return_value = ""
    mock_session.read_until_prompt.return_value = "You go north. > "
    Mud._register_with_session(registry, mock_session, name="Tester", password="secret")
    result = registry.dispatch("move", {"direction": "north"})
    mock_session.send_command.assert_called_once_with("north")


def test_move_rejects_invalid_direction():
    registry = _make_registry()
    mock_session = MagicMock()
    mock_session.is_open = True
    Mud._register_with_session(registry, mock_session, name="Tester", password="secret")
    result = registry.dispatch("move", {"direction": "sideways"})
    assert result.startswith("error:")


def test_send_raw_passes_command_through():
    registry = _make_registry()
    mock_session = MagicMock()
    mock_session.is_open = True
    mock_session.read_until_prompt.return_value = "who output > "
    Mud._register_with_session(registry, mock_session, name="Tester", password="secret")
    registry.dispatch("send_raw", {"command": "who"})
    mock_session.send_command.assert_called_once_with("who")


def test_mud_register_classmethod_calls_internal():
    """Mud.register() creates a session and calls _register_with_session."""
    registry = _make_registry()
    mock_session = MagicMock()
    mock_session.is_open = False

    with patch("boukensha.tools.mud.MudSession", return_value=mock_session):
        Mud.register(registry, host="localhost", port=4000, name="Hero", password="pw")

    assert registry.get("mud_connect") is not None


def test_tools_module_exports_mud():
    from boukensha import tools
    assert hasattr(tools, "Mud")


def test_mud_opts_from_config_returns_none_when_no_username(tmp_path):
    """_mud_opts_from_config returns None when mud.username is not set."""
    import boukensha
    from boukensha.config import Config
    from unittest.mock import patch, PropertyMock

    mock_cfg = MagicMock(spec=Config)
    mock_cfg.mud_username = None
    result = boukensha._mud_opts_from_config(mock_cfg)
    assert result is None


def test_mud_opts_from_config_returns_dict_when_username_set():
    """_mud_opts_from_config returns a dict with connection params when username is set."""
    import boukensha
    from boukensha.config import Config

    mock_cfg = MagicMock(spec=Config)
    mock_cfg.mud_host = "localhost"
    mock_cfg.mud_port = 4000
    mock_cfg.mud_username = "Hero"
    mock_cfg.mud_password = "secret"
    result = boukensha._mud_opts_from_config(mock_cfg)
    assert result == {"host": "localhost", "port": 4000, "name": "Hero", "password": "secret"}
