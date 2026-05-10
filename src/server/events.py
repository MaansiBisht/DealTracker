"""In-process event bus for the SSE terminal stream.

The runner emits Event rows from APScheduler's worker thread; SSE
clients consume them from FastAPI's asyncio loop. Crossing that
boundary safely is what this module is for.

Each subscription is an asyncio.Queue. publish() is callable from any
thread — it hands payloads to subscribers via loop.call_soon_threadsafe.
Slow subscribers don't block fast publishers (oldest message is dropped
when a queue fills).
"""

from __future__ import annotations

import asyncio
import logging
from contextlib import asynccontextmanager
from typing import Any, AsyncIterator


log = logging.getLogger("dealtracker.events")

QUEUE_CAPACITY = 200


class EventBus:
    def __init__(self) -> None:
        self._loop: asyncio.AbstractEventLoop | None = None
        self._subscribers: set[asyncio.Queue[dict[str, Any]]] = set()

    def attach_loop(self, loop: asyncio.AbstractEventLoop) -> None:
        """Called once during FastAPI lifespan startup."""
        self._loop = loop

    def publish(self, payload: dict[str, Any]) -> None:
        """Thread-safe: safe to call from APScheduler worker threads."""
        loop = self._loop
        if loop is None or loop.is_closed():
            return
        for q in list(self._subscribers):
            loop.call_soon_threadsafe(self._safe_put, q, payload)

    @asynccontextmanager
    async def subscribe(self) -> AsyncIterator[asyncio.Queue[dict[str, Any]]]:
        q: asyncio.Queue[dict[str, Any]] = asyncio.Queue(maxsize=QUEUE_CAPACITY)
        self._subscribers.add(q)
        try:
            yield q
        finally:
            self._subscribers.discard(q)

    @staticmethod
    def _safe_put(q: asyncio.Queue[dict[str, Any]], payload: dict[str, Any]) -> None:
        """Best-effort enqueue — drops the oldest pending message if full."""
        try:
            q.put_nowait(payload)
            return
        except asyncio.QueueFull:
            pass
        try:
            q.get_nowait()
            q.put_nowait(payload)
        except (asyncio.QueueEmpty, asyncio.QueueFull):
            log.warning("event bus dropped a message — slow subscriber")


bus = EventBus()
