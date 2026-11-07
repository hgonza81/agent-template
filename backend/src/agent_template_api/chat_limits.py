"""Process-local controls for the chat endpoint.

These limiters live in memory, so they bound one API process. Multi-instance
deployments need a shared store (or per-instance sizing) before relying on
the rate limit as a global quota.
"""

import asyncio
import math
import threading
import time
from collections import deque
from collections.abc import Callable, Coroutine
from typing import Any, Protocol


class ClientDisconnectedError(Exception):
    """The HTTP client went away before the response was ready."""


class ConcurrencyLimiter:
    """Non-blocking cap on in-flight requests (reject, don't queue)."""

    def __init__(self, limit: int) -> None:
        self._limit = limit
        self._active = 0
        self._lock = threading.Lock()

    @property
    def active(self) -> int:
        return self._active

    def try_acquire(self) -> bool:
        with self._lock:
            if self._active >= self._limit:
                return False
            self._active += 1
            return True

    def release(self) -> None:
        with self._lock:
            self._active = max(0, self._active - 1)


class RateLimiter:
    """Sliding-window limit per key. `check` returns retry-after seconds."""

    def __init__(
        self,
        limit: int,
        window_seconds: float = 60,
        clock: Callable[[], float] = time.monotonic,
    ) -> None:
        self._limit = limit
        self._window = window_seconds
        self._clock = clock
        self._hits: dict[str, deque[float]] = {}
        self._lock = threading.Lock()

    def check(self, key: str) -> int | None:
        """Record a hit; return None if allowed, else seconds until retry."""
        now = self._clock()
        with self._lock:
            for stale in [
                k for k, hits in self._hits.items() if hits[-1] <= now - self._window
            ]:
                del self._hits[stale]
            hits = self._hits.setdefault(key, deque())
            while hits and hits[0] <= now - self._window:
                hits.popleft()
            if len(hits) >= self._limit:
                return max(1, math.ceil(hits[0] + self._window - now))
            hits.append(now)
            return None


class _Disconnectable(Protocol):
    async def is_disconnected(self) -> bool: ...


async def run_until_disconnect[T](
    request: _Disconnectable,
    work: Coroutine[Any, Any, T],
    poll_seconds: float = 0.25,
) -> T:
    """Run `work`, cancelling it if the client disconnects or we are cancelled."""
    task = asyncio.ensure_future(work)
    try:
        while True:
            done, _ = await asyncio.wait({task}, timeout=poll_seconds)
            if done:
                return task.result()
            if await request.is_disconnected():
                raise ClientDisconnectedError
    finally:
        if not task.done():
            task.cancel()
            await asyncio.gather(task, return_exceptions=True)
