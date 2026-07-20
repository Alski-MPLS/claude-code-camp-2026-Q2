"""Boukensha-specific error classes.

Ruby's ``UnknownToolError < StandardError`` maps to Python's
``Exception`` — the base for ordinary application errors (not
``BaseException``, which is reserved for system-exiting conditions like
``SystemExit``/``KeyboardInterrupt``).
"""

from __future__ import annotations


class UnknownToolError(Exception):
    """Raised when dispatch is called with a name that has no registered tool."""
