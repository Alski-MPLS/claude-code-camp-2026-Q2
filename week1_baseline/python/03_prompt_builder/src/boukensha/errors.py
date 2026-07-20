"""Boukensha-specific error classes.

Ruby's ``UnknownToolError < StandardError`` and
``UnsupportedModelError < StandardError`` both map to Python's ``Exception``
— the base for ordinary application errors (not ``BaseException``, which is
reserved for system-exiting conditions like ``SystemExit``/``KeyboardInterrupt``).
"""

from __future__ import annotations


class UnknownToolError(Exception):
    """Raised when dispatch is called with a name that has no registered tool."""


class UnsupportedModelError(Exception):
    """Raised when a backend is configured with a model it does not support."""
