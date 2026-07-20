"""Boukensha agent loop."""

from __future__ import annotations

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
    "Tool",
    "UnknownToolError",
    "UnsupportedModelError",
    "backends",
    "debug",
    "enable_debug",
    "tasks",
]

__version__ = "0.1.0"

_debug: bool = False


def enable_debug() -> None:
    global _debug
    _debug = True


def debug() -> bool:
    return _debug
