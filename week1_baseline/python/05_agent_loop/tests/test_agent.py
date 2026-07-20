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


import json
from io import BytesIO
from unittest.mock import MagicMock, patch

from boukensha.client import Client
from boukensha.errors import ApiError
from boukensha.prompt_builder import PromptBuilder


def _make_builder(url="https://api.example.com/v1/messages", payload=None):
    builder = MagicMock(spec=PromptBuilder)
    builder.url = url
    builder.headers = {"Content-Type": "application/json", "x-api-key": "test"}
    builder.to_api_payload.return_value = payload or {"model": "test", "messages": []}
    return builder


def _fake_response(body: dict):
    raw = json.dumps(body).encode()
    resp = MagicMock()
    resp.read.return_value = raw
    resp.__enter__ = lambda s: s
    resp.__exit__ = MagicMock(return_value=False)
    return resp


def test_client_call_passes_tools_none_by_default():
    builder = _make_builder()
    with patch("boukensha.client.urllib.request.urlopen", return_value=_fake_response({})):
        Client(builder).call()
    builder.to_api_payload.assert_called_once_with(max_output_tokens=1024, tools=None)


def test_client_call_passes_tools_empty_list():
    builder = _make_builder()
    with patch("boukensha.client.urllib.request.urlopen", return_value=_fake_response({})):
        Client(builder).call(tools=[])
    builder.to_api_payload.assert_called_once_with(max_output_tokens=1024, tools=[])


def test_prompt_builder_parse_response_delegates_to_backend():
    backend = MagicMock()
    backend.parse_response.return_value = {"stop_reason": "end_turn", "content": []}
    builder = PromptBuilder(MagicMock(), backend)
    result = builder.parse_response({"some": "response"})
    backend.parse_response.assert_called_once_with({"some": "response"})
    assert result == {"stop_reason": "end_turn", "content": []}
