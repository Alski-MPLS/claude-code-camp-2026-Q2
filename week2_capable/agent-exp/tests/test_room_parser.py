from boukensha.memory.parser import RoomParser

SAMPLE_LOOK = """\
The Temple Square
   You are in the middle of a large open square in the middle of the
   city. Around you, citizens going about their daily business. To the
   north is the imposing Temple of Midgaard.
Exits: north, east, south, west
A dog is here.
A loaf of bread is here.
"""

MINIMAL_LOOK = """\
A Dark Corridor
   A narrow passage.
Exits: north
"""

NO_EXITS_LOOK = """\
A Dead End
   The path ends here.
"""


def test_parse_title():
    r = RoomParser.parse(SAMPLE_LOOK)
    assert r["title"] == "The Temple Square"


def test_parse_description():
    r = RoomParser.parse(SAMPLE_LOOK)
    assert "large open square" in r["description"]


def test_parse_exits_keys():
    r = RoomParser.parse(SAMPLE_LOOK)
    assert set(r["exits"].keys()) == {"north", "east", "south", "west"}


def test_parse_exits_values_none():
    r = RoomParser.parse(SAMPLE_LOOK)
    for v in r["exits"].values():
        assert v is None


def test_parse_npcs():
    r = RoomParser.parse(SAMPLE_LOOK)
    assert any("dog" in n.lower() for n in r["npcs"])


def test_parse_items():
    r = RoomParser.parse(SAMPLE_LOOK)
    assert any("bread" in i.lower() for i in r["items"])


def test_parse_minimal():
    r = RoomParser.parse(MINIMAL_LOOK)
    assert r["title"] == "A Dark Corridor"
    assert r["exits"] == {"north": None}
    assert r["npcs"] == []
    assert r["items"] == []


def test_parse_no_exits():
    r = RoomParser.parse(NO_EXITS_LOOK)
    assert r["exits"] == {}


def test_parse_returns_required_keys():
    r = RoomParser.parse(SAMPLE_LOOK)
    assert all(k in r for k in ("title", "description", "exits", "npcs", "items"))


def test_parse_empty_string():
    r = RoomParser.parse("")
    assert r["title"] == ""
    assert r["exits"] == {}
