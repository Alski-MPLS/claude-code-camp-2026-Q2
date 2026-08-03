"""Tests for boukensha.backends.Anthropic — prompt-caching payload shape."""
from __future__ import annotations

from boukensha.backends.anthropic import Anthropic
from boukensha.context import Context
from boukensha.message import Message
from boukensha.tasks.player import Player
from boukensha.tool import Tool


def _make_backend() -> Anthropic:
    return Anthropic(api_key="test-key", model="claude-haiku-4-5")


def _make_context(system: str | None = "You are a MUD agent.") -> Context:
    return Context(task=Player, system=system)


def test_to_payload_caches_the_system_prompt():
    backend = _make_backend()
    ctx = _make_context(system="You are a MUD agent.")

    payload = backend.to_payload(ctx, tools=[])

    assert payload["system"] == [
        {"type": "text", "text": "You are a MUD agent.", "cache_control": {"type": "ephemeral"}}
    ]


def test_to_payload_leaves_empty_system_untouched():
    backend = _make_backend()
    ctx = _make_context(system=None)

    payload = backend.to_payload(ctx, tools=[])

    assert payload["system"] is None


def test_to_tools_marks_only_the_last_tool_cacheable():
    backend = _make_backend()
    ctx = _make_context()
    ctx.register_tool(Tool(name="look", description="Look around.", parameters={}, block=lambda: None))
    ctx.register_tool(Tool(name="move", description="Move a direction.", parameters={}, block=lambda: None))

    tools = backend.to_tools(ctx.tools)

    assert "cache_control" not in tools[0]
    assert tools[1]["cache_control"] == {"type": "ephemeral"}


def test_to_tools_handles_empty_registry():
    backend = _make_backend()
    assert backend.to_tools({}) == []


def test_to_messages_caches_only_the_last_message_plain_text():
    backend = _make_backend()
    messages = [
        Message(role="user", content="first turn"),
        Message(role="assistant", content="ack"),
        Message(role="user", content="latest turn"),
    ]

    result = backend.to_messages(messages)

    assert result[0]["content"] == "first turn"
    assert result[1]["content"] == "ack"
    assert result[2]["content"] == [
        {"type": "text", "text": "latest turn", "cache_control": {"type": "ephemeral"}}
    ]


def test_to_messages_caches_last_block_of_a_tool_result_message():
    backend = _make_backend()
    messages = [
        Message(role="user", content="explore"),
        Message(role="tool_result", content="You see a corpse.", tool_use_id="tool_123"),
    ]

    result = backend.to_messages(messages)

    assert result[0]["content"] == "explore"
    assert result[1]["content"] == [
        {
            "type": "tool_result",
            "tool_use_id": "tool_123",
            "content": "You see a corpse.",
            "cache_control": {"type": "ephemeral"},
        }
    ]


def test_to_messages_caches_last_block_when_content_is_already_a_list():
    """Assistant turns carry raw API content blocks (e.g. tool_use) as a
    list — the cache breakpoint must land on the last block, not replace
    the whole list or clobber the earlier blocks."""
    backend = _make_backend()
    messages = [
        Message(
            role="assistant",
            content=[
                {"type": "text", "text": "Let me look."},
                {"type": "tool_use", "id": "t1", "name": "look", "input": {}},
            ],
        ),
    ]

    result = backend.to_messages(messages)

    assert result[0]["content"][0] == {"type": "text", "text": "Let me look."}
    assert result[0]["content"][1] == {
        "type": "tool_use", "id": "t1", "name": "look", "input": {},
        "cache_control": {"type": "ephemeral"},
    }


def test_to_messages_handles_empty_history():
    backend = _make_backend()
    assert backend.to_messages([]) == []


def test_estimate_cost_with_no_cache_activity_matches_pre_caching_behavior():
    backend = _make_backend()  # claude-haiku-4-5: $1/MTok in, $5/MTok out

    cost = backend.estimate_cost(input_tokens=1000, output_tokens=1000)

    assert cost == (1000 * 1.0 + 1000 * 5.0) / 1_000_000.0


def test_estimate_cost_bills_cache_write_at_1_25x_input_price():
    backend = _make_backend()

    cost = backend.estimate_cost(
        input_tokens=0, output_tokens=0, cache_creation_tokens=1_000_000
    )

    assert cost == 1.25  # 1,000,000 tokens * $1/MTok * 1.25


def test_estimate_cost_bills_cache_read_at_one_tenth_input_price():
    backend = _make_backend()

    cost = backend.estimate_cost(
        input_tokens=0, output_tokens=0, cache_read_tokens=1_000_000
    )

    assert cost == 0.1  # 1,000,000 tokens * $1/MTok * 0.1


def test_estimate_cost_combines_all_four_token_buckets():
    backend = _make_backend()

    cost = backend.estimate_cost(
        input_tokens=7,
        output_tokens=69,
        cache_creation_tokens=402,
        cache_read_tokens=9224,
    )

    expected = (7 * 1.0 + 69 * 5.0 + 402 * 1.0 * 1.25 + 9224 * 1.0 * 0.1) / 1_000_000.0
    assert cost == expected
