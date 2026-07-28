from boukensha.memory.darkness import is_dark_room


def test_detects_pitch_black_response():
    assert is_dark_room("It is pitch black...\r\n\r\n34H 100M 87V (news) (motd) > ")


def test_detects_pitch_black_case_insensitive():
    assert is_dark_room("IT IS PITCH BLACK...")


def test_normal_room_is_not_dark():
    raw = "The Great Field\n   You stand in a great field.\n[ Exits: n s ]\n"
    assert not is_dark_room(raw)


def test_empty_string_is_not_dark():
    assert not is_dark_room("")
