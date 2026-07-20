"""Boukensha::Repl port: interactive session loop.

Wraps the same primitives as a single boukensha.run() call but stays alive:
reads a task from stdin, runs the agent, prints the reply, and loops back.
The Context is shared across every turn so conversation history accumulates.
"""

from __future__ import annotations

import sys
from typing import TYPE_CHECKING, Any

import boukensha
from .agent import Agent
from .errors import ApiError, LoopError

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
  /exit    leave the REPL
  /help    show this message"""


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
        self._max_output_tokens = max_output_tokens
        self._config_dir = config_dir
        self._provider = provider
        self._model = model
        self._version = version
        self._api_key = api_key
        self._turn = 0

    def start(self) -> None:
        print(self._banner())

        for line in sys.stdin:
            text = line.rstrip("\n").strip()
            if not text:
                continue

            if text in ("/exit", "/quit"):
                print("Goodbye.")
                break
            elif text == "/help":
                print(HELP)
            elif text == "/quiet":
                boukensha.enable_quiet()
                print("(logging suppressed — type /loud to re-enable)")
            elif text == "/loud":
                boukensha.disable_quiet()
                print("(logging enabled)")
            elif text == "/clear":
                self._context.clear_messages()
                self._turn = 0
                print("(conversation history cleared)")
            else:
                self._run_turn(text)

    def _banner(self) -> str:
        ver = self._version or "?.?.?"
        key_status = (
            "API key set"
            if self._api_key and self._api_key.strip()
            else "API key not set"
        )
        provider_line = f"{self._provider or 'default'} ({self._model or 'default'})  {key_status}"
        config_line = self._config_dir or "(default)"

        pad = max(0, 9 - len(ver))
        return (
            f"\n"
            f"╔══════════════════════════════════════╗\n"
            f"║  BOUKENSHA MUD Assistant (v{ver}){' ' * pad}║\n"
            f"╚══════════════════════════════════════╝\n"
            f"  config:    {config_line}\n"
            f"  provider:  {provider_line}\n"
            f"\n"
            f"  /quiet or /loud   toggle logging\n"
            f"  /clear           reset conversation history\n"
            f"  /exit or /quit    leave the REPL\n"
        )

    def _run_turn(self, user_input: str) -> None:
        self._turn += 1
        if self._logger:
            self._logger.turn(n=self._turn)

        self._context.add_message("user", user_input)

        agent = Agent(
            context=self._context,
            registry=self._registry,
            builder=self._builder,
            client=self._client,
            logger=self._logger,
            task_settings=self._task_settings,
            max_iterations=self._max_iterations,
            max_output_tokens=self._max_output_tokens,
        )
        try:
            result = agent.run()
            print()
            print(result)
        except LoopError as e:
            print(f"\n[error] {e}")
        except ApiError as e:
            print(f"\n[error] API call failed: {e}")
