"""Boukensha agent loop."""

from __future__ import annotations

import os
from typing import Any

from . import backends, tasks
from .agent import Agent
from .client import Client
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
    "RunDSL",
    "Tool",
    "UnknownToolError",
    "UnsupportedModelError",
    "backends",
    "debug",
    "enable_debug",
    "run",
    "tasks",
]

__version__ = "0.1.0"

_debug: bool = False


def enable_debug() -> None:
    global _debug
    _debug = True


def debug() -> bool:
    return _debug


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
    tool_registrar: Any = None,
) -> str:
    """Wire together every primitive and run the agent loop.

    The caller supplies *what* to do (task text + optional tools via a
    ``RunDSL`` closure); this function handles all plumbing.

    Args:
        task: The user message handed to the agent.
        system: System prompt. Defaults to the Player task's prompt from Config.
        model: Model name. Defaults to the player task's model from settings.yaml.
        backend: Provider name string — "anthropic", "openai", "gemini", "ollama",
            or "ollama_cloud". Defaults to the player task's provider from settings.yaml.
        api_key: API key for the chosen backend. Defaults to the matching
            ``ANTHROPIC_API_KEY`` / ``OPENAI_API_KEY`` / ``GEMINI_API_KEY`` /
            ``OLLAMA_API_KEY`` env var.
        ollama_host: Ollama base URL. Defaults to "http://localhost:11434".
        log: Optional JSONL path override. Defaults to
            ``.boukensha/sessions/<session-id>.jsonl``.
        max_output_tokens: Per-reply output cap. Defaults to the player task's
            setting (1024).
        tool_registrar: A callable that accepts a ``RunDSL`` and registers tools
            on it. Typical usage is via the module-level ``run()`` function
            called with a helper; the example script uses a plain function.

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

    ctx = Context(task=task_class, system=resolved_system)
    registry = Registry(ctx)

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
