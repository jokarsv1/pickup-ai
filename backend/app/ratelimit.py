"""Small in-memory rate limiter (sliding window), for one server process.

Guards sign-in against code guessing and the costly endpoints (AI chat, outbound calls) against
abuse. With several servers, move the counters to Redis.
"""

import time
from collections import defaultdict, deque

from fastapi import HTTPException, Request, status

_hits: dict[str, deque[float]] = defaultdict(deque)
_MAX_KEYS = 50_000


def check(key: str, limit: int, window_seconds: int) -> None:
    """Count one attempt for `key`; raise 429 if it went over `limit` within the window."""
    now = time.monotonic()
    hits = _hits[key]
    while hits and hits[0] <= now - window_seconds:
        hits.popleft()
    if len(hits) >= limit:
        retry = int(window_seconds - (now - hits[0])) + 1
        raise HTTPException(
            status.HTTP_429_TOO_MANY_REQUESTS,
            f"Too many attempts. Try again in {max(1, retry // 60)} minute{'s' if retry >= 120 else ''}.",
            headers={"Retry-After": str(retry)},
        )
    hits.append(now)
    if len(_hits) > _MAX_KEYS:  # drop idle keys so memory stays bounded
        for k in [k for k, v in _hits.items() if not v or v[-1] <= now - 3600][:10_000]:
            _hits.pop(k, None)


def client_ip(request: Request) -> str:
    # uvicorn runs with --proxy-headers behind Fly's proxy, so this is the caller's address.
    return request.client.host if request.client else "unknown"


def reset() -> None:
    _hits.clear()
