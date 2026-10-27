"""Bot Platform v1 discovery and bootstrap endpoints."""

import asyncio
import time
from collections.abc import Callable, Mapping
from types import MappingProxyType
from typing import Any

from voiceroute.errors import FeatureUnavailable
from voiceroute.models import (
    CurrentApplication,
    GatewayDiscovery,
    PlatformCapabilities,
    PlatformServiceStatus,
    StartupDiagnostics,
)
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
        self._status: PlatformServiceStatus | None = None
        self._status_expires_at = 0.0
        self._status_lock = asyncio.Lock()

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

    async def status(self, *, force: bool = False) -> PlatformServiceStatus:
        now = self._clock()
        if not force and self._status is not None and now < self._status_expires_at:
            return self._status
        async with self._status_lock:
            now = self._clock()
            if not force and self._status is not None and now < self._status_expires_at:
                return self._status
            payload = await self._transport.request("GET", "/api/v1/status")
            status = PlatformServiceStatus.from_dict(payload or {})
            self._status = status
            self._status_expires_at = now + min(self._cache_ttl, 5.0)
            return status

    async def openapi(self) -> Mapping[str, Any]:
        payload = await self._transport.request("GET", "/api/v1/openapi.json")
        return MappingProxyType(dict(payload or {}))

    async def asyncapi(self) -> Mapping[str, Any]:
        payload = await self._transport.request("GET", "/api/v1/asyncapi.json")
        return MappingProxyType(dict(payload or {}))

    async def current_application(self) -> CurrentApplication:
        payload = await self._transport.request("GET", "/api/v1/applications/@me")
        if payload is None:
            raise RuntimeError("VoiceRoute returned no current application")
        return CurrentApplication.from_dict(payload)

    async def gateway(self) -> GatewayDiscovery:
        await self.require("gateway")
        payload = await self._transport.request("GET", "/api/v1/gateway")
        if payload is None:
            raise RuntimeError("VoiceRoute returned no Gateway discovery document")
        return GatewayDiscovery.from_dict(payload)

    async def diagnostics(self) -> StartupDiagnostics:
        """Return sanitized startup information that never contains credentials."""
        capabilities, application, status = await asyncio.gather(
            self.capabilities(),
            self.current_application(),
            self.status(),
        )
        approved = frozenset(application.approved_intents)
        return StartupDiagnostics(
            application_id=application.id,
            bot_id=application.bot.id,
            api_version=capabilities.api_version,
            environment=capabilities.environment,
            service_status=status.status,
            requested_intents=application.requested_intents,
            approved_intents=application.approved_intents,
            unavailable_intents=tuple(
                intent for intent in application.requested_intents if intent not in approved
            ),
            enabled_features=tuple(
                sorted(name for name, enabled in capabilities.features.items() if enabled)
            ),
        )

    async def refresh(self) -> tuple[PlatformCapabilities, PlatformServiceStatus]:
        return await asyncio.gather(
            self.capabilities(force=True),
            self.status(force=True),
        )

    def invalidate_capabilities(self) -> None:
        self._expires_at = 0.0
        self._status_expires_at = 0.0
