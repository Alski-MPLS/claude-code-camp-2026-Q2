from __future__ import annotations

import boukensha


def test_debug_flag_starts_false():
    # Reset in case another test mutated it
    boukensha._debug = False
    assert boukensha.debug() is False


def test_enable_debug_sets_flag():
    boukensha._debug = False
    boukensha.enable_debug()
    assert boukensha.debug() is True
    boukensha._debug = False  # cleanup
