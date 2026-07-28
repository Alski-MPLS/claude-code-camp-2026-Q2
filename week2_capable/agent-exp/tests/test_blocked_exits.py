import json

from boukensha.memory.blocked_exits import BlockedExits


def test_get_returns_empty_set_for_unknown_room(tmp_path):
    b = BlockedExits(tmp_path)
    assert b.get("nope") == set()


def test_mark_blocked_persists_across_instances(tmp_path):
    b = BlockedExits(tmp_path)
    b.mark_blocked("roomhash", "north")
    b2 = BlockedExits(tmp_path)
    assert b2.get("roomhash") == {"north"}


def test_mark_blocked_is_additive(tmp_path):
    b = BlockedExits(tmp_path)
    b.mark_blocked("roomhash", "north")
    b.mark_blocked("roomhash", "east")
    assert b.get("roomhash") == {"north", "east"}


def test_unmark_removes_direction(tmp_path):
    b = BlockedExits(tmp_path)
    b.mark_blocked("roomhash", "north")
    b.mark_blocked("roomhash", "east")
    b.unmark("roomhash", "north")
    assert b.get("roomhash") == {"east"}


def test_unmark_removes_room_entirely_when_empty(tmp_path):
    b = BlockedExits(tmp_path)
    b.mark_blocked("roomhash", "north")
    b.unmark("roomhash", "north")
    assert b.read_all() == {}


def test_reads_pre_existing_old_schema_file_without_crashing(tmp_path):
    """Before BlockedExits gained a reason field, it persisted a plain list
    of blocked directions per room. A file already written in that format
    by a previous run must still load — not raise AttributeError — after
    upgrading to the dict-of-reasons schema."""
    (tmp_path / "blocked_exits.json").write_text(
        json.dumps({"roomhash": ["down"]}), encoding="utf-8"
    )
    b = BlockedExits(tmp_path)
    assert b.get("roomhash") == {"down"}
    assert b.reason("roomhash", "down") == "blocked"


def test_old_schema_room_can_still_be_unmarked(tmp_path):
    (tmp_path / "blocked_exits.json").write_text(
        json.dumps({"roomhash": ["down", "east"]}), encoding="utf-8"
    )
    b = BlockedExits(tmp_path)
    b.unmark("roomhash", "down")
    assert b.get("roomhash") == {"east"}
