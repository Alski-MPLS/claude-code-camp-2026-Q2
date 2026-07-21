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


from boukensha.agent import Agent
from boukensha.context import Context
from boukensha.registry import Registry
from boukensha.tasks.player import Player


def _make_agent(responses, max_iterations=25, tools_side_effect=None):
    """Build an Agent wired to a sequence of mock parsed responses."""
    ctx = Context(task=Player, system="sys")
    registry = Registry(ctx)

    mock_builder = MagicMock()
    mock_builder.parse_response.side_effect = responses
    mock_builder.to_api_payload.return_value = {}
    mock_builder.backend = None

    mock_client = MagicMock()
    mock_client.call.return_value = {}

    if tools_side_effect:
        registry.tool("echo", description="echo", parameters={"msg": {"type": "string"}}, block=tools_side_effect)

    ctx.add_message("user", "hello")
    return Agent(
        context=ctx,
        registry=registry,
        builder=mock_builder,
        client=mock_client,
        max_iterations=max_iterations,
    ), mock_client, mock_builder


def test_agent_returns_text_on_end_turn():
    responses = [{"stop_reason": "end_turn", "content": [{"type": "text", "text": "Done!"}]}]
    agent, _, _ = _make_agent(responses)
    result = agent.run()
    assert result == "Done!"


def test_agent_calls_tool_then_ends():
    tool_called = []

    def echo(msg):
        tool_called.append(msg)
        return f"echo:{msg}"

    responses = [
        {
            "stop_reason": "tool_use",
            "content": [{"type": "tool_use", "id": "tu_1", "name": "echo", "input": {"msg": "hi"}}],
        },
        {"stop_reason": "end_turn", "content": [{"type": "text", "text": "All done"}]},
    ]
    ctx = Context(task=Player, system="sys")
    registry = Registry(ctx)
    registry.tool("echo", description="echo", parameters={"msg": {"type": "string"}}, block=echo)

    mock_builder = MagicMock()
    mock_builder.parse_response.side_effect = responses
    mock_builder.to_api_payload.return_value = {}
    mock_builder.backend = None
    mock_client = MagicMock()
    mock_client.call.return_value = {}

    ctx.add_message("user", "hello")
    agent = Agent(context=ctx, registry=registry, builder=mock_builder, client=mock_client)
    result = agent.run()

    assert result == "All done"
    assert tool_called == ["hi"]
    # assistant message stored before tool_result, and final assistant reply after tool_result
    roles = [m.role for m in ctx.messages]
    assert roles == ["user", "assistant", "tool_result", "assistant"]


def test_agent_wraps_up_at_max_iterations():
    # All responses are tool_use so the agent would loop forever without the ceiling
    tool_response = {
        "stop_reason": "tool_use",
        "content": [{"type": "tool_use", "id": "tu_1", "name": "noop", "input": {}}],
    }
    wrap_up_response = {"stop_reason": "end_turn", "content": [{"type": "text", "text": "Wrapping up"}]}

    ctx = Context(task=Player, system="sys")
    registry = Registry(ctx)
    registry.tool("noop", description="noop", parameters={}, block=lambda: "ok")

    mock_builder = MagicMock()
    # First 2 calls return tool_use, the wrap-up call returns end_turn
    mock_builder.parse_response.side_effect = [tool_response, tool_response, wrap_up_response]
    mock_builder.to_api_payload.return_value = {}
    mock_builder.backend = None
    mock_client = MagicMock()
    mock_client.call.return_value = {}

    ctx.add_message("user", "go")
    agent = Agent(context=ctx, registry=registry, builder=mock_builder, client=mock_client, max_iterations=2)
    result = agent.run()

    assert result == "Wrapping up"
    # wrap-up call must pass tools=[]
    wrap_up_call = mock_client.call.call_args_list[-1]
    assert wrap_up_call.kwargs.get("tools") == []


def test_agent_exports_from_top_level():
    import boukensha
    assert hasattr(boukensha, "Agent")
    assert hasattr(boukensha, "LoopError")


# --- OllamaCloud parse_response ---

def test_ollama_cloud_parse_response_end_turn():
    backend = OllamaCloud(api_key="test_key", model="gemma4:31b-cloud")
    raw = {"message": {"role": "assistant", "content": "Hello", "tool_calls": []}}
    result = backend.parse_response(raw)
    assert result["stop_reason"] == "end_turn"
    assert result["content"] == [{"type": "text", "text": "Hello"}]


def test_ollama_cloud_parse_response_tool_use():
    backend = OllamaCloud(api_key="test_key", model="gemma4:31b-cloud")
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


# -- Logger integration tests ------------------------------------------------

import tempfile
from pathlib import Path
import json as _json

from boukensha.logger import Logger


def _make_agent_with_logger(responses, tmp_dir, max_iterations=25):
    """Build an Agent with a real Logger writing to tmp_dir."""
    from unittest.mock import MagicMock
    from boukensha.agent import Agent
    from boukensha.context import Context
    from boukensha.registry import Registry
    from boukensha.tasks.player import Player

    ctx = Context(task=Player, system="sys")
    registry = Registry(ctx)

    mock_builder = MagicMock()
    mock_builder.parse_response.side_effect = responses
    mock_builder.to_api_payload.return_value = {}
    mock_builder.backend = None

    mock_client = MagicMock()
    mock_client.call.return_value = {}

    ctx.add_message("user", "hello")
    logger = Logger(dir=tmp_dir)
    agent = Agent(
        context=ctx,
        registry=registry,
        builder=mock_builder,
        client=mock_client,
        max_iterations=max_iterations,
        logger=logger,
    )
    return agent, logger


def _read_phases(path: str) -> list[str]:
    return [_json.loads(l)["phase"] for l in Path(path).read_text().splitlines() if l.strip()]


def test_logger_receives_iteration_events():
    responses = [{"stop_reason": "end_turn", "content": [{"type": "text", "text": "Done"}]}]
    with tempfile.TemporaryDirectory() as d:
        agent, logger = _make_agent_with_logger(responses, d)
        agent.run()
        logger.close()
        phases = _read_phases(logger.path)
        assert "session_start" in phases
        assert "iteration" in phases
        assert "prompt" in phases
        assert "response" in phases
        assert "turn_end" in phases


def test_logger_records_tool_call_and_result():
    from unittest.mock import MagicMock
    from boukensha.agent import Agent
    from boukensha.context import Context
    from boukensha.registry import Registry
    from boukensha.tasks.player import Player

    tool_responses = [
        {
            "stop_reason": "tool_use",
            "content": [{"type": "tool_use", "id": "tu_1", "name": "echo", "input": {"msg": "hi"}}],
        },
        {"stop_reason": "end_turn", "content": [{"type": "text", "text": "Done"}]},
    ]

    ctx = Context(task=Player, system="sys")
    registry = Registry(ctx)
    registry.tool("echo", description="echo", parameters={"msg": {"type": "string"}}, block=lambda msg: f"echo:{msg}")

    mock_builder = MagicMock()
    mock_builder.parse_response.side_effect = tool_responses
    mock_builder.to_api_payload.return_value = {}
    mock_builder.backend = None

    mock_client = MagicMock()
    mock_client.call.return_value = {}
    ctx.add_message("user", "hello")

    with tempfile.TemporaryDirectory() as d:
        logger = Logger(dir=d)
        agent = Agent(
            context=ctx,
            registry=registry,
            builder=mock_builder,
            client=mock_client,
            logger=logger,
        )
        agent.run()
        logger.close()
        phases = _read_phases(logger.path)
        assert "tool_call" in phases
        assert "tool_result" in phases


def test_agent_works_without_logger():
    """Passing no logger= must not raise."""
    from unittest.mock import MagicMock
    from boukensha.agent import Agent
    from boukensha.context import Context
    from boukensha.registry import Registry
    from boukensha.tasks.player import Player

    ctx = Context(task=Player, system="sys")
    registry = Registry(ctx)
    mock_builder = MagicMock()
    mock_builder.parse_response.return_value = {"stop_reason": "end_turn", "content": [{"type": "text", "text": "ok"}]}
    mock_builder.to_api_payload.return_value = {}
    mock_builder.backend = None
    mock_client = MagicMock()
    mock_client.call.return_value = {}
    ctx.add_message("user", "hi")

    agent = Agent(context=ctx, registry=registry, builder=mock_builder, client=mock_client)
    result = agent.run()
    assert result == "ok"


def test_prompt_builder_exposes_backend():
    from boukensha.backends.anthropic import Anthropic
    from boukensha.context import Context
    from boukensha.prompt_builder import PromptBuilder
    from boukensha.tasks.player import Player

    ctx = Context(task=Player, system="sys")
    backend = Anthropic(api_key="k", model="claude-haiku-4-5")
    builder = PromptBuilder(ctx, backend)
    assert builder.backend is backend


def test_logger_limit_reached_event():
    tool_response = {
        "stop_reason": "tool_use",
        "content": [{"type": "tool_use", "id": "tu_1", "name": "noop", "input": {}}],
    }
    wrap_up = {"stop_reason": "end_turn", "content": [{"type": "text", "text": "Wrapping up"}]}

    from unittest.mock import MagicMock
    from boukensha.agent import Agent
    from boukensha.context import Context
    from boukensha.registry import Registry
    from boukensha.tasks.player import Player

    ctx = Context(task=Player, system="sys")
    registry = Registry(ctx)
    registry.tool("noop", description="noop", parameters={}, block=lambda: "ok")

    mock_builder = MagicMock()
    mock_builder.parse_response.side_effect = [tool_response, tool_response, wrap_up]
    mock_builder.to_api_payload.return_value = {}
    mock_builder.backend = None
    mock_client = MagicMock()
    mock_client.call.return_value = {}
    ctx.add_message("user", "go")

    with tempfile.TemporaryDirectory() as d:
        logger = Logger(dir=d)
        agent = Agent(
            context=ctx,
            registry=registry,
            builder=mock_builder,
            client=mock_client,
            max_iterations=2,
            logger=logger,
        )
        agent.run()
        logger.close()
        phases = _read_phases(logger.path)
        assert "limit_reached" in phases
        assert "turn_end" in phases


def test_agent_run_adds_assistant_reply_to_context():
    """Final reply must be stored in context so subsequent REPL turns see it."""
    responses = [{"stop_reason": "end_turn", "content": [{"type": "text", "text": "Done!"}]}]
    agent, _, _ = _make_agent(responses)
    agent.run()
    last_msg = agent._context.messages[-1]
    assert last_msg.role == "assistant"
    assert last_msg.content == "Done!"


def test_agent_wrap_up_adds_assistant_reply_to_context():
    """Wrap-up reply must also be stored in context."""
    tool_response = {
        "stop_reason": "tool_use",
        "content": [{"type": "tool_use", "id": "tu_1", "name": "noop", "input": {}}],
    }
    wrap_up_response = {"stop_reason": "end_turn", "content": [{"type": "text", "text": "Wrapping up"}]}

    from unittest.mock import MagicMock
    from boukensha.agent import Agent
    from boukensha.context import Context
    from boukensha.registry import Registry
    from boukensha.tasks.player import Player

    ctx = Context(task=Player, system="sys")
    registry = Registry(ctx)
    registry.tool("noop", description="noop", parameters={}, block=lambda: "ok")

    mock_builder = MagicMock()
    mock_builder.parse_response.side_effect = [tool_response, wrap_up_response]
    mock_builder.to_api_payload.return_value = {}
    mock_builder.backend = None
    mock_client = MagicMock()
    mock_client.call.return_value = {}
    ctx.add_message("user", "go")

    agent = Agent(
        context=ctx,
        registry=registry,
        builder=mock_builder,
        client=mock_client,
        max_iterations=1,
    )
    agent.run()
    roles = [m.role for m in ctx.messages]
    assert roles[-1] == "assistant"
    assert ctx.messages[-1].content == "Wrapping up"


# ── Step 12: token tracking and compaction tests ─────────────────────────────

from boukensha.context import Context
from boukensha.registry import Registry
from boukensha.tasks.player import Player


def _make_agent_12(responses, max_iterations=25, max_turn_tokens=None, context_window=200_000):
    """Build Agent with token-tracking context and mock builder/client."""
    from unittest.mock import MagicMock
    from boukensha.agent import Agent

    ctx = Context(task=Player, system="sys", context_window=context_window)
    registry = Registry(ctx)

    mock_builder = MagicMock()
    mock_builder.parse_response.side_effect = responses
    mock_builder.to_api_payload.return_value = {}
    mock_builder.backend = None

    mock_client = MagicMock()
    # Each call returns a response dict with usage
    mock_client.call.return_value = {
        "usage": {"input_tokens": 1000, "output_tokens": 100}
    }
    # Override for each response when usage varies
    mock_builder.parse_response.side_effect = responses

    ctx.add_message("user", "hello")
    agent = Agent(
        context=ctx,
        registry=registry,
        builder=mock_builder,
        client=mock_client,
        max_iterations=max_iterations,
        max_turn_tokens=max_turn_tokens,
    )
    return agent, ctx, mock_client, mock_builder


def test_agent_records_usage_in_context():
    responses = [{"stop_reason": "end_turn", "content": [{"type": "text", "text": "Done"}]}]
    agent, ctx, mock_client, _ = _make_agent_12(responses)
    mock_client.call.return_value = {"usage": {"input_tokens": 5000, "output_tokens": 200}}
    agent.run()
    # current_tokens updated from input_tokens of last API call
    assert ctx.current_tokens == 5000


def test_agent_resets_turn_tokens_at_start():
    responses = [{"stop_reason": "end_turn", "content": [{"type": "text", "text": "Done"}]}]
    agent, ctx, mock_client, _ = _make_agent_12(responses)
    # Pre-load stale turn_tokens
    ctx.add_turn_tokens(99_999, 0)
    mock_client.call.return_value = {"usage": {"input_tokens": 100, "output_tokens": 50}}
    agent.run()
    # After run, turn_tokens = 100+50 = 150 (stale value was reset)
    assert ctx.turn_tokens == 150


def test_agent_stops_at_max_turn_tokens():
    """Agent should trigger wrap-up when turn tokens exceed max_turn_tokens."""
    from unittest.mock import MagicMock
    from boukensha.agent import Agent

    ctx = Context(task=Player, system="sys", context_window=200_000)
    registry = Registry(ctx)
    registry.tool("noop", description="noop", parameters={}, block=lambda: "ok")

    tool_response = {
        "stop_reason": "tool_use",
        "content": [{"type": "tool_use", "id": "tu_1", "name": "noop", "input": {}}],
    }
    wrap_up_response = {"stop_reason": "end_turn", "content": [{"type": "text", "text": "Token limit hit"}]}

    mock_builder = MagicMock()
    mock_builder.parse_response.side_effect = [tool_response, wrap_up_response]
    mock_builder.to_api_payload.return_value = {}
    mock_builder.backend = None

    mock_client = MagicMock()
    # Each call consumes 600 tokens; max_turn_tokens=500 so first call already exceeds it
    mock_client.call.return_value = {"usage": {"input_tokens": 400, "output_tokens": 200}}

    ctx.add_message("user", "go")
    agent = Agent(
        context=ctx,
        registry=registry,
        builder=mock_builder,
        client=mock_client,
        max_iterations=25,
        max_turn_tokens=500,
    )
    result = agent.run()
    assert result == "Token limit hit"


def test_agent_compact_if_needed_runs_before_loop():
    """When context is at threshold, compact_messages is called before the first iteration."""
    import tempfile
    from unittest.mock import MagicMock
    from boukensha.agent import Agent
    from boukensha.logger import Logger

    ctx = Context(task=Player, system="sys", context_window=200_000)
    # Fill context to 90% — above 85% threshold
    ctx.update_tokens(180_000)
    for i in range(10):
        ctx.add_message("user", f"msg {i}")

    registry = Registry(ctx)
    mock_builder = MagicMock()
    mock_builder.parse_response.return_value = {
        "stop_reason": "end_turn",
        "content": [{"type": "text", "text": "ok"}],
    }
    mock_builder.to_api_payload.return_value = {}
    mock_builder.backend = None
    mock_client = MagicMock()
    mock_client.call.return_value = {"usage": {"input_tokens": 0, "output_tokens": 0}}

    msg_count_before = len(ctx.messages)

    with tempfile.TemporaryDirectory() as d:
        logger = Logger(dir=d)
        agent = Agent(
            context=ctx,
            registry=registry,
            builder=mock_builder,
            client=mock_client,
            logger=logger,
        )
        agent.run()
        logger.close()
        import json
        from pathlib import Path
        lines = [json.loads(l) for l in Path(logger.path).read_text().splitlines() if l.strip()]
        phases = [l["phase"] for l in lines]
        assert "compaction" in phases
    # Messages were reduced
    assert len(ctx.messages) < msg_count_before


def test_agent_reasoning_blocks_logged():
    """Reasoning blocks in the response content are forwarded to logger.reasoning()."""
    import tempfile
    from unittest.mock import MagicMock, call
    from boukensha.agent import Agent
    from boukensha.logger import Logger

    ctx = Context(task=Player, system="sys")
    registry = Registry(ctx)

    reasoning_block = {"type": "reasoning", "text": "Let me think about this.", "redacted": False}
    text_block = {"type": "text", "text": "Done"}

    mock_builder = MagicMock()
    mock_builder.parse_response.return_value = {
        "stop_reason": "end_turn",
        "content": [reasoning_block, text_block],
    }
    mock_builder.to_api_payload.return_value = {}
    mock_builder.backend = None
    mock_client = MagicMock()
    mock_client.call.return_value = {}

    ctx.add_message("user", "hello")
    with tempfile.TemporaryDirectory() as d:
        logger = Logger(dir=d)
        agent = Agent(
            context=ctx,
            registry=registry,
            builder=mock_builder,
            client=mock_client,
            logger=logger,
        )
        agent.run()
        logger.close()
        import json
        from pathlib import Path
        lines = [json.loads(l) for l in Path(logger.path).read_text().splitlines() if l.strip()]
        reasoning_events = [l for l in lines if l["phase"] == "reasoning"]
        assert len(reasoning_events) == 1
        assert reasoning_events[0]["text"] == "Let me think about this."
        assert reasoning_events[0]["redacted"] is False
