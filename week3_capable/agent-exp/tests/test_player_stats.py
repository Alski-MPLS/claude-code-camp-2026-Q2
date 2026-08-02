from boukensha.memory.player_stats import PlayerStats


def test_parse_score_extracts_hp_mana_move():
    text = (
        "You have 20(20) hit, 100(100) mana and 85(85) movement points.\n"
        "Your armor class is 100/10, and your alignment is 0.\n"
    )
    assert PlayerStats.parse_score(text) == {
        "hp": 20, "max_hp": 20,
        "mana": 100, "max_mana": 100,
        "move": 85, "max_move": 85,
        "hungry": False, "thirsty": False,
    }


def test_parse_score_detects_hungry_and_thirsty():
    text = (
        "You have 34(37) hit, 100(100) mana and 86(87) movement points.\n"
        "You are standing.\n"
        "You are hungry.\n"
        "You are thirsty.\n"
    )
    stats = PlayerStats.parse_score(text)
    assert stats["hungry"] is True
    assert stats["thirsty"] is True


def test_parse_score_not_hungry_or_thirsty_when_lines_absent():
    text = "You have 37(37) hit, 100(100) mana and 87(87) movement points.\n"
    stats = PlayerStats.parse_score(text)
    assert stats["hungry"] is False
    assert stats["thirsty"] is False


def test_parse_score_handles_damaged_player():
    text = "You have 7(20) hit, 40(100) mana and 85(85) movement points.\n"
    stats = PlayerStats.parse_score(text)
    assert stats["hp"] == 7
    assert stats["max_hp"] == 20
    assert stats["mana"] == 40


def test_parse_score_returns_none_for_unrelated_text():
    assert PlayerStats.parse_score("You are carrying nothing.") is None


def test_parse_score_returns_none_for_empty_string():
    assert PlayerStats.parse_score("") is None
