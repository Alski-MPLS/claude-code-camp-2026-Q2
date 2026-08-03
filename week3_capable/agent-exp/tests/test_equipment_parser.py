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
        "wield": "a long sword",
    }


def test_parse_equipment_returns_empty_dict_when_nothing_worn():
    # "This IS equipment output and nothing is worn" — distinct from None.
    assert parse_equipment("You are using: nothing.\n") == {}


def test_parse_equipment_returns_none_for_unrelated_text():
    assert parse_equipment("You aren't holding that item.\n") is None


def test_parse_equipment_returns_none_for_empty_string():
    assert parse_equipment("") is None


def test_parse_equipment_canonicalizes_every_wear_where_label():
    text = (
        "You are using:\n"
        "<used as light>       a small candle\n"
        "<worn on finger>      a gold ring\n"
        "<worn around neck>    an amulet\n"
        "<worn on body>        a suit of leather armor\n"
        "<worn on head>        a leather cap\n"
        "<worn on legs>        leather leggings\n"
        "<worn on feet>        leather boots\n"
        "<worn on hands>       leather gloves\n"
        "<worn on arms>        leather sleeves\n"
        "<worn as shield>      a small shield\n"
        "<worn about body>     a black cloak\n"
        "<worn around waist>   a leather belt\n"
        "<worn around wrist>   a bracelet\n"
        "<wielded>             a long sword\n"
        "<held>                a torch\n"
    )
    assert parse_equipment(text) == {
        "light": "a small candle",
        "finger": "a gold ring",
        "neck": "an amulet",
        "body": "a suit of leather armor",
        "head": "a leather cap",
        "legs": "leather leggings",
        "feet": "leather boots",
        "hands": "leather gloves",
        "arms": "leather sleeves",
        "shield": "a small shield",
        "about": "a black cloak",
        "waist": "a leather belt",
        "wrist": "a bracelet",
        "wield": "a long sword",
        "hold": "a torch",
    }


def test_parse_equipment_about_body_does_not_collide_with_body():
    text = (
        "You are using:\n"
        "<worn on body>     plate mail\n"
        "<worn about body>  a black cloak\n"
    )
    assert parse_equipment(text) == {"body": "plate mail", "about": "a black cloak"}


def test_parse_equipment_last_worn_wins_for_dual_slots():
    # Known limitation: RING_R/RING_L both print "<worn on finger>".
    text = (
        "You are using:\n"
        "<worn on finger>   a gold ring\n"
        "<worn on finger>   a silver ring\n"
    )
    assert parse_equipment(text) == {"finger": "a silver ring"}


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
    assert parsed["wear_slot"] == "wield"
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


def test_parse_identify_ignores_take_bit_on_wear_line():
    # sprintbit prints every set wear bit; WEAR_TAKE is set on nearly every
    # wearable item, so the real line leads with TAKE.
    text = (
        "Object 'a gold ring', Item type: WORN\n"
        "This item can be worn on: TAKE FINGER\n"
    )
    assert parse_identify(text)["wear_slot"] == "finger"


def test_parse_identify_ignores_take_bit_for_multiword_slots():
    for bits, expected in [
        ("TAKE NECK", "neck"),
        ("TAKE ABOUT", "about"),
        ("TAKE WAIST", "waist"),
        ("TAKE WRIST", "wrist"),
        ("TAKE WIELD", "wield"),
        ("TAKE HOLD", "hold"),
    ]:
        text = f"Object 'a thing', Item type: WORN\nThis item can be worn on: {bits}\n"
        assert parse_identify(text)["wear_slot"] == expected


def test_parse_identify_wear_slot_none_when_only_take_bit_and_not_a_weapon():
    text = "Object 'a rusty spoon', Item type: OTHER\nThis item can be worn on: TAKE\n"
    assert parse_identify(text)["wear_slot"] is None


def test_parse_identify_handles_apostrophe_in_item_name():
    text = (
        "Object 'a mage's staff', Item type: WEAPON\n"
        "This item can be worn on: TAKE WIELD\n"
    )
    parsed = parse_identify(text)
    assert parsed["name"] == "a mage's staff"
    assert parsed["wear_slot"] == "wield"


def test_item_lookup_key_strips_magic_flag_suffixes():
    from boukensha.memory.equipment_parser import _item_lookup_key

    assert _item_lookup_key("a gold ring ..(Yellow Aura)") == "a gold ring"
    assert _item_lookup_key("a gold ring (invisible)") == "a gold ring"
    assert _item_lookup_key("a gold ring (Glowing) (Humming)") == "a gold ring"
    assert _item_lookup_key("  a gold ring  ") == "a gold ring"
    assert _item_lookup_key("a gold ring") == "a gold ring"


def test_parse_equipment_and_parse_identify_agree_on_slot_keys():
    """The bug that motivated the canonical table: these must be the same key."""
    pairs = [
        ("<worn around neck>   an amulet", "NECK"),
        ("<worn about body>    a cloak", "ABOUT"),
        ("<worn around waist>  a belt", "WAIST"),
        ("<worn around wrist>  a bracelet", "WRIST"),
        ("<held>               a torch", "HOLD"),
        ("<wielded>            a sword", "WIELD"),
    ]
    for equip_line, bit in pairs:
        eq = parse_equipment("You are using:\n" + equip_line + "\n")
        ident = parse_identify(
            f"Object 'a thing', Item type: WORN\nThis item can be worn on: TAKE {bit}\n"
        )
        assert list(eq) == [ident["wear_slot"]], (equip_line, bit)
