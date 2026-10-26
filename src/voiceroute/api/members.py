"""Bot-visible community member endpoints."""

import builtins

from voiceroute.models import Member
from voiceroute.transport import HTTPTransport


class MembersAPI:
    """Read active members visible to the current bot."""

    def __init__(self, transport: HTTPTransport) -> None:
        self._transport = transport

    async def list(
        self,
        community_id: str,
        *,
        channel_id: str | None = None,
    ) -> builtins.list[Member]:
        payload = await self._transport.request(
            "GET",
            f"/api/communities/{community_id}/members",
            params={"channelId": channel_id},
        )
        if payload is None:
            return []
        return [
            Member.from_dict(item, community_id=community_id) for item in payload.get("items", [])
        ]

    async def get(
        self,
        community_id: str,
        user_id: int,
        *,
        channel_id: str | None = None,
    ) -> Member | None:
        """Find a member in the server-provided active member snapshot."""
        members = await self.list(community_id, channel_id=channel_id)
        return next((member for member in members if member.id == user_id), None)
