from unittest.mock import MagicMock

from boukensha.tools.room_processor import RoomProcessor
from boukensha.context import Context
from boukensha.registry import Registry
from boukensha.tasks.player import Player


def _make_registry() -> Registry:
    return Registry(Context(task=Player, system="sys"))


def _make_session(*responses: str) -> MagicMock:
    session = MagicMock()
    session.is_open = True
    session.drain.return_value = ""
    session.read_until_prompt.side_effect = list(responses)
    return session


def test_process_room_reports_full_detail_on_first_visit(tmp_path):
    registry = _make_registry()
    session = _make_session(
        "The Temple Square\n   A large square.\n[ Exits: n s ]\n"
        "A large fountain carved from blue-streaked marble is here, bubbling merrily.\n"
    )
    RoomProcessor.register(registry, session=session, memory_dir=tmp_path)

    result = registry.dispatch("process_room", {})

    assert "fountain" in result.lower()


def test_process_room_still_surfaces_items_on_a_known_room_revisit(tmp_path):
    """The exact scenario reported live: asked to find a fountain and drink
    from it, the agent revisited a known room and process_room's diff-only
    design hid the fountain (already in items, unchanged) entirely, along
    with everything else in the room — leaving the agent with nothing to
    act on. NPCs/items must always be reported, known room or not, since
    they're exactly what a goal usually needs the agent to act on."""
    raw = (
        "The Temple Square\n   A large square.\n[ Exits: n s ]\n"
        "A large fountain carved from blue-streaked marble is here, bubbling merrily.\n"
    )
    registry = _make_registry()
    session = _make_session(raw, raw)
    RoomProcessor.register(registry, session=session, memory_dir=tmp_path)

    registry.dispatch("process_room", {})  # first visit: records the room
    result = registry.dispatch("process_room", {})  # second visit: "known"

    assert "known room" in result.lower()
    assert "fountain" in result.lower()


def test_process_room_known_room_with_no_npcs_or_items_says_nothing_new(tmp_path):
    raw = "A Plain Hallway\n   Nothing here.\n[ Exits: n ]\n"
    registry = _make_registry()
    session = _make_session(raw, raw)
    RoomProcessor.register(registry, session=session, memory_dir=tmp_path)

    registry.dispatch("process_room", {})
    result = registry.dispatch("process_room", {})

    assert "nothing new observed" in result.lower()
