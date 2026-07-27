from boukensha.memory.player_tracker import PlayerTracker


def test_read_all_empty_when_no_file(tmp_path):
    tracker = PlayerTracker(tmp_path)
    assert tracker.read_all() == {}


def test_update_records_position(tmp_path):
    tracker = PlayerTracker(tmp_path)
    tracker.update("Hero", "abc123", "Temple Square")
    data = tracker.read_all()
    assert data["Hero"]["room_hash"] == "abc123"
    assert data["Hero"]["title"] == "Temple Square"
    assert "updated_at" in data["Hero"]


def test_update_overwrites_same_character(tmp_path):
    tracker = PlayerTracker(tmp_path)
    tracker.update("Hero", "abc123", "Temple Square")
    tracker.update("Hero", "def456", "Main Street")
    data = tracker.read_all()
    assert len(data) == 1
    assert data["Hero"]["room_hash"] == "def456"


def test_multiple_characters_tracked_independently(tmp_path):
    tracker = PlayerTracker(tmp_path)
    tracker.update("Hero", "abc123", "Temple Square")
    tracker.update("Villain", "xyz789", "Dark Alley")
    data = tracker.read_all()
    assert set(data.keys()) == {"Hero", "Villain"}
    assert data["Villain"]["title"] == "Dark Alley"


def test_persists_across_instances(tmp_path):
    PlayerTracker(tmp_path).update("Hero", "abc123", "Temple Square")
    reloaded = PlayerTracker(tmp_path).read_all()
    assert reloaded["Hero"]["room_hash"] == "abc123"
