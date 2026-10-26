"""Bot Platform v1 discovery and bootstrap endpoints."""

import asyncio
import time
from collections.abc import Callable

from voiceroute.errors import FeatureUnavailable
from voiceroute.models import CurrentApplication, PlatformCapabilities
from voiceroute.transport import HTTPTransport


class PlatformAPI:
    """Discover runtime capabilities before using optional v1 features."""

    def __init__(
        self,
        transport: HTTPTransport,
        *,
        cache_ttl: float = 300.0,
        clock: Callable[[], float] = time.monotonic,
    ) -> None:
        if cache_ttl < 0:
            raise ValueError("cache_ttl cannot be negative")
        self._transport = transport
        self._cache_ttl = cache_ttl
        self._clock = clock
        self._capabilities: PlatformCapabilities | None = None
        self._expires_at = 0.0
        self._lock = asyncio.Lock()

    async def capabilities(self, *, force: bool = False) -> PlatformCapabilities:
        now = self._clock()
        if not force and self._capabilities is not None and now < self._expires_at:
            return self._capabilities
        async with self._lock:
            now = self._clock()
            if not force and self._capabilities is not None and now < self._expires_at:
                return self._capabilities
            payload = await self._transport.request("GET", "/api/v1/capabilities")
            capabilities = PlatformCapabilities.from_dict(payload or {})
            self._capabilities = capabilities
            self._expires_at = now + self._cache_ttl
            return capabilities

    async def require(self, feature: str) -> None:
        capabilities = await self.capabilities()
        if not capabilities.supports(feature):
            raise FeatureUnavailable(
                f"VoiceRoute deployment does not advertise capability {feature!r}"
            )

    async def current_application(self) -> CurrentApplication:
        payload = await self._transport.request("GET", "/api/v1/applications/@me")
        if payload is None:
            raise RuntimeError("VoiceRoute returned no current application")
        return CurrentApplication.from_dict(payload)

    def invalidate_capabilities(self) -> None:
        self._expires_at = 0.0
