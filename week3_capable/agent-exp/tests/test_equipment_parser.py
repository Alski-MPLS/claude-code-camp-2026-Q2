from boukensha.memory.equipment_parser import parse_equipment, parse_identify


def test_parse_equipment_extracts_worn_slots():
    text = (
        "You are using:\n"
        "<used as light>       a small candle\n"
        "<worn on finger>      a gold ring\n"
        "<worn on body>        a suit of leather armor\n"
        "<wielded>              a long sword\n"
    )
    assert parse_equipment(text) == {
        "light": "a small candle",
        "finger": "a gold ring",
        "body": "a suit of leather armor",
        "wielded": "a long sword",
    }


def test_parse_equipment_returns_none_when_no_slot_lines():
    assert parse_equipment("You are using: nothing.\n") is None


def test_parse_equipment_returns_none_for_empty_string():
    assert parse_equipment("") is None


def test_parse_equipment_strips_trailing_whitespace_from_item_name():
    text = "<worn on head>        a leather cap   \n"
    assert parse_equipment(text) == {"head": "a leather cap"}


def test_parse_identify_extracts_name_slot_and_affects():
    text = (
        "You feel informed:\n"
        "Object 'a gold ring', Item type: WORN\n"
        "This item can be worn on: FINGER\n"
        "Can affect you as :\n"
        "   Affects: HITROLL By 2\n"
        "   Affects: DAMROLL By 1\n"
        "   Affects: AC By -10\n"
    )
    parsed = parse_identify(text)
    assert parsed == {
        "name": "a gold ring",
        "wear_slot": "finger",
        "affects": {"hitroll": 2, "damroll": 1, "ac": -10},
    }


def test_parse_identify_infers_wielded_slot_for_weapons_without_worn_on_line():
    text = (
        "Object 'a long sword', Item type: WEAPON\n"
        "Can affect you as :\n"
        "   Affects: HITROLL By 1\n"
    )
    parsed = parse_identify(text)
    assert parsed["wear_slot"] == "wielded"
    assert parsed["affects"] == {"hitroll": 1}


def test_parse_identify_wear_slot_none_when_neither_marker_present():
    text = (
        "Object 'a bag of holding', Item type: CONTAINER\n"
        "Can affect you as :\n"
        "   Affects: STR By 1\n"
    )
    parsed = parse_identify(text)
    assert parsed["wear_slot"] is None
    assert parsed["affects"] == {"str": 1}


def test_parse_identify_returns_empty_affects_when_no_affects_lines():
    text = "Object 'a rusty spoon', Item type: OTHER\n"
    parsed = parse_identify(text)
    assert parsed["affects"] == {}


def test_parse_identify_returns_none_for_non_identify_text():
    assert parse_identify("You aren't holding that item.\n") is None


def test_parse_identify_returns_none_for_empty_string():
    assert parse_identify("") is None
