"""Cooperative process-local request rate limiting."""

from __future__ import annotations

import asyncio
import time
from collections import deque
from collections.abc import Awaitable, Callable


class RateLimiter:
    """A sliding-window limiter shared by all requests of one client."""

    def __init__(
        self,
        limit: int = 50,
        period: float = 1.0,
        *,
        clock: Callable[[], float] = time.monotonic,
        sleep: Callable[[float], Awaitable[None]] = asyncio.sleep,
    ) -> None:
        if limit <= 0:
            raise ValueError("limit must be positive")
        if period <= 0:
            raise ValueError("period must be positive")
        self.limit = limit
        self.period = period
        self._clock = clock
        self._sleep = sleep
        self._timestamps: deque[float] = deque()
        self._lock = asyncio.Lock()

    async def acquire(self) -> None:
        """Wait until one request slot is available."""
        while True:
            async with self._lock:
                now = self._clock()
                boundary = now - self.period
                while self._timestamps and self._timestamps[0] <= boundary:
                    self._timestamps.popleft()
                if len(self._timestamps) < self.limit:
                    self._timestamps.append(now)
                    return
                delay = max(0.0, self._timestamps[0] + self.period - now)
            await self._sleep(delay)
