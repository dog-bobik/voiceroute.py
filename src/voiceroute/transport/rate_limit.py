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
        self._bucket_timestamps: dict[str, deque[float]] = {}
        self._lock = asyncio.Lock()

    async def acquire(self, bucket: str | None = None) -> None:
        """Wait for both the client-wide budget and an optional server bucket."""
        while True:
            async with self._lock:
                now = self._clock()
                boundary = now - self.period
                while self._timestamps and self._timestamps[0] <= boundary:
                    self._timestamps.popleft()
                bucket_timestamps = self._bucket_timestamps.get(bucket) if bucket else None
                if bucket is not None and bucket_timestamps is None:
                    bucket_timestamps = self._bucket_timestamps[bucket] = deque()
                while bucket_timestamps and bucket_timestamps[0] <= boundary:
                    bucket_timestamps.popleft()
                global_full = len(self._timestamps) >= self.limit
                bucket_full = bucket_timestamps is not None and len(bucket_timestamps) >= self.limit
                if not global_full and not bucket_full:
                    self._timestamps.append(now)
                    if bucket_timestamps is not None:
                        bucket_timestamps.append(now)
                    return
                windows = [self._timestamps] if global_full else []
                if bucket_full and bucket_timestamps is not None:
                    windows.append(bucket_timestamps)
                delay = max(0.0, max(window[0] for window in windows) + self.period - now)
            await self._sleep(delay)
