from boukensha.goals.gold_monitor import GoldMonitor
from boukensha.goals.goal_manager import GoalManager


def test_check_below_threshold_returns_none(tmp_path):
    gm = GoalManager(tmp_path)
    gm.update(gold_deposit_threshold=200)
    goal = gm.read()
    assert GoldMonitor.check(gold=150, goal=goal) is None


def test_check_at_threshold_returns_advisory(tmp_path):
    gm = GoalManager(tmp_path)
    gm.update(gold_deposit_threshold=200)
    goal = gm.read()
    advisory = GoldMonitor.check(gold=200, goal=goal)
    assert advisory is not None
    assert "[Bank]" in advisory
    assert "amount=100" in advisory


def test_check_above_threshold_returns_advisory_with_correct_half(tmp_path):
    gm = GoalManager(tmp_path)
    gm.update(gold_deposit_threshold=200)
    goal = gm.read()
    advisory = GoldMonitor.check(gold=215, goal=goal)
    assert advisory is not None
    assert "215 gold" in advisory
    assert "amount=107" in advisory  # 215 // 2


def test_check_uses_default_threshold_when_unset():
    advisory = GoldMonitor.check(gold=250, goal={})
    assert advisory is not None
    advisory_below = GoldMonitor.check(gold=100, goal={})
    assert advisory_below is None
