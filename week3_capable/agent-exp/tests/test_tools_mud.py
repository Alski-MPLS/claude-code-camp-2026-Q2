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
        "look", "examine", "check", "wait",
        "move", "flee", "set_position", "track", "door", "portal",
        "attack", "skill_strike", "consider",
        "say", "tell", "channel_say",
        "get_item", "drop_item", "put_item", "give_item", "equip_item", "consume_item", "pour_liquid",
        "cast_spell", "use_magic_item",
        "shop", "bank", "practice", "save_character", "send_raw",
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


# ---------------------------------------------------------------------------
# Combat tools must refuse targets that aren't a known living NPC in the
# room — real-world bug: an LLM attacked a mob whose corpse (not the mob
# itself) was lying in the room, and got a confusing MUD bounce-back instead
# of a clear refusal.
# ---------------------------------------------------------------------------

def test_attack_refuses_when_target_not_present():
    registry = _make_registry()
    mock_session = MagicMock()
    mock_session.is_open = True
    mock_session.drain.return_value = ""
    Mud._register_with_session(registry, mock_session, name="Tester", password="secret")
    result = registry.dispatch("attack", {"target": "dragon"})
    assert "No living 'dragon'" in result
    mock_session.send_command.assert_not_called()


def test_attack_succeeds_when_target_matches_known_npc():
    registry = _make_registry()
    mock_session = MagicMock()
    mock_session.is_open = True
    mock_session.drain.return_value = ""
    mock_session.read_until_prompt.return_value = "You hit the creepy crawler. > "
    Mud._register_with_session(
        registry, mock_session, name="Tester", password="secret",
        current_npcs_ref=[["a creepy crawler"]],
    )
    result = registry.dispatch("attack", {"target": "creepy crawler"})
    mock_session.send_command.assert_called_once_with("kill creepy crawler")
    assert "hit" in result.lower()


def test_move_refreshes_known_npcs_for_combat_tools():
    registry = _make_registry()
    mock_session = MagicMock()
    mock_session.is_open = True
    mock_session.drain.return_value = ""
    mock_session.read_until_prompt.side_effect = [
        "The Dirty Hallway\n   A grimy hall.\n[ Exits: n ]\nA creepy crawler is here.\n",
        "You hit the creepy crawler. > ",
    ]
    Mud._register_with_session(registry, mock_session, name="Tester", password="secret")
    registry.dispatch("move", {"direction": "north"})
    result = registry.dispatch("attack", {"target": "creepy crawler"})
    assert "hit" in result.lower()


def test_move_into_room_with_only_a_corpse_refuses_the_old_npc():
    registry = _make_registry()
    mock_session = MagicMock()
    mock_session.is_open = True
    mock_session.drain.return_value = ""
    mock_session.read_until_prompt.return_value = (
        "The Dirty Hallway\n   A grimy hall.\n[ Exits: n ]\n"
        "The corpse of the creepy crawler is lying here.\n"
    )
    Mud._register_with_session(registry, mock_session, name="Tester", password="secret")
    registry.dispatch("move", {"direction": "north"})
    result = registry.dispatch("attack", {"target": "creepy crawler"})
    assert "No living 'creepy crawler'" in result


def test_look_refreshes_known_npcs_for_combat_tools():
    registry = _make_registry()
    mock_session = MagicMock()
    mock_session.is_open = True
    mock_session.drain.return_value = ""
    mock_session.read_until_prompt.side_effect = [
        "The Dirty Hallway\n   A grimy hall.\n[ Exits: n ]\nA creepy crawler is here.\n",
        "You hit the creepy crawler. > ",
    ]
    Mud._register_with_session(registry, mock_session, name="Tester", password="secret")
    registry.dispatch("look", {})
    result = registry.dispatch("attack", {"target": "creepy crawler"})
    assert "hit" in result.lower()


def test_look_at_target_does_not_refresh_known_npcs():
    # "look at X" describes X, not the room — must not overwrite room state.
    registry = _make_registry()
    mock_session = MagicMock()
    mock_session.is_open = True
    mock_session.drain.return_value = ""
    mock_session.read_until_prompt.return_value = "It's a sword.\n"
    Mud._register_with_session(
        registry, mock_session, name="Tester", password="secret",
        current_npcs_ref=[["a creepy crawler"]],
    )
    registry.dispatch("look", {"target": "sword", "preposition": "at"})
    result = registry.dispatch("attack", {"target": "creepy crawler"})
    assert "No living" not in result


def test_look_when_not_connected_does_not_clear_known_npcs():
    """_look() returns a local "error: not connected" string without ever
    reaching the MUD when the session is closed — that must not be treated
    as an (empty-npc) room observation and wipe out npcs seen earlier."""
    registry = _make_registry()
    mock_session = MagicMock()
    mock_session.is_open = False
    Mud._register_with_session(
        registry, mock_session, name="Tester", password="secret",
        current_npcs_ref=[["a creepy crawler"]],
    )
    result = registry.dispatch("look", {})
    assert result.startswith("error:")
    result2 = registry.dispatch("attack", {"target": "creepy crawler"})
    assert "No living" not in result2


def test_consider_refuses_unknown_target():
    registry = _make_registry()
    mock_session = MagicMock()
    mock_session.is_open = True
    mock_session.drain.return_value = ""
    Mud._register_with_session(registry, mock_session, name="Tester", password="secret")
    result = registry.dispatch("consider", {"target": "newbie monster"})
    assert "No living 'newbie monster'" in result
    mock_session.send_command.assert_not_called()


def test_skill_strike_rescue_is_not_gated_by_npc_list():
    # rescue/assist target a fellow player, not an npc — must never be gated.
    registry = _make_registry()
    mock_session = MagicMock()
    mock_session.is_open = True
    mock_session.drain.return_value = ""
    mock_session.read_until_prompt.return_value = "You rescue Bob! > "
    Mud._register_with_session(registry, mock_session, name="Tester", password="secret")
    result = registry.dispatch("skill_strike", {"skill": "rescue", "target": "Bob"})
    mock_session.send_command.assert_called_once_with("rescue Bob")
    assert "rescue" in result.lower()


def test_skill_strike_backstab_is_gated_by_npc_list():
    registry = _make_registry()
    mock_session = MagicMock()
    mock_session.is_open = True
    mock_session.drain.return_value = ""
    Mud._register_with_session(registry, mock_session, name="Tester", password="secret")
    result = registry.dispatch("skill_strike", {"skill": "backstab", "target": "dragon"})
    assert "No living 'dragon'" in result
    mock_session.send_command.assert_not_called()


def test_send_recovers_from_main_menu_and_resends_command():
    """If a command lands on the post-login main menu (e.g. after a death
    dropped the connection back to it), the tool must re-enter the game and
    resend the original command instead of surfacing menu text forever."""
    registry = _make_registry()
    mock_session = MagicMock()
    mock_session.is_open = True
    mock_session.drain.return_value = ""
    mock_session.read_until_prompt.side_effect = [
        "Welcome to tbaMUD!\n0) Exit\n1) Enter the game.\n\n   Make your choice: > ",
        "You are standing in the Temple of Midgaard. > ",  # after sending "1"
        "34H 100M 87V > ",  # actual score result after resending the original command
    ]
    Mud._register_with_session(registry, mock_session, name="Tester", password="secret")
    result = registry.dispatch("check", {"kind": "score"})

    sent = [c.args[0] for c in mock_session.send_command.call_args_list]
    assert sent == ["score", "1", "score"]
    assert "Make your choice" not in result


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


def test_move_rejects_invalid_direction_without_polluting_the_map(tmp_path):
    """A bad direction is a local Python validation error — _move() returns
    it without ever contacting the MUD. That error string must never be
    parsed as room text: doing so previously created a phantom room node
    titled after the error message, wired into the graph with a real edge
    from wherever the agent actually was, and silently moved the tracked
    player position onto it."""
    from boukensha.memory.world_graph import WorldGraph
    from boukensha.memory.player_tracker import PlayerTracker

    memory_dir = tmp_path / "memory"
    graph = WorldGraph(memory_dir)

    registry = _make_registry()
    mock_session = MagicMock()
    mock_session.is_open = True
    mock_session.drain.return_value = ""
    mock_session.read_until_prompt.return_value = "The Dump\n   A pile of refuse.\n[ Exits: n ]\n"
    prev_hash_ref: list[str | None] = [None]
    Mud._register_with_session(
        registry,
        mock_session,
        name="Tester",
        password="secret",
        memory_dir=str(memory_dir),
        world_graph=graph,
        prev_hash_ref=prev_hash_ref,
    )

    # Establish a real current room first.
    registry.dispatch("move", {"direction": "north"})
    assert graph.graph.number_of_nodes() == 1

    result = registry.dispatch("move", {"direction": "d"})

    assert result.startswith("error:")
    # No phantom room/edge from the rejected direction.
    assert graph.graph.number_of_nodes() == 1
    assert graph.graph.number_of_edges() == 0
    titles = {a.get("title") for _, a in graph.graph.nodes(data=True)}
    assert "The Dump" in titles
    assert not any(t.lower().startswith("error:") for t in titles)
    # The player tracker must still point at the real room, not the error.
    tracker = PlayerTracker(memory_dir)
    assert tracker.read_all()["Tester"]["title"] == "The Dump"


def test_move_records_room_and_edge_in_world_graph(tmp_path):
    """A raw 'move' call — with no process_room in between — must still add
    the new room and the edge from wherever the agent just left, so
    navigate_to can route through ground covered by plain movement."""
    from boukensha.memory.world_graph import WorldGraph

    memory_dir = tmp_path / "memory"
    graph = WorldGraph(memory_dir)

    registry = _make_registry()
    mock_session = MagicMock()
    mock_session.is_open = True
    mock_session.drain.return_value = ""
    mock_session.read_until_prompt.side_effect = [
        "The Temple Square\n   A large open square.\n[ Exits: n e ]\n",
        "Main Street\n   The main street of town.\n[ Exits: n s ]\n",
    ]
    prev_hash_ref: list[str | None] = [None]
    Mud._register_with_session(
        registry,
        mock_session,
        name="Tester",
        password="secret",
        memory_dir=str(memory_dir),
        world_graph=graph,
        prev_hash_ref=prev_hash_ref,
    )

    registry.dispatch("move", {"direction": "north"})
    registry.dispatch("move", {"direction": "south"})

    titles = {n: a.get("title") for n, a in graph.graph.nodes(data=True)}
    assert set(titles.values()) == {"The Temple Square", "Main Street"}

    square_hash = next(h for h, t in titles.items() if t == "The Temple Square")
    street_hash = next(h for h, t in titles.items() if t == "Main Street")
    # Second move ("south") is what carried us from the square to the street.
    edge = graph.graph.get_edge_data(square_hash, street_hash)
    assert edge == {"direction": "south"}

    # Reloading from disk proves move() actually persisted it, not just kept it in memory.
    reloaded = WorldGraph(memory_dir)
    reloaded.load()
    # WorldGraph.add_edge also fills in the reverse direction (north back to
    # the square), since CircleMUD exits are almost always bidirectional.
    assert reloaded.graph.number_of_edges() == 2
    assert reloaded.graph.get_edge_data(street_hash, square_hash) == {"direction": "north"}


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


def test_check_score_persists_stats_to_player_tracker(tmp_path):
    registry = _make_registry()
    mock_session = MagicMock()
    mock_session.is_open = True
    mock_session.drain.return_value = ""
    mock_session.read_until_prompt.return_value = (
        "You have 20(20) hit, 100(100) mana and 85(85) movement points. > "
    )
    Mud._register_with_session(
        registry, mock_session, name="Tester", password="secret", memory_dir=tmp_path
    )
    registry.dispatch("check", {"kind": "score"})

    from boukensha.memory.player_tracker import PlayerTracker
    data = PlayerTracker(tmp_path).read_all()
    assert data["Tester"]["stats"] == {
        "hp": 20, "max_hp": 20,
        "mana": 100, "max_mana": 100,
        "move": 85, "max_move": 85,
        "hungry": False, "thirsty": False,
    }


def test_check_non_score_kind_does_not_touch_player_tracker(tmp_path):
    registry = _make_registry()
    mock_session = MagicMock()
    mock_session.is_open = True
    mock_session.drain.return_value = ""
    mock_session.read_until_prompt.return_value = "You aren't carrying anything. > "
    Mud._register_with_session(
        registry, mock_session, name="Tester", password="secret", memory_dir=tmp_path
    )
    registry.dispatch("check", {"kind": "inventory"})

    from boukensha.memory.player_tracker import PlayerTracker
    assert PlayerTracker(tmp_path).read_all() == {}


def test_check_score_without_memory_dir_does_not_crash():
    """check(kind='score') must still work when the tool is registered
    without a memory_dir (tracker is None) — e.g. in older callers/tests
    that don't pass it."""
    registry = _make_registry()
    mock_session = MagicMock()
    mock_session.is_open = True
    mock_session.drain.return_value = ""
    mock_session.read_until_prompt.return_value = (
        "You have 20(20) hit, 100(100) mana and 85(85) movement points. > "
    )
    Mud._register_with_session(registry, mock_session, name="Tester", password="secret")
    result = registry.dispatch("check", {"kind": "score"})
    assert "20(20) hit" in result


def test_check_score_appends_sustenance_advisory_when_hungry_and_thirsty():
    registry = _make_registry()
    mock_session = MagicMock()
    mock_session.is_open = True
    mock_session.drain.return_value = ""
    mock_session.read_until_prompt.return_value = (
        "You have 34(37) hit, 100(100) mana and 86(87) movement points.\n"
        "You are standing.\n"
        "You are hungry.\n"
        "You are thirsty. > "
    )
    Mud._register_with_session(registry, mock_session, name="Tester", password="secret")

    result = registry.dispatch("check", {"kind": "score"})

    assert "[Sustenance]" in result
    assert "hungry and thirsty" in result


def test_check_score_omits_sustenance_advisory_when_neither():
    registry = _make_registry()
    mock_session = MagicMock()
    mock_session.is_open = True
    mock_session.drain.return_value = ""
    mock_session.read_until_prompt.return_value = (
        "You have 37(37) hit, 100(100) mana and 87(87) movement points. > "
    )
    Mud._register_with_session(registry, mock_session, name="Tester", password="secret")

    result = registry.dispatch("check", {"kind": "score"})

    assert "[Sustenance]" not in result


def test_check_score_appends_level_up_advisory_when_level_increased(tmp_path):
    from boukensha.memory.player_tracker import PlayerTracker
    PlayerTracker(tmp_path).update_stats("Tester", {
        "hp": 37, "max_hp": 37, "mana": 100, "max_mana": 100,
        "move": 87, "max_move": 87, "hungry": False, "thirsty": False,
        "level": 2, "title": "Dummy the Recruit",
    })

    registry = _make_registry()
    mock_session = MagicMock()
    mock_session.is_open = True
    mock_session.drain.return_value = ""
    mock_session.read_until_prompt.return_value = (
        "You have 50(50) hit, 100(100) mana and 88(88) movement points.\n"
        "You have 5829 exp, 130 gold coins, and 0 questpoints.\n"
        "You need 2171 exp to reach your next level.\n"
        "This ranks you as Dummy the Sentry (level 3). > "
    )
    Mud._register_with_session(
        registry, mock_session, name="Tester", password="secret", memory_dir=tmp_path
    )

    result = registry.dispatch("check", {"kind": "score"})

    assert "[Level up!]" in result
    assert "level 3" in result
    assert "Dummy the Sentry" in result
    assert "level 2" in result  # mentions the previous level


def test_check_score_omits_level_up_advisory_on_first_ever_check(tmp_path):
    registry = _make_registry()
    mock_session = MagicMock()
    mock_session.is_open = True
    mock_session.drain.return_value = ""
    mock_session.read_until_prompt.return_value = (
        "You have 20(20) hit, 100(100) mana and 85(85) movement points.\n"
        "This ranks you as Dummy the Recruit (level 2). > "
    )
    Mud._register_with_session(
        registry, mock_session, name="Tester", password="secret", memory_dir=tmp_path
    )

    result = registry.dispatch("check", {"kind": "score"})

    assert "[Level up!]" not in result


def test_check_score_omits_level_up_advisory_when_level_unchanged(tmp_path):
    from boukensha.memory.player_tracker import PlayerTracker
    PlayerTracker(tmp_path).update_stats("Tester", {
        "hp": 37, "max_hp": 37, "mana": 100, "max_mana": 100,
        "move": 87, "max_move": 87, "hungry": False, "thirsty": False,
        "level": 3, "title": "Dummy the Sentry",
    })

    registry = _make_registry()
    mock_session = MagicMock()
    mock_session.is_open = True
    mock_session.drain.return_value = ""
    mock_session.read_until_prompt.return_value = (
        "You have 45(50) hit, 100(100) mana and 88(88) movement points.\n"
        "This ranks you as Dummy the Sentry (level 3). > "
    )
    Mud._register_with_session(
        registry, mock_session, name="Tester", password="secret", memory_dir=tmp_path
    )

    result = registry.dispatch("check", {"kind": "score"})

    assert "[Level up!]" not in result


def test_check_score_partial_read_does_not_delete_stored_level(tmp_path):
    from boukensha.memory.player_tracker import PlayerTracker
    PlayerTracker(tmp_path).update_stats("Tester", {
        "hp": 37, "max_hp": 37, "mana": 100, "max_mana": 100,
        "move": 87, "max_move": 87, "hungry": False, "thirsty": False,
        "level": 3, "title": "Dummy the Sentry",
        "exp": 5829, "exp_to_next": 2171, "gold": 130,
    })

    registry = _make_registry()
    mock_session = MagicMock()
    mock_session.is_open = True
    mock_session.drain.return_value = ""
    # Truncated read: only the HP/mana/move line, no "This ranks you as..."
    # line and no exp/gold line, so parse_score's dict has no level/title/
    # exp/exp_to_next/gold keys at all.
    mock_session.read_until_prompt.return_value = (
        "You have 45(50) hit, 100(100) mana and 88(88) movement points.\n> "
    )
    Mud._register_with_session(
        registry, mock_session, name="Tester", password="secret", memory_dir=tmp_path
    )

    registry.dispatch("check", {"kind": "score"})

    stored = PlayerTracker(tmp_path).read_all()["Tester"]["stats"]
    assert stored["level"] == 3


def test_door_open_with_direction_sends_open_door_direction():
    registry = _make_registry()
    mock_session = MagicMock()
    mock_session.is_open = True
    mock_session.drain.return_value = ""
    mock_session.read_until_prompt.return_value = "Okay.\n"
    Mud._register_with_session(registry, mock_session, name="Tester", password="secret")

    result = registry.dispatch("door", {"action": "open", "target": "east"})

    mock_session.send_command.assert_called_once_with("open door east")
    assert "Okay" in result


def test_door_open_with_item_name_unchanged():
    registry = _make_registry()
    mock_session = MagicMock()
    mock_session.is_open = True
    mock_session.drain.return_value = ""
    mock_session.read_until_prompt.return_value = "You open the chest.\n"
    Mud._register_with_session(registry, mock_session, name="Tester", password="secret")

    result = registry.dispatch("door", {"action": "open", "target": "chest"})

    mock_session.send_command.assert_called_once_with("open chest")
    assert "chest" in result


def test_door_lock_with_direction_sends_lock_door_direction():
    registry = _make_registry()
    mock_session = MagicMock()
    mock_session.is_open = True
    mock_session.drain.return_value = ""
    mock_session.read_until_prompt.return_value = "*click*\n"
    Mud._register_with_session(registry, mock_session, name="Tester", password="secret")

    result = registry.dispatch("door", {"action": "lock", "target": "north"})

    mock_session.send_command.assert_called_once_with("lock door north")
    assert "click" in result


def test_bank_deposit_sends_deposit_amount():
    registry = _make_registry()
    mock_session = MagicMock()
    mock_session.is_open = True
    mock_session.drain.return_value = ""
    mock_session.read_until_prompt.return_value = "You deposit 400 coins.\n"
    Mud._register_with_session(registry, mock_session, name="Tester", password="secret")

    result = registry.dispatch("bank", {"action": "deposit", "amount": 400})

    mock_session.send_command.assert_called_once_with("deposit 400")
    assert "deposit" in result


def test_bank_withdraw_sends_withdraw_amount():
    registry = _make_registry()
    mock_session = MagicMock()
    mock_session.is_open = True
    mock_session.drain.return_value = ""
    mock_session.read_until_prompt.return_value = "You withdraw 100 coins.\n"
    Mud._register_with_session(registry, mock_session, name="Tester", password="secret")

    result = registry.dispatch("bank", {"action": "withdraw", "amount": 100})

    mock_session.send_command.assert_called_once_with("withdraw 100")
    assert "withdraw" in result


def test_bank_balance_ignores_amount():
    registry = _make_registry()
    mock_session = MagicMock()
    mock_session.is_open = True
    mock_session.drain.return_value = ""
    mock_session.read_until_prompt.return_value = "Current balance: 200 coins.\n"
    Mud._register_with_session(registry, mock_session, name="Tester", password="secret")

    result = registry.dispatch("bank", {"action": "balance"})

    mock_session.send_command.assert_called_once_with("balance")
    assert "balance" in result


def test_bank_rejects_invalid_action():
    registry = _make_registry()
    mock_session = MagicMock()
    mock_session.is_open = True
    Mud._register_with_session(registry, mock_session, name="Tester", password="secret")

    result = registry.dispatch("bank", {"action": "rob"})

    mock_session.send_command.assert_not_called()
    assert "action" in result.lower()


def test_wait_sleeps_real_seconds_then_reports_fresh_score():
    registry = _make_registry()
    mock_session = MagicMock()
    mock_session.is_open = True
    mock_session.drain.return_value = ""
    mock_session.read_until_prompt.return_value = (
        "You have 20(20) hit, 100(100) mana and 85(85) movement points. > "
    )
    Mud._register_with_session(registry, mock_session, name="Tester", password="secret")

    with patch("boukensha.tools.mud.time.sleep") as mock_sleep:
        result = registry.dispatch("wait", {"seconds": 30})

    mock_sleep.assert_called_once_with(30)
    mock_session.send_command.assert_called_once_with("score")
    assert "Waited 30s" in result
    assert "20(20) hit" in result


def test_wait_clamps_seconds_to_a_sane_range():
    registry = _make_registry()
    mock_session = MagicMock()
    mock_session.is_open = True
    mock_session.drain.return_value = ""
    mock_session.read_until_prompt.return_value = "You have 20(20) hit. > "
    Mud._register_with_session(registry, mock_session, name="Tester", password="secret")

    with patch("boukensha.tools.mud.time.sleep") as mock_sleep:
        registry.dispatch("wait", {"seconds": 9999})

    mock_sleep.assert_called_once_with(90)


def test_wait_returns_error_when_not_connected():
    registry = _make_registry()
    mock_session = MagicMock()
    mock_session.is_open = False
    Mud._register_with_session(registry, mock_session, name="Tester", password="secret")

    with patch("boukensha.tools.mud.time.sleep") as mock_sleep:
        result = registry.dispatch("wait", {"seconds": 10})

    mock_sleep.assert_not_called()
    assert "error" in result.lower()


def test_check_equipment_persists_slots_to_player_tracker(tmp_path):
    registry = _make_registry()
    mock_session = MagicMock()
    mock_session.is_open = True
    mock_session.drain.return_value = ""
    mock_session.read_until_prompt.return_value = (
        "You are using:\n"
        "<worn on finger>      a gold ring\n"
        "<wielded>              a long sword\n"
        "> "
    )
    Mud._register_with_session(
        registry, mock_session, name="Tester", password="secret", memory_dir=tmp_path
    )
    registry.dispatch("check", {"kind": "equipment"})

    from boukensha.memory.player_tracker import PlayerTracker
    data = PlayerTracker(tmp_path).read_all()
    assert data["Tester"]["equipment"] == {
        "finger": "a gold ring",
        "wielded": "a long sword",
    }


def test_check_equipment_without_memory_dir_does_not_crash():
    registry = _make_registry()
    mock_session = MagicMock()
    mock_session.is_open = True
    mock_session.drain.return_value = ""
    mock_session.read_until_prompt.return_value = "<wielded> a long sword\n> "
    Mud._register_with_session(registry, mock_session, name="Tester", password="secret")
    result = registry.dispatch("check", {"kind": "equipment"})
    assert "a long sword" in result


def test_check_equipment_with_no_items_worn_does_not_crash(tmp_path):
    registry = _make_registry()
    mock_session = MagicMock()
    mock_session.is_open = True
    mock_session.drain.return_value = ""
    mock_session.read_until_prompt.return_value = "You are using: nothing.\n> "
    Mud._register_with_session(
        registry, mock_session, name="Tester", password="secret", memory_dir=tmp_path
    )
    result = registry.dispatch("check", {"kind": "equipment"})
    assert "nothing" in result
    from boukensha.memory.player_tracker import PlayerTracker
    assert PlayerTracker(tmp_path).read_all() == {}


def _identify_output(name: str, wear_slot: str | None, affects: dict[str, int]) -> str:
    lines = [f"Object '{name}', Item type: WORN"]
    if wear_slot:
        lines.append(f"This item can be worn on: {wear_slot.upper()}")
    lines.append("Can affect you as :")
    for k, v in affects.items():
        lines.append(f"   Affects: {k.upper()} By {v}")
    return "\n".join(lines) + " > "


def test_cast_spell_identify_saves_item_stats(tmp_path):
    registry = _make_registry()
    mock_session = MagicMock()
    mock_session.is_open = True
    mock_session.drain.return_value = ""
    mock_session.read_until_prompt.return_value = _identify_output(
        "a gold ring", "finger", {"ac": -10, "hitroll": 2}
    )
    Mud._register_with_session(
        registry, mock_session, name="Tester", password="secret", memory_dir=tmp_path
    )

    registry.dispatch("cast_spell", {"spell": "identify", "target": "gold ring"})

    from boukensha.memory.item_stats import ItemStatsStore
    saved = ItemStatsStore(tmp_path).get("a gold ring")
    assert saved["wear_slot"] == "finger"
    assert saved["affects"] == {"ac": -10, "hitroll": 2}


def test_cast_spell_non_identify_result_does_not_touch_item_stats(tmp_path):
    registry = _make_registry()
    mock_session = MagicMock()
    mock_session.is_open = True
    mock_session.drain.return_value = ""
    mock_session.read_until_prompt.return_value = "You failed to concentrate. > "
    Mud._register_with_session(
        registry, mock_session, name="Tester", password="secret", memory_dir=tmp_path
    )

    registry.dispatch("cast_spell", {"spell": "magic missile", "target": "rat"})

    from boukensha.memory.item_stats import ItemStatsStore
    assert ItemStatsStore(tmp_path).read_all() == {}


def test_use_magic_item_identify_appends_upgrade_advisory_when_slot_occupied(tmp_path):
    from boukensha.memory.item_stats import ItemStatsStore
    from boukensha.memory.player_tracker import PlayerTracker

    ItemStatsStore(tmp_path).save(
        "a copper ring", {"wear_slot": "finger", "affects": {"ac": -2, "hitroll": 0}}
    )
    PlayerTracker(tmp_path).update_equipment("Tester", {"finger": "a copper ring"})

    registry = _make_registry()
    mock_session = MagicMock()
    mock_session.is_open = True
    mock_session.drain.return_value = ""
    mock_session.read_until_prompt.return_value = _identify_output(
        "a gold ring", "finger", {"ac": -10, "hitroll": 2}
    )
    Mud._register_with_session(
        registry, mock_session, name="Tester", password="secret", memory_dir=tmp_path
    )

    result = registry.dispatch(
        "use_magic_item", {"item": "scroll of identify", "mode": "recite", "target_args": "gold ring"}
    )

    assert "[Equipment]" in result
    assert "a gold ring" in result
    assert "finger" in result
    assert "a copper ring" in result


def test_use_magic_item_identify_omits_advisory_when_slot_empty(tmp_path):
    registry = _make_registry()
    mock_session = MagicMock()
    mock_session.is_open = True
    mock_session.drain.return_value = ""
    mock_session.read_until_prompt.return_value = _identify_output(
        "a gold ring", "finger", {"ac": -10, "hitroll": 2}
    )
    Mud._register_with_session(
        registry, mock_session, name="Tester", password="secret", memory_dir=tmp_path
    )

    result = registry.dispatch(
        "use_magic_item", {"item": "scroll of identify", "mode": "recite", "target_args": "gold ring"}
    )

    assert "[Equipment]" not in result


def test_use_magic_item_identify_omits_advisory_when_current_item_never_identified(tmp_path):
    from boukensha.memory.player_tracker import PlayerTracker
    PlayerTracker(tmp_path).update_equipment("Tester", {"finger": "a mystery ring"})

    registry = _make_registry()
    mock_session = MagicMock()
    mock_session.is_open = True
    mock_session.drain.return_value = ""
    mock_session.read_until_prompt.return_value = _identify_output(
        "a gold ring", "finger", {"ac": -10, "hitroll": 2}
    )
    Mud._register_with_session(
        registry, mock_session, name="Tester", password="secret", memory_dir=tmp_path
    )

    result = registry.dispatch(
        "use_magic_item", {"item": "scroll of identify", "mode": "recite", "target_args": "gold ring"}
    )

    assert "[Equipment]" not in result


def test_use_magic_item_identify_omits_advisory_when_new_item_not_better(tmp_path):
    from boukensha.memory.item_stats import ItemStatsStore
    from boukensha.memory.player_tracker import PlayerTracker

    ItemStatsStore(tmp_path).save(
        "a platinum ring", {"wear_slot": "finger", "affects": {"ac": -20, "hitroll": 5}}
    )
    PlayerTracker(tmp_path).update_equipment("Tester", {"finger": "a platinum ring"})

    registry = _make_registry()
    mock_session = MagicMock()
    mock_session.is_open = True
    mock_session.drain.return_value = ""
    mock_session.read_until_prompt.return_value = _identify_output(
        "a gold ring", "finger", {"ac": -10, "hitroll": 2}
    )
    Mud._register_with_session(
        registry, mock_session, name="Tester", password="secret", memory_dir=tmp_path
    )

    result = registry.dispatch(
        "use_magic_item", {"item": "scroll of identify", "mode": "recite", "target_args": "gold ring"}
    )

    assert "[Equipment]" not in result


def test_use_magic_item_identify_weapon_upgrade_advisory_suggests_wield_not_wear(tmp_path):
    from boukensha.memory.item_stats import ItemStatsStore
    from boukensha.memory.player_tracker import PlayerTracker

    ItemStatsStore(tmp_path).save(
        "a rusty sword", {"wear_slot": "wielded", "affects": {"hitroll": 0}}
    )
    PlayerTracker(tmp_path).update_equipment("Tester", {"wielded": "a rusty sword"})

    registry = _make_registry()
    mock_session = MagicMock()
    mock_session.is_open = True
    mock_session.drain.return_value = ""
    mock_session.read_until_prompt.return_value = (
        "Object 'a flaming longsword', Item type: WEAPON\n"
        "Can affect you as :\n"
        "   Affects: HITROLL By 3\n"
        " > "
    )
    Mud._register_with_session(
        registry, mock_session, name="Tester", password="secret", memory_dir=tmp_path
    )

    result = registry.dispatch(
        "use_magic_item",
        {"item": "scroll of identify", "mode": "recite", "target_args": "flaming longsword"},
    )

    assert "[Equipment]" in result
    assert 'action="wield"' in result
    assert 'action="wear"' not in result


def test_affects_score_negates_saving_throws_like_ac():
    from boukensha.tools.mud import _affects_score

    # A saving throw of -3 is better than +2 (lower is better), so the
    # score for the -3 case must exceed the score for the +2 case.
    better = _affects_score({"saving_spell": -3})
    worse = _affects_score({"saving_spell": 2})
    assert better > worse

    # Other saving-throw variants are negated the same way.
    assert _affects_score({"saving_para": -5}) == 5
    assert _affects_score({"saving_breath": 4}) == -4
    assert _affects_score({"saving_rod": -1}) == 1
    assert _affects_score({"saving_petri": 2}) == -2

    # Non-saving, non-ac affects remain additive.
    assert _affects_score({"hitroll": 3, "damroll": 2, "str": 1}) == 6

    # AC and saving throws combine correctly alongside additive affects.
    assert _affects_score({"ac": -10, "saving_spell": -2, "hitroll": 4}) == 10 + 2 + 4


def test_use_magic_item_identify_appends_advisory_for_better_saving_throw(tmp_path):
    from boukensha.memory.item_stats import ItemStatsStore
    from boukensha.memory.player_tracker import PlayerTracker

    ItemStatsStore(tmp_path).save(
        "a plain cloak", {"wear_slot": "neck", "affects": {"saving_spell": 2}}
    )
    PlayerTracker(tmp_path).update_equipment("Tester", {"neck": "a plain cloak"})

    registry = _make_registry()
    mock_session = MagicMock()
    mock_session.is_open = True
    mock_session.drain.return_value = ""
    mock_session.read_until_prompt.return_value = (
        "Object 'a warded cloak', Item type: WORN\n"
        "This item can be worn on: NECK\n"
        "Can affect you as :\n"
        "   Affects: SAVING_SPELL By -3\n"
        " > "
    )
    Mud._register_with_session(
        registry, mock_session, name="Tester", password="secret", memory_dir=tmp_path
    )

    result = registry.dispatch(
        "use_magic_item",
        {"item": "scroll of identify", "mode": "recite", "target_args": "warded cloak"},
    )

    assert "[Equipment]" in result
    assert "a warded cloak" in result


def test_identify_without_memory_dir_does_not_crash():
    registry = _make_registry()
    mock_session = MagicMock()
    mock_session.is_open = True
    mock_session.drain.return_value = ""
    mock_session.read_until_prompt.return_value = _identify_output(
        "a gold ring", "finger", {"ac": -10}
    )
    Mud._register_with_session(registry, mock_session, name="Tester", password="secret")
    result = registry.dispatch("cast_spell", {"spell": "identify", "target": "gold ring"})
    assert "a gold ring" in result
