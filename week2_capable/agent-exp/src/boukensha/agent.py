"""Boukensha::Agent port: drives the tool-call loop until the model signals
done or an iteration/token ceiling is reached.
"""

from __future__ import annotations

import json
from typing import TYPE_CHECKING, Any

import boukensha

from .errors import ApiError

if TYPE_CHECKING:
    from .logger import Logger

MAX_ITERATIONS = 25
WRAP_UP_OUTPUT_TOKENS = 400
WRAP_UP_DIRECTIVE = (
    "You have reached your action limit for this turn. Do not call any more tools.\n"
    "Briefly summarize what you accomplished, what is still unfinished, and the\n"
    "single next action you would take."
)

# How many consecutive tool calls with the identical (name, args, result) — or
# just the identical result, e.g. repeated "Alas, you cannot go that way..."
# across different directions — before the loop is considered stuck.
STUCK_REPEAT_THRESHOLD = 3
STUCK_WRAP_UP_DIRECTIVE = (
    "You have repeated the same failed action (or kept getting the same failure) several\n"
    "times in a row without making progress. Do not call any more tools. Briefly explain\n"
    "what you were trying to do, why it isn't working, and one concretely different next\n"
    "step — or say that you need the user's help."
)


class Agent:
    def __init__(
        self,
        *,
        context: Any,
        registry: Any,
        builder: Any,
        client: Any,
        logger: Logger | None = None,
        task_settings: dict[str, Any] | None = None,
        max_iterations: int | None = None,
        max_turn_tokens: int | None = None,
        max_output_tokens: int | None = None,
    ) -> None:
        self._context = context
        self._registry = registry
        self._builder = builder
        self._client = client
        if logger is None:
            from .logger import Logger as _Logger
            logger = _Logger()
        self._logger = logger
        self._max_iterations = self._resolve_max_iterations(task_settings, max_iterations)
        self._max_turn_tokens = int(max_turn_tokens or 0)
        self._max_output_tokens = self._resolve_max_output_tokens(task_settings, max_output_tokens)
        self._iteration = 0
        self.last_stop_reason = "completed"
        self._last_action_key: tuple[str, str, str] | None = None
        self._same_action_streak = 0
        self._last_result_key: str | None = None
        self._same_result_streak = 0
        self._stuck = False

    def run(self) -> str:
        self._context.reset_turn_tokens()
        self._compact_if_needed()

        while True:
            if self._iteration_limit_reached():
                if self._logger:
                    self._logger.limit_reached(
                        kind="max_iterations", n=self._iteration, max=self._max_iterations
                    )
                self.last_stop_reason = "max_iterations"
                return self._wrap_up("max_iterations")

            if self._token_limit_reached():
                if self._logger:
                    self._logger.limit_reached(
                        kind="max_tokens",
                        n=self._context.turn_tokens,
                        max=self._max_turn_tokens,
                    )
                self.last_stop_reason = "max_tokens"
                return self._wrap_up("max_tokens")

            self._iteration += 1
            if self._logger:
                self._logger.iteration(n=self._iteration, max=self._max_iterations)
                self._logger.prompt(
                    messages=self._context.messages,
                    tools=self._context.tools,
                    context_window=self._context.context_window,
                )
            if not boukensha.is_quiet():
                print(f"[iteration {self._iteration}/{self._max_iterations}]")

            response = self._client.call(**self._call_opts())
            if self._logger:
                self._logger.raw(data=response)
            parsed = self._builder.parse_response(response)
            self._record_usage(response)
            self._log_reasoning(parsed["content"])

            if parsed["stop_reason"] == "tool_use":
                self._handle_tool_calls(parsed["content"], response)
                if self._stuck:
                    if self._logger:
                        self._logger.limit_reached(
                            kind="stuck_repetition",
                            n=self._iteration,
                            max=STUCK_REPEAT_THRESHOLD,
                        )
                    self.last_stop_reason = "stuck_repetition"
                    return self._wrap_up("stuck_repetition")
            else:
                text = self._extract_text(parsed["content"])
                self._log_response(text=text, response=response)
                if self._logger:
                    self._logger.turn_end(
                        reason="completed",
                        iterations=self._iteration,
                        tokens=self._context.turn_tokens,
                    )
                self._context.add_message("assistant", text)
                return text

    # ---------- private -----------------------------------------------------

    def _resolve_max_iterations(
        self, task_settings: dict[str, Any] | None, explicit: int | None
    ) -> int:
        if explicit is not None:
            return int(explicit)
        if task_settings is not None and hasattr(self._context.task, "max_iterations"):
            return self._context.task.max_iterations(task_settings)
        return MAX_ITERATIONS

    def _resolve_max_output_tokens(
        self, task_settings: dict[str, Any] | None, explicit: int | None
    ) -> int | None:
        if explicit is not None:
            return explicit
        if task_settings is not None and hasattr(self._context.task, "max_output_tokens"):
            return self._context.task.max_output_tokens(task_settings)
        return None

    def _iteration_limit_reached(self) -> bool:
        return self._max_iterations > 0 and self._iteration >= self._max_iterations

    def _token_limit_reached(self) -> bool:
        return self._max_turn_tokens > 0 and self._context.turn_tokens >= self._max_turn_tokens

    def _call_opts(self) -> dict[str, Any]:
        if self._max_output_tokens is not None:
            return {"max_output_tokens": self._max_output_tokens}
        return {}

    def _record_usage(self, response: Any) -> None:
        usage = response.get("usage", {}) if isinstance(response, dict) else {}
        input_tok = int(usage.get("input_tokens", 0))
        output_tok = int(usage.get("output_tokens", 0))
        self._context.add_turn_tokens(input_tok, output_tok)
        self._context.update_tokens(input_tok)

    def _compact_if_needed(self) -> None:
        if not self._context.needs_compaction():
            return
        before = self._context.current_tokens
        dropped = self._context.compact_messages()
        if self._logger:
            self._logger.compaction(
                before=before,
                dropped=dropped,
                context_window=self._context.context_window,
            )

    def _wrap_up(self, reason: str) -> str:
        directive = STUCK_WRAP_UP_DIRECTIVE if reason == "stuck_repetition" else WRAP_UP_DIRECTIVE
        self._context.add_message("user", directive)
        try:
            response = self._client.call(tools=[], max_output_tokens=WRAP_UP_OUTPUT_TOKENS)
            parsed = self._builder.parse_response(response)
            text = self._extract_text(parsed["content"])
            result = text.strip() or self._fallback_message(reason)
            self._record_usage(response)
            self._log_response(text=result, response=response)
            if self._logger:
                self._logger.turn_end(
                    reason=reason,
                    iterations=self._iteration,
                    tokens=self._context.turn_tokens,
                )
            self._context.add_message("assistant", result)
            return result
        except ApiError:
            msg = self._fallback_message(reason)
            if self._logger:
                self._logger.turn_end(
                    reason=reason,
                    iterations=self._iteration,
                    tokens=self._context.turn_tokens,
                )
            self._context.add_message("assistant", msg)
            return msg

    def _fallback_message(self, reason: str) -> str:
        if reason == "stuck_repetition":
            return (
                "I repeated the same failed action without making progress, so I stopped "
                "instead of retrying it. Let me know how you'd like to proceed."
            )
        return (
            f"I reached my {self._max_iterations}-action limit for this turn before finishing "
            f"({reason}). Ask me to continue and I'll pick up from here."
        )

    def _extract_text(self, content: list[dict[str, Any]]) -> str:
        return "".join(b["text"] for b in content if b.get("type") == "text")

    def _log_reasoning(self, content: list[dict[str, Any]]) -> None:
        if not self._logger:
            return
        for block in content:
            if block.get("type") != "reasoning":
                continue
            redacted = block.get("redacted") is True
            text = str(block.get("text", ""))
            if not text.strip() and not redacted:
                continue
            self._logger.reasoning(text=text, redacted=redacted)

    def _log_response(self, *, text: str, response: Any) -> None:
        if not self._logger:
            return
        self._logger.response(
            text=text,
            usage=_normalized_usage(response),
            stop_reason=response.get("stop_reason") if isinstance(response, dict) else None,
            task=self._context.task,
            backend=self._builder.backend,
        )

    def _handle_tool_calls(self, content: list[dict[str, Any]], response: Any) -> None:
        reasoning = self._extract_text(content)
        tool_calls = [b for b in content if b.get("type") == "tool_use"]
        display = reasoning.strip() or f"(tool use — {len(tool_calls)} call{'s' if len(tool_calls) != 1 else ''})"
        self._log_response(text=display, response=response)

        self._context.add_message("assistant", content)

        for block in tool_calls:
            name = block["name"]
            args = block["input"]
            use_id = block["id"]

            if self._logger:
                self._logger.tool_call(name=name, args=args)
            if not boukensha.is_quiet():
                print(f"  tool call -> {name}({args})")
            try:
                result = self._registry.dispatch(name, args)
                if self._logger:
                    self._logger.tool_result(name=name, result=result, ok=True)
            except Exception as e:
                result = f"ERROR: {type(e).__name__}: {e}"
                if self._logger:
                    self._logger.tool_result(name=name, result=result, ok=False, error=str(e))
            if not boukensha.is_quiet():
                print(f"  tool result -> {str(result)[:61]}")

            self._context.add_message("tool_result", str(result), tool_use_id=use_id)
            self._track_repetition(name, args, result)

    def _track_repetition(self, name: str, args: Any, result: Any) -> None:
        # Flags _stuck once the same call, or just the same result under
        # different args, has repeated STUCK_REPEAT_THRESHOLD times running.
        try:
            args_key = json.dumps(args, sort_keys=True, default=str)
        except TypeError:
            args_key = str(args)
        result_key = str(result)

        action_key = (name, args_key, result_key)
        if action_key == self._last_action_key:
            self._same_action_streak += 1
        else:
            self._last_action_key = action_key
            self._same_action_streak = 1

        if result_key == self._last_result_key:
            self._same_result_streak += 1
        else:
            self._last_result_key = result_key
            self._same_result_streak = 1

        if (
            self._same_action_streak >= STUCK_REPEAT_THRESHOLD
            or self._same_result_streak >= STUCK_REPEAT_THRESHOLD
        ):
            self._stuck = True


def _normalized_usage(response: Any) -> dict[str, Any] | None:
    if not isinstance(response, dict):
        return None
    if "usage" in response:
        return response["usage"]
    if "usageMetadata" in response:
        return response["usageMetadata"]
    usage = {k: response[k] for k in ("prompt_eval_count", "eval_count") if k in response}
    return usage or None
