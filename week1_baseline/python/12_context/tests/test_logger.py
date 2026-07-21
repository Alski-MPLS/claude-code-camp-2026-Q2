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


import json
import tempfile
from pathlib import Path

from boukensha.logger import Logger


def _read_lines(path: str) -> list[dict]:
    return [json.loads(line) for line in Path(path).read_text().splitlines() if line.strip()]


def test_logger_creates_file_on_init():
    with tempfile.TemporaryDirectory() as d:
        lg = Logger(dir=d)
        assert Path(lg.path).exists()
        lg.close()


def test_logger_session_start_line_written():
    with tempfile.TemporaryDirectory() as d:
        lg = Logger(dir=d)
        lg.close()
        lines = _read_lines(lg.path)
        assert lines[0]["phase"] == "session_start"
        assert "session_id" in lines[0]
        assert "at" in lines[0]


def test_logger_custom_session_id():
    with tempfile.TemporaryDirectory() as d:
        lg = Logger(dir=d, session_id="my-session")
        lg.close()
        lines = _read_lines(lg.path)
        assert lines[0]["session_id"] == "my-session"


def test_logger_snapshot_merged_into_session_start():
    with tempfile.TemporaryDirectory() as d:
        lg = Logger(dir=d, snapshot={"model": "claude-haiku-4-5"})
        lg.close()
        lines = _read_lines(lg.path)
        assert lines[0]["model"] == "claude-haiku-4-5"


def test_logger_explicit_log_path():
    with tempfile.TemporaryDirectory() as d:
        log_path = str(Path(d) / "custom.jsonl")
        lg = Logger(log=log_path)
        lg.close()
        assert Path(log_path).exists()


def test_logger_iteration():
    with tempfile.TemporaryDirectory() as d:
        lg = Logger(dir=d)
        lg.iteration(n=1, max=25)
        lg.close()
        lines = _read_lines(lg.path)
        iter_line = next(l for l in lines if l["phase"] == "iteration")
        assert iter_line["n"] == 1
        assert iter_line["max"] == 25


def test_logger_limit_reached():
    with tempfile.TemporaryDirectory() as d:
        lg = Logger(dir=d)
        lg.limit_reached(kind="max_iterations", n=25, max=25)
        lg.close()
        lines = _read_lines(lg.path)
        lr = next(l for l in lines if l["phase"] == "limit_reached")
        assert lr["kind"] == "max_iterations"
        assert lr["n"] == 25


def test_logger_turn_end():
    with tempfile.TemporaryDirectory() as d:
        lg = Logger(dir=d)
        lg.turn_end(reason="completed", iterations=3)
        lg.close()
        lines = _read_lines(lg.path)
        te = next(l for l in lines if l["phase"] == "turn_end")
        assert te["reason"] == "completed"
        assert te["iterations"] == 3


def test_logger_prompt():
    from boukensha.message import Message
    with tempfile.TemporaryDirectory() as d:
        lg = Logger(dir=d)
        msgs = [Message(role="user", content="hello")]
        tools = {"read_file": object()}
        lg.prompt(messages=msgs, tools=tools)
        lg.close()
        lines = _read_lines(lg.path)
        p = next(l for l in lines if l["phase"] == "prompt")
        assert p["message_count"] == 1
        assert p["tool_count"] == 1
        assert p["messages"][0]["role"] == "user"
        assert p["tools"] == ["read_file"]


def test_logger_tool_call():
    with tempfile.TemporaryDirectory() as d:
        lg = Logger(dir=d)
        lg.tool_call(name="read_file", args={"path": "f.txt"})
        lg.close()
        lines = _read_lines(lg.path)
        tc = next(l for l in lines if l["phase"] == "tool_call")
        assert tc["name"] == "read_file"
        assert tc["args"] == {"path": "f.txt"}


def test_logger_tool_result_ok():
    with tempfile.TemporaryDirectory() as d:
        lg = Logger(dir=d)
        lg.tool_result(name="read_file", result="contents", ok=True)
        lg.close()
        lines = _read_lines(lg.path)
        tr = next(l for l in lines if l["phase"] == "tool_result")
        assert tr["ok"] is True
        assert tr["result"] == "contents"


def test_logger_tool_result_error():
    with tempfile.TemporaryDirectory() as d:
        lg = Logger(dir=d)
        lg.tool_result(name="read_file", result="ERROR: FileNotFoundError: f.txt", ok=False, error="f.txt")
        lg.close()
        lines = _read_lines(lg.path)
        tr = next(l for l in lines if l["phase"] == "tool_result")
        assert tr["ok"] is False
        assert tr["error"] == "f.txt"


def test_logger_response_basic():
    with tempfile.TemporaryDirectory() as d:
        lg = Logger(dir=d)
        lg.response(text="Done!", usage=None, stop_reason="end_turn")
        lg.close()
        lines = _read_lines(lg.path)
        r = next(l for l in lines if l["phase"] == "response")
        assert r["text"] == "Done!"
        assert r["stop_reason"] == "end_turn"


def test_logger_response_with_anthropic_usage():
    from boukensha.backends.anthropic import Anthropic
    backend = Anthropic(api_key="k", model="claude-haiku-4-5")
    with tempfile.TemporaryDirectory() as d:
        lg = Logger(dir=d)
        lg.response(
            text="hi",
            usage={"input_tokens": 100, "output_tokens": 50},
            stop_reason="end_turn",
            backend=backend,
        )
        lg.close()
        lines = _read_lines(lg.path)
        r = next(l for l in lines if l["phase"] == "response")
        assert r["input_tokens"] == 100
        assert r["output_tokens"] == 50
        assert r["provider"] == "anthropic"
        assert r["model"] == "claude-haiku-4-5"
        assert isinstance(r["cost_usd"], float)


def test_logger_raw_no_op_when_debug_false():
    import boukensha
    boukensha._debug = False
    with tempfile.TemporaryDirectory() as d:
        lg = Logger(dir=d)
        lg.raw(data={"some": "data"})
        lg.close()
        lines = _read_lines(lg.path)
        assert not any(l["phase"] == "raw" for l in lines)


def test_logger_raw_written_when_debug_true():
    import boukensha
    boukensha._debug = False
    boukensha.enable_debug()
    with tempfile.TemporaryDirectory() as d:
        lg = Logger(dir=d)
        lg.raw(data={"some": "data"})
        lg.close()
        lines = _read_lines(lg.path)
        raw_line = next((l for l in lines if l["phase"] == "raw"), None)
        assert raw_line is not None
        assert raw_line["data"] == {"some": "data"}
    boukensha._debug = False  # cleanup


def test_logger_session_id_format():
    import re
    with tempfile.TemporaryDirectory() as d:
        lg = Logger(dir=d)
        lg.close()
        # Format: YYYYMMDDTHHMMSSZ-<8 hex chars>
        assert re.match(r"^\d{8}T\d{6}Z-[0-9a-f]{8}$", lg.session_id)


def test_logger_turn_event():
    with tempfile.TemporaryDirectory() as d:
        lg = Logger(dir=d)
        lg.turn(n=1)
        lg.turn(n=2)
        lg.close()
        lines = _read_lines(lg.path)
        turn_lines = [l for l in lines if l["phase"] == "turn"]
        assert len(turn_lines) == 2
        assert turn_lines[0]["n"] == 1
        assert turn_lines[1]["n"] == 2


def test_logger_subscribe_receives_events():
    received = []
    with tempfile.TemporaryDirectory() as d:
        lg = Logger(dir=d)
        lg.subscribe(received.append)
        lg.tool_call(name="read_file", args={"path": "f.txt"})
        lg.close()
    phases = [e["phase"] for e in received]
    assert "tool_call" in phases


def test_logger_subscribe_multiple_callbacks():
    received_a = []
    received_b = []
    with tempfile.TemporaryDirectory() as d:
        lg = Logger(dir=d)
        lg.subscribe(received_a.append)
        lg.subscribe(received_b.append)
        lg.iteration(n=1, max=10)
        lg.close()
    assert any(e["phase"] == "iteration" for e in received_a)
    assert any(e["phase"] == "iteration" for e in received_b)


def test_logger_subscribe_receives_session_start():
    received = []
    with tempfile.TemporaryDirectory() as d:
        lg = Logger(dir=d)
        lg.subscribe(received.append)
        lg.close()
    # session_start is written in __init__ before subscribe is called,
    # but close() triggers no extra write — received should be empty here
    assert received == []


def test_logger_subscribe_event_has_session_id():
    received = []
    with tempfile.TemporaryDirectory() as d:
        lg = Logger(dir=d)
        lg.subscribe(received.append)
        lg.turn(n=1)
        lg.close()
    turn_events = [e for e in received if e["phase"] == "turn"]
    assert len(turn_events) == 1
    assert "session_id" in turn_events[0]
