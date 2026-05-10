"""Event bus pub/sub — the bridge between the worker thread and SSE clients.

Uses asyncio.run() per test so we don't need pytest-asyncio as a dep.
"""

import asyncio

from src.server.events import EventBus


def test_publish_reaches_subscriber():
    async def scenario():
        bus = EventBus()
        bus.attach_loop(asyncio.get_running_loop())
        async with bus.subscribe() as q:
            bus.publish({"id": 1, "kind": "tick_start", "message": "hi"})
            ev = await asyncio.wait_for(q.get(), timeout=1.0)
            assert ev["id"] == 1
            assert ev["message"] == "hi"

    asyncio.run(scenario())


def test_publish_without_loop_is_noop():
    """No loop attached → publish must not raise; safe to call before startup."""
    bus = EventBus()
    bus.publish({"id": 999, "kind": "tick_start", "message": "no listener"})


def test_unsubscribe_on_context_exit():
    async def scenario():
        bus = EventBus()
        bus.attach_loop(asyncio.get_running_loop())
        async with bus.subscribe() as q:
            bus.publish({"id": 1, "kind": "tick_start", "message": "in"})
            await asyncio.wait_for(q.get(), timeout=1.0)
        # After exit the queue is detached.
        assert bus._subscribers == set()
        # And further publishes don't error.
        bus.publish({"id": 2, "kind": "tick_done", "message": "after-exit"})

    asyncio.run(scenario())


def test_publish_drops_oldest_when_subscriber_full():
    """Slow subscriber gets oldest messages dropped; never blocks publisher."""
    async def scenario():
        bus = EventBus()
        bus.attach_loop(asyncio.get_running_loop())
        # Force a tiny queue so we can test the drop path.
        async with bus.subscribe() as q:
            # Patch the queue capacity so we don't have to flood.
            small_q = asyncio.Queue(maxsize=2)
            bus._subscribers.discard(q)
            bus._subscribers.add(small_q)

            bus.publish({"id": 1, "message": "first"})
            bus.publish({"id": 2, "message": "second"})
            bus.publish({"id": 3, "message": "third"})  # forces a drop

            received = []
            for _ in range(2):
                received.append(await asyncio.wait_for(small_q.get(), timeout=1.0))
            ids = [e["id"] for e in received]
            # The newest two survive; the oldest got dropped.
            assert 3 in ids

    asyncio.run(scenario())
