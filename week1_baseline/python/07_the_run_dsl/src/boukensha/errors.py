"""Boukensha-specific error classes."""

from __future__ import annotations


class UnknownToolError(Exception):
    """Raised when dispatch is called with a name that has no registered tool."""


class UnsupportedModelError(Exception):
    """Raised when a backend is configured with a model it does not support."""


class ApiError(Exception):
    """Raised when an HTTP request to the LLM API fails."""


class LoopError(Exception):
    """Raised when the agent loop exceeds its iteration ceiling."""
