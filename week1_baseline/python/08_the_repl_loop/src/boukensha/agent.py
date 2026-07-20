"""Boukensha::Agent port: drives the tool-call loop until the model signals
done or the iteration ceiling is reached.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

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
        self._max_output_tokens = self._resolve_max_output_tokens(task_settings, max_output_tokens)
        self._iteration = 0

    def run(self) -> str:
        while True:
            if self._iteration_limit_reached():
                if self._logger:
                    self._logger.limit_reached(
                        kind="max_iterations", n=self._iteration, max=self._max_iterations
                    )
                return self._wrap_up("max_iterations")

            self._iteration += 1
            if self._logger:
                self._logger.iteration(n=self._iteration, max=self._max_iterations)
                self._logger.prompt(messages=self._context.messages, tools=self._context.tools)
            print(f"[iteration {self._iteration}/{self._max_iterations}]")

            response = self._client.call(**self._call_opts())
            if self._logger:
                self._logger.raw(data=response)
            parsed = self._builder.parse_response(response)

            if parsed["stop_reason"] == "tool_use":
                self._handle_tool_calls(parsed["content"], response)
            else:
                text = self._extract_text(parsed["content"])
                self._log_response(text=text, response=response)
                if self._logger:
                    self._logger.turn_end(reason="completed", iterations=self._iteration)
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

    def _call_opts(self) -> dict[str, Any]:
        if self._max_output_tokens is not None:
            return {"max_output_tokens": self._max_output_tokens}
        return {}

    def _wrap_up(self, reason: str) -> str:
        self._context.add_message("user", WRAP_UP_DIRECTIVE)
        try:
            response = self._client.call(tools=[], max_output_tokens=WRAP_UP_OUTPUT_TOKENS)
            text = self._extract_text(self._builder.parse_response(response)["content"])
            result = text.strip() or self._fallback_message(reason)
            self._log_response(text=result, response=response)
            if self._logger:
                self._logger.turn_end(reason=reason, iterations=self._iteration)
            return result
        except ApiError:
            msg = self._fallback_message(reason)
            if self._logger:
                self._logger.turn_end(reason=reason, iterations=self._iteration)
            return msg

    def _fallback_message(self, reason: str) -> str:
        return (
            f"I reached my {self._max_iterations}-action limit for this turn before finishing "
            f"({reason}). Ask me to continue and I'll pick up from here."
        )

    def _extract_text(self, content: list[dict[str, Any]]) -> str:
        return "".join(b["text"] for b in content if b.get("type") == "text")

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
            print(f"  tool call -> {name}({args})")
            try:
                result = self._registry.dispatch(name, args)
                if self._logger:
                    self._logger.tool_result(name=name, result=result, ok=True)
            except Exception as e:
                result = f"ERROR: {type(e).__name__}: {e}"
                if self._logger:
                    self._logger.tool_result(name=name, result=result, ok=False, error=str(e))
            print(f"  tool result -> {str(result)[:61]}")

            self._context.add_message("tool_result", str(result), tool_use_id=use_id)


def _normalized_usage(response: Any) -> dict[str, Any] | None:
    if not isinstance(response, dict):
        return None
    if "usage" in response:
        return response["usage"]
    if "usageMetadata" in response:
        return response["usageMetadata"]
    usage = {k: response[k] for k in ("prompt_eval_count", "eval_count") if k in response}
    return usage or None
