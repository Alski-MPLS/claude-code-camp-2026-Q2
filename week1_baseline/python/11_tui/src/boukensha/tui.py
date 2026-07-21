"""Boukensha TUI — Textual four-zone terminal UI wrapping Repl."""

from __future__ import annotations

import asyncio
import time
from concurrent.futures import Future
from typing import TYPE_CHECKING, Any

from textual.app import App, ComposeResult
from textual.widgets import Input, Label, RichLog
from textual.binding import Binding

if TYPE_CHECKING:
    from .repl import Repl

SPINNER_FRAMES = ["⠋", "⠙", "⠹", "⠸", "⠼", "⠴", "⠦", "⠧", "⠇", "⠏"]
TICK_S = 0.06
MAX_ITERATIONS = 25

CSS = """
Screen {
    layout: vertical;
}

RichLog {
    height: 1fr;
    border: none;
    scrollbar-gutter: stable;
}

#progress {
    height: 1;
    padding: 0 1;
    color: $text-muted;
}

#progress.active {
    color: cyan;
}

Input {
    height: 3;
    border: none;
    padding: 0 0;
}

#status {
    height: 1;
    background: $surface;
    color: $text;
    padding: 0 1;
}
"""


class Tui(App):
    BINDINGS = [
        Binding("ctrl+c", "quit", "Quit", show=False),
        Binding("ctrl+d", "quit", "Quit", show=False),
        Binding("ctrl+l", "clear_history", "Clear", show=False),
        Binding("escape", "interrupt_turn", "Interrupt", show=False),
        Binding("pageup", "scroll_up", "Scroll Up", show=False),
        Binding("pagedown", "scroll_down", "Scroll Down", show=False),
    ]

    CSS = CSS

    def __init__(self, repl: Repl) -> None:
        super().__init__()
        self._repl = repl
        self._turn_count = 0
        self._session_input_tokens = 0
        self._session_output_tokens = 0
        self._live: dict[str, Any] = self._idle_state()
        self._spinner_idx = 0
        self._future: Future | None = None

    # ── layout ────────────────────────────────────────────────────────────

    def compose(self) -> ComposeResult:
        yield RichLog(highlight=False, markup=False, wrap=True, id="log")
        yield Label("", id="progress")
        yield Input(placeholder="Type a message…", id="input")
        yield Label("", id="status")

    def on_mount(self) -> None:
        self._repl.on_output(self._on_repl_output)
        if self._repl.logger:
            self._repl.logger.subscribe(self._on_logger_event_from_thread)

        log = self.query_one("#log", RichLog)
        log.write(self._repl.banner)

        self.query_one("#input", Input).focus()
        self.set_interval(TICK_S, self._tick)

    # ── input submission ──────────────────────────────────────────────────

    def on_input_submitted(self, event: Input.Submitted) -> None:
        text = event.value.strip()
        event.input.clear()
        if not text:
            return

        result = self._repl.handle_command(text)
        if result == "quit":
            self.exit()
            return
        if result == "command":
            if text == "/clear":
                self._turn_count = 0
            return

        log = self.query_one("#log", RichLog)
        log.write(f"> {text}")
        self._launch_turn(text)

    # ── keyboard actions ──────────────────────────────────────────────────

    def action_quit(self) -> None:
        self.exit()

    def action_clear_history(self) -> None:
        self._repl.handle_command("/clear")
        self._turn_count = 0

    def action_interrupt_turn(self) -> None:
        if self._future and not self._future.done():
            self._future.cancel()

    def action_scroll_up(self) -> None:
        self.query_one("#log", RichLog).scroll_up(5)

    def action_scroll_down(self) -> None:
        self.query_one("#log", RichLog).scroll_down(5)

    # ── agent thread ──────────────────────────────────────────────────────

    def _launch_turn(self, text: str) -> None:
        self._live = {
            "active": True,
            "start_time": time.monotonic(),
            "elapsed": 0,
            "current_action": "Thinking…",
            "iteration": 0,
            "tool_call_count": 0,
            "turn_input_tokens": 0,
            "turn_output_tokens": 0,
        }
        loop = asyncio.get_event_loop()
        self._future = loop.run_in_executor(None, self._run_turn_sync, text)

    def _run_turn_sync(self, text: str) -> None:
        try:
            self._repl.run_turn(text)
        except Exception as e:
            self.call_from_thread(self._on_turn_error, str(e))
        finally:
            self.call_from_thread(self._on_turn_complete)

    # ── event callbacks (called from logger subscriber, thread-safe) ───────

    def _on_logger_event_from_thread(self, event: dict[str, Any]) -> None:
        self.call_from_thread(self._handle_live_event, event)

    def _handle_live_event(self, event: dict[str, Any]) -> None:
        phase = event.get("phase", "")
        if phase == "iteration":
            self._live["iteration"] = int(event.get("n", 0))
            self._live["current_action"] = "Thinking…"
        elif phase == "tool_call":
            self._live["current_action"] = f"Calling tool: {event.get('name', '')}"
            self._live["tool_call_count"] = self._live.get("tool_call_count", 0) + 1
        elif phase == "tool_result":
            self._live["current_action"] = "Awaiting result…"
        elif phase == "response":
            usage = event.get("usage") or {}
            itu = int(usage.get("input_tokens", 0))
            otu = int(usage.get("output_tokens", 0))
            self._live["turn_input_tokens"] = self._live.get("turn_input_tokens", 0) + itu
            self._live["turn_output_tokens"] = self._live.get("turn_output_tokens", 0) + otu
            self._session_input_tokens += itu
            self._session_output_tokens += otu

    def _on_repl_output(self, text: str) -> None:
        self.call_from_thread(self._append_to_log, text)

    def _append_to_log(self, text: str) -> None:
        self.query_one("#log", RichLog).write(text)

    def _on_turn_complete(self) -> None:
        self._live = self._idle_state()
        self._turn_count += 1

    def _on_turn_error(self, message: str) -> None:
        self._live = self._idle_state()
        self.query_one("#log", RichLog).write(f"[error] {message}")

    # ── periodic tick (spinner + status refresh) ──────────────────────────

    def _tick(self) -> None:
        self._spinner_idx = (self._spinner_idx + 1) % len(SPINNER_FRAMES)
        if self._live.get("active") and self._live.get("start_time"):
            self._live["elapsed"] = time.monotonic() - self._live["start_time"]
        self._refresh_progress()
        self._refresh_status()

    def _refresh_progress(self) -> None:
        label = self.query_one("#progress", Label)
        if self._live.get("active"):
            frame = SPINNER_FRAMES[self._spinner_idx]
            action = self._live.get("current_action", "")
            iteration = self._live.get("iteration", 0)
            elapsed = int(self._live.get("elapsed", 0))
            itok = _fmt_tokens(self._live.get("turn_input_tokens", 0))
            otok = _fmt_tokens(self._live.get("turn_output_tokens", 0))
            calls = self._live.get("tool_call_count", 0)
            label.update(
                f"{frame} {action}  "
                f"(iter {iteration}/{MAX_ITERATIONS} · {elapsed}s · "
                f"↑ {itok} · ↓ {otok} · {calls} calls)"
            )
            label.add_class("active")
        else:
            used = _fmt_tokens(self._session_input_tokens)
            label.update(f"  [ready]   ctx {used}   {self._turn_count} turns")
            label.remove_class("active")

    def _refresh_status(self) -> None:
        import datetime

        label = self.query_one("#status", Label)
        ver = self._repl.version or "?.?.?"
        model = self._repl.model or "(model)"
        used = _fmt_tokens(self._session_input_tokens)
        tool_count = len(self._repl.context.tools)
        clock = datetime.datetime.now().strftime("%H:%M:%S")
        label.update(
            f" boukensha v{ver} · {model}  ·  ctx {used}  ·  {tool_count} tools  ·  {clock} "
        )

    # ── helpers ───────────────────────────────────────────────────────────

    @staticmethod
    def _idle_state() -> dict[str, Any]:
        return {
            "active": False,
            "start_time": None,
            "elapsed": 0,
            "current_action": "idle",
            "iteration": 0,
            "tool_call_count": 0,
            "turn_input_tokens": 0,
            "turn_output_tokens": 0,
        }


def _fmt_tokens(n: int) -> str:
    n = int(n)
    return f"{n / 1000:.1f}k" if n >= 1000 else str(n)
