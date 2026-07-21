# Python MUD Tools Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add a `boukensha.tools.Mud` class to Python steps 10, 11, and 12 so the agent has the same 28 MUD gameplay tools that the Ruby track has had since step 10.

**Architecture:** Each step is a self-contained snapshot — the same `tools/mud.py` file (plus matching changes to `tools/__init__.py`, the top-level `__init__.py`, and `boukensha_loader.py`) is written independently into each step folder. A `MudSession` class wraps a raw TCP socket with a background reader thread and CircleMUD login dance; `Mud.register()` closes over a single session and registers 28 tools against the registry. Config auto-wiring reads `mud: { host, port, username, password }` from `settings.yaml` (already parsed by `Config`) when `mud=None` is passed to `run()`/`repl()`.

**Tech Stack:** Python 3.11+, stdlib only (`socket`, `threading`, `re`) for the session; `pytest` for tests; `uv` for package management.

## Global Constraints

- Python ≥ 3.11 (all steps already require this)
- stdlib-only for the MUD session — no new dependencies added to any `pyproject.toml`
- No new dependencies in `pyproject.toml` (stdlib `socket`/`threading`/`re` used)
- Each step is a self-contained snapshot — code is duplicated, not shared between steps
- Tests must not require a live MUD server — use a mock TCP server or monkeypatching

---

## File Map

For **each** of steps 10, 11, 12 the same set of files changes. Paths shown for step 10; substitute `11_tui` / `12_context` for the other two.

| Action | Path |
|--------|------|
| Create | `week1_baseline/python/10_standard_tool_library/src/boukensha/tools/mud.py` |
| Modify | `week1_baseline/python/10_standard_tool_library/src/boukensha/tools/__init__.py` |
| Modify | `week1_baseline/python/10_standard_tool_library/src/boukensha/__init__.py` |
| Modify | `week1_baseline/python/10_standard_tool_library/src/boukensha_loader.py` |
| Create | `week1_baseline/python/10_standard_tool_library/tests/test_tools_mud.py` |

Same five files for `11_tui` and `12_context`.

---

## Task 1: `tools/mud.py` — Session + Mud.register() for step 10

**Files:**
- Create: `week1_baseline/python/10_standard_tool_library/src/boukensha/tools/mud.py`
- Create: `week1_baseline/python/10_standard_tool_library/tests/test_tools_mud.py`

**Interfaces:**
- Produces: `class MudSession` with `open()`, `close()`, `open: bool`, `send_command(cmd: str) -> None`, `read_until_prompt(timeout: float = 10.0) -> str`, `drain() -> str`, `login(name: str, password: str) -> str`
- Produces: `class Mud` with classmethod `register(registry: Registry, *, host: str = "localhost", port: int = 4000, name: str, password: str) -> None`
- The 28 registered tool names: `mud_connect`, `mud_disconnect`, `mud_status`, `look`, `examine`, `check`, `move`, `flee`, `set_position`, `track`, `attack`, `skill_strike`, `consider`, `say`, `tell`, `channel_say`, `get_item`, `drop_item`, `put_item`, `equip_item`, `consume_item`, `cast_spell`, `use_magic_item`, `shop`, `practice`, `save_character`, `send_raw`

- [ ] **Step 1: Write the failing tests**

Create `week1_baseline/python/10_standard_tool_library/tests/test_tools_mud.py`:

```python
"""Tests for boukensha.tools.Mud — all run without a live MUD server."""
from __future__ import annotations

import socket
import threading
import time
from unittest.mock import patch, MagicMock

import pytest

from boukensha.context import Context
from boukensha.registry import Registry
from boukensha.tasks.player import Player
from boukensha.tools.mud import Mud, MudSession


def _make_registry() -> Registry:
    ctx = Context(task=Player, system="sys")
    return Registry(ctx)


# ---------------------------------------------------------------------------
# MudSession unit tests (no live server — mock the socket)
# ---------------------------------------------------------------------------

def test_mud_session_open_sets_open_flag():
    session = MudSession(host="localhost", port=4000)
    mock_sock = MagicMock()
    mock_sock.recv.return_value = b""
    with patch("socket.create_connection", return_value=mock_sock):
        session.open()
    assert session.is_open


def test_mud_session_close_clears_flag():
    session = MudSession(host="localhost", port=4000)
    mock_sock = MagicMock()
    mock_sock.recv.return_value = b""
    with patch("socket.create_connection", return_value=mock_sock):
        session.open()
        session.close()
    assert not session.is_open


def test_mud_session_send_command_raises_when_closed():
    session = MudSession(host="localhost", port=4000)
    with pytest.raises(RuntimeError, match="not open"):
        session.send_command("look")


# ---------------------------------------------------------------------------
# Mud.register tool registration tests (mock session entirely)
# ---------------------------------------------------------------------------

def _registered_session(registry, session):
    """Register Mud tools against registry with a pre-built session."""
    Mud._register_with_session(registry, session, name="Tester", password="secret")


def test_mud_register_adds_expected_tools():
    registry = _make_registry()
    mock_session = MagicMock()
    mock_session.is_open = False
    Mud._register_with_session(registry, mock_session, name="Tester", password="secret")

    expected = [
        "mud_connect", "mud_disconnect", "mud_status",
        "look", "examine", "check",
        "move", "flee", "set_position", "track",
        "attack", "skill_strike", "consider",
        "say", "tell", "channel_say",
        "get_item", "drop_item", "put_item", "equip_item", "consume_item",
        "cast_spell", "use_magic_item",
        "shop", "practice", "save_character", "send_raw",
    ]
    for name in expected:
        assert registry.get(name) is not None, f"tool {name!r} not registered"


def test_mud_status_returns_disconnected_when_closed():
    registry = _make_registry()
    mock_session = MagicMock()
    mock_session.is_open = False
    Mud._register_with_session(registry, mock_session, name="Tester", password="secret")
    result = registry.dispatch("mud_status", {})
    assert "disconnected" in result


def test_mud_status_returns_connected_when_open():
    registry = _make_registry()
    mock_session = MagicMock()
    mock_session.is_open = True
    mock_session.host = "localhost"
    mock_session.port = 4000
    Mud._register_with_session(registry, mock_session, name="Tester", password="secret")
    result = registry.dispatch("mud_status", {})
    assert "connected" in result


def test_tool_returns_error_when_not_connected():
    registry = _make_registry()
    mock_session = MagicMock()
    mock_session.is_open = False
    Mud._register_with_session(registry, mock_session, name="Tester", password="secret")
    result = registry.dispatch("look", {})
    assert result.startswith("error:")


def test_look_sends_look_command_when_connected():
    registry = _make_registry()
    mock_session = MagicMock()
    mock_session.is_open = True
    mock_session.drain.return_value = ""
    mock_session.read_until_prompt.return_value = "You are in a room. > "
    Mud._register_with_session(registry, mock_session, name="Tester", password="secret")
    result = registry.dispatch("look", {})
    mock_session.send_command.assert_called_once_with("look")
    assert "room" in result


def test_move_sends_direction():
    registry = _make_registry()
    mock_session = MagicMock()
    mock_session.is_open = True
    mock_session.drain.return_value = ""
    mock_session.read_until_prompt.return_value = "You go north. > "
    Mud._register_with_session(registry, mock_session, name="Tester", password="secret")
    result = registry.dispatch("move", {"direction": "north"})
    mock_session.send_command.assert_called_once_with("north")


def test_move_rejects_invalid_direction():
    registry = _make_registry()
    mock_session = MagicMock()
    mock_session.is_open = True
    Mud._register_with_session(registry, mock_session, name="Tester", password="secret")
    result = registry.dispatch("move", {"direction": "sideways"})
    assert result.startswith("error:")


def test_send_raw_passes_command_through():
    registry = _make_registry()
    mock_session = MagicMock()
    mock_session.is_open = True
    mock_session.read_until_prompt.return_value = "who output > "
    Mud._register_with_session(registry, mock_session, name="Tester", password="secret")
    registry.dispatch("send_raw", {"command": "who"})
    mock_session.send_command.assert_called_once_with("who")


def test_mud_register_classmethod_calls_internal():
    """Mud.register() creates a session and calls _register_with_session."""
    registry = _make_registry()
    mock_session = MagicMock()
    mock_session.is_open = False

    with patch("boukensha.tools.mud.MudSession", return_value=mock_session):
        Mud.register(registry, host="localhost", port=4000, name="Hero", password="pw")

    assert registry.get("mud_connect") is not None
```

- [ ] **Step 2: Run tests to verify they fail**

```bash
cd week1_baseline/python/10_standard_tool_library
uv run pytest tests/test_tools_mud.py -v 2>&1 | head -40
```

Expected: `ModuleNotFoundError: No module named 'boukensha.tools.mud'`

- [ ] **Step 3: Create `tools/mud.py`**

Create `week1_baseline/python/10_standard_tool_library/src/boukensha/tools/mud.py`:

```python
"""MUD gameplay tools for the Boukensha agent.

A single MudSession is created when tools are registered and shared by every
tool via closure — the agent logs in once and reuses the connection for all
subsequent tool calls.

Tools registered (grouped by concern):

  Connection
    mud_connect       — open socket and log in
    mud_disconnect    — close socket gracefully
    mud_status        — report whether the session is open

  Perception
    look              — look at the room or a specific target
    examine           — examine something in detail
    check             — query self-info (score, inventory, equipment, exits…)

  Movement
    move              — go a compass direction or up/down
    flee              — flee from combat
    set_position      — change body position (stand/sit/rest/sleep/wake)
    track             — track a mob or player by name

  Combat
    attack            — attack a target
    skill_strike      — use a combat skill (bash, kick, backstab, rescue, assist)
    consider          — assess a mob's relative strength

  Communication
    say               — say/emote/reply in the room
    tell              — tell/whisper/ask a specific player
    channel_say       — broadcast over a channel (shout, gossip, auction…)

  Inventory & equipment
    get_item          — pick up an item
    drop_item         — drop, donate, or junk an item
    put_item          — put an item into a container
    equip_item        — wear, wield, hold, grab, or remove an item
    consume_item      — eat, drink, taste, or sip something

  Magic
    cast_spell        — cast a named spell with an optional target
    use_magic_item    — quaff a potion, recite a scroll, or use a wand/staff

  Utility
    shop              — buy, sell, list, or value items at a shop
    practice          — list or practice a skill with a guildmaster
    save_character    — save the character to disk
    send_raw          — send an arbitrary command string (escape hatch)
"""

from __future__ import annotations

import re
import select
import socket
import threading
import time
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from boukensha.registry import Registry

_IAC_RE = re.compile(
    rb"\xff[\xfb-\xfe]."          # WILL/WONT/DO/DONT + option
    rb"|\xff\xfa.*?\xff\xf0"      # SB ... SE
    rb"|\xff\xff"                 # escaped 0xFF
    rb"|\xff.",                   # any other IAC sequence
    re.DOTALL,
)
_ANSI_RE = re.compile(rb"\x1b\[[0-9;]*[a-zA-Z]")
_PROMPT = "> "

_DIRECTIONS   = {"north", "east", "south", "west", "up", "down"}
_POSITIONS    = {"stand", "sit", "rest", "sleep", "wake"}
_ATTACK_STYLES = {"kill", "hit", "murder"}
_STRIKE_SKILLS = {"bash", "kick", "backstab", "rescue", "assist"}
_LOCAL_SAY    = {"say", "emote", "reply"}
_TARGETED_SAY = {"tell", "whisper", "ask"}
_CHANNELS     = {"shout", "gossip", "auction", "grats", "holler"}
_DROP_MODES   = {"drop", "donate", "junk"}
_EQUIP_OPS    = {"wear", "wield", "hold", "grab", "remove"}
_CONSUME_MODES = {"eat", "drink", "taste", "sip"}
_SHOP_OPS     = {"buy", "sell", "list", "value", "offer"}
_INFO_SELF    = {
    "score", "inventory", "equipment", "gold", "exits",
    "time", "weather", "levels", "wimpy", "toggle", "where",
}


def _strip_telnet(data: bytes) -> bytes:
    data = _IAC_RE.sub(b"", data)
    data = _ANSI_RE.sub(b"", data)
    return data


class MudSession:
    """Long-lived TCP connection to a CircleMUD server.

    A background thread continuously drains the socket into an internal
    buffer. Call send_command() then read_until_prompt() to interact.
    """

    def __init__(self, host: str = "localhost", port: int = 4000, timeout: float = 10.0) -> None:
        self.host = host
        self.port = port
        self._timeout = timeout
        self._sock: socket.socket | None = None
        self._reader: threading.Thread | None = None
        self._buf = b""
        self._lock = threading.Lock()
        self._data_event = threading.Event()
        self._closed = True

    @property
    def is_open(self) -> bool:
        return self._sock is not None and not self._closed

    def open(self) -> None:
        if self.is_open:
            raise RuntimeError("session already open")
        self._buf = b""
        self._closed = False
        self._sock = socket.create_connection((self.host, self.port), timeout=self._timeout)
        self._sock.settimeout(None)
        self._reader = threading.Thread(target=self._read_loop, daemon=True)
        self._reader.start()

    def close(self) -> None:
        if self._closed:
            return
        self._closed = True
        try:
            self._sock.close()  # type: ignore[union-attr]
        except Exception:
            pass
        self._sock = None
        if self._reader:
            self._reader.join(timeout=1.0)
            self._reader = None

    def send_command(self, cmd: str) -> None:
        if not self.is_open:
            raise RuntimeError("session not open — call mud_connect first")
        self._sock.sendall((cmd + "\r\n").encode("utf-8", errors="replace"))  # type: ignore[union-attr]

    def drain(self) -> str:
        with self._lock:
            out, self._buf = self._buf, b""
        return out.decode("utf-8", errors="replace")

    def read_until_prompt(self, timeout: float | None = None) -> str:
        """Block until the "> " prompt is seen or timeout expires."""
        deadline = time.monotonic() + (timeout or self._timeout)
        while time.monotonic() < deadline:
            with self._lock:
                text = self._buf.decode("utf-8", errors="replace")
                if _PROMPT in text:
                    self._buf = b""
                    return text
            remaining = deadline - time.monotonic()
            self._data_event.wait(timeout=min(0.1, remaining))
            self._data_event.clear()
        # timeout: return whatever we have
        return self.drain()

    def login(self, name: str, password: str) -> str:
        self._wait_for(b"wish to be known", timeout=10.0)
        self.send_command(name)
        self._wait_for(b"Password", timeout=10.0)
        self.send_command(password)
        out = self._wait_for_any(
            [b"Welcome", b"Reconnecting", b"Wrong password"], timeout=10.0
        )
        if b"Wrong password" in out:
            raise RuntimeError("MUD login failed: wrong password")
        if b"Welcome" in out:
            self.send_command("")   # press return at main menu
            self.send_command("1")  # enter the game
            self.read_until_prompt(timeout=10.0)
        return self.drain()

    # ------------------------------------------------------------------ private

    def _read_loop(self) -> None:
        try:
            while not self._closed:
                assert self._sock is not None
                r, _, _ = select.select([self._sock], [], [], 0.5)
                if not r:
                    continue
                chunk = self._sock.recv(4096)
                if not chunk:
                    break
                clean = _strip_telnet(chunk)
                if clean:
                    with self._lock:
                        self._buf += clean
                    self._data_event.set()
        except (OSError, ConnectionResetError):
            pass
        finally:
            self._closed = True
            self._data_event.set()

    def _wait_for(self, pattern: bytes, timeout: float) -> bytes:
        deadline = time.monotonic() + timeout
        while time.monotonic() < deadline:
            with self._lock:
                if pattern.lower() in self._buf.lower():
                    out, self._buf = self._buf, b""
                    return out
            remaining = deadline - time.monotonic()
            self._data_event.wait(timeout=min(0.1, remaining))
            self._data_event.clear()
        return b""

    def _wait_for_any(self, patterns: list[bytes], timeout: float) -> bytes:
        deadline = time.monotonic() + timeout
        while time.monotonic() < deadline:
            with self._lock:
                buf_lower = self._buf.lower()
                for pat in patterns:
                    if pat.lower() in buf_lower:
                        out, self._buf = self._buf, b""
                        return out
            remaining = deadline - time.monotonic()
            self._data_event.wait(timeout=min(0.1, remaining))
            self._data_event.clear()
        return b""


def _guard(session: MudSession) -> str | None:
    """Return an error string if session is not open, else None."""
    if not session.is_open:
        return "error: not connected — call mud_connect first"
    return None


def _send(session: MudSession, cmd: str) -> str:
    session.drain()
    session.send_command(cmd)
    return session.read_until_prompt()


def _check_enum(value: str, allowed: set[str], name: str) -> str | None:
    """Return None if valid, else an error string."""
    v = value.strip().lower()
    if v not in allowed:
        return f"error: invalid {name}: {value!r} (expected one of {', '.join(sorted(allowed))})"
    return None


class Mud:
    """Registers all MUD gameplay tools against a registry."""

    @classmethod
    def register(
        cls,
        registry: "Registry",
        *,
        host: str = "localhost",
        port: int = 4000,
        name: str,
        password: str,
    ) -> None:
        session = MudSession(host=host, port=port)
        cls._register_with_session(registry, session, name=name, password=password)

    @classmethod
    def _register_with_session(
        cls,
        registry: "Registry",
        session: MudSession,
        *,
        name: str,
        password: str,
    ) -> None:
        # ── Connection ────────────────────────────────────────────────────────

        registry.tool(
            "mud_connect",
            description=(
                "Open the connection to the MUD server and log in. "
                "Safe to call when already connected (returns current status)."
            ),
            parameters={},
        )(lambda **_: _mud_connect(session, name, password))

        registry.tool(
            "mud_disconnect",
            description="Close the connection to the MUD server gracefully.",
            parameters={},
        )(lambda **_: _mud_disconnect(session))

        registry.tool(
            "mud_status",
            description="Return whether the MUD session is currently connected.",
            parameters={},
        )(lambda **_: _mud_status(session))

        # ── Perception ────────────────────────────────────────────────────────

        registry.tool(
            "look",
            description=(
                "Look at the current room or at a specific target. "
                "Call with NO arguments to describe the current room. "
                "Pass target to inspect an item, mob, or player. "
                "Use preposition 'in' to look inside a container, 'at' to inspect, "
                "or a direction (north/east/south/west/up/down) to peek into an adjacent room."
            ),
            parameters={
                "target":      {"type": "string", "description": "Item, mob, or player to inspect (optional)"},
                "preposition": {"type": "string", "description": "in | at | north | east | south | west | up | down (optional)"},
            },
        )(lambda target=None, preposition=None, **_: _look(session, target, preposition))

        registry.tool(
            "examine",
            description="Examine a target in detail (more verbose than look).",
            parameters={
                "target": {"type": "string", "description": "The item, mob, or player to examine"},
            },
        )(lambda target, **_: _guard(session) or _send(session, f"examine {target}"))

        registry.tool(
            "check",
            description=(
                "Query information about your character or surroundings. "
                "Kinds: score, inventory, equipment, gold, exits, time, weather, "
                "levels, wimpy, toggle, where."
            ),
            parameters={
                "kind": {"type": "string", "description": "score | inventory | equipment | gold | exits | time | weather | levels | wimpy | toggle | where"},
            },
        )(lambda kind, **_: _check_info(session, kind))

        # ── Movement ──────────────────────────────────────────────────────────

        registry.tool(
            "move",
            description="Move in a compass direction or up/down.",
            parameters={
                "direction": {"type": "string", "description": "north | east | south | west | up | down"},
            },
        )(lambda direction, **_: _move(session, direction))

        registry.tool(
            "flee",
            description="Attempt to flee from combat in a random available direction.",
            parameters={},
        )(lambda **_: _guard(session) or _send(session, "flee"))

        registry.tool(
            "set_position",
            description=(
                "Change body position. Use 'rest' or 'sleep' to recover HP/mana. "
                "Must be standing to move or fight."
            ),
            parameters={
                "position": {"type": "string", "description": "stand | sit | rest | sleep | wake"},
            },
        )(lambda position, **_: _set_position(session, position))

        registry.tool(
            "track",
            description=(
                "Track a mob or player by name, revealing which direction they are in. "
                "Requires the Track skill."
            ),
            parameters={
                "target": {"type": "string", "description": "Name of the mob or player to track"},
            },
        )(lambda target, **_: _guard(session) or _send(session, f"track {target}"))

        # ── Combat ────────────────────────────────────────────────────────────

        registry.tool(
            "attack",
            description=(
                "Attack a target. Style 'kill' is the standard approach; "
                "'murder' bypasses the mercy check; 'hit' is a one-off strike."
            ),
            parameters={
                "target": {"type": "string", "description": "Name of the mob or player to attack"},
                "style":  {"type": "string", "description": "kill | hit | murder (default: kill)"},
            },
        )(lambda target, style="kill", **_: _attack(session, target, style))

        registry.tool(
            "skill_strike",
            description="Use a combat skill against a target.",
            parameters={
                "skill":  {"type": "string", "description": "bash | kick | backstab | rescue | assist"},
                "target": {"type": "string", "description": "Name of the mob or player"},
            },
        )(lambda skill, target, **_: _skill_strike(session, skill, target))

        registry.tool(
            "consider",
            description=(
                "Assess a mob's relative strength before engaging in combat. "
                "Always consider before attacking an unknown mob."
            ),
            parameters={
                "target": {"type": "string", "description": "Name of the mob to consider"},
            },
        )(lambda target, **_: _guard(session) or _send(session, f"consider {target}"))

        # ── Communication ─────────────────────────────────────────────────────

        registry.tool(
            "say",
            description="Speak or emote in the current room.",
            parameters={
                "text": {"type": "string", "description": "What to say or emote"},
                "mode": {"type": "string", "description": "say | emote | reply (default: say)"},
            },
        )(lambda text, mode="say", **_: _say_local(session, text, mode))

        registry.tool(
            "tell",
            description="Send a private message to a specific player.",
            parameters={
                "target": {"type": "string", "description": "Player name to message"},
                "text":   {"type": "string", "description": "The message"},
                "mode":   {"type": "string", "description": "tell | whisper | ask (default: tell)"},
            },
        )(lambda target, text, mode="tell", **_: _say_targeted(session, target, text, mode))

        registry.tool(
            "channel_say",
            description="Broadcast a message over a global channel.",
            parameters={
                "channel": {"type": "string", "description": "shout | gossip | auction | grats | holler"},
                "text":    {"type": "string", "description": "The message to broadcast"},
            },
        )(lambda channel, text, **_: _channel_say(session, channel, text))

        # ── Inventory & equipment ─────────────────────────────────────────────

        registry.tool(
            "get_item",
            description="Pick up an item from the room or from a container.",
            parameters={
                "item":      {"type": "string",  "description": "Name of the item to get"},
                "container": {"type": "string",  "description": "Container to get it from (optional)"},
                "count":     {"type": "integer", "description": "Number of items to get (optional)"},
            },
        )(lambda item, container=None, count=None, **_: _get_item(session, item, container, count))

        registry.tool(
            "drop_item",
            description="Drop, donate, or junk an item.",
            parameters={
                "item":  {"type": "string",  "description": "Name of the item"},
                "mode":  {"type": "string",  "description": "drop | donate | junk (default: drop)"},
                "count": {"type": "integer", "description": "Number of items (optional)"},
            },
        )(lambda item, mode="drop", count=None, **_: _drop_item(session, item, mode, count))

        registry.tool(
            "put_item",
            description="Put an item into a container.",
            parameters={
                "item":      {"type": "string",  "description": "Name of the item to put"},
                "container": {"type": "string",  "description": "Name of the container"},
                "count":     {"type": "integer", "description": "Number of items (optional)"},
            },
        )(lambda item, container, count=None, **_: _put_item(session, item, container, count))

        registry.tool(
            "equip_item",
            description="Wear, wield, hold, grab, or remove an item.",
            parameters={
                "item":     {"type": "string", "description": "Name of the item"},
                "action":   {"type": "string", "description": "wear | wield | hold | grab | remove"},
                "body_loc": {"type": "string", "description": "Body location to wear on (optional, e.g. 'head', 'finger')"},
            },
        )(lambda item, action, body_loc=None, **_: _equip_item(session, item, action, body_loc))

        registry.tool(
            "consume_item",
            description="Eat, drink, taste, or sip a consumable item.",
            parameters={
                "item": {"type": "string", "description": "Name of the item to consume"},
                "mode": {"type": "string", "description": "eat | drink | taste | sip (default: eat)"},
            },
        )(lambda item, mode="eat", **_: _consume_item(session, item, mode))

        # ── Magic ─────────────────────────────────────────────────────────────

        registry.tool(
            "cast_spell",
            description="Cast a spell, optionally at a target.",
            parameters={
                "spell":  {"type": "string", "description": "Full spell name (e.g. 'cure light wounds', 'magic missile')"},
                "target": {"type": "string", "description": "Target mob, player, or object (optional)"},
            },
        )(lambda spell, target=None, **_: _guard(session) or _send(
            session, f"cast '{spell}' {target}" if target else f"cast '{spell}'"
        ))

        registry.tool(
            "use_magic_item",
            description="Activate a magic item: quaff a potion, recite a scroll, or use a wand/staff.",
            parameters={
                "item":        {"type": "string", "description": "Name of the item to activate"},
                "mode":        {"type": "string", "description": "quaff | recite | use"},
                "target_args": {"type": "string", "description": "Optional target arguments (e.g. mob name for a wand)"},
            },
        )(lambda item, mode, target_args=None, **_: _use_magic_item(session, item, mode, target_args))

        # ── Utility ───────────────────────────────────────────────────────────

        registry.tool(
            "shop",
            description="Interact with a shop NPC: list stock, buy, sell, or get item value.",
            parameters={
                "action": {"type": "string", "description": "list | buy | sell | value | offer"},
                "args":   {"type": "string", "description": "Item name or number (optional)"},
            },
        )(lambda action, args=None, **_: _shop(session, action, args))

        registry.tool(
            "practice",
            description="List your known skills at a guildmaster, or practice a specific skill.",
            parameters={
                "skill": {"type": "string", "description": "Skill name to practice (omit to list all)"},
            },
        )(lambda skill=None, **_: _guard(session) or _send(
            session, f"practice {skill}" if skill else "practice"
        ))

        registry.tool(
            "save_character",
            description="Save your character to disk so progress is not lost on disconnect.",
            parameters={},
        )(lambda **_: _guard(session) or _send(session, "save"))

        registry.tool(
            "send_raw",
            description=(
                "Send an arbitrary command string to the MUD and return the response. "
                "Use as an escape hatch when no structured tool fits."
            ),
            parameters={
                "command": {"type": "string", "description": "The raw command to send (e.g. 'who', 'help backstab')"},
            },
        )(lambda command, **_: _guard(session) or _send(session, command))

        # Auto-connect at startup so the session is ready immediately.
        try:
            session.open()
            session.login(name, password)
        except Exception as exc:
            import warnings
            warnings.warn(
                f"[boukensha] MUD auto-connect failed: {exc} — call mud_connect manually",
                stacklevel=2,
            )


# ---------------------------------------------------------------------------
# Tool implementation helpers (pure functions over a session)
# ---------------------------------------------------------------------------

def _mud_connect(session: MudSession, name: str, password: str) -> str:
    if session.is_open:
        return f"already connected to {session.host}:{session.port}"
    try:
        session.open()
        welcome = session.login(name, password)
        return f"connected to {session.host}:{session.port}\n{welcome}"
    except Exception as exc:
        return f"error: {exc}"


def _mud_disconnect(session: MudSession) -> str:
    if not session.is_open:
        return "already disconnected"
    session.close()
    return "disconnected"


def _mud_status(session: MudSession) -> str:
    if session.is_open:
        return f"connected to {session.host}:{session.port}"
    return "disconnected"


def _look(session: MudSession, target: str | None, preposition: str | None) -> str:
    err = _guard(session)
    if err:
        return err
    parts = ["look"]
    if preposition:
        parts.append(preposition.strip().lower())
    if target:
        parts.append(target)
    return _send(session, " ".join(parts))


def _check_info(session: MudSession, kind: str) -> str:
    err = _guard(session)
    if err:
        return err
    err = _check_enum(kind, _INFO_SELF, "kind")
    if err:
        return err
    return _send(session, kind.strip().lower())


def _move(session: MudSession, direction: str) -> str:
    err = _guard(session)
    if err:
        return err
    err = _check_enum(direction, _DIRECTIONS, "direction")
    if err:
        return err
    return _send(session, direction.strip().lower())


def _set_position(session: MudSession, position: str) -> str:
    err = _guard(session)
    if err:
        return err
    err = _check_enum(position, _POSITIONS, "position")
    if err:
        return err
    return _send(session, position.strip().lower())


def _attack(session: MudSession, target: str, style: str) -> str:
    err = _guard(session)
    if err:
        return err
    err = _check_enum(style, _ATTACK_STYLES, "style")
    if err:
        return err
    return _send(session, f"{style.strip().lower()} {target}")


def _skill_strike(session: MudSession, skill: str, target: str) -> str:
    err = _guard(session)
    if err:
        return err
    err = _check_enum(skill, _STRIKE_SKILLS, "skill")
    if err:
        return err
    return _send(session, f"{skill.strip().lower()} {target}")


def _say_local(session: MudSession, text: str, mode: str) -> str:
    err = _guard(session)
    if err:
        return err
    err = _check_enum(mode, _LOCAL_SAY, "mode")
    if err:
        return err
    return _send(session, f"{mode.strip().lower()} {text}")


def _say_targeted(session: MudSession, target: str, text: str, mode: str) -> str:
    err = _guard(session)
    if err:
        return err
    err = _check_enum(mode, _TARGETED_SAY, "mode")
    if err:
        return err
    return _send(session, f"{mode.strip().lower()} {target} {text}")


def _channel_say(session: MudSession, channel: str, text: str) -> str:
    err = _guard(session)
    if err:
        return err
    err = _check_enum(channel, _CHANNELS, "channel")
    if err:
        return err
    return _send(session, f"{channel.strip().lower()} {text}")


def _get_item(session: MudSession, item: str, container: str | None, count: int | None) -> str:
    err = _guard(session)
    if err:
        return err
    parts = ["get"]
    if count is not None:
        parts.append(str(count))
    parts.append(item)
    if container:
        parts.append(container)
    return _send(session, " ".join(parts))


def _drop_item(session: MudSession, item: str, mode: str, count: int | None) -> str:
    err = _guard(session)
    if err:
        return err
    err = _check_enum(mode, _DROP_MODES, "mode")
    if err:
        return err
    parts = [mode.strip().lower()]
    if count is not None:
        parts.append(str(count))
    parts.append(item)
    return _send(session, " ".join(parts))


def _put_item(session: MudSession, item: str, container: str, count: int | None) -> str:
    err = _guard(session)
    if err:
        return err
    parts = ["put"]
    if count is not None:
        parts.append(str(count))
    parts.append(item)
    parts.append(container)
    return _send(session, " ".join(parts))


def _equip_item(session: MudSession, item: str, action: str, body_loc: str | None) -> str:
    err = _guard(session)
    if err:
        return err
    err = _check_enum(action, _EQUIP_OPS, "action")
    if err:
        return err
    cmd = f"{action.strip().lower()} {item}"
    if body_loc:
        cmd += f" {body_loc}"
    return _send(session, cmd)


def _consume_item(session: MudSession, item: str, mode: str) -> str:
    err = _guard(session)
    if err:
        return err
    err = _check_enum(mode, _CONSUME_MODES, "mode")
    if err:
        return err
    return _send(session, f"{mode.strip().lower()} {item}")


def _use_magic_item(session: MudSession, item: str, mode: str, target_args: str | None) -> str:
    err = _guard(session)
    if err:
        return err
    allowed = {"quaff", "recite", "use"}
    err = _check_enum(mode, allowed, "mode")
    if err:
        return err
    cmd = f"{mode.strip().lower()} {item}"
    if target_args:
        cmd += f" {target_args}"
    return _send(session, cmd)


def _shop(session: MudSession, action: str, args: str | None) -> str:
    err = _guard(session)
    if err:
        return err
    err = _check_enum(action, _SHOP_OPS, "action")
    if err:
        return err
    cmd = action.strip().lower()
    if args:
        cmd += f" {args}"
    return _send(session, cmd)
```

- [ ] **Step 4: Run tests — expect most to pass, investigate any failures**

```bash
cd week1_baseline/python/10_standard_tool_library
uv run pytest tests/test_tools_mud.py -v
```

Expected: All tests pass.

- [ ] **Step 5: Commit**

```bash
git add week1_baseline/python/10_standard_tool_library/src/boukensha/tools/mud.py \
        week1_baseline/python/10_standard_tool_library/tests/test_tools_mud.py
git commit -m "feat(10): add MudSession and Mud.register() tool module"
```

---

## Task 2: Wire `Mud` into `tools/__init__.py` and `__init__.py` for step 10

**Files:**
- Modify: `week1_baseline/python/10_standard_tool_library/src/boukensha/tools/__init__.py`
- Modify: `week1_baseline/python/10_standard_tool_library/src/boukensha/__init__.py`
- Modify: `week1_baseline/python/10_standard_tool_library/src/boukensha_loader.py`

**Interfaces:**
- Consumes: `Mud` from Task 1
- Produces: `tools.Mud` accessible from `import boukensha; boukensha.tools.Mud`
- Produces: `run(task, ..., mud=None)` and `repl(..., mud=None)` accepting `dict | bool | None`
- `mud=None` → reads from config if `mud_username` is set; `mud=False` → skip entirely; `mud={...}` → use that dict

- [ ] **Step 1: Write failing test for wiring**

Add to `week1_baseline/python/10_standard_tool_library/tests/test_tools_mud.py` (append at end of file):

```python
def test_tools_module_exports_mud():
    from boukensha import tools
    assert hasattr(tools, "Mud")


def test_mud_opts_from_config_returns_none_when_no_username(tmp_path):
    """_mud_opts_from_config returns None when mud.username is not set."""
    import boukensha
    from boukensha.config import Config
    from unittest.mock import patch, PropertyMock

    mock_cfg = MagicMock(spec=Config)
    mock_cfg.mud_username = None
    result = boukensha._mud_opts_from_config(mock_cfg)
    assert result is None


def test_mud_opts_from_config_returns_dict_when_username_set():
    """_mud_opts_from_config returns a dict with connection params when username is set."""
    import boukensha
    from boukensha.config import Config

    mock_cfg = MagicMock(spec=Config)
    mock_cfg.mud_host = "localhost"
    mock_cfg.mud_port = 4000
    mock_cfg.mud_username = "Hero"
    mock_cfg.mud_password = "secret"
    result = boukensha._mud_opts_from_config(mock_cfg)
    assert result == {"host": "localhost", "port": 4000, "name": "Hero", "password": "secret"}
```

Run to confirm failure:

```bash
cd week1_baseline/python/10_standard_tool_library
uv run pytest tests/test_tools_mud.py::test_tools_module_exports_mud \
             tests/test_tools_mud.py::test_mud_opts_from_config_returns_none_when_no_username \
             tests/test_tools_mud.py::test_mud_opts_from_config_returns_dict_when_username_set -v
```

Expected: `AttributeError: module 'boukensha.tools' has no attribute 'Mud'`

- [ ] **Step 2: Update `tools/__init__.py`**

Replace `week1_baseline/python/10_standard_tool_library/src/boukensha/tools/__init__.py` with:

```python
"""Boukensha built-in tool modules."""

from __future__ import annotations

from .file_system import FileSystem
from .mud import Mud
from .shell import Shell

__all__ = ["FileSystem", "Mud", "Shell"]
```

- [ ] **Step 3: Update `__init__.py` — add `mud` param and `_mud_opts_from_config`**

In `week1_baseline/python/10_standard_tool_library/src/boukensha/__init__.py`:

Add `_mud_opts_from_config` helper and `mud` parameter to both `run()` and `repl()`.

The full updated file (replace entirely — changes are: `mud` param in both functions, `_mud_opts_from_config`, and Mud registration block after FileSystem/Shell):

```python
"""Boukensha agent loop."""

from __future__ import annotations

import os
from collections.abc import Callable
from typing import Any

from . import backends, tasks, tools
from .agent import Agent
from .client import Client
from .repl import Repl
from .config import Config
from .context import Context
from .errors import ApiError, LoopError, UnknownToolError, UnsupportedModelError
from .logger import Logger
from .message import Message
from .prompt_builder import PromptBuilder
from .registry import Registry
from .run_dsl import RunDSL
from .tool import Tool

__all__ = [
    "Agent",
    "ApiError",
    "Client",
    "Config",
    "Context",
    "Logger",
    "LoopError",
    "Message",
    "PromptBuilder",
    "Registry",
    "Repl",
    "RunDSL",
    "Tool",
    "UnknownToolError",
    "UnsupportedModelError",
    "backends",
    "debug",
    "disable_quiet",
    "enable_debug",
    "enable_quiet",
    "is_quiet",
    "repl",
    "run",
    "tasks",
    "tools",
]

__version__ = "0.1.0"

_debug: bool = False


def enable_debug() -> None:
    global _debug
    _debug = True


def debug() -> bool:
    return _debug


_quiet: bool = False


def enable_quiet() -> None:
    global _quiet
    _quiet = True


def disable_quiet() -> None:
    global _quiet
    _quiet = False


def is_quiet() -> bool:
    return _quiet


def _mud_opts_from_config(cfg: Config) -> dict | None:
    """Build mud kwargs from config. Returns None if mud.username is not set."""
    if not cfg.mud_username:
        return None
    return {
        "host":     cfg.mud_host,
        "port":     cfg.mud_port,
        "name":     cfg.mud_username,
        "password": cfg.mud_password,
    }


def run(
    task: str,
    *,
    system: str | None = None,
    model: str | None = None,
    backend: str | None = None,
    api_key: str | None = None,
    ollama_host: str = "http://localhost:11434",
    log: str | None = None,
    max_output_tokens: int | None = None,
    working_dir: str | bool | None = None,
    allowed_commands: list[str] | None = None,
    shell_timeout: int = 30,
    mud: dict | bool | None = None,
    tool_registrar: Callable[[RunDSL], None] | None = None,
) -> str:
    """Wire together every primitive and run the agent loop.

    Args:
        task: The user message handed to the agent.
        system: System prompt. Defaults to the Player task's prompt from Config.
        model: Model name. Defaults to settings.yaml.
        backend: Provider name string. Defaults to settings.yaml.
        api_key: API key for the chosen backend.
        ollama_host: Ollama base URL. Defaults to "http://localhost:11434".
        log: Optional JSONL path override.
        max_output_tokens: Per-reply output cap.
        mud: MUD connection options dict (host, port, name, password).
            None (default) reads from config if mud.username is set.
            False disables MUD tools entirely.
            A dict uses those connection params directly.
        tool_registrar: A callable that accepts a RunDSL and registers tools.

    Returns:
        The agent's final text response.
    """
    cfg = Config()
    task_class = tasks.Player
    task_settings = cfg.tasks(task_class.task_name())

    resolved_system = system or task_class.system_prompt(
        task_settings,
        user_prompts_dir=cfg.user_prompts_dir,
        default_prompts_dir=Config.PROMPTS_DIR,
    )
    resolved_model = model or task_class.model(task_settings)
    resolved_backend = backend or task_class.provider(task_settings)

    resolved_api_key = api_key or {
        "anthropic": os.environ.get("ANTHROPIC_API_KEY"),
        "openai": os.environ.get("OPENAI_API_KEY"),
        "gemini": os.environ.get("GEMINI_API_KEY"),
        "ollama_cloud": os.environ.get("OLLAMA_API_KEY"),
    }.get(resolved_backend)

    resolved_wd: str | None
    if working_dir is None:
        resolved_wd = os.getcwd()
    elif not working_dir:
        resolved_wd = None
    else:
        resolved_wd = str(working_dir)

    ctx = Context(task=task_class, system=resolved_system, working_dir=resolved_wd)
    registry = Registry(ctx)

    if resolved_wd:
        tools.FileSystem.register(registry, working_dir=resolved_wd)
        tools.Shell.register(
            registry,
            working_dir=resolved_wd,
            timeout=shell_timeout,
            allowed_commands=allowed_commands,
        )

    resolved_mud = None if mud is False else (mud or _mud_opts_from_config(cfg))
    if resolved_mud:
        tools.Mud.register(registry, **resolved_mud)

    if tool_registrar is not None:
        dsl = RunDSL(registry)
        tool_registrar(dsl)

    be: Any
    if resolved_backend == "anthropic":
        be = backends.Anthropic(api_key=resolved_api_key, model=resolved_model)
    elif resolved_backend == "openai":
        be = backends.OpenAI(api_key=resolved_api_key, model=resolved_model)
    elif resolved_backend == "gemini":
        be = backends.Gemini(api_key=resolved_api_key, model=resolved_model)
    elif resolved_backend == "ollama":
        be = backends.Ollama(host=ollama_host, model=resolved_model)
    elif resolved_backend == "ollama_cloud":
        be = backends.OllamaCloud(api_key=resolved_api_key, model=resolved_model)
    else:
        raise ValueError(
            f"Unknown backend {resolved_backend!r}. "
            "Use 'anthropic', 'openai', 'gemini', 'ollama', or 'ollama_cloud'."
        )

    builder = PromptBuilder(ctx, be)
    client = Client(builder)
    effective_max_iterations = task_class.max_iterations(task_settings)
    effective_max_output_tokens = max_output_tokens or task_class.max_output_tokens(task_settings)

    logger = Logger(
        log=log,
        snapshot={
            "task": task_class.task_name(),
            "max_iterations": effective_max_iterations,
            "max_output_tokens": effective_max_output_tokens,
            "model": resolved_model,
            "provider": resolved_backend,
        },
    )
    agent = Agent(
        context=ctx,
        registry=registry,
        builder=builder,
        client=client,
        logger=logger,
        task_settings=task_settings,
        max_iterations=effective_max_iterations,
        max_output_tokens=effective_max_output_tokens,
    )

    ctx.add_message("user", task)
    try:
        return agent.run()
    finally:
        logger.close()


# Each step is a self-contained snapshot — the boilerplate below intentionally
# mirrors run() rather than sharing a helper so step 08 can be read on its own.
def repl(
    *,
    system: str | None = None,
    model: str | None = None,
    backend: str | None = None,
    api_key: str | None = None,
    ollama_host: str = "http://localhost:11434",
    log: str | None = None,
    max_output_tokens: int | None = None,
    working_dir: str | bool | None = None,
    allowed_commands: list[str] | None = None,
    shell_timeout: int = 30,
    mud: dict | bool | None = None,
    tool_registrar: Callable[[RunDSL], None] | None = None,
) -> None:
    """Start the interactive REPL loop.

    Same plumbing as run() but stays alive across multiple turns.
    See run() for full parameter documentation including the mud parameter.
    """
    from .repl import Repl as _Repl

    cfg = Config()
    task_class = tasks.Player
    task_settings = cfg.tasks(task_class.task_name())

    resolved_system = system or task_class.system_prompt(
        task_settings,
        user_prompts_dir=cfg.user_prompts_dir,
        default_prompts_dir=Config.PROMPTS_DIR,
    )
    resolved_model = model or task_class.model(task_settings)
    resolved_backend = backend or task_class.provider(task_settings)

    resolved_api_key = api_key or {
        "anthropic": os.environ.get("ANTHROPIC_API_KEY"),
        "openai": os.environ.get("OPENAI_API_KEY"),
        "gemini": os.environ.get("GEMINI_API_KEY"),
        "ollama_cloud": os.environ.get("OLLAMA_API_KEY"),
    }.get(resolved_backend)

    resolved_wd: str | None
    if working_dir is None:
        resolved_wd = os.getcwd()
    elif not working_dir:
        resolved_wd = None
    else:
        resolved_wd = str(working_dir)

    ctx = Context(task=task_class, system=resolved_system, working_dir=resolved_wd)
    registry = Registry(ctx)

    if resolved_wd:
        tools.FileSystem.register(registry, working_dir=resolved_wd)
        tools.Shell.register(
            registry,
            working_dir=resolved_wd,
            timeout=shell_timeout,
            allowed_commands=allowed_commands,
        )

    resolved_mud = None if mud is False else (mud or _mud_opts_from_config(cfg))
    if resolved_mud:
        tools.Mud.register(registry, **resolved_mud)

    if tool_registrar is not None:
        dsl = RunDSL(registry)
        tool_registrar(dsl)

    be: Any
    if resolved_backend == "anthropic":
        be = backends.Anthropic(api_key=resolved_api_key, model=resolved_model)
    elif resolved_backend == "openai":
        be = backends.OpenAI(api_key=resolved_api_key, model=resolved_model)
    elif resolved_backend == "gemini":
        be = backends.Gemini(api_key=resolved_api_key, model=resolved_model)
    elif resolved_backend == "ollama":
        be = backends.Ollama(host=ollama_host, model=resolved_model)
    elif resolved_backend == "ollama_cloud":
        be = backends.OllamaCloud(api_key=resolved_api_key, model=resolved_model)
    else:
        raise ValueError(
            f"Unknown backend {resolved_backend!r}. "
            "Use 'anthropic', 'openai', 'gemini', 'ollama', or 'ollama_cloud'."
        )

    builder = PromptBuilder(ctx, be)
    client = Client(builder)
    effective_max_iterations = task_class.max_iterations(task_settings)
    effective_max_output_tokens = max_output_tokens or task_class.max_output_tokens(task_settings)

    logger = Logger(
        log=log,
        snapshot={
            "task": task_class.task_name(),
            "max_iterations": effective_max_iterations,
            "max_output_tokens": effective_max_output_tokens,
            "model": resolved_model,
            "provider": resolved_backend,
        },
    )

    try:
        _Repl(
            context=ctx,
            registry=registry,
            builder=builder,
            client=client,
            logger=logger,
            task_settings=task_settings,
            max_iterations=effective_max_iterations,
            max_output_tokens=effective_max_output_tokens,
            config_dir=str(cfg.dir),
            provider=resolved_backend,
            model=resolved_model,
            version=__version__,
            api_key=resolved_api_key,
        ).start()
    except KeyboardInterrupt:
        print("\nInterrupted.")
    finally:
        logger.close()
```

- [ ] **Step 4: Update `boukensha_loader.py` — pass MUD env vars when set**

In `week1_baseline/python/10_standard_tool_library/src/boukensha_loader.py`, replace the `load_and_start_repl` function body so that when `MUD_NAME` is set in the environment it passes explicit mud opts:

```python
def load_and_start_repl() -> None:
    src_dir = resolve()
    step_dir = str(Path(src_dir).parent)

    if os.environ.get("BOUKENSHA_DEBUG"):
        print(f"[boukensha] loading from: {step_dir}")

    for name in [m for m in list(sys.modules) if m == "boukensha" or m.startswith("boukensha.")]:
        del sys.modules[name]
    sys.path.insert(0, src_dir)

    import boukensha

    if not hasattr(boukensha, "repl"):
        raise SystemExit(
            f"boukensha: the step at {step_dir}\n"
            "       does not support the interactive REPL (added in step 08).\n"
            "       Run its examples directly, e.g.:\n"
            f"         python {step_dir}/examples/*.py\n"
            "       Or point BOUKENSHA_PATH at step 08 or later."
        )

    repl_kwargs: dict = {}

    mud_name = os.environ.get("MUD_NAME")
    if mud_name:
        mud_password = os.environ.get("MUD_PASSWORD")
        if not mud_password:
            raise SystemExit("boukensha: MUD_NAME is set but MUD_PASSWORD is missing.")
        repl_kwargs["mud"] = {
            "host":     os.environ.get("MUD_HOST", "localhost"),
            "port":     int(os.environ.get("MUD_PORT", "4000")),
            "name":     mud_name,
            "password": mud_password,
        }
        repl_kwargs["working_dir"] = False

    import inspect
    repl_sig = inspect.signature(boukensha.repl)
    if "tui" in repl_sig.parameters:
        repl_kwargs["tui"] = sys.stdin.isatty()

    boukensha.repl(**repl_kwargs)
```

(Note: step 10's `repl()` does NOT have a `tui` param — the `inspect.signature` check handles this gracefully.)

- [ ] **Step 5: Run all tests for step 10**

```bash
cd week1_baseline/python/10_standard_tool_library
uv run pytest tests/ -v
```

Expected: All tests pass.

- [ ] **Step 6: Commit**

```bash
git add week1_baseline/python/10_standard_tool_library/src/boukensha/tools/__init__.py \
        week1_baseline/python/10_standard_tool_library/src/boukensha/__init__.py \
        week1_baseline/python/10_standard_tool_library/src/boukensha_loader.py \
        week1_baseline/python/10_standard_tool_library/tests/test_tools_mud.py
git commit -m "feat(10): wire Mud tools into run/repl and boukensha_loader"
```

---

## Task 3: Apply the same changes to step 11 (`11_tui`)

Step 11 has `tui: bool = True` in `repl()` and `Tui` lazy-imported in `__getattr__`. The diff from step 10 is only in `repl()` (the `tui` param and the `Tui(repl_instance).run()` call) and `__getattr__`.

**Files:**
- Create: `week1_baseline/python/11_tui/src/boukensha/tools/mud.py`
- Modify: `week1_baseline/python/11_tui/src/boukensha/tools/__init__.py`
- Modify: `week1_baseline/python/11_tui/src/boukensha/__init__.py`
- Modify: `week1_baseline/python/11_tui/src/boukensha_loader.py`
- Create: `week1_baseline/python/11_tui/tests/test_tools_mud.py`

**Interfaces:**
- Same as Task 1 + Task 2, but `repl()` also accepts `tui: bool = True`

- [ ] **Step 1: Copy `tools/mud.py` from step 10**

```bash
cp week1_baseline/python/10_standard_tool_library/src/boukensha/tools/mud.py \
   week1_baseline/python/11_tui/src/boukensha/tools/mud.py
```

- [ ] **Step 2: Copy `tests/test_tools_mud.py` from step 10**

```bash
cp week1_baseline/python/10_standard_tool_library/tests/test_tools_mud.py \
   week1_baseline/python/11_tui/tests/test_tools_mud.py
```

- [ ] **Step 3: Run tests to verify they fail (module not yet exported)**

```bash
cd week1_baseline/python/11_tui
uv run pytest tests/test_tools_mud.py -v 2>&1 | head -20
```

Expected: `AttributeError: module 'boukensha.tools' has no attribute 'Mud'`

- [ ] **Step 4: Update `tools/__init__.py`**

Replace `week1_baseline/python/11_tui/src/boukensha/tools/__init__.py` with:

```python
"""Boukensha built-in tool modules."""

from __future__ import annotations

from .file_system import FileSystem
from .mud import Mud
from .shell import Shell

__all__ = ["FileSystem", "Mud", "Shell"]
```

- [ ] **Step 5: Update `__init__.py`**

Replace `week1_baseline/python/11_tui/src/boukensha/__init__.py` with the full content below. Key difference from step 10: `repl()` has `tui: bool = True`, uses `Tui(repl_instance).run()`, and has `__getattr__` for lazy Tui import.

```python
"""Boukensha agent loop."""

from __future__ import annotations

import os
from collections.abc import Callable
from typing import Any

from . import backends, tasks, tools
from .agent import Agent
from .client import Client
from .repl import Repl
from .config import Config
from .context import Context
from .errors import ApiError, LoopError, UnknownToolError, UnsupportedModelError
from .logger import Logger
from .message import Message
from .prompt_builder import PromptBuilder
from .registry import Registry
from .run_dsl import RunDSL
from .tool import Tool


def __getattr__(name: str):
    if name == "Tui":
        from .tui import Tui
        return Tui
    raise AttributeError(f"module 'boukensha' has no attribute {name!r}")

__all__ = [
    "Agent",
    "ApiError",
    "Client",
    "Config",
    "Context",
    "Logger",
    "LoopError",
    "Message",
    "PromptBuilder",
    "Registry",
    "Repl",
    "RunDSL",
    "Tool",
    "Tui",
    "UnknownToolError",
    "UnsupportedModelError",
    "backends",
    "debug",
    "disable_quiet",
    "enable_debug",
    "enable_quiet",
    "is_quiet",
    "repl",
    "run",
    "tasks",
    "tools",
]

__version__ = "0.1.0"

_debug: bool = False


def enable_debug() -> None:
    global _debug
    _debug = True


def debug() -> bool:
    return _debug


_quiet: bool = False


def enable_quiet() -> None:
    global _quiet
    _quiet = True


def disable_quiet() -> None:
    global _quiet
    _quiet = False


def is_quiet() -> bool:
    return _quiet


def _mud_opts_from_config(cfg: Config) -> dict | None:
    """Build mud kwargs from config. Returns None if mud.username is not set."""
    if not cfg.mud_username:
        return None
    return {
        "host":     cfg.mud_host,
        "port":     cfg.mud_port,
        "name":     cfg.mud_username,
        "password": cfg.mud_password,
    }


def run(
    task: str,
    *,
    system: str | None = None,
    model: str | None = None,
    backend: str | None = None,
    api_key: str | None = None,
    ollama_host: str = "http://localhost:11434",
    log: str | None = None,
    max_output_tokens: int | None = None,
    working_dir: str | bool | None = None,
    allowed_commands: list[str] | None = None,
    shell_timeout: int = 30,
    mud: dict | bool | None = None,
    tool_registrar: Callable[[RunDSL], None] | None = None,
) -> str:
    """Wire together every primitive and run the agent loop.

    Args:
        task: The user message handed to the agent.
        system: System prompt. Defaults to the Player task's prompt from Config.
        model: Model name. Defaults to settings.yaml.
        backend: Provider name string. Defaults to settings.yaml.
        api_key: API key for the chosen backend.
        ollama_host: Ollama base URL. Defaults to "http://localhost:11434".
        log: Optional JSONL path override.
        max_output_tokens: Per-reply output cap.
        mud: MUD connection options dict (host, port, name, password).
            None (default) reads from config if mud.username is set.
            False disables MUD tools entirely.
            A dict uses those connection params directly.
        tool_registrar: A callable that accepts a RunDSL and registers tools.

    Returns:
        The agent's final text response.
    """
    cfg = Config()
    task_class = tasks.Player
    task_settings = cfg.tasks(task_class.task_name())

    resolved_system = system or task_class.system_prompt(
        task_settings,
        user_prompts_dir=cfg.user_prompts_dir,
        default_prompts_dir=Config.PROMPTS_DIR,
    )
    resolved_model = model or task_class.model(task_settings)
    resolved_backend = backend or task_class.provider(task_settings)

    resolved_api_key = api_key or {
        "anthropic": os.environ.get("ANTHROPIC_API_KEY"),
        "openai": os.environ.get("OPENAI_API_KEY"),
        "gemini": os.environ.get("GEMINI_API_KEY"),
        "ollama_cloud": os.environ.get("OLLAMA_API_KEY"),
    }.get(resolved_backend)

    resolved_wd: str | None
    if working_dir is None:
        resolved_wd = os.getcwd()
    elif not working_dir:
        resolved_wd = None
    else:
        resolved_wd = str(working_dir)

    ctx = Context(task=task_class, system=resolved_system, working_dir=resolved_wd)
    registry = Registry(ctx)

    if resolved_wd:
        tools.FileSystem.register(registry, working_dir=resolved_wd)
        tools.Shell.register(
            registry,
            working_dir=resolved_wd,
            timeout=shell_timeout,
            allowed_commands=allowed_commands,
        )

    resolved_mud = None if mud is False else (mud or _mud_opts_from_config(cfg))
    if resolved_mud:
        tools.Mud.register(registry, **resolved_mud)

    if tool_registrar is not None:
        dsl = RunDSL(registry)
        tool_registrar(dsl)

    be: Any
    if resolved_backend == "anthropic":
        be = backends.Anthropic(api_key=resolved_api_key, model=resolved_model)
    elif resolved_backend == "openai":
        be = backends.OpenAI(api_key=resolved_api_key, model=resolved_model)
    elif resolved_backend == "gemini":
        be = backends.Gemini(api_key=resolved_api_key, model=resolved_model)
    elif resolved_backend == "ollama":
        be = backends.Ollama(host=ollama_host, model=resolved_model)
    elif resolved_backend == "ollama_cloud":
        be = backends.OllamaCloud(api_key=resolved_api_key, model=resolved_model)
    else:
        raise ValueError(
            f"Unknown backend {resolved_backend!r}. "
            "Use 'anthropic', 'openai', 'gemini', 'ollama', or 'ollama_cloud'."
        )

    builder = PromptBuilder(ctx, be)
    client = Client(builder)
    effective_max_iterations = task_class.max_iterations(task_settings)
    effective_max_output_tokens = max_output_tokens or task_class.max_output_tokens(task_settings)

    logger = Logger(
        log=log,
        snapshot={
            "task": task_class.task_name(),
            "max_iterations": effective_max_iterations,
            "max_output_tokens": effective_max_output_tokens,
            "model": resolved_model,
            "provider": resolved_backend,
        },
    )
    agent = Agent(
        context=ctx,
        registry=registry,
        builder=builder,
        client=client,
        logger=logger,
        task_settings=task_settings,
        max_iterations=effective_max_iterations,
        max_output_tokens=effective_max_output_tokens,
    )

    ctx.add_message("user", task)
    try:
        return agent.run()
    finally:
        logger.close()


# Each step is a self-contained snapshot — the boilerplate below intentionally
# mirrors run() rather than sharing a helper so step 08 can be read on its own.
def repl(
    *,
    tui: bool = True,
    system: str | None = None,
    model: str | None = None,
    backend: str | None = None,
    api_key: str | None = None,
    ollama_host: str = "http://localhost:11434",
    log: str | None = None,
    max_output_tokens: int | None = None,
    working_dir: str | bool | None = None,
    allowed_commands: list[str] | None = None,
    shell_timeout: int = 30,
    mud: dict | bool | None = None,
    tool_registrar: Callable[[RunDSL], None] | None = None,
) -> None:
    """Start the interactive REPL loop.

    Same plumbing as run() but stays alive across multiple turns.
    See run() for full parameter documentation including the mud parameter.
    """
    from .repl import Repl as _Repl
    from .tui import Tui

    cfg = Config()
    task_class = tasks.Player
    task_settings = cfg.tasks(task_class.task_name())

    resolved_system = system or task_class.system_prompt(
        task_settings,
        user_prompts_dir=cfg.user_prompts_dir,
        default_prompts_dir=Config.PROMPTS_DIR,
    )
    resolved_model = model or task_class.model(task_settings)
    resolved_backend = backend or task_class.provider(task_settings)

    resolved_api_key = api_key or {
        "anthropic": os.environ.get("ANTHROPIC_API_KEY"),
        "openai": os.environ.get("OPENAI_API_KEY"),
        "gemini": os.environ.get("GEMINI_API_KEY"),
        "ollama_cloud": os.environ.get("OLLAMA_API_KEY"),
    }.get(resolved_backend)

    resolved_wd: str | None
    if working_dir is None:
        resolved_wd = os.getcwd()
    elif not working_dir:
        resolved_wd = None
    else:
        resolved_wd = str(working_dir)

    ctx = Context(task=task_class, system=resolved_system, working_dir=resolved_wd)
    registry = Registry(ctx)

    if resolved_wd:
        tools.FileSystem.register(registry, working_dir=resolved_wd)
        tools.Shell.register(
            registry,
            working_dir=resolved_wd,
            timeout=shell_timeout,
            allowed_commands=allowed_commands,
        )

    resolved_mud = None if mud is False else (mud or _mud_opts_from_config(cfg))
    if resolved_mud:
        tools.Mud.register(registry, **resolved_mud)

    if tool_registrar is not None:
        dsl = RunDSL(registry)
        tool_registrar(dsl)

    be: Any
    if resolved_backend == "anthropic":
        be = backends.Anthropic(api_key=resolved_api_key, model=resolved_model)
    elif resolved_backend == "openai":
        be = backends.OpenAI(api_key=resolved_api_key, model=resolved_model)
    elif resolved_backend == "gemini":
        be = backends.Gemini(api_key=resolved_api_key, model=resolved_model)
    elif resolved_backend == "ollama":
        be = backends.Ollama(host=ollama_host, model=resolved_model)
    elif resolved_backend == "ollama_cloud":
        be = backends.OllamaCloud(api_key=resolved_api_key, model=resolved_model)
    else:
        raise ValueError(
            f"Unknown backend {resolved_backend!r}. "
            "Use 'anthropic', 'openai', 'gemini', 'ollama', or 'ollama_cloud'."
        )

    builder = PromptBuilder(ctx, be)
    client = Client(builder)
    effective_max_iterations = task_class.max_iterations(task_settings)
    effective_max_output_tokens = max_output_tokens or task_class.max_output_tokens(task_settings)

    logger = Logger(
        log=log,
        snapshot={
            "task": task_class.task_name(),
            "max_iterations": effective_max_iterations,
            "max_output_tokens": effective_max_output_tokens,
            "model": resolved_model,
            "provider": resolved_backend,
        },
    )

    repl_instance = _Repl(
        context=ctx,
        registry=registry,
        builder=builder,
        client=client,
        logger=logger,
        task_settings=task_settings,
        max_iterations=effective_max_iterations,
        max_output_tokens=effective_max_output_tokens,
        config_dir=str(cfg.dir),
        provider=resolved_backend,
        model=resolved_model,
        version=__version__,
        api_key=resolved_api_key,
    )
    try:
        if tui:
            Tui(repl_instance).run()
        else:
            repl_instance.start()
    except KeyboardInterrupt:
        print("\nInterrupted.")
    finally:
        logger.close()
```

- [ ] **Step 6: Update `boukensha_loader.py`**

Replace `week1_baseline/python/11_tui/src/boukensha_loader.py` with the same content as Task 2 Step 4 (the `load_and_start_repl` with MUD env-var handling and `inspect.signature` tui check). The existing loader already has the `tui=sys.stdin.isatty()` logic; replace the entire `load_and_start_repl` function:

```python
def load_and_start_repl() -> None:
    src_dir = resolve()
    step_dir = str(Path(src_dir).parent)

    if os.environ.get("BOUKENSHA_DEBUG"):
        print(f"[boukensha] loading from: {step_dir}")

    for name in [m for m in list(sys.modules) if m == "boukensha" or m.startswith("boukensha.")]:
        del sys.modules[name]
    sys.path.insert(0, src_dir)

    import boukensha

    if not hasattr(boukensha, "repl"):
        raise SystemExit(
            f"boukensha: the step at {step_dir}\n"
            "       does not support the interactive REPL (added in step 08).\n"
            "       Run its examples directly, e.g.:\n"
            f"         python {step_dir}/examples/*.py\n"
            "       Or point BOUKENSHA_PATH at step 08 or later."
        )

    repl_kwargs: dict = {}

    mud_name = os.environ.get("MUD_NAME")
    if mud_name:
        mud_password = os.environ.get("MUD_PASSWORD")
        if not mud_password:
            raise SystemExit("boukensha: MUD_NAME is set but MUD_PASSWORD is missing.")
        repl_kwargs["mud"] = {
            "host":     os.environ.get("MUD_HOST", "localhost"),
            "port":     int(os.environ.get("MUD_PORT", "4000")),
            "name":     mud_name,
            "password": mud_password,
        }
        repl_kwargs["working_dir"] = False

    repl_sig = inspect.signature(boukensha.repl)
    if "tui" in repl_sig.parameters:
        repl_kwargs["tui"] = sys.stdin.isatty()

    boukensha.repl(**repl_kwargs)
```

- [ ] **Step 7: Run all tests for step 11**

```bash
cd week1_baseline/python/11_tui
uv run pytest tests/ -v
```

Expected: All tests pass.

- [ ] **Step 8: Commit**

```bash
git add week1_baseline/python/11_tui/src/boukensha/tools/mud.py \
        week1_baseline/python/11_tui/src/boukensha/tools/__init__.py \
        week1_baseline/python/11_tui/src/boukensha/__init__.py \
        week1_baseline/python/11_tui/src/boukensha_loader.py \
        week1_baseline/python/11_tui/tests/test_tools_mud.py
git commit -m "feat(11): add MUD tools (port from step 10)"
```

---

## Task 4: Apply the same changes to step 12 (`12_context`)

Step 12 differs from step 11 in: `context_window` and `max_turn_tokens` params in `run()`/`repl()`, `Context` constructor takes `context_window=`, and `Tui` is used via `Tui(repl_instance).run()` (same as step 11). The `__version__` is `"0.12.0"`.

**Files:**
- Create: `week1_baseline/python/12_context/src/boukensha/tools/mud.py`
- Modify: `week1_baseline/python/12_context/src/boukensha/tools/__init__.py`
- Modify: `week1_baseline/python/12_context/src/boukensha/__init__.py`
- Modify: `week1_baseline/python/12_context/src/boukensha_loader.py`
- Create: `week1_baseline/python/12_context/tests/test_tools_mud.py`

**Interfaces:**
- Same as Task 3, but `run()` and `repl()` also have `context_window: int = 200_000` and `max_turn_tokens: int | None = None`

- [ ] **Step 1: Copy `tools/mud.py` from step 10**

```bash
cp week1_baseline/python/10_standard_tool_library/src/boukensha/tools/mud.py \
   week1_baseline/python/12_context/src/boukensha/tools/mud.py
```

- [ ] **Step 2: Copy `tests/test_tools_mud.py` from step 10**

```bash
cp week1_baseline/python/10_standard_tool_library/tests/test_tools_mud.py \
   week1_baseline/python/12_context/tests/test_tools_mud.py
```

- [ ] **Step 3: Run tests to verify they fail**

```bash
cd week1_baseline/python/12_context
uv run pytest tests/test_tools_mud.py -v 2>&1 | head -20
```

Expected: `AttributeError: module 'boukensha.tools' has no attribute 'Mud'`

- [ ] **Step 4: Update `tools/__init__.py`**

Replace `week1_baseline/python/12_context/src/boukensha/tools/__init__.py` with:

```python
"""Boukensha built-in tool modules."""

from __future__ import annotations

from .file_system import FileSystem
from .mud import Mud
from .shell import Shell

__all__ = ["FileSystem", "Mud", "Shell"]
```

- [ ] **Step 5: Update `__init__.py`**

Replace `week1_baseline/python/12_context/src/boukensha/__init__.py` with the full content below. Key differences from step 11: `context_window` and `max_turn_tokens` params, `Context(... context_window=context_window)`, `max_turn_tokens` threaded through `Agent` and `Repl`, and `__version__ = "0.12.0"`.

```python
"""Boukensha agent loop."""

from __future__ import annotations

import os
from collections.abc import Callable
from typing import Any

from . import backends, tasks, tools
from .agent import Agent
from .client import Client
from .repl import Repl
from .config import Config
from .context import Context
from .errors import ApiError, LoopError, UnknownToolError, UnsupportedModelError
from .logger import Logger
from .message import Message
from .prompt_builder import PromptBuilder
from .registry import Registry
from .run_dsl import RunDSL
from .tool import Tool


def __getattr__(name: str):
    if name == "Tui":
        from .tui import Tui
        return Tui
    raise AttributeError(f"module 'boukensha' has no attribute {name!r}")

__all__ = [
    "Agent",
    "ApiError",
    "Client",
    "Config",
    "Context",
    "Logger",
    "LoopError",
    "Message",
    "PromptBuilder",
    "Registry",
    "Repl",
    "RunDSL",
    "Tool",
    "Tui",
    "UnknownToolError",
    "UnsupportedModelError",
    "backends",
    "debug",
    "disable_quiet",
    "enable_debug",
    "enable_quiet",
    "is_quiet",
    "repl",
    "run",
    "tasks",
    "tools",
]

__version__ = "0.12.0"

_debug: bool = False


def enable_debug() -> None:
    global _debug
    _debug = True


def debug() -> bool:
    return _debug


_quiet: bool = False


def enable_quiet() -> None:
    global _quiet
    _quiet = True


def disable_quiet() -> None:
    global _quiet
    _quiet = False


def is_quiet() -> bool:
    return _quiet


def _mud_opts_from_config(cfg: Config) -> dict | None:
    """Build mud kwargs from config. Returns None if mud.username is not set."""
    if not cfg.mud_username:
        return None
    return {
        "host":     cfg.mud_host,
        "port":     cfg.mud_port,
        "name":     cfg.mud_username,
        "password": cfg.mud_password,
    }


def run(
    task: str,
    *,
    system: str | None = None,
    model: str | None = None,
    backend: str | None = None,
    api_key: str | None = None,
    ollama_host: str = "http://localhost:11434",
    log: str | None = None,
    context_window: int = 200_000,
    max_turn_tokens: int | None = None,
    max_output_tokens: int | None = None,
    working_dir: str | bool | None = None,
    allowed_commands: list[str] | None = None,
    shell_timeout: int = 30,
    mud: dict | bool | None = None,
    tool_registrar: Callable[[RunDSL], None] | None = None,
) -> str:
    """Wire together every primitive and run the agent loop.

    Args:
        task: The user message handed to the agent.
        system: System prompt. Defaults to the Player task's prompt from Config.
        model: Model name. Defaults to settings.yaml.
        backend: Provider name string. Defaults to settings.yaml.
        api_key: API key for the chosen backend.
        ollama_host: Ollama base URL. Defaults to "http://localhost:11434".
        log: Optional JSONL path override.
        context_window: Token budget for the context window (default 200_000).
        max_turn_tokens: Per-turn token budget for compaction trigger.
        max_output_tokens: Per-reply output cap.
        mud: MUD connection options dict (host, port, name, password).
            None (default) reads from config if mud.username is set.
            False disables MUD tools entirely.
            A dict uses those connection params directly.
        tool_registrar: A callable that accepts a RunDSL and registers tools.

    Returns:
        The agent's final text response.
    """
    cfg = Config()
    task_class = tasks.Player
    task_settings = cfg.tasks(task_class.task_name())

    resolved_system = system or task_class.system_prompt(
        task_settings,
        user_prompts_dir=cfg.user_prompts_dir,
        default_prompts_dir=Config.PROMPTS_DIR,
    )
    resolved_model = model or task_class.model(task_settings)
    resolved_backend = backend or task_class.provider(task_settings)

    resolved_api_key = api_key or {
        "anthropic": os.environ.get("ANTHROPIC_API_KEY"),
        "openai": os.environ.get("OPENAI_API_KEY"),
        "gemini": os.environ.get("GEMINI_API_KEY"),
        "ollama_cloud": os.environ.get("OLLAMA_API_KEY"),
    }.get(resolved_backend)

    resolved_wd: str | None
    if working_dir is None:
        resolved_wd = os.getcwd()
    elif not working_dir:
        resolved_wd = None
    else:
        resolved_wd = str(working_dir)

    ctx = Context(task=task_class, system=resolved_system, working_dir=resolved_wd, context_window=context_window)
    registry = Registry(ctx)

    if resolved_wd:
        tools.FileSystem.register(registry, working_dir=resolved_wd)
        tools.Shell.register(
            registry,
            working_dir=resolved_wd,
            timeout=shell_timeout,
            allowed_commands=allowed_commands,
        )

    resolved_mud = None if mud is False else (mud or _mud_opts_from_config(cfg))
    if resolved_mud:
        tools.Mud.register(registry, **resolved_mud)

    if tool_registrar is not None:
        dsl = RunDSL(registry)
        tool_registrar(dsl)

    be: Any
    if resolved_backend == "anthropic":
        be = backends.Anthropic(api_key=resolved_api_key, model=resolved_model)
    elif resolved_backend == "openai":
        be = backends.OpenAI(api_key=resolved_api_key, model=resolved_model)
    elif resolved_backend == "gemini":
        be = backends.Gemini(api_key=resolved_api_key, model=resolved_model)
    elif resolved_backend == "ollama":
        be = backends.Ollama(host=ollama_host, model=resolved_model)
    elif resolved_backend == "ollama_cloud":
        be = backends.OllamaCloud(api_key=resolved_api_key, model=resolved_model)
    else:
        raise ValueError(
            f"Unknown backend {resolved_backend!r}. "
            "Use 'anthropic', 'openai', 'gemini', 'ollama', or 'ollama_cloud'."
        )

    builder = PromptBuilder(ctx, be)
    client = Client(builder)
    effective_max_iterations = task_class.max_iterations(task_settings)
    effective_max_output_tokens = max_output_tokens or task_class.max_output_tokens(task_settings)

    logger = Logger(
        log=log,
        snapshot={
            "task": task_class.task_name(),
            "max_iterations": effective_max_iterations,
            "max_output_tokens": effective_max_output_tokens,
            "model": resolved_model,
            "provider": resolved_backend,
        },
    )
    agent = Agent(
        context=ctx,
        registry=registry,
        builder=builder,
        client=client,
        logger=logger,
        task_settings=task_settings,
        max_iterations=effective_max_iterations,
        max_turn_tokens=max_turn_tokens,
        max_output_tokens=effective_max_output_tokens,
    )

    ctx.add_message("user", task)
    try:
        return agent.run()
    finally:
        logger.close()


# Each step is a self-contained snapshot — the boilerplate below intentionally
# mirrors run() rather than sharing a helper so step 08 can be read on its own.
def repl(
    *,
    tui: bool = True,
    system: str | None = None,
    model: str | None = None,
    backend: str | None = None,
    api_key: str | None = None,
    ollama_host: str = "http://localhost:11434",
    log: str | None = None,
    context_window: int = 200_000,
    max_turn_tokens: int | None = None,
    max_output_tokens: int | None = None,
    working_dir: str | bool | None = None,
    allowed_commands: list[str] | None = None,
    shell_timeout: int = 30,
    mud: dict | bool | None = None,
    tool_registrar: Callable[[RunDSL], None] | None = None,
) -> None:
    """Start the interactive REPL loop.

    Same plumbing as run() but stays alive across multiple turns.
    See run() for full parameter documentation including the mud parameter.
    """
    from .repl import Repl as _Repl

    cfg = Config()
    task_class = tasks.Player
    task_settings = cfg.tasks(task_class.task_name())

    resolved_system = system or task_class.system_prompt(
        task_settings,
        user_prompts_dir=cfg.user_prompts_dir,
        default_prompts_dir=Config.PROMPTS_DIR,
    )
    resolved_model = model or task_class.model(task_settings)
    resolved_backend = backend or task_class.provider(task_settings)

    resolved_api_key = api_key or {
        "anthropic": os.environ.get("ANTHROPIC_API_KEY"),
        "openai": os.environ.get("OPENAI_API_KEY"),
        "gemini": os.environ.get("GEMINI_API_KEY"),
        "ollama_cloud": os.environ.get("OLLAMA_API_KEY"),
    }.get(resolved_backend)

    resolved_wd: str | None
    if working_dir is None:
        resolved_wd = os.getcwd()
    elif not working_dir:
        resolved_wd = None
    else:
        resolved_wd = str(working_dir)

    ctx = Context(task=task_class, system=resolved_system, working_dir=resolved_wd, context_window=context_window)
    registry = Registry(ctx)

    if resolved_wd:
        tools.FileSystem.register(registry, working_dir=resolved_wd)
        tools.Shell.register(
            registry,
            working_dir=resolved_wd,
            timeout=shell_timeout,
            allowed_commands=allowed_commands,
        )

    resolved_mud = None if mud is False else (mud or _mud_opts_from_config(cfg))
    if resolved_mud:
        tools.Mud.register(registry, **resolved_mud)

    if tool_registrar is not None:
        dsl = RunDSL(registry)
        tool_registrar(dsl)

    be: Any
    if resolved_backend == "anthropic":
        be = backends.Anthropic(api_key=resolved_api_key, model=resolved_model)
    elif resolved_backend == "openai":
        be = backends.OpenAI(api_key=resolved_api_key, model=resolved_model)
    elif resolved_backend == "gemini":
        be = backends.Gemini(api_key=resolved_api_key, model=resolved_model)
    elif resolved_backend == "ollama":
        be = backends.Ollama(host=ollama_host, model=resolved_model)
    elif resolved_backend == "ollama_cloud":
        be = backends.OllamaCloud(api_key=resolved_api_key, model=resolved_model)
    else:
        raise ValueError(
            f"Unknown backend {resolved_backend!r}. "
            "Use 'anthropic', 'openai', 'gemini', 'ollama', or 'ollama_cloud'."
        )

    builder = PromptBuilder(ctx, be)
    client = Client(builder)
    effective_max_iterations = task_class.max_iterations(task_settings)
    effective_max_output_tokens = max_output_tokens or task_class.max_output_tokens(task_settings)

    logger = Logger(
        log=log,
        snapshot={
            "task": task_class.task_name(),
            "max_iterations": effective_max_iterations,
            "max_output_tokens": effective_max_output_tokens,
            "model": resolved_model,
            "provider": resolved_backend,
        },
    )

    repl_instance = _Repl(
        context=ctx,
        registry=registry,
        builder=builder,
        client=client,
        logger=logger,
        task_settings=task_settings,
        max_iterations=effective_max_iterations,
        max_turn_tokens=max_turn_tokens,
        max_output_tokens=effective_max_output_tokens,
        config_dir=str(cfg.dir),
        provider=resolved_backend,
        model=resolved_model,
        version=__version__,
        api_key=resolved_api_key,
    )
    try:
        if tui:
            Tui(repl_instance).run()
        else:
            repl_instance.start()
    except KeyboardInterrupt:
        print("\nInterrupted.")
    finally:
        logger.close()
```

- [ ] **Step 6: Update `boukensha_loader.py`**

Replace the `load_and_start_repl` function in `week1_baseline/python/12_context/src/boukensha_loader.py` with exactly the same implementation as Task 2 Step 4:

```python
def load_and_start_repl() -> None:
    src_dir = resolve()
    step_dir = str(Path(src_dir).parent)

    if os.environ.get("BOUKENSHA_DEBUG"):
        print(f"[boukensha] loading from: {step_dir}")

    for name in [m for m in list(sys.modules) if m == "boukensha" or m.startswith("boukensha.")]:
        del sys.modules[name]
    sys.path.insert(0, src_dir)

    import boukensha

    if not hasattr(boukensha, "repl"):
        raise SystemExit(
            f"boukensha: the step at {step_dir}\n"
            "       does not support the interactive REPL (added in step 08).\n"
            "       Run its examples directly, e.g.:\n"
            f"         python {step_dir}/examples/*.py\n"
            "       Or point BOUKENSHA_PATH at step 08 or later."
        )

    repl_kwargs: dict = {}

    mud_name = os.environ.get("MUD_NAME")
    if mud_name:
        mud_password = os.environ.get("MUD_PASSWORD")
        if not mud_password:
            raise SystemExit("boukensha: MUD_NAME is set but MUD_PASSWORD is missing.")
        repl_kwargs["mud"] = {
            "host":     os.environ.get("MUD_HOST", "localhost"),
            "port":     int(os.environ.get("MUD_PORT", "4000")),
            "name":     mud_name,
            "password": mud_password,
        }
        repl_kwargs["working_dir"] = False

    repl_sig = inspect.signature(boukensha.repl)
    if "tui" in repl_sig.parameters:
        repl_kwargs["tui"] = sys.stdin.isatty()

    boukensha.repl(**repl_kwargs)
```

- [ ] **Step 7: Run all tests for step 12**

```bash
cd week1_baseline/python/12_context
uv run pytest tests/ -v
```

Expected: All tests pass.

- [ ] **Step 8: Commit**

```bash
git add week1_baseline/python/12_context/src/boukensha/tools/mud.py \
        week1_baseline/python/12_context/src/boukensha/tools/__init__.py \
        week1_baseline/python/12_context/src/boukensha/__init__.py \
        week1_baseline/python/12_context/src/boukensha_loader.py \
        week1_baseline/python/12_context/tests/test_tools_mud.py
git commit -m "feat(12): add MUD tools (port from step 10)"
```

---

## Task 5: Add `mud:` block to `.boukensha/settings.yaml.example`

**Files:**
- Modify: `.boukensha/settings.yaml.example`

**Interfaces:**
- None (documentation only)

- [ ] **Step 1: Append the mud block to the example settings file**

Add the following to the end of `.boukensha/settings.yaml.example`:

```yaml

# MUD connection (optional — remove the mud: block entirely to disable MUD tools)
# mud:
#   host: localhost
#   port: 4000
#   username: YourCharacterName
#   password: YourPassword
```

- [ ] **Step 2: Verify file looks correct**

```bash
tail -10 .boukensha/settings.yaml.example
```

Expected: the four commented mud lines visible at the end.

- [ ] **Step 3: Commit**

```bash
git add .boukensha/settings.yaml.example
git commit -m "docs: add mud: block to settings.yaml.example"
```

---

## Self-Review Checklist

- [x] **Spec coverage:** All 28 tools covered; MUD session (connect/login/read/drain); `mud` param in `run()` and `repl()` for all three steps; `_mud_opts_from_config` helper; `boukensha_loader.py` env-var wiring; `tools/__init__.py` export; settings.yaml documentation.
- [x] **No placeholders:** All code blocks contain complete implementations.
- [x] **Type consistency:** `MudSession`, `Mud`, `_mud_opts_from_config`, `_register_with_session` — names are consistent across all tasks. `tools.Mud.register(registry, **resolved_mud)` matches the classmethod signature `register(cls, registry, *, host, port, name, password)`.
- [x] **Step 11 note:** The existing step 11 `__init__.py` uses `Tui` imported inside `repl()` — the Task 3 replacement matches that. Step 11 does NOT have `inspect` imported at the top level; the loader already had the `inspect.signature` check so the replacement is safe.
- [x] **Step 12 note:** `boukensha_loader.py` in step 12 already imports `inspect` at the top — the replacement function body does not add a new import for it, but uses it (it's already imported). Verify the existing import is present before running.
