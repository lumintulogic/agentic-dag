"""Thread-safe mechanism for waiting on human review responses.

When the Telegram bot is started from the web server, both the bot polling
thread and the FastAPI request threads live in the same process.  This module
bridges the two: the bot thread *notifies* when a review reply arrives, and
an HTTP handler (or any other caller) can *wait* for that notification.
"""
from __future__ import annotations

import threading


class ReviewWaiter:
    """Allows callers to block until a review response arrives for a given node."""

    def __init__(self) -> None:
        self._events: dict[str, threading.Event] = {}
        self._results: dict[str, dict] = {}
        self._lock = threading.Lock()

    def wait(self, node_id: str, timeout: float = 300) -> dict | None:
        """Block until a review result is available for *node_id*, or *timeout* seconds elapse.

        Returns the review result dict on success, or ``None`` on timeout.
        """
        with self._lock:
            # If a result arrived before anyone started waiting, return immediately.
            if node_id in self._results:
                return self._results.pop(node_id)
            if node_id not in self._events:
                self._events[node_id] = threading.Event()
            event = self._events[node_id]

        signaled = event.wait(timeout=timeout)

        with self._lock:
            self._events.pop(node_id, None)
            if signaled:
                return self._results.pop(node_id, None)
            return None

    def notify(self, node_id: str, result: dict) -> None:
        """Signal that a review response has been received for *node_id*."""
        with self._lock:
            self._results[node_id] = result
            event = self._events.get(node_id)
        # Set outside the lock so waiting threads wake up without contention.
        if event:
            event.set()
