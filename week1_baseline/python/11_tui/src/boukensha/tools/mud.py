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

_DIRECTIONS    = {"north", "east", "south", "west", "up", "down"}
_POSITIONS     = {"stand", "sit", "rest", "sleep", "wake"}
_ATTACK_STYLES = {"kill", "hit", "murder"}
_STRIKE_SKILLS = {"bash", "kick", "backstab", "rescue", "assist"}
_LOCAL_SAY     = {"say", "emote", "reply"}
_TARGETED_SAY  = {"tell", "whisper", "ask"}
_CHANNELS      = {"shout", "gossip", "auction", "grats", "holler"}
_DROP_MODES    = {"drop", "donate", "junk"}
_EQUIP_OPS     = {"wear", "wield", "hold", "grab", "remove"}
_CONSUME_MODES = {"eat", "drink", "taste", "sip"}
_SHOP_OPS      = {"buy", "sell", "list", "value", "offer"}
_INFO_SELF     = {
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
                    self._closed = True  # server closed connection
                    break
                clean = _strip_telnet(chunk)
                if clean:
                    with self._lock:
                        self._buf += clean
                    self._data_event.set()
        except (OSError, ConnectionResetError):
            self._closed = True
        except Exception:
            # Unexpected error (e.g., mock objects in tests that lack fileno()).
            # Do not mark session as disconnected — leave _closed as-is.
            pass
        finally:
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
        session: "MudSession",
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
            block=lambda **_: _mud_connect(session, name, password),
        )

        registry.tool(
            "mud_disconnect",
            description="Close the connection to the MUD server gracefully.",
            parameters={},
            block=lambda **_: _mud_disconnect(session),
        )

        registry.tool(
            "mud_status",
            description="Return whether the MUD session is currently connected.",
            parameters={},
            block=lambda **_: _mud_status(session),
        )

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
            block=lambda target=None, preposition=None, **_: _look(session, target, preposition),
        )

        registry.tool(
            "examine",
            description="Examine a target in detail (more verbose than look).",
            parameters={
                "target": {"type": "string", "description": "The item, mob, or player to examine"},
            },
            block=lambda target, **_: _guard(session) or _send(session, f"examine {target}"),
        )

        registry.tool(
            "check",
            description=(
                "Query information about your character or surroundings. "
                "Use kind='score' for your core stats — HP, mana, moves, "
                "experience, level, and gold carried — all in one report. "
                "Other kinds: inventory, equipment, gold (coin purse only), "
                "exits, time, weather, levels, wimpy, toggle, where."
            ),
            parameters={
                "kind": {
                    "type": "string",
                    "description": (
                        "score | inventory | equipment | gold | exits | time | weather | "
                        "levels | wimpy | toggle | where. "
                        "Use 'score' to check health, experience, gold, and level."
                    ),
                },
            },
            block=lambda kind, **_: _check_info(session, kind),
        )

        # ── Movement ──────────────────────────────────────────────────────────

        registry.tool(
            "move",
            description="Move in a compass direction or up/down.",
            parameters={
                "direction": {"type": "string", "description": "north | east | south | west | up | down"},
            },
            block=lambda direction, **_: _move(session, direction),
        )

        registry.tool(
            "flee",
            description="Attempt to flee from combat in a random available direction.",
            parameters={},
            block=lambda **_: _guard(session) or _send(session, "flee"),
        )

        registry.tool(
            "set_position",
            description=(
                "Change body position. Use 'rest' or 'sleep' to recover HP/mana. "
                "Must be standing to move or fight."
            ),
            parameters={
                "position": {"type": "string", "description": "stand | sit | rest | sleep | wake"},
            },
            block=lambda position, **_: _set_position(session, position),
        )

        registry.tool(
            "track",
            description=(
                "Track a mob or player by name, revealing which direction they are in. "
                "Requires the Track skill."
            ),
            parameters={
                "target": {"type": "string", "description": "Name of the mob or player to track"},
            },
            block=lambda target, **_: _guard(session) or _send(session, f"track {target}"),
        )

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
            block=lambda target, style="kill", **_: _attack(session, target, style),
        )

        registry.tool(
            "skill_strike",
            description="Use a combat skill against a target.",
            parameters={
                "skill":  {"type": "string", "description": "bash | kick | backstab | rescue | assist"},
                "target": {"type": "string", "description": "Name of the mob or player"},
            },
            block=lambda skill, target, **_: _skill_strike(session, skill, target),
        )

        registry.tool(
            "consider",
            description=(
                "Assess a mob's relative strength before engaging in combat. "
                "Always consider before attacking an unknown mob."
            ),
            parameters={
                "target": {"type": "string", "description": "Name of the mob to consider"},
            },
            block=lambda target, **_: _guard(session) or _send(session, f"consider {target}"),
        )

        # ── Communication ─────────────────────────────────────────────────────

        registry.tool(
            "say",
            description="Speak or emote in the current room.",
            parameters={
                "text": {"type": "string", "description": "What to say or emote"},
                "mode": {"type": "string", "description": "say | emote | reply (default: say)"},
            },
            block=lambda text, mode="say", **_: _say_local(session, text, mode),
        )

        registry.tool(
            "tell",
            description="Send a private message to a specific player.",
            parameters={
                "target": {"type": "string", "description": "Player name to message"},
                "text":   {"type": "string", "description": "The message"},
                "mode":   {"type": "string", "description": "tell | whisper | ask (default: tell)"},
            },
            block=lambda target, text, mode="tell", **_: _say_targeted(session, target, text, mode),
        )

        registry.tool(
            "channel_say",
            description="Broadcast a message over a global channel.",
            parameters={
                "channel": {"type": "string", "description": "shout | gossip | auction | grats | holler"},
                "text":    {"type": "string", "description": "The message to broadcast"},
            },
            block=lambda channel, text, **_: _channel_say(session, channel, text),
        )

        # ── Inventory & equipment ─────────────────────────────────────────────

        registry.tool(
            "get_item",
            description="Pick up an item from the room or from a container.",
            parameters={
                "item":      {"type": "string",  "description": "Name of the item to get"},
                "container": {"type": "string",  "description": "Container to get it from (optional)"},
                "count":     {"type": "integer", "description": "Number of items to get (optional)"},
            },
            block=lambda item, container=None, count=None, **_: _get_item(session, item, container, count),
        )

        registry.tool(
            "drop_item",
            description="Drop, donate, or junk an item.",
            parameters={
                "item":  {"type": "string",  "description": "Name of the item"},
                "mode":  {"type": "string",  "description": "drop | donate | junk (default: drop)"},
                "count": {"type": "integer", "description": "Number of items (optional)"},
            },
            block=lambda item, mode="drop", count=None, **_: _drop_item(session, item, mode, count),
        )

        registry.tool(
            "put_item",
            description="Put an item into a container.",
            parameters={
                "item":      {"type": "string",  "description": "Name of the item to put"},
                "container": {"type": "string",  "description": "Name of the container"},
                "count":     {"type": "integer", "description": "Number of items (optional)"},
            },
            block=lambda item, container, count=None, **_: _put_item(session, item, container, count),
        )

        registry.tool(
            "equip_item",
            description="Wear, wield, hold, grab, or remove an item.",
            parameters={
                "item":     {"type": "string", "description": "Name of the item"},
                "action":   {"type": "string", "description": "wear | wield | hold | grab | remove"},
                "body_loc": {"type": "string", "description": "Body location to wear on (optional, e.g. 'head', 'finger')"},
            },
            block=lambda item, action, body_loc=None, **_: _equip_item(session, item, action, body_loc),
        )

        registry.tool(
            "consume_item",
            description="Eat, drink, taste, or sip a consumable item.",
            parameters={
                "item": {"type": "string", "description": "Name of the item to consume"},
                "mode": {"type": "string", "description": "eat | drink | taste | sip (default: eat)"},
            },
            block=lambda item, mode="eat", **_: _consume_item(session, item, mode),
        )

        # ── Magic ─────────────────────────────────────────────────────────────

        registry.tool(
            "cast_spell",
            description="Cast a spell, optionally at a target.",
            parameters={
                "spell":  {"type": "string", "description": "Full spell name (e.g. 'cure light wounds', 'magic missile')"},
                "target": {"type": "string", "description": "Target mob, player, or object (optional)"},
            },
            block=lambda spell, target=None, **_: _guard(session) or _send(
                session, f"cast '{spell}' {target}" if target else f"cast '{spell}'"
            ),
        )

        registry.tool(
            "use_magic_item",
            description="Activate a magic item: quaff a potion, recite a scroll, or use a wand/staff.",
            parameters={
                "item":        {"type": "string", "description": "Name of the item to activate"},
                "mode":        {"type": "string", "description": "quaff | recite | use"},
                "target_args": {"type": "string", "description": "Optional target arguments (e.g. mob name for a wand)"},
            },
            block=lambda item, mode, target_args=None, **_: _use_magic_item(session, item, mode, target_args),
        )

        # ── Utility ───────────────────────────────────────────────────────────

        registry.tool(
            "shop",
            description="Interact with a shop NPC: list stock, buy, sell, or get item value.",
            parameters={
                "action": {"type": "string", "description": "list | buy | sell | value | offer"},
                "args":   {"type": "string", "description": "Item name or number (optional)"},
            },
            block=lambda action, args=None, **_: _shop(session, action, args),
        )

        registry.tool(
            "practice",
            description="List your known skills at a guildmaster, or practice a specific skill.",
            parameters={
                "skill": {"type": "string", "description": "Skill name to practice (omit to list all)"},
            },
            block=lambda skill=None, **_: _guard(session) or _send(
                session, f"practice {skill}" if skill else "practice"
            ),
        )

        registry.tool(
            "save_character",
            description="Save your character to disk so progress is not lost on disconnect.",
            parameters={},
            block=lambda **_: _guard(session) or _send(session, "save"),
        )

        registry.tool(
            "send_raw",
            description=(
                "Send an arbitrary command string to the MUD and return the response. "
                "Use as an escape hatch when no structured tool fits."
            ),
            parameters={
                "command": {"type": "string", "description": "The raw command to send (e.g. 'who', 'help backstab')"},
            },
            block=lambda command, **_: _guard(session) or _send(session, command),
        )

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
