"""Main VoiceRoute client."""

import asyncio
from types import TracebackType

from voiceroute.api import (
    ApplicationCommandsAPI,
    AuditAPI,
    AutoModAPI,
    BotsAPI,
    CommunitiesAPI,
    EventsAPI,
    InteractionsAPI,
    MembersAPI,
    MessagesAPI,
    MiniAppsAPI,
    ModerationAPI,
    PlatformAPI,
    PollsAPI,
    RolesAPI,
    ThreadsAPI,
    UploadsAPI,
    VoiceAPI,
    WebhooksAPI,
)
from voiceroute.config import APIVersion, ClientConfig
from voiceroute.gateway import (
    Capabilities,
    GatewayCheckpointCoordinator,
    GatewayCheckpointStore,
    GatewayClient,
    GatewayMetricHook,
    Intents,
    ShardManager,
)
from voiceroute.transport import HTTPTransport, RateLimiter, Transport


class VoiceRouteClient:
    """Asynchronous entry point for the VoiceRoute bot API."""

    def __init__(
        self,
        *,
        token: str | None = None,
        transport: Transport | None = None,
        owns_transport: bool | None = None,
        base_url: str = "https://voiceroute.cc",
        timeout: float = 30.0,
        rate_limiter: RateLimiter | None = None,
        max_attempts: int = 3,
        api_version: APIVersion | str = APIVersion.AUTO,
        max_http_concurrency: int = 100,
        max_response_bytes: int = 8 * 1024 * 1024,
    ) -> None:
        config = ClientConfig(
            base_url=base_url, timeout=timeout, api_version=APIVersion(api_version)
        )
        self.api_version = config.api_version
        if token is None and transport is None:
            raise ValueError("token or transport is required")
        self._token = token
        self._base_url = config.base_url
        self._transport: Transport = (
            transport
            if transport is not None
            else HTTPTransport(
                token=token,
                base_url=config.base_url,
                timeout=config.timeout,
                rate_limiter=rate_limiter,
                max_attempts=max_attempts,
                max_concurrency=max_http_concurrency,
                max_response_bytes=max_response_bytes,
            )
        )
        self._owns_transport = transport is None if owns_transport is None else owns_transport
        self._resolved_api_version: APIVersion | None = (
            self.api_version if self.api_version is not APIVersion.AUTO else None
        )
        self._version_lock = asyncio.Lock()
        self.application_commands = ApplicationCommandsAPI(self._transport)
        self.automod = AutoModAPI(self._transport)
        self.audit = AuditAPI(self._transport)
        self.bots = BotsAPI(self._transport)
        self.communities = CommunitiesAPI(self._transport)
        self.events = EventsAPI(self._transport)
        self.interactions = InteractionsAPI(self._transport)
        self.messages = MessagesAPI(self._transport)
        self.mini_apps = MiniAppsAPI(self._transport)
        self.moderation = ModerationAPI(self._transport)
        self.platform = PlatformAPI(self._transport)
        self.members = MembersAPI(
            self._transport,
            api_version=self.api_version,
            resolve_api_version=self.resolve_api_version,
        )
        self.roles = RolesAPI(self._transport)
        self.voice = VoiceAPI(self._transport)
        self.uploads = UploadsAPI(self._transport)
        self.threads = ThreadsAPI(self._transport)
        self.polls = PollsAPI(self._transport)
        self.webhooks = WebhooksAPI(self._transport)

    async def resolve_api_version(self) -> APIVersion:
        """Resolve and cache the deployment's API version for this client."""
        if self._resolved_api_version is not None:
            return self._resolved_api_version
        async with self._version_lock:
            if self._resolved_api_version is None:
                capabilities = await self.platform.capabilities()
                self._resolved_api_version = (
                    APIVersion.V1 if capabilities.api_version == "1" else APIVersion.LEGACY
                )
            return self._resolved_api_version

    async def require_feature(self, feature: str) -> None:
        """Fail early when the connected deployment does not expose a feature."""
        await self.platform.require(feature)

    def gateway(
        self,
        *,
        capabilities: Capabilities | tuple[str, ...] | None = None,
        intents: Intents | tuple[str, ...] | None = None,
        shard: tuple[int, int] = (0, 1),
        store: GatewayCheckpointStore | None = None,
        coordinator: GatewayCheckpointCoordinator | None = None,
        dispatch_queue_size: int = 1_000,
        metric_hook: GatewayMetricHook | None = None,
        drain_timeout: float = 30.0,
    ) -> GatewayClient:
        """Create a v1 Gateway session sharing this client's discovery API."""
        if self._token is None:
            raise RuntimeError("Gateway connections require a bot token")
        return GatewayClient(
            token=self._token,
            platform_api=self.platform,
            base_url=self._base_url,
            capabilities=capabilities,
            intents=intents,
            shard=shard,
            store=store,
            coordinator=coordinator,
            dispatch_queue_size=dispatch_queue_size,
            metric_hook=metric_hook,
            drain_timeout=drain_timeout,
        )

    def shards(
        self,
        shard_count: int,
        *,
        capabilities: Capabilities | tuple[str, ...] | None = None,
        intents: Intents | tuple[str, ...] | None = None,
        shard_ids: tuple[int, ...] | None = None,
        store: GatewayCheckpointStore | None = None,
        identify_interval: float = 5.0,
        coordinator: GatewayCheckpointCoordinator | None = None,
        dispatch_queue_size: int = 1_000,
        metric_hook: GatewayMetricHook | None = None,
        drain_timeout: float = 30.0,
    ) -> ShardManager:
        """Create all shards or a process-local subset for one application."""
        selected = shard_ids if shard_ids is not None else tuple(range(shard_count))
        clients = tuple(
            self.gateway(
                capabilities=capabilities,
                intents=intents,
                shard=(shard_id, shard_count),
                store=store,
                coordinator=coordinator,
                dispatch_queue_size=dispatch_queue_size,
                metric_hook=metric_hook,
                drain_timeout=drain_timeout,
            )
            for shard_id in selected
        )
        return ShardManager(clients, identify_interval=identify_interval)

    async def close(self) -> None:
        """Close network resources owned by this client."""
        if self._owns_transport:
            await self._transport.close()

    async def __aenter__(self) -> "VoiceRouteClient":
        return self

    async def __aexit__(
        self,
        exc_type: type[BaseException] | None,
        exc: BaseException | None,
        traceback: TracebackType | None,
    ) -> None:
        await self.close()
