"""Boukensha::Repl port: interactive session loop."""

from __future__ import annotations

import sys
from collections.abc import Callable
from typing import TYPE_CHECKING, Any

import boukensha
from .agent import Agent
from .errors import ApiError

if TYPE_CHECKING:
    from .context import Context
    from .logger import Logger
    from .registry import Registry

PROMPT = "boukensha> "

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
    "map_here", "map_path_to", "map_summary", "map_find_capability", "map_scan_exits",
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
        self._turn = 0
        self._output_cb: Callable[[str], None] | None = None

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

    def run_turn(self, user_input: str) -> None:
        """Run one agent turn; output goes through on_output callback (or print)."""
        self._turn += 1
        if self._logger:
            self._logger.turn(n=self._turn)

        self._context.set_goal(user_input)
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
        )
        try:
            result = agent.run()
            self._output("")
            self._output(result)
        except ApiError as e:
            self._output(f"\n[error] API call failed: {e}")

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
