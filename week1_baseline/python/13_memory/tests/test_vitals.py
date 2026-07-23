"""Tests for VitalsTracker."""
from __future__ import annotations
import pytest
from boukensha.tools.vitals import PlayerVitals, VitalsTracker


def test_initial_state_is_fine():
    vt = VitalsTracker()
    assert vt.hint is None


def test_detects_thirst_phrase():
    vt = VitalsTracker()
    vt.update("You are thirsty.\n> ")
    assert vt._vitals.is_thirsty is True


def test_detects_hunger_phrase():
    vt = VitalsTracker()
    vt.update("You are hungry.\n> ")
    assert vt._vitals.is_hungry is True


def test_clears_thirst_on_drink_response():
    vt = VitalsTracker()
    vt.update("You are thirsty.\n> ")
    vt.update("You drink the water.  You don't feel thirsty anymore.\n> ")
    assert vt._vitals.is_thirsty is False


def test_clears_hunger_on_eat_response():
    vt = VitalsTracker()
    vt.update("You are hungry.\n> ")
    vt.update("You eat the bread.  You are full.\n> ")
    assert vt._vitals.is_hungry is False


def test_parses_hp_from_score():
    vt = VitalsTracker()
    score_response = "Hit Points: 45/120\nMana: 80/100\n> "
    vt.update(score_response)
    assert vt._vitals.hp_current == 45
    assert vt._vitals.hp_max == 120


def test_parses_hp_colon_format():
    vt = VitalsTracker()
    vt.update("HP: 10/200  Mana: 50/100\n> ")
    assert vt._vitals.hp_current == 10
    assert vt._vitals.hp_max == 200


def test_hint_none_when_healthy():
    vt = VitalsTracker()
    vt.update("HP: 100/100  Mana: 100/100\n> ")
    assert vt.hint is None


def test_hint_low_hp():
    vt = VitalsTracker()
    vt.update("HP: 40/100  Mana: 50/100\n> ")
    assert vt.hint is not None
    assert "can_rest" in vt.hint
    assert "40%" in vt.hint


def test_hint_thirst():
    vt = VitalsTracker()
    vt.update("You are thirsty.\n> ")
    assert vt.hint is not None
    assert "can_drink" in vt.hint


def test_hint_hunger():
    vt = VitalsTracker()
    vt.update("You are hungry.\n> ")
    assert vt.hint is not None
    assert "can_eat" in vt.hint


def test_hint_hp_takes_priority_over_thirst():
    vt = VitalsTracker()
    vt.update("You are thirsty.\n> ")
    vt.update("HP: 30/100\n> ")
    assert "can_rest" in vt.hint


def test_hp_fraction_none_when_no_data():
    v = PlayerVitals()
    assert v.hp_fraction is None


def test_hp_fraction_calculated():
    v = PlayerVitals(hp_current=50, hp_max=100)
    assert v.hp_fraction == 0.5
