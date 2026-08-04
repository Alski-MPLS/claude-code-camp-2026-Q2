from boukensha.memory.parser import RoomParser

SAMPLE_LOOK = """\
The Temple Square
   You are in the middle of a large open square in the middle of the
   city. Around you, citizens going about their daily business. To the
   north is the imposing Temple of Midgaard.
[ Exits: n e s w ]
A dog is here.
A loaf of bread is lying here.
"""

MINIMAL_LOOK = """\
A Dark Corridor
   A narrow passage.
[ Exits: n ]
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


# --- non-room text must not be mistaken for a room title (real-world bug:
# these were showing up as garbage nodes on the map) ---

def test_parse_move_failure_yields_empty_title():
    r = RoomParser.parse("Alas, you cannot go that way...\n")
    assert r["title"] == ""


def test_parse_generic_failure_sentence_yields_empty_title():
    r = RoomParser.parse("That's not a menu choice!\n")
    assert r["title"] == ""


def test_parse_classifies_longer_named_npc_correctly():
    # A real-world regression: "A creepy crawler is here." (5 words) used to
    # be misfiled as an item by a word-count heuristic, which would make a
    # combat-safety consumer of npcs[] wrongly think nothing living is here.
    raw = (
        "The Dirty Hallway\n"
        "   A grimy hallway.\n"
        "[ Exits: n ]\n"
        "A creepy crawler is here.\n"
    )
    r = RoomParser.parse(raw)
    assert r["npcs"] == ["A creepy crawler is here."]
    assert r["items"] == []


def test_parse_npc_line_ending_in_exclamation_mark_is_not_dropped():
    # Real-world regression: "The newbie monster stands here looking
    # confused.  Kill him!  Kill him!" ends in "!", not ".", so the old
    # endswith(".") check silently dropped it from both npcs and items —
    # look() showed the mob but combat_loop/attack always said nothing
    # living was here, since _match_npc had nothing to match against.
    raw = (
        "The Beginning Of The Passage\n"
        "   A long corridor.\n"
        "[ Exits: e s ]\n"
        "The newbie monster stands here looking confused.  Kill him!  Kill him!\n"
    )
    r = RoomParser.parse(raw)
    assert any("newbie monster" in n.lower() for n in r["npcs"])
    assert r["items"] == []


def test_parse_npc_line_ending_in_question_mark_is_not_dropped():
    raw = (
        "A Small Room\n"
        "   A cramped room.\n"
        "[ Exits: n ]\n"
        "A confused guard looks around, lost. Where am I?\n"
    )
    r = RoomParser.parse(raw)
    assert any("confused guard" in n.lower() for n in r["npcs"])


def test_parse_corpse_stays_an_item_even_with_a_short_name():
    raw = (
        "The Dirty Hallway\n"
        "   A grimy hallway.\n"
        "[ Exits: n ]\n"
        "The corpse of the creepy crawler is lying here.\n"
    )
    r = RoomParser.parse(raw)
    assert r["npcs"] == []
    assert r["items"] == ["The corpse of the creepy crawler is lying here."]


def test_parse_skips_zone_banner_to_find_real_title():
    raw = (
        "This zone is above the level of most zones. Here be dragons.\n"
        "\n"
        "The Dirt Path\n"
        "   You are on a dirt path.\n"
        "[ Exits: n w ]\n"
    )
    r = RoomParser.parse(raw)
    assert r["title"] == "The Dirt Path"
    assert r["description"] == "You are on a dirt path."
    assert set(r["exits"].keys()) == {"north", "west"}
