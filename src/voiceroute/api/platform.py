"""Bot Platform v1 discovery and bootstrap endpoints."""

import asyncio
import time
from collections.abc import AsyncIterator, Callable, Mapping
from types import MappingProxyType
from typing import Any, cast

from voiceroute.errors import FeatureUnavailable
from voiceroute.models import (
    CurrentApplication,
    GatewayDiscovery,
    PlatformCapabilities,
    PlatformServiceStatus,
    StartupDiagnostics,
    VerificationKeySet,
)
from voiceroute.models.generated.platform_wire import ApplicationProfile
from voiceroute.transport import Transport


class PlatformAPI:
    """Discover runtime capabilities before using optional v1 features."""

    def __init__(
        self,
        transport: Transport,
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

    async def application_profile(self, application_id: str) -> ApplicationProfile:
        """Fetch the public metadata profile for an application."""
        payload = await self._transport.request(
            "GET", f"/api/v1/applications/{application_id}/profile"
        )
        if payload is None:
            raise RuntimeError("VoiceRoute returned no application profile")
        return cast(ApplicationProfile, payload)

    async def branding_asset(
        self, application_id: str, kind: str, *, version: str | None = None
    ) -> AsyncIterator[bytes]:
        """Stream an application's scanned icon or banner asset."""
        if kind not in {"icon", "banner"}:
            raise ValueError("kind must be 'icon' or 'banner'")
        async with self._transport.stream(
            f"/api/v1/applications/{application_id}/assets/{kind}",
            params={"v": version},
        ) as response:
            response.raise_for_status()
            async for chunk in response.aiter_bytes():
                yield chunk

    async def embed_image(self, image_id: str) -> AsyncIterator[bytes]:
        """Stream an authorized embed image without exposing its source URL."""
        async with self._transport.stream(f"/api/v1/media/images/{image_id}") as response:
            response.raise_for_status()
            async for chunk in response.aiter_bytes():
                yield chunk

    async def verification_keys(self, application_id: str) -> VerificationKeySet:
        """Fetch public webhook signing keys from this client's configured origin."""
        payload = await self._transport.request(
            "GET", f"/api/v1/applications/{application_id}/verification-keys"
        )
        if payload is None:
            raise RuntimeError("VoiceRoute returned no webhook verification keys")
        return VerificationKeySet.from_dict(payload)

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
        granted = frozenset(application.granted_capabilities)
        return StartupDiagnostics(
            application_id=application.id,
            bot_id=application.bot.id,
            api_version=capabilities.api_version,
            environment=capabilities.environment,
            service_status=status.status,
            manifest_capabilities=application.access_manifest.capabilities,
            granted_capabilities=application.granted_capabilities,
            unavailable_capabilities=tuple(
                capability
                for capability in application.access_manifest.capabilities
                if capability not in granted
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
