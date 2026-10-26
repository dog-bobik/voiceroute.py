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
    ) -> None:
        config = ClientConfig(
            base_url=base_url, timeout=timeout, api_version=APIVersion(api_version)
        )
        self.api_version = config.api_version
        self._transport = HTTPTransport(
            token=token,
            base_url=config.base_url,
            timeout=config.timeout,
            rate_limiter=rate_limiter,
            max_attempts=max_attempts,
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
