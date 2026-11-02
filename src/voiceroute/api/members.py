"""Bot-visible community member endpoints."""

import builtins
from collections.abc import AsyncIterator, Awaitable, Callable
from dataclasses import dataclass

from voiceroute.config import APIVersion
from voiceroute.models import Member
from voiceroute.transport import Transport


@dataclass(frozen=True, slots=True)
class MemberPage:
    """One cursor-paginated page of members."""

    items: tuple[Member, ...]
    next_cursor: str | None


class MembersAPI:
    """Read active members visible to the current bot."""

    def __init__(
        self,
        transport: Transport,
        *,
        api_version: APIVersion,
        resolve_api_version: Callable[[], Awaitable[APIVersion]],
    ) -> None:
        self._transport = transport
        self._api_version = api_version
        self._resolve_api_version = resolve_api_version

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
        """Fetch one active member using the selected API contract."""
        version = (
            await self._resolve_api_version()
            if self._api_version is APIVersion.AUTO
            else self._api_version
        )
        if channel_id is not None or version is APIVersion.LEGACY:
            members = await self.list(community_id, channel_id=channel_id)
            return next((member for member in members if member.id == user_id), None)
        payload = await self._transport.request(
            "GET", f"/api/v1/communities/{community_id}/members/{user_id}"
        )
        if payload is None:
            return None
        if isinstance(payload.get("user"), dict):
            return Member.from_dict(payload, community_id=community_id)
        # v1 member DTO is flattened while the legacy public model nests User.
        normalized = dict(payload)
        normalized["user"] = {
            "id": payload.get("id", user_id),
            "username": payload.get("username", ""),
            "displayName": payload.get("displayName", payload.get("username", "")),
            "bot": payload.get("bot", False),
        }
        return Member.from_dict(normalized, community_id=community_id)

    async def search(
        self, community_id: str, query: str, *, cursor: str | None = None, limit: int = 50
    ) -> MemberPage:
        """Search members using the server's literal, query-bound cursor."""
        version = (
            await self._resolve_api_version()
            if self._api_version is APIVersion.AUTO
            else self._api_version
        )
        if version is APIVersion.LEGACY:
            raise RuntimeError("member search requires the VoiceRoute v1 API")
        if not query or len(query) > 100:
            raise ValueError("query must contain between 1 and 100 characters")
        if not 1 <= limit <= 100:
            raise ValueError("limit must be between 1 and 100")
        payload = await self._transport.request(
            "GET",
            f"/api/v1/communities/{community_id}/members/search",
            params={"query": query, "cursor": cursor, "limit": limit},
        )
        data = payload or {}
        return MemberPage(
            tuple(
                Member.from_dict(item, community_id=community_id) for item in data.get("items", ())
            ),
            str(data["nextCursor"]) if data.get("nextCursor") is not None else None,
        )

    async def iter_search(
        self, community_id: str, query: str, *, limit: int = 50
    ) -> AsyncIterator[Member]:
        """Iterate through a search without loading all pages into memory."""
        cursor = None
        while True:
            page = await self.search(community_id, query, cursor=cursor, limit=limit)
            for member in page.items:
                yield member
            if page.next_cursor is None:
                break
            cursor = page.next_cursor
