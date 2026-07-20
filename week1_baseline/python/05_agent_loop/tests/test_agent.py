from __future__ import annotations

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


from boukensha.backends.anthropic import Anthropic
from boukensha.backends.gemini import Gemini
from boukensha.backends.ollama import Ollama
from boukensha.backends.ollama_cloud import OllamaCloud
from boukensha.backends.openai import OpenAI


# --- Anthropic parse_response ---

def test_anthropic_parse_response_end_turn():
    backend = Anthropic(api_key="k", model="claude-haiku-4-5")
    raw = {"stop_reason": "end_turn", "content": [{"type": "text", "text": "Hello"}]}
    result = backend.parse_response(raw)
    assert result["stop_reason"] == "end_turn"
    assert result["content"] == [{"type": "text", "text": "Hello"}]


def test_anthropic_parse_response_tool_use():
    backend = Anthropic(api_key="k", model="claude-haiku-4-5")
    raw = {
        "stop_reason": "tool_use",
        "content": [
            {"type": "tool_use", "id": "tu_1", "name": "read_file", "input": {"path": "f.txt"}}
        ],
    }
    result = backend.parse_response(raw)
    assert result["stop_reason"] == "tool_use"
    assert result["content"][0]["type"] == "tool_use"
    assert result["content"][0]["id"] == "tu_1"


# --- OpenAI parse_response ---

def test_openai_parse_response_end_turn():
    backend = OpenAI(api_key="k", model="gpt-5.4")
    raw = {"choices": [{"message": {"role": "assistant", "content": "Hello", "tool_calls": None}}]}
    result = backend.parse_response(raw)
    assert result["stop_reason"] == "end_turn"
    assert result["content"] == [{"type": "text", "text": "Hello"}]


def test_openai_parse_response_tool_use():
    backend = OpenAI(api_key="k", model="gpt-5.4")
    raw = {
        "choices": [{
            "message": {
                "role": "assistant",
                "content": None,
                "tool_calls": [{
                    "id": "call_1",
                    "function": {"name": "read_file", "arguments": '{"path": "f.txt"}'}
                }]
            }
        }]
    }
    result = backend.parse_response(raw)
    assert result["stop_reason"] == "tool_use"
    assert result["content"][0]["type"] == "tool_use"
    assert result["content"][0]["id"] == "call_1"
    assert result["content"][0]["input"] == {"path": "f.txt"}


# --- Gemini parse_response ---

def test_gemini_parse_response_end_turn():
    backend = Gemini(api_key="k", model="gemini-2.5-flash")
    raw = {"candidates": [{"content": {"parts": [{"text": "Hello"}]}}]}
    result = backend.parse_response(raw)
    assert result["stop_reason"] == "end_turn"
    assert result["content"] == [{"type": "text", "text": "Hello"}]


def test_gemini_parse_response_tool_use():
    backend = Gemini(api_key="k", model="gemini-2.5-flash")
    raw = {
        "candidates": [{
            "content": {
                "parts": [{"functionCall": {"name": "read_file", "args": {"path": "f.txt"}}}]
            }
        }]
    }
    result = backend.parse_response(raw)
    assert result["stop_reason"] == "tool_use"
    assert result["content"][0]["type"] == "tool_use"
    assert result["content"][0]["id"] == "read_file"
    assert result["content"][0]["name"] == "read_file"
    assert result["content"][0]["input"] == {"path": "f.txt"}


# --- Ollama parse_response ---

def test_ollama_parse_response_end_turn():
    backend = Ollama(model="gemma4")
    raw = {"message": {"role": "assistant", "content": "Hello", "tool_calls": []}}
    result = backend.parse_response(raw)
    assert result["stop_reason"] == "end_turn"
    assert result["content"] == [{"type": "text", "text": "Hello"}]


def test_ollama_parse_response_tool_use():
    backend = Ollama(model="gemma4")
    raw = {
        "message": {
            "role": "assistant",
            "content": "",
            "tool_calls": [{"function": {"name": "read_file", "arguments": {"path": "f.txt"}}}]
        }
    }
    result = backend.parse_response(raw)
    assert result["stop_reason"] == "tool_use"
    assert result["content"][0]["type"] == "tool_use"
    assert result["content"][0]["id"] == "read_file"
    assert result["content"][0]["input"] == {"path": "f.txt"}


# --- to_payload tools override ---

def test_anthropic_to_payload_empty_tools_override():
    from boukensha.context import Context
    from boukensha.tasks.player import Player
    backend = Anthropic(api_key="k", model="claude-haiku-4-5")
    ctx = Context(task=Player, system="sys")
    payload = backend.to_payload(ctx, tools=[])
    assert payload["tools"] == []
