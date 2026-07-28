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
