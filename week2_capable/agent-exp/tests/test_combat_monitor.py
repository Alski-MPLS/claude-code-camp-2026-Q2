from unittest.mock import MagicMock
from boukensha.goals.combat_monitor import CombatMonitor
from boukensha.goals.goal_manager import GoalManager


def test_check_below_threshold_returns_directive(tmp_path):
    gm = GoalManager(tmp_path)
    gm.update(hp_flee_threshold=5)
    goal = gm.read()
    directive = CombatMonitor.check(hp=3, goal=goal)
    assert directive is not None
    assert "flee" in directive.lower()


def test_check_at_threshold_returns_directive(tmp_path):
    gm = GoalManager(tmp_path)
    gm.update(hp_flee_threshold=5)
    goal = gm.read()
    directive = CombatMonitor.check(hp=5, goal=goal)
    assert directive is not None


def test_check_above_threshold_returns_none(tmp_path):
    gm = GoalManager(tmp_path)
    gm.update(hp_flee_threshold=5)
    goal = gm.read()
    assert CombatMonitor.check(hp=20, goal=goal) is None


def test_update_on_low_hp_sets_flee_status(tmp_path):
    gm = GoalManager(tmp_path)
    gm.update(hp_flee_threshold=5)
    CombatMonitor.update_on_low_hp(hp=3, goal_manager=gm)
    assert gm.read()["status"] == "flee"


def test_update_on_low_hp_returns_directive(tmp_path):
    gm = GoalManager(tmp_path)
    gm.update(hp_flee_threshold=5)
    result = CombatMonitor.update_on_low_hp(hp=3, goal_manager=gm)
    assert result is not None


def test_update_on_low_hp_above_threshold_returns_none(tmp_path):
    gm = GoalManager(tmp_path)
    gm.update(hp_flee_threshold=5)
    result = CombatMonitor.update_on_low_hp(hp=20, goal_manager=gm)
    assert result is None
