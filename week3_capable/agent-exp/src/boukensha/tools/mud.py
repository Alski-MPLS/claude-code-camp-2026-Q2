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
    check             — query self-info (score = HP/exp/gold/level, inventory, equipment, exits…)
    wait              — pause real seconds so server-side regen ticks can actually happen

  Movement
    move              — go a compass direction or up/down
    flee              — flee from combat
    set_position      — change body position (stand/sit/rest/sleep/wake)
    track             — track a mob or player by name
    door              — open, close, lock, or unlock a door or container
    portal            — enter a portal/vehicle, or leave the one you're in

  Combat
    attack            — attack a target
    skill_strike      — use a combat skill (bash, kick, backstab, rescue, assist)
    consider          — assess a mob's relative strength

  Communication
    say               — say/emote/reply in the room
    tell              — tell/whisper/ask a specific player
    channel_say       — broadcast over a channel (shout, gossip, auction…)

  Inventory & equipment
    get_item          — pick up an item, including looting one off a corpse
    drop_item         — drop, donate, or junk an item
    put_item          — put an item into a container
    give_item         — give an item to another player or mob
    equip_item        — wear, wield, hold, grab, or remove an item
    consume_item      — eat, drink, taste, or sip something
    pour_liquid       — pour liquid from a container into another, or out

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
from pathlib import Path
from typing import TYPE_CHECKING, Callable

from boukensha.memory.equipment_parser import parse_equipment, parse_identify
from boukensha.memory.item_stats import ItemStatsStore
from boukensha.memory.parser import RoomParser
from boukensha.memory.player_stats import PlayerStats
from boukensha.memory.room_memory import RoomMemory
from boukensha.memory.player_tracker import PlayerTracker

if TYPE_CHECKING:
    from boukensha.memory.world_graph import WorldGraph
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

# CircleMUD appends a vitals/status line before its "> " prompt after every
# command, e.g. "34H 100M 87V (news) (motd) >" — noise for tool results and
# the LLM's context, not information about the game world.
_VITALS_PROMPT_RE = re.compile(r"\r?\n?\s*\d+H\s+\d+M\s+\d+V\b[^\r\n]*>\s*$")


def _strip_vitals_prompt(text: str) -> str:
    return _VITALS_PROMPT_RE.sub("", text).rstrip()

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
_BANK_OPS      = {"deposit", "withdraw", "balance"}
_DOOR_OPS      = {"open", "close", "lock", "unlock"}
_PORTAL_OPS    = {"enter", "leave"}
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


_MAIN_MENU_SIGNATURE = "Make your choice"


def _send(session: MudSession, cmd: str) -> str:
    session.drain()
    session.send_command(cmd)
    text = _strip_vitals_prompt(session.read_until_prompt())
    if _MAIN_MENU_SIGNATURE in text:
        # The server sometimes drops the connection back to the post-login
        # main menu mid-session (e.g. after a death or a connection hiccup).
        # `cmd` above landed on the menu, not in the game, so it was never
        # actually acted on — re-enter the game and resend it for real
        # instead of leaving every future tool call getting
        # "That's not a menu choice!" forever.
        session.send_command("1")  # enter the game
        session.read_until_prompt()
        session.send_command(cmd)
        text = _strip_vitals_prompt(session.read_until_prompt())
    return text


def _check_enum(value: str, allowed: set[str], name: str) -> str | None:
    """Return None if valid, else an error string."""
    v = value.strip().lower()
    if v not in allowed:
        return f"error: invalid {name}: {value!r} (expected one of {', '.join(sorted(allowed))})"
    return None


def _match_npc(target: str, npcs: list[str]) -> str | None:
    """Fuzzy, case-insensitive match of a combat target against the NPCs
    RoomParser saw in the last room look (e.g. target='crawler' should match
    'a creepy crawler'). Corpses are filed under items, not npcs, so a room
    with only a corpse correctly has no match here."""
    t = target.strip().lower()
    if not t:
        return None
    for npc in npcs:
        n = npc.strip().lower()
        if t in n or n in t:
            return npc
    return None


def _sustenance_advisory(stats: dict[str, int | bool]) -> str:
    """Hunger/thirst are just flavor lines buried in raw `score` output —
    nothing else in the codebase reads them. This surfaces them as an
    explicit, actionable note appended to score's result (not a hard gate;
    unlike combat or a dead body, going hungry/thirsty for a while isn't
    an immediate failure) so the model actually notices and acts instead of
    needing to remember to re-read the score text carefully."""
    hungry = bool(stats.get("hungry"))
    thirsty = bool(stats.get("thirsty"))
    if not hungry and not thirsty:
        return ""
    need = "hungry and thirsty" if hungry and thirsty else ("hungry" if hungry else "thirsty")
    action = "eat and drink something" if hungry and thirsty else ("eat something" if hungry else "drink something")
    return (
        f"\n\n[Sustenance] You are {need}. Plan to {action} soon — navigate_to a known "
        "food/drink source (e.g. a bakery, or a fountain via consume_item(item=\"fountain\", "
        "mode=\"drink\")) and consume_item to actually eat/drink. Not urgent enough to interrupt "
        "a fight in progress, but don't let it go unaddressed for many turns in a row."
    )


def _level_up_advisory(previous_level: int, stats: dict[str, int | str | bool]) -> str:
    level = stats.get("level")
    title = stats.get("title", "")
    title_part = f" ({title})" if title else ""
    return (
        f"\n\n[Level up!] You are now level {level}{title_part} — up from level "
        f"{previous_level}. Consider finding a guildmaster and using practice to "
        "train any new skills before continuing to farm. If you haven't located "
        "a guildmaster yet, explore toward one; navigate_to it once it's mapped. "
        "Not urgent enough to interrupt a fight in progress."
    )


def _format_affects(affects: dict[str, int]) -> str:
    if not affects:
        return "no known bonuses"
    ordered = sorted(affects.items(), key=lambda kv: (kv[0] != "ac", kv[0]))
    return ", ".join(f"{k.upper()} {v:+d}" for k, v in ordered)


def _affects_score(affects: dict[str, int]) -> int:
    # Lower AC is better in CircleMUD, and the same holds for every SAVING_*
    # affect (saving_spell, saving_para, saving_breath, saving_rod,
    # saving_petri, ...) — every other tracked affect (hitroll, damroll,
    # stat mods) is better when higher. Negate AC and saving throws so a
    # single sum ranks both consistently.
    return sum(-v if k == "ac" or k.startswith("saving") else v for k, v in affects.items())


def _equipment_upgrade_advisory(
    parsed: dict, item_stats: "ItemStatsStore", tracker: "PlayerTracker | None", name: str
) -> str:
    item_stats.save(parsed["name"], {"wear_slot": parsed["wear_slot"], "affects": parsed["affects"]})

    slot = parsed["wear_slot"]
    if not slot or tracker is None:
        return ""

    current_slots = (tracker.read_all().get(name) or {}).get("equipment") or {}
    current_item = current_slots.get(slot)
    if not current_item or current_item.strip().lower() == parsed["name"].strip().lower():
        return ""

    current_stats = item_stats.get(current_item)
    if not current_stats:
        return ""

    new_affects = parsed["affects"]
    current_affects = current_stats.get("affects") or {}
    if _affects_score(new_affects) <= _affects_score(current_affects):
        return ""

    action = "wield" if slot == "wielded" else "wear"
    return (
        f"\n\n[Equipment] '{parsed['name']}' ({_format_affects(new_affects)}) is stronger "
        f"than what's currently worn in your {slot} slot ('{current_item}', "
        f"{_format_affects(current_affects)}). Consider equip_item(item={parsed['name']!r}, "
        f'action="{action}").'
    )


def _no_living_target_message(target: str, npcs: list[str]) -> str:
    here = ", ".join(npcs) if npcs else "nothing living — only items (possibly a corpse) or nothing at all"
    return (
        f"No living '{target}' is known to be here right now. What's actually in this room: {here}. "
        "If you're seeing a corpse, that creature is already dead — don't attack it, loot it with "
        "get_item instead. Call look with no arguments to refresh if this seems stale."
    )


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
        last_direction_ref: list[str | None] | None = None,
        memory_dir: str | Path | None = None,
        world_graph: "WorldGraph | None" = None,
        prev_hash_ref: list[str | None] | None = None,
        current_npcs_ref: list[list[str]] | None = None,
    ) -> None:
        # Recording the world graph here — not just in process_room/navigate_to —
        # means every raw 'move' updates the map immediately, so navigate_to can
        # route through ground the agent has just covered without a separate
        # process_room call in between.
        mem = RoomMemory(memory_dir) if memory_dir is not None else None
        graph = world_graph if (memory_dir is not None and world_graph is not None) else None
        tracker = PlayerTracker(memory_dir) if memory_dir is not None else None
        item_stats = ItemStatsStore(memory_dir) if memory_dir is not None else None
        _prev: list[str | None] = prev_hash_ref if prev_hash_ref is not None else [None]
        # Wrapped in a single-slot list (like _prev above) so process_room —
        # a different registrar entirely — can share and update the same
        # "who's actually alive here right now" state that combat tools read.
        _npcs: list[list[str]] = current_npcs_ref if current_npcs_ref is not None else [[]]

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

        def _look_and_record(target: str | None, preposition: str | None) -> str:
            raw = _look(session, target, preposition)
            # _look() can return a local validation/connection error (e.g.
            # "error: not connected...") without ever reaching the MUD — that
            # string must never be treated as room text.
            if raw.startswith("error:"):
                return raw
            # Only a bare "look" (the room itself) tells us who's here right
            # now — "look at X" / "look in X" describe something else.
            if not target and not preposition:
                room = RoomParser.parse(raw)
                if room["title"]:
                    _npcs[0] = room.get("npcs", [])
            return raw

        def _record_identify_if_present(raw: str) -> str:
            if raw.startswith("error:"):
                return raw
            parsed = parse_identify(raw)
            if parsed and item_stats is not None:
                raw += _equipment_upgrade_advisory(parsed, item_stats, tracker, name)
            return raw

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
            block=lambda target=None, preposition=None, **_: _look_and_record(target, preposition),
        )

        registry.tool(
            "examine",
            description="Examine a target in detail (more verbose than look).",
            parameters={
                "target": {"type": "string", "description": "The item, mob, or player to examine"},
            },
            block=lambda target, **_: _guard(session) or _send(session, f"examine {target}"),
        )

        def _check_and_record(kind: str) -> str:
            raw = _check_info(session, kind)
            k = kind.strip().lower()
            if k == "score" and not raw.startswith("error:"):
                stats = PlayerStats.parse_score(raw)
                if stats:
                    previous_level = None
                    if tracker is not None:
                        previous = (tracker.read_all().get(name) or {}).get("stats") or {}
                        previous_level = previous.get("level")
                        tracker.update_stats(name, {**previous, **stats})
                    raw += _sustenance_advisory(stats)
                    new_level = stats.get("level")
                    if (
                        previous_level is not None
                        and new_level is not None
                        and new_level > previous_level
                    ):
                        raw += _level_up_advisory(previous_level, stats)
            elif k == "equipment" and not raw.startswith("error:"):
                slots = parse_equipment(raw)
                if slots and tracker is not None:
                    tracker.update_equipment(name, slots)
            return raw

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
            block=lambda kind, **_: _check_and_record(kind),
        )

        registry.tool(
            "wait",
            description=(
                "Pause for real seconds so the MUD server's own clock can advance — use this "
                "while resting/sleeping to let HP/mana/movement regen ticks actually happen. "
                "Tool calls otherwise return near-instantly, so repeated check(kind='score') "
                "calls in a row can show zero recovery simply because no real time has passed "
                "on the server, not because regen is broken or you're stuck. After waiting, "
                "automatically reports fresh score so you don't need a separate check call."
            ),
            parameters={
                "seconds": {
                    "type": "integer",
                    "description": "How long to pause, in real seconds (default 30, max 90).",
                },
            },
            block=lambda seconds=30, **_: _wait_and_check(session, seconds, _check_and_record),
        )

        # ── Movement ──────────────────────────────────────────────────────────

        def _move_and_record(direction: str) -> str:
            if last_direction_ref is not None:
                last_direction_ref[0] = direction
            raw = _move(session, direction)
            # _move() can fail its own local validation (bad direction,
            # not connected) and return an "error: ..." string without ever
            # sending anything to the MUD. That string must never be parsed
            # as room text — doing so previously created a phantom room
            # node titled after the error message, wired into the map with
            # a real edge, and silently moved the tracked player position
            # onto it.
            if raw.startswith("error:"):
                return raw
            room = RoomParser.parse(raw)
            if room["title"]:
                # Independent of map memory — combat tools need this even
                # when memory_dir/world_graph aren't configured.
                _npcs[0] = room.get("npcs", [])
                if mem is not None and graph is not None:
                    h, _diff = mem.record(room)
                    graph.add_room(h, room["title"])
                    if _prev[0] and _prev[0] != h:
                        graph.add_edge(_prev[0], h, direction, to_room_exits=set(room.get("exits") or {}))
                    _prev[0] = h
                    graph.save()
                    if last_direction_ref is not None:
                        last_direction_ref[0] = None
                    if tracker is not None:
                        tracker.update(name, h, room["title"])
            return raw

        registry.tool(
            "move",
            description="Move in a compass direction or up/down.",
            parameters={
                "direction": {"type": "string", "description": "north | east | south | west | up | down"},
            },
            block=lambda direction, **_: _move_and_record(direction),
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

        registry.tool(
            "door",
            description=(
                "Open, close, lock, or unlock a door or container. "
                "Target may be a compass direction (e.g. 'north') for a room exit, "
                "or an item/container name."
            ),
            parameters={
                "action": {"type": "string", "description": "open | close | lock | unlock"},
                "target": {"type": "string", "description": "Direction or door/container name"},
            },
            block=lambda action, target, **_: _door(session, action, target),
        )

        registry.tool(
            "portal",
            description=(
                "Enter a portal, vehicle, or other enterable object, or leave the one "
                "you're currently in. Target is required for 'enter', ignored for 'leave'."
            ),
            parameters={
                "action": {"type": "string", "description": "enter | leave"},
                "target": {"type": "string", "description": "Name of the portal/vehicle to enter (required for 'enter')"},
            },
            block=lambda action, target=None, **_: _portal(session, action, target),
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
            block=lambda target, style="kill", **_: _attack(session, target, style, _npcs[0]),
        )

        registry.tool(
            "skill_strike",
            description="Use a combat skill against a target.",
            parameters={
                "skill":  {"type": "string", "description": "bash | kick | backstab | rescue | assist"},
                "target": {"type": "string", "description": "Name of the mob or player"},
            },
            block=lambda skill, target, **_: _skill_strike(session, skill, target, _npcs[0]),
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
            block=lambda target, **_: _consider(session, target, _npcs[0]),
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
            description=(
                "Pick up an item from the room or from a container. "
                "To loot a dead body, pass item='all' and container='corpse' "
                "(sends 'get all corpse')."
            ),
            parameters={
                "item":      {"type": "string",  "description": "Name of the item to get, or 'all' to get everything"},
                "container": {"type": "string",  "description": "Container to get it from, e.g. 'corpse' to loot a body (optional)"},
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
            "give_item",
            description="Give an item to another player or mob in the room.",
            parameters={
                "item":    {"type": "string",  "description": "Name of the item to give"},
                "target":  {"type": "string",  "description": "Name of the player or mob to give it to"},
                "count":   {"type": "integer", "description": "Number of items to give (optional)"},
            },
            block=lambda item, target, count=None, **_: _give_item(session, item, target, count),
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

        registry.tool(
            "pour_liquid",
            description=(
                "Pour liquid from one container into another, or pour a container out. "
                "Omit destination to empty the source container."
            ),
            parameters={
                "source":      {"type": "string", "description": "Container to pour from"},
                "destination": {"type": "string", "description": "Container to pour into (omit to pour out)"},
            },
            block=lambda source, destination=None, **_: _pour_liquid(session, source, destination),
        )

        # ── Magic ─────────────────────────────────────────────────────────────

        registry.tool(
            "cast_spell",
            description="Cast a spell, optionally at a target.",
            parameters={
                "spell":  {"type": "string", "description": "Full spell name (e.g. 'cure light wounds', 'magic missile')"},
                "target": {"type": "string", "description": "Target mob, player, or object (optional)"},
            },
            block=lambda spell, target=None, **_: _guard(session) or _record_identify_if_present(
                _send(session, f"cast '{spell}' {target}" if target else f"cast '{spell}'")
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
            block=lambda item, mode, target_args=None, **_: _record_identify_if_present(
                _use_magic_item(session, item, mode, target_args)
            ),
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
            "bank",
            description=(
                "Deposit, withdraw, or check gold via an automatic teller machine (ATM) "
                "fixture built into the current room's wall — only works in a room whose "
                "description mentions an ATM/teller machine; there is no separate bank room."
            ),
            parameters={
                "action": {"type": "string", "description": "deposit | withdraw | balance"},
                "amount": {"type": "integer", "description": "Gold amount (omit for balance)"},
            },
            block=lambda action, amount=None, **_: _bank(session, action, amount),
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


def _wait_and_check(session: MudSession, seconds: int, check_and_record: Callable[[str], str]) -> str:
    err = _guard(session)
    if err:
        return err
    clamped = max(1, min(int(seconds), 90))
    time.sleep(clamped)
    return f"Waited {clamped}s.\n" + check_and_record("score")


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


def _door(session: MudSession, action: str, target: str) -> str:
    err = _guard(session)
    if err:
        return err
    err = _check_enum(action, _DOOR_OPS, "action")
    if err:
        return err
    action = action.strip().lower()
    t = target.strip().lower()
    if t in _DIRECTIONS:
        return _send(session, f"{action} door {t}")
    return _send(session, f"{action} {target}")


def _portal(session: MudSession, action: str, target: str | None) -> str:
    err = _guard(session)
    if err:
        return err
    err = _check_enum(action, _PORTAL_OPS, "action")
    if err:
        return err
    action = action.strip().lower()
    if action == "enter":
        if not target:
            return "error: 'enter' requires a target"
        return _send(session, f"enter {target}")
    return _send(session, "leave")


_HOSTILE_STRIKE_SKILLS = {"bash", "kick", "backstab"}  # not rescue/assist — those target a player, not an npc


def _consider(session: MudSession, target: str, npcs: list[str]) -> str:
    err = _guard(session)
    if err:
        return err
    if not _match_npc(target, npcs):
        return _no_living_target_message(target, npcs)
    return _send(session, f"consider {target}")


def _attack(session: MudSession, target: str, style: str, npcs: list[str]) -> str:
    err = _guard(session)
    if err:
        return err
    err = _check_enum(style, _ATTACK_STYLES, "style")
    if err:
        return err
    if not _match_npc(target, npcs):
        return _no_living_target_message(target, npcs)
    return _send(session, f"{style.strip().lower()} {target}")


def _skill_strike(session: MudSession, skill: str, target: str, npcs: list[str]) -> str:
    err = _guard(session)
    if err:
        return err
    err = _check_enum(skill, _STRIKE_SKILLS, "skill")
    if err:
        return err
    if skill.strip().lower() in _HOSTILE_STRIKE_SKILLS and not _match_npc(target, npcs):
        return _no_living_target_message(target, npcs)
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


def _give_item(session: MudSession, item: str, target: str, count: int | None) -> str:
    err = _guard(session)
    if err:
        return err
    parts = ["give"]
    if count is not None:
        parts.append(str(count))
    parts.append(item)
    parts.append(target)
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


def _pour_liquid(session: MudSession, source: str, destination: str | None) -> str:
    err = _guard(session)
    if err:
        return err
    if destination:
        return _send(session, f"pour {source} {destination}")
    return _send(session, f"pour {source} out")


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


def _bank(session: MudSession, action: str, amount: int | None) -> str:
    err = _guard(session)
    if err:
        return err
    err = _check_enum(action, _BANK_OPS, "action")
    if err:
        return err
    cmd = action.strip().lower()
    if cmd != "balance" and amount:
        cmd += f" {amount}"
    return _send(session, cmd)
