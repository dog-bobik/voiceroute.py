"""Bot profile endpoints."""

from voiceroute.models import BotIdentity, User
from voiceroute.transport import HTTPTransport


class BotsAPI:
    """Operations for the currently authenticated bot."""

    def __init__(self, transport: HTTPTransport) -> None:
        self._transport = transport

    async def get_current(self) -> BotIdentity:
        payload = await self._transport.request("GET", "/api/bots/@me")
        if payload is None:
            raise RuntimeError("VoiceRoute returned no bot identity")
        return BotIdentity.from_dict(payload)

    async def update_current(
        self,
        *,
        display_name: str | None = None,
        bio: str | None = None,
        custom_status: str | None = None,
        accent_color: str | None = None,
    ) -> User:
        data = {
            key: value
            for key, value in {
                "displayName": display_name,
                "bio": bio,
                "customStatus": custom_status,
                "accentColor": accent_color,
            }.items()
            if value is not None
        }
        payload = await self._transport.request("PATCH", "/api/bots/@me", json=data)
        if payload is None:
            raise RuntimeError("VoiceRoute returned no updated bot profile")
        return User.from_dict(payload["user"])
