from boukensha.errors import ApiError, LoopError, UnknownToolError, UnsupportedModelError
from boukensha.tasks.player import Player


def test_loop_error_is_exception():
    err = LoopError("ran away")
    assert isinstance(err, Exception)
    assert str(err) == "ran away"


def test_existing_errors_still_present():
    assert issubclass(ApiError, Exception)
    assert issubclass(UnknownToolError, Exception)
    assert issubclass(UnsupportedModelError, Exception)


def test_player_max_iterations_default():
    assert Player.max_iterations({}) == 25


def test_player_max_iterations_from_settings():
    assert Player.max_iterations({"max_iterations": 10}) == 10


def test_player_max_output_tokens_default():
    assert Player.max_output_tokens({}) == 1024


def test_player_max_output_tokens_from_settings():
    assert Player.max_output_tokens({"max_output_tokens": 512}) == 512


def test_message_content_accepts_list():
    from boukensha.message import Message
    blocks = [{"type": "text", "text": "hi"}, {"type": "tool_use", "id": "x", "name": "f", "input": {}}]
    msg = Message(role="assistant", content=blocks)
    assert msg.content == blocks
