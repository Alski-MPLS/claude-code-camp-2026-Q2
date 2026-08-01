from __future__ import annotations
from boukensha.memory.room_aliases import RoomAliases


def test_add_and_get(tmp_path):
    aliases = RoomAliases(tmp_path)
    aliases.add("bakery", "abc123")
    assert aliases.get("bakery") == "abc123"


def test_get_is_case_insensitive(tmp_path):
    aliases = RoomAliases(tmp_path)
    aliases.add("Bakery", "abc123")
    assert aliases.get("bakery") == "abc123"
    assert aliases.get("BAKERY") == "abc123"


def test_get_missing_alias_returns_none(tmp_path):
    aliases = RoomAliases(tmp_path)
    assert aliases.get("nonexistent") is None


def test_add_overwrites_existing_alias(tmp_path):
    aliases = RoomAliases(tmp_path)
    aliases.add("guild", "old_hash")
    aliases.add("guild", "new_hash")
    assert aliases.get("guild") == "new_hash"


def test_read_all_returns_lowercased_map(tmp_path):
    aliases = RoomAliases(tmp_path)
    aliases.add("Bakery", "abc123")
    aliases.add("newbie zone", "def456")
    assert aliases.read_all() == {"bakery": "abc123", "newbie zone": "def456"}


def test_persists_across_instances(tmp_path):
    RoomAliases(tmp_path).add("bakery", "abc123")
    reloaded = RoomAliases(tmp_path)
    assert reloaded.get("bakery") == "abc123"


def test_atomic_write_no_partial_state(tmp_path):
    import os
    aliases = RoomAliases(tmp_path)
    aliases.add("bakery", "abc123")
    assert not any(f.endswith(".tmp") for f in os.listdir(tmp_path))
    assert (tmp_path / "room_aliases.json").exists()


def test_read_all_empty_when_no_file(tmp_path):
    aliases = RoomAliases(tmp_path)
    assert aliases.read_all() == {}


def test_tolerates_corrupt_file(tmp_path):
    (tmp_path / "room_aliases.json").write_text("not valid json", encoding="utf-8")
    aliases = RoomAliases(tmp_path)
    assert aliases.read_all() == {}
