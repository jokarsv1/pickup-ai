"""In-process pub/sub with optional Redis fan-out across instances.

Topics:
  user:{user_id}  events for the user's phone (call started, transcript, intent, summary ...)
  call:{call_id}  control commands for the voice agent handling that call (say, take over, end)

With REDIS_URL set, every publish goes through Redis and each instance relays messages to its
local subscribers, so the WebSocket and the voice agent can live on different servers.
"""

import asyncio
import contextlib
import json
from collections import defaultdict
from collections.abc import AsyncIterator
from typing import Any

from loguru import logger

CHANNEL_PREFIX = "pickup:"


class EventBus:
    def __init__(self) -> None:
        self._subscribers: dict[str, set[asyncio.Queue]] = defaultdict(set)
        self._redis = None
        self._listener: asyncio.Task | None = None

    async def start(self, redis_url: str | None) -> None:
        if not redis_url:
            return
        from redis import asyncio as aioredis

        self._redis = aioredis.from_url(redis_url, decode_responses=True)
        self._listener = asyncio.create_task(self._listen())
        logger.info("Event bus using Redis")

    async def stop(self) -> None:
        if self._listener:
            self._listener.cancel()
            with contextlib.suppress(asyncio.CancelledError):
                await self._listener
        if self._redis:
            await self._redis.aclose()

    async def publish(self, topic: str, event: dict[str, Any]) -> None:
        if self._redis is not None:
            await self._redis.publish(CHANNEL_PREFIX + topic, json.dumps(event, default=str))
        else:
            self._deliver(topic, event)

    def _deliver(self, topic: str, event: dict[str, Any]) -> None:
        for queue in list(self._subscribers.get(topic, ())):
            try:
                queue.put_nowait(event)
            except asyncio.QueueFull:
                logger.warning(f"Dropping event for slow subscriber on {topic}")

    async def _listen(self) -> None:
        assert self._redis is not None
        pubsub = self._redis.pubsub()
        await pubsub.psubscribe(CHANNEL_PREFIX + "*")
        try:
            async for message in pubsub.listen():
                if message.get("type") != "pmessage":
                    continue
                topic = str(message["channel"])[len(CHANNEL_PREFIX) :]
                try:
                    self._deliver(topic, json.loads(message["data"]))
                except (TypeError, ValueError):
                    logger.warning("Ignoring malformed event")
        finally:
            await pubsub.aclose()

    @contextlib.asynccontextmanager
    async def subscribe(self, topic: str, maxsize: int = 256) -> AsyncIterator[asyncio.Queue]:
        queue: asyncio.Queue = asyncio.Queue(maxsize=maxsize)
        self._subscribers[topic].add(queue)
        try:
            yield queue
        finally:
            self._subscribers[topic].discard(queue)
            if not self._subscribers[topic]:
                self._subscribers.pop(topic, None)

    def has_local_subscribers(self, topic: str) -> bool:
        return bool(self._subscribers.get(topic))


bus = EventBus()


def user_topic(user_id: str) -> str:
    return f"user:{user_id}"


def call_topic(call_id: str) -> str:
    return f"call:{call_id}"
