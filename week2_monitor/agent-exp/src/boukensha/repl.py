"""Boukensha::Repl port: interactive session loop."""

from __future__ import annotations

import sys
import threading
from collections.abc import Callable
from typing import TYPE_CHECKING, Any

import boukensha
from .agent import Agent
from .errors import ApiError, InterruptRequested

if TYPE_CHECKING:
    from .context import Context
    from .logger import Logger
    from .registry import Registry

PROMPT = "boukensha> "

AUTO_CONTINUE_DIRECTIVE = "continue toward the current goal"

HELP = """\
Commands:
  /quiet   suppress logging output
  /loud    re-enable logging output
  /clear   wipe conversation history (tools stay)
  /compact drop oldest 40% of messages to free context
  /mud     list registered MUD tool names
  /file    list registered FILE tool names
  /exit    leave the REPL
  /help    show this message"""

_MUD_TOOL_NAMES: frozenset[str] = frozenset({
    "mud_connect", "mud_disconnect", "mud_status",
    "look", "examine", "check",
    "move", "flee", "set_position", "track",
    "attack", "skill_strike", "consider",
    "say", "tell", "channel_say",
    "get_item", "drop_item", "put_item", "equip_item", "consume_item",
    "cast_spell", "use_magic_item",
    "shop", "practice", "save_character", "send_raw",
})


class Repl:
    def __init__(
        self,
        *,
        context: Context,
        registry: Registry,
        builder: Any,
        client: Any,
        logger: Logger | None,
        task_settings: dict[str, Any] | None,
        max_iterations: int | None,
        max_turn_tokens: int | None,
        max_output_tokens: int | None,
        config_dir: str | None,
        provider: str | None,
        model: str | None,
        version: str | None,
        api_key: str | None,
        goals_dir: str | None = None,
        max_auto_continues: int | None = None,
    ) -> None:
        self._context = context
        self._registry = registry
        self._builder = builder
        self._client = client
        self._logger = logger
        self._task_settings = task_settings
        self._max_iterations = max_iterations
        self._max_turn_tokens = max_turn_tokens
        self._max_output_tokens = max_output_tokens
        self._config_dir = config_dir
        self._provider = provider
        self._model = model
        self._version = version
        self._api_key = api_key
        self._goals_dir = goals_dir
        self._max_auto_continues = self._resolve_max_auto_continues(max_auto_continues)
        self._turn = 0
        self._output_cb: Callable[[str], None] | None = None
        self._interrupt_requested = threading.Event()

    def request_interrupt(self) -> None:
        self._interrupt_requested.set()

    def clear_interrupt(self) -> None:
        self._interrupt_requested.clear()

    # ── public properties ──────────────────────────────────────────────────

    @property
    def banner(self) -> str:
        return self._banner()

    @property
    def model(self) -> str | None:
        return self._model

    @property
    def version(self) -> str | None:
        return self._version

    @property
    def context(self) -> Context:
        return self._context

    @property
    def logger(self) -> Logger | None:
        return self._logger

    # ── composability API (used by Tui) ───────────────────────────────────

    def on_output(self, callback: Callable[[str], None]) -> None:
        """Route all output through *callback* instead of print()."""
        self._output_cb = callback

    def handle_command(self, text: str) -> str | None:
        """Process a slash command.

        Returns:
            "quit"    — caller should exit
            "command" — handled, no agent turn needed
            None      — not a slash command
        """
        if text in ("/exit", "/quit"):
            self._output("Goodbye.")
            return "quit"
        if text == "/help":
            self._output(HELP)
            return "command"
        if text == "/quiet":
            boukensha.enable_quiet()
            self._output("(logging suppressed — type /loud to re-enable)")
            return "command"
        if text == "/loud":
            boukensha.disable_quiet()
            self._output("(logging enabled)")
            return "command"
        if text == "/clear":
            self._context.clear_messages()
            self._turn = 0
            self._output("(conversation history cleared)")
            return "command"
        if text == "/compact":
            dropped = self._context.compact_messages()
            self._output(f"(compacted context — {dropped} messages dropped)")
            return "command"
        if text == "/mud":
            mud_tools = sorted(set(self._context.tools) & _MUD_TOOL_NAMES)
            if mud_tools:
                self._output("MUD tools:\n" + "\n".join(f"  {n}" for n in mud_tools))
            else:
                self._output("(no MUD tools registered)")
            return "command"
        if text == "/file":
            file_tools = sorted(set(self._context.tools) - _MUD_TOOL_NAMES)
            if file_tools:
                self._output("FILE tools:\n" + "\n".join(f"  {n}" for n in file_tools))
            else:
                self._output("(no FILE tools registered)")
            return "command"
        return None

    def run_turn(self, user_input: str, *, _auto_continue_count: int = 0) -> None:
        """Run one agent turn; output goes through on_output callback (or print).

        If the turn stops because it hit its iteration limit (not because the
        model finished naturally), automatically resumes with a "continue"
        turn — up to max_auto_continues times, and only while the goal is
        still marked active — so the agent keeps working toward its goal
        instead of going idle mid-task.
        """
        self._turn += 1
        if self._logger:
            self._logger.turn(n=self._turn)

        # A genuinely new instruction from the user — as opposed to this
        # method recursing on itself with AUTO_CONTINUE_DIRECTIVE — always
        # supersedes whatever goal is on disk. Without this, a stale goal
        # left over from a previous session (or a prior task the model never
        # marked completed/paused) stays "active", and if this new turn runs
        # out of iterations before the model calls goal_update itself, the
        # auto-continue below resumes it with "continue toward the current
        # goal" — which then resolves to the OLD goal, silently overriding
        # what the user just asked for.
        if user_input != AUTO_CONTINUE_DIRECTIVE and self._goals_dir:
            from .goals.goal_manager import GoalManager
            GoalManager(self._goals_dir).update(current_goal=user_input, status="active")

        self._context.add_message("user", user_input)

        agent = Agent(
            context=self._context,
            registry=self._registry,
            builder=self._builder,
            client=self._client,
            logger=self._logger,
            task_settings=self._task_settings,
            max_iterations=self._max_iterations,
            max_turn_tokens=self._max_turn_tokens,
            max_output_tokens=self._max_output_tokens,
            interrupt_event=self._interrupt_requested,
        )
        try:
            result = agent.run()
            self._output("")
            self._output(result)
        except ApiError as e:
            self._output(f"\n[error] API call failed: {e}")
            return
        except InterruptRequested:
            return

        if (
            agent.last_stop_reason == "max_iterations"
            and _auto_continue_count < self._max_auto_continues
            and self._goal_is_active()
            and not self._interrupt_requested.is_set()
        ):
            self._output(
                f"\n[auto-continuing — {_auto_continue_count + 1}/{self._max_auto_continues}]"
            )
            self.run_turn(AUTO_CONTINUE_DIRECTIVE, _auto_continue_count=_auto_continue_count + 1)

    # ── plain REPL entry point ─────────────────────────────────────────────

    def start(self) -> None:
        self._output(self._banner())

        while True:
            if not self._output_cb:
                print(PROMPT, end="", flush=True)
            line = sys.stdin.readline()
            if not line:
                break
            text = line.rstrip("\n").strip()
            if not text:
                continue

            result = self.handle_command(text)
            if result == "quit":
                break
            if result == "command":
                continue

            self.run_turn(text)

    # ── private ────────────────────────────────────────────────────────────

    def _resolve_max_auto_continues(self, explicit: int | None) -> int:
        if explicit is not None:
            return int(explicit)
        task = getattr(self._context, "task", None)
        if self._task_settings is not None and task is not None and hasattr(task, "max_auto_continues"):
            return task.max_auto_continues(self._task_settings)
        from .tasks.base import Base as _Base
        return _Base.DEFAULT_MAX_AUTO_CONTINUES

    def _goal_is_active(self) -> bool:
        if not self._goals_dir:
            return True
        from .goals.goal_manager import GoalManager
        status = GoalManager(self._goals_dir).read().get("status")
        return status not in ("completed", "paused")

    def _output(self, text: str) -> None:
        if self._output_cb:
            self._output_cb(text)
        else:
            print(text)

    def _banner(self) -> str:
        ver = self._version or "?.?.?"
        key_status = (
            "API key set"
            if self._api_key and self._api_key.strip()
            else "API key not set"
        )
        provider_line = f"{self._provider or 'default'} ({self._model or 'default'})  {key_status}"
        config_line = self._config_dir or "(default)"

        all_tools = set(self._context.tools)
        mud_count = len(all_tools & _MUD_TOOL_NAMES)
        file_count = len(all_tools - _MUD_TOOL_NAMES)
        tools_line = f"MUD ({mud_count})  FILE ({file_count})"
        pad = max(0, 9 - len(ver))
        return (
            f"\n"
            f"╔══════════════════════════════════════╗\n"
            f"║  BOUKENSHA MUD Assistant (v{ver}){' ' * pad}║\n"
            f"╚══════════════════════════════════════╝\n"
            f"  config:    {config_line}\n"
            f"  provider:  {provider_line}\n"
            f"  tools:     {tools_line}\n"
            f"\n"
            f"  /quiet or /loud   toggle logging\n"
            f"  /clear           reset conversation history\n"
            f"  /compact         free context (drop oldest messages)\n"
            f"  /mud or /file    list tools by group\n"
            f"  /exit or /quit    leave the REPL\n"
        )
