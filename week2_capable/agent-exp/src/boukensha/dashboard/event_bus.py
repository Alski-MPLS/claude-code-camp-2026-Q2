"""Thread-safe SSE event queue."""

from __future__ import annotations

import json
import queue
import threading
from collections.abc import Iterator
from typing import Any


class EventBus:
    def __init__(self) -> None:
        self._queues: list[queue.Queue] = []
        self._lock = threading.Lock()

    def publish(self, event: dict[str, Any]) -> None:
        data = json.dumps(event)
        with self._lock:
            dead = []
            for q in self._queues:
                try:
                    q.put_nowait(data)
                except queue.Full:
                    dead.append(q)
            for q in dead:
                self._queues.remove(q)

    def subscribe(self) -> queue.Queue:
        q: queue.Queue = queue.Queue(maxsize=500)
        with self._lock:
            self._queues.append(q)
        return q

    def unsubscribe(self, q: queue.Queue) -> None:
        with self._lock:
            try:
                self._queues.remove(q)
            except ValueError:
                pass

    def stream(self) -> Iterator[str]:
        q = self.subscribe()
        try:
            while True:
                try:
                    data = q.get(timeout=15.0)
                    yield f"data: {data}\n\n"
                except queue.Empty:
                    yield ": heartbeat\n\n"
        finally:
            self.unsubscribe(q)
