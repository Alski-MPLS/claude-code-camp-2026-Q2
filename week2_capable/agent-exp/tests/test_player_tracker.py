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


def test_prev_room_hash_set_on_room_change(tmp_path):
    tracker = PlayerTracker(tmp_path)
    tracker.update("Aria", "room_a", "Entry Hall")
    tracker.update("Aria", "room_b", "Dark Corridor")
    data = tracker.read_all()
    assert data["Aria"]["room_hash"] == "room_b"
    assert data["Aria"]["prev_room_hash"] == "room_a"


def test_prev_room_hash_none_on_first_update(tmp_path):
    tracker = PlayerTracker(tmp_path)
    tracker.update("Aria", "room_a", "Entry Hall")
    data = tracker.read_all()
    assert data["Aria"]["prev_room_hash"] is None


def test_prev_room_hash_unchanged_when_room_same(tmp_path):
    tracker = PlayerTracker(tmp_path)
    tracker.update("Aria", "room_a", "Entry Hall")
    tracker.update("Aria", "room_b", "Dark Corridor")
    tracker.update("Aria", "room_b", "Dark Corridor")  # same room again
    data = tracker.read_all()
    # prev_room_hash should still be room_a (last real move), not room_b
    assert data["Aria"]["prev_room_hash"] == "room_a"


def test_update_stats_records_stats_for_new_player(tmp_path):
    tracker = PlayerTracker(tmp_path)
    tracker.update_stats("Hero", {"hp": 20, "max_hp": 20})
    data = tracker.read_all()
    assert data["Hero"]["stats"] == {"hp": 20, "max_hp": 20}
    assert "stats_updated_at" in data["Hero"]


def test_update_stats_preserves_existing_position(tmp_path):
    tracker = PlayerTracker(tmp_path)
    tracker.update("Hero", "abc123", "Temple Square")
    tracker.update_stats("Hero", {"hp": 20, "max_hp": 20})
    data = tracker.read_all()
    assert data["Hero"]["room_hash"] == "abc123"
    assert data["Hero"]["stats"]["hp"] == 20


def test_update_preserves_existing_stats(tmp_path):
    tracker = PlayerTracker(tmp_path)
    tracker.update_stats("Hero", {"hp": 20, "max_hp": 20})
    tracker.update("Hero", "abc123", "Temple Square")
    data = tracker.read_all()
    assert data["Hero"]["stats"] == {"hp": 20, "max_hp": 20}
    assert data["Hero"]["room_hash"] == "abc123"
