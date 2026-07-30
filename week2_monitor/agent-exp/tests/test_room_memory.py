import json
from pathlib import Path
from boukensha.memory.room_memory import RoomMemory

ROOM_A = {
    "title": "The Temple Square",
    "description": "A large open square.",
    "exits": {"north": None, "south": None},
    "npcs": [],
    "items": [],
}

ROOM_B = {
    "title": "The Dark Corridor",
    "description": "A narrow passage.",
    "exits": {"south": None},
    "npcs": [],
    "items": [],
}


def test_room_hash_is_12_hex_chars(tmp_path):
    mem = RoomMemory(tmp_path)
    h = mem.room_hash(ROOM_A)
    assert len(h) == 12
    assert all(c in "0123456789abcdef" for c in h)


def test_room_hash_is_deterministic(tmp_path):
    mem = RoomMemory(tmp_path)
    assert mem.room_hash(ROOM_A) == mem.room_hash(ROOM_A)


def test_room_hash_differs_for_different_rooms(tmp_path):
    mem = RoomMemory(tmp_path)
    assert mem.room_hash(ROOM_A) != mem.room_hash(ROOM_B)


def test_record_writes_file(tmp_path):
    mem = RoomMemory(tmp_path)
    h, _ = mem.record(ROOM_A)
    room_file = tmp_path / "rooms" / f"{h}.json"
    assert room_file.exists()


def test_record_new_room_returns_full_diff(tmp_path):
    mem = RoomMemory(tmp_path)
    _, diff = mem.record(ROOM_A)
    assert diff["title"] == ROOM_A["title"]


def test_record_same_room_twice_returns_empty_diff(tmp_path):
    mem = RoomMemory(tmp_path)
    mem.record(ROOM_A)
    _, diff = mem.record(ROOM_A)
    assert diff == {}


def test_record_updates_on_new_npc(tmp_path):
    mem = RoomMemory(tmp_path)
    mem.record(ROOM_A)
    updated = {**ROOM_A, "npcs": ["A fierce guard"]}
    _, diff = mem.record(updated)
    assert "npcs" in diff


def test_get_returns_stored_room(tmp_path):
    mem = RoomMemory(tmp_path)
    h, _ = mem.record(ROOM_A)
    stored = mem.get(h)
    assert stored is not None
    assert stored["title"] == ROOM_A["title"]


def test_get_unknown_hash_returns_none(tmp_path):
    mem = RoomMemory(tmp_path)
    assert mem.get("deadbeefcafe") is None
