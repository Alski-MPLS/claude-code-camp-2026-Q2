"""Tests for boukensha.tools.Combat — no live MUD server required."""
from __future__ import annotations

from unittest.mock import MagicMock

from boukensha.context import Context
from boukensha.registry import Registry
from boukensha.tasks.player import Player
from boukensha.tools.combat import Combat


def _make_registry() -> Registry:
    ctx = Context(task=Player, system="sys")
    return Registry(ctx)


def test_combat_loop_refuses_a_dangerous_target(tmp_path):
    registry = _make_registry()
    mock_session = MagicMock()
    mock_session.is_open = True
    mock_session.drain.return_value = ""
    mock_session.read_until_prompt.return_value = (
        "You size up the Pawn of the Black Court.\nDo you feel lucky, punk?\n"
    )
    Combat.register(
        registry, session=mock_session, goals_dir=tmp_path,
        current_npcs_ref=[["The Pawn of the Black Court"]],
    )

    result = registry.dispatch("combat_loop", {"target": "Pawn of the Black Court"})

    assert "Refused to attack" in result
    assert "do you feel lucky" in result.lower()
    # never sent "kill" — the fight must not have started
    sent = [c.args[0] for c in mock_session.send_command.call_args_list]
    assert not any(s.startswith("kill") for s in sent)


def test_combat_loop_marks_goal_flee_when_refusing(tmp_path):
    from boukensha.goals.goal_manager import GoalManager

    registry = _make_registry()
    mock_session = MagicMock()
    mock_session.is_open = True
    mock_session.drain.return_value = ""
    mock_session.read_until_prompt.return_value = "Do you feel lucky, punk?\n"
    Combat.register(
        registry, session=mock_session, goals_dir=tmp_path,
        current_npcs_ref=[["The Pawn of the Black Court"]],
    )

    registry.dispatch("combat_loop", {"target": "Pawn of the Black Court"})

    assert GoalManager(tmp_path).read()["status"] == "flee"


def test_combat_loop_force_skips_the_danger_check(tmp_path):
    registry = _make_registry()
    mock_session = MagicMock()
    mock_session.is_open = True
    mock_session.drain.return_value = ""
    mock_session.read_until_prompt.return_value = "Kestrel the Pawn of the Black Court is dead!\n"
    Combat.register(registry, session=mock_session, goals_dir=tmp_path)

    result = registry.dispatch(
        "combat_loop", {"target": "Pawn of the Black Court", "force": True}
    )

    assert "defeated" in result
    sent = [c.args[0] for c in mock_session.send_command.call_args_list]
    assert sent[0] == "kill Pawn of the Black Court"
    assert not any(s.startswith("consider") for s in sent)


def test_combat_loop_refuses_when_only_a_corpse_is_present(tmp_path):
    """Real-world bug: the room has only a corpse, but the agent targets the
    creature's living name anyway — this must be refused before ever
    touching the socket, not bounced off an ambiguous MUD reply."""
    registry = _make_registry()
    mock_session = MagicMock()
    mock_session.is_open = True
    mock_session.drain.return_value = ""
    # npcs is empty because RoomParser correctly files corpses as items, not npcs
    Combat.register(registry, session=mock_session, goals_dir=tmp_path, current_npcs_ref=[[]])

    result = registry.dispatch("combat_loop", {"target": "newbie monster"})

    assert "No living 'newbie monster'" in result
    mock_session.send_command.assert_not_called()


def test_combat_loop_proceeds_when_consider_looks_safe(tmp_path):
    registry = _make_registry()
    mock_session = MagicMock()
    mock_session.is_open = True
    mock_session.drain.return_value = ""
    mock_session.read_until_prompt.side_effect = [
        "This will be a piece of cake.\n",              # consider
        "The rat is dead! You receive experience points.\n",  # kill
    ]
    Combat.register(
        registry, session=mock_session, goals_dir=tmp_path,
        current_npcs_ref=[["a rat"]],
    )

    result = registry.dispatch("combat_loop", {"target": "rat"})

    assert "defeated" in result
    sent = [c.args[0] for c in mock_session.send_command.call_args_list]
    assert sent == ["consider rat", "kill rat"]
