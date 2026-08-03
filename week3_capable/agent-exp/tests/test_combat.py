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


def test_combat_loop_refuses_stock_circlemud_top_danger_tier(tmp_path):
    """Real-world near-death: stock CircleMUD's own most severe consider
    responses ("Are you mad!?" / "You ARE mad!") for a wildly outmatched
    opponent were missing from the danger list, letting a fight through
    that dropped HP to -9 and wiped gold/inventory on the resulting death."""
    registry = _make_registry()
    mock_session = MagicMock()
    mock_session.is_open = True
    mock_session.drain.return_value = ""
    mock_session.read_until_prompt.return_value = (
        "You size up the gelatinous blob.\nYou ARE mad!\n"
    )
    Combat.register(
        registry, session=mock_session, goals_dir=tmp_path,
        current_npcs_ref=[["gelatinous blob"]],
    )

    result = registry.dispatch("combat_loop", {"target": "gelatinous blob"})

    assert "Refused to attack" in result
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
        "You didn't find anything.\n",  # get all corpse
    ]
    Combat.register(
        registry, session=mock_session, goals_dir=tmp_path,
        current_npcs_ref=[["a rat"]],
    )

    result = registry.dispatch("combat_loop", {"target": "rat"})

    assert "defeated" in result
    sent = [c.args[0] for c in mock_session.send_command.call_args_list]
    assert sent == ["consider rat", "kill rat", "get all corpse"]


def test_combat_loop_auto_loots_corpse_after_kill(tmp_path):
    registry = _make_registry()
    mock_session = MagicMock()
    mock_session.is_open = True
    mock_session.drain.return_value = ""
    mock_session.read_until_prompt.side_effect = [
        "This will be a piece of cake.\n",
        "The rat is dead! You receive experience points.\n",
        "You get a handful of gold coins from the corpse of the rat.\n",
    ]
    Combat.register(
        registry, session=mock_session, goals_dir=tmp_path,
        current_npcs_ref=[["a rat"]],
    )

    result = registry.dispatch("combat_loop", {"target": "rat"})

    assert "defeated" in result
    assert "Loot: You get a handful of gold coins" in result
    sent = [c.args[0] for c in mock_session.send_command.call_args_list]
    assert sent == ["consider rat", "kill rat", "get all corpse"]


def test_combat_loop_bails_early_when_target_wanders_off_mid_fight(tmp_path):
    """Real-world bug: a mob flees/wanders mid-fight without printing
    "you stop fighting" or "no one is fighting". The loop must not spin
    all the way to max_rounds waiting on a fight that already ended."""
    registry = _make_registry()
    mock_session = MagicMock()
    mock_session.is_open = True
    mock_session.drain.return_value = ""
    mock_session.read_until_prompt.side_effect = [
        "This will be a piece of cake.\n",  # consider
        "You hit the crawling thing hard!\n34/37H 86/87V> ",  # kill (round 1, real hit)
        "34/37H 86/87V> ",  # round 2: quiet (target already gone)
        "34/37H 86/87V> ",  # round 3: quiet
        "34/37H 86/87V> ",  # round 4: quiet -> probe
        "You don't see them here.\n34/37H 86/87V> ",  # probe: confirms truly gone
    ]
    Combat.register(
        registry, session=mock_session, goals_dir=tmp_path,
        current_npcs_ref=[["a crawling thing"]],
    )

    result = registry.dispatch("combat_loop", {"target": "crawling thing"})

    assert "likely fled, died, or wandered off" in result
    # bailed after the quiet-round limit + one confirming probe, not after all 30 rounds
    assert mock_session.read_until_prompt.call_count == 6


def test_combat_loop_does_not_bail_when_target_is_still_actually_fighting(tmp_path):
    """Real-world bug: some mobs' round text doesn't match any of the known
    hit/miss/dodge phrases, so the quiet-round heuristic alone would wrongly
    conclude "fled" while the fight is still genuinely ongoing (confirmed by
    the server's own "You're fighting the best you can!" reply to a repeat
    kill). The loop must verify with a probe before believing the guess."""
    registry = _make_registry()
    mock_session = MagicMock()
    mock_session.is_open = True
    mock_session.drain.return_value = ""
    mock_session.read_until_prompt.side_effect = [
        "The perfect match!\n",  # consider
        "34/37H 86/87V> ",  # kill (round 1: unusual round text, no matched keyword)
        "34/37H 86/87V> ",  # round 2: quiet
        "34/37H 86/87V> ",  # round 3: quiet -> probe
        "You're fighting the best you can!\n34/37H 86/87V> ",  # probe: still fighting
        "You hit the newbie hard!\nIt is DEAD!!\nYou get experience points.\n34/37H 86/87V> ",
    ]
    Combat.register(
        registry, session=mock_session, goals_dir=tmp_path,
        current_npcs_ref=[["a newbie"]],
    )

    result = registry.dispatch("combat_loop", {"target": "newbie", "auto_loot": False})

    assert "Combat complete" in result
    assert "newbie defeated" in result


def test_combat_loop_auto_loot_false_skips_looting(tmp_path):
    registry = _make_registry()
    mock_session = MagicMock()
    mock_session.is_open = True
    mock_session.drain.return_value = ""
    mock_session.read_until_prompt.return_value = "The rat is dead! You receive experience points.\n"
    Combat.register(registry, session=mock_session, goals_dir=tmp_path)

    result = registry.dispatch(
        "combat_loop", {"target": "rat", "force": True, "auto_loot": False}
    )

    assert "defeated" in result
    assert "Loot:" not in result
    sent = [c.args[0] for c in mock_session.send_command.call_args_list]
    assert "get all corpse" not in sent
