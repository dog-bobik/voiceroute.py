"""Community member moderation endpoints."""

import builtins

from voiceroute.models import Ban, MemberTimeout, ModerationSnapshot
from voiceroute.transport import HTTPTransport

MAX_TIMEOUT_SECONDS = 28 * 24 * 60 * 60
MAX_REASON_LENGTH = 512


class ModerationAPI:
    """Kick, ban, unban, and timeout community members."""

    def __init__(self, transport: HTTPTransport) -> None:
        self._transport = transport

    async def current_timeout(self, community_id: str) -> MemberTimeout | None:
        payload = await self._transport.request(
            "GET", f"/api/communities/{community_id}/moderation/me"
        )
        raw_timeout = payload.get("timeout") if payload else None
        return MemberTimeout.from_dict(raw_timeout) if isinstance(raw_timeout, dict) else None

    async def snapshot(self, community_id: str) -> ModerationSnapshot:
        payload = await self._transport.request(
            "GET", f"/api/communities/{community_id}/moderation"
        )
        return ModerationSnapshot.from_dict(payload or {})

    async def bans(self, community_id: str) -> builtins.list[Ban]:
        payload = await self._transport.request("GET", f"/api/communities/{community_id}/bans")
        return [Ban.from_dict(item) for item in (payload or {}).get("items", ())]

    async def kick(self, community_id: str, user_id: int, *, reason: str = "") -> None:
        await self._transport.request(
            "DELETE",
            f"/api/communities/{community_id}/members/{user_id}",
            json={"reason": _reason(reason)},
        )

    async def ban(self, community_id: str, user_id: int, *, reason: str = "") -> Ban:
        payload = await self._transport.request(
            "PUT",
            f"/api/communities/{community_id}/bans/{user_id}",
            json={"reason": _reason(reason)},
        )
        raw_ban = payload.get("ban") if payload else None
        if not isinstance(raw_ban, dict):
            raise RuntimeError("VoiceRoute returned no ban")
        return Ban.from_dict(raw_ban)

    async def unban(self, community_id: str, user_id: int, *, reason: str = "") -> None:
        await self._transport.request(
            "DELETE",
            f"/api/communities/{community_id}/bans/{user_id}",
            json={"reason": _reason(reason)},
        )

    async def timeout(
        self,
        community_id: str,
        user_id: int,
        duration_seconds: int,
        *,
        reason: str = "",
    ) -> MemberTimeout:
        if not 1 <= duration_seconds <= MAX_TIMEOUT_SECONDS:
            raise ValueError("duration_seconds must be between 1 and 2419200")
        payload = await self._transport.request(
            "PUT",
            f"/api/communities/{community_id}/members/{user_id}/timeout",
            json={"durationSeconds": duration_seconds, "reason": _reason(reason)},
        )
        raw_timeout = payload.get("timeout") if payload else None
        if not isinstance(raw_timeout, dict):
            raise RuntimeError("VoiceRoute returned no timeout")
        return MemberTimeout.from_dict(raw_timeout)

    async def remove_timeout(self, community_id: str, user_id: int, *, reason: str = "") -> None:
        await self._transport.request(
            "DELETE",
            f"/api/communities/{community_id}/members/{user_id}/timeout",
            json={"reason": _reason(reason)},
        )


def _reason(value: str) -> str:
    if "\x00" in value:
        raise ValueError("reason cannot contain a null character")
    if len(value) > MAX_REASON_LENGTH:
        raise ValueError("reason cannot exceed 512 characters")
    return value.strip()
