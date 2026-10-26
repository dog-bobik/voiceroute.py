"""Main VoiceRoute client."""

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
    ModerationAPI,
    PlatformAPI,
    RolesAPI,
)
from voiceroute.config import APIVersion, ClientConfig
from voiceroute.gateway import (
    GatewayCheckpointCoordinator,
    GatewayCheckpointStore,
    GatewayClient,
    GatewayMetricHook,
    Intents,
    ShardManager,
)
from voiceroute.transport import HTTPTransport, RateLimiter


class VoiceRouteClient:
    """Asynchronous entry point for the VoiceRoute bot API."""

    def __init__(
        self,
        *,
        token: str,
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
        self._token = token
        self._base_url = config.base_url
        self._transport = HTTPTransport(
            token=token,
            base_url=config.base_url,
            timeout=config.timeout,
            rate_limiter=rate_limiter,
            max_attempts=max_attempts,
            max_concurrency=max_http_concurrency,
            max_response_bytes=max_response_bytes,
        )
        self.application_commands = ApplicationCommandsAPI(self._transport)
        self.automod = AutoModAPI(self._transport)
        self.audit = AuditAPI(self._transport)
        self.bots = BotsAPI(self._transport)
        self.communities = CommunitiesAPI(self._transport)
        self.events = EventsAPI(self._transport)
        self.interactions = InteractionsAPI(self._transport)
        self.messages = MessagesAPI(self._transport)
        self.moderation = ModerationAPI(self._transport)
        self.platform = PlatformAPI(self._transport)
        self.members = MembersAPI(self._transport)
        self.roles = RolesAPI(self._transport)

    async def resolve_api_version(self) -> APIVersion:
        """Resolve auto mode without changing existing resource routing."""
        if self.api_version is not APIVersion.AUTO:
            return self.api_version
        capabilities = await self.platform.capabilities()
        return APIVersion.V1 if capabilities.api_version == "1" else APIVersion.LEGACY

    def gateway(
        self,
        *,
        intents: Intents | tuple[str, ...] = (),
        shard: tuple[int, int] = (0, 1),
        store: GatewayCheckpointStore | None = None,
        coordinator: GatewayCheckpointCoordinator | None = None,
        dispatch_queue_size: int = 1_000,
        metric_hook: GatewayMetricHook | None = None,
        drain_timeout: float = 30.0,
    ) -> GatewayClient:
        """Create a v1 Gateway session sharing this client's discovery API."""
        return GatewayClient(
            token=self._token,
            platform_api=self.platform,
            base_url=self._base_url,
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
        intents: Intents | tuple[str, ...] = (),
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
