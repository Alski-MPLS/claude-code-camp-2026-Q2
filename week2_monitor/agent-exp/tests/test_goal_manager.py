import yaml
from pathlib import Path
from boukensha.goals.goal_manager import GoalManager


def test_read_returns_defaults_when_no_file(tmp_path):
    gm = GoalManager(tmp_path)
    goal = gm.read()
    assert "current_goal" in goal
    assert "priority" in goal
    assert "hp_flee_threshold" in goal
    assert "status" in goal


def test_update_writes_file(tmp_path):
    gm = GoalManager(tmp_path)
    gm.update(current_goal="Kill the dragon")
    path = tmp_path / "goals" / "current.yaml"
    assert path.exists()


def test_update_persists_value(tmp_path):
    gm = GoalManager(tmp_path)
    gm.update(current_goal="Explore temple")
    goal = gm.read()
    assert goal["current_goal"] == "Explore temple"


def test_update_sets_last_updated(tmp_path):
    gm = GoalManager(tmp_path)
    gm.update(status="flee")
    goal = gm.read()
    assert goal.get("last_updated") is not None


def test_update_merges_not_replaces(tmp_path):
    gm = GoalManager(tmp_path)
    gm.update(current_goal="Heal up", hp_flee_threshold=10)
    gm.update(status="active")
    goal = gm.read()
    assert goal["current_goal"] == "Heal up"
    assert goal["hp_flee_threshold"] == 10
    assert goal["status"] == "active"


def test_reset_restores_defaults(tmp_path):
    gm = GoalManager(tmp_path)
    gm.update(current_goal="Custom goal", status="paused")
    gm.reset()
    goal = gm.read()
    assert goal["current_goal"] == GoalManager.DEFAULT_FIELDS["current_goal"]


def test_write_is_valid_yaml(tmp_path):
    gm = GoalManager(tmp_path)
    gm.update(notes="Found a sword")
    path = tmp_path / "goals" / "current.yaml"
    parsed = yaml.safe_load(path.read_text())
    assert isinstance(parsed, dict)
