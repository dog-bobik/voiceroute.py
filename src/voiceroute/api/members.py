"""Bot-visible community member endpoints."""

import builtins
import uuid
from collections.abc import AsyncIterator, Awaitable, Callable
from dataclasses import dataclass
from urllib.parse import quote

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
        """Fetch all visible members, following v1 cursors when available."""
        version = (
            await self._resolve_api_version()
            if self._api_version is APIVersion.AUTO
            else self._api_version
        )
        if version is APIVersion.V1 and channel_id is None:
            members: builtins.list[Member] = []
            async for member in self.iter_members(community_id):
                members.append(member)
            return members
        payload = await self._transport.request(
            "GET",
            f"/api/communities/{community_id}/members",
            params={"channelId": channel_id},
        )
        if payload is None:
            return []
        return [
            _member_from_payload(item, community_id=community_id)
            for item in payload.get("items", [])
        ]

    async def list_page(
        self,
        community_id: str,
        *,
        cursor: str | None = None,
        limit: int = 50,
    ) -> MemberPage:
        """Fetch one page from the v1 member collection."""
        version = (
            await self._resolve_api_version()
            if self._api_version is APIVersion.AUTO
            else self._api_version
        )
        if version is APIVersion.LEGACY:
            raise RuntimeError("member pagination requires the VoiceRoute v1 API")
        if not 1 <= limit <= 100:
            raise ValueError("limit must be between 1 and 100")
        payload = await self._transport.request(
            "GET",
            f"/api/v1/communities/{community_id}/members",
            params={"cursor": cursor, "limit": limit},
        )
        data = payload or {}
        return MemberPage(
            tuple(
                _member_from_payload(item, community_id=community_id)
                for item in data.get("items", ())
            ),
            str(data["nextCursor"]) if data.get("nextCursor") is not None else None,
        )

    async def iter_members(self, community_id: str, *, limit: int = 50) -> AsyncIterator[Member]:
        """Iterate through v1 member pages without retaining the full collection."""
        cursor = None
        while True:
            page = await self.list_page(community_id, cursor=cursor, limit=limit)
            for member in page.items:
                yield member
            if page.next_cursor is None:
                break
            cursor = page.next_cursor

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
        return _member_from_payload(payload, community_id=community_id, fallback_user_id=user_id)

    async def update_v1(
        self,
        community_id: str,
        user_id: int,
        *,
        if_match: str,
        nickname: str | None = None,
        clear_nickname: bool = False,
        role_ids: tuple[str, ...] | None = None,
        timeout_until: str | None = None,
        clear_timeout: bool = False,
        pending: bool | None = None,
        reason: str | None = None,
        idempotency_key: str | uuid.UUID | None = None,
    ) -> Member:
        """Update a member with version protection and an auditable reason."""
        if user_id <= 0:
            raise ValueError("user_id must be positive")
        if nickname is not None and clear_nickname:
            raise ValueError("nickname and clear_nickname cannot be used together")
        if timeout_until is not None and clear_timeout:
            raise ValueError("timeout_until and clear_timeout cannot be used together")
        if role_ids is not None and (len(role_ids) > 100 or len(set(role_ids)) != len(role_ids)):
            raise ValueError("role_ids must contain at most 100 unique IDs")
        if reason is not None and (len(reason) > 512 or "\x00" in reason):
            raise ValueError("reason must contain at most 512 characters and no null character")
        body: dict[str, object] = {}
        if nickname is not None or clear_nickname:
            if nickname is not None and not 1 <= len(nickname) <= 32:
                raise ValueError("nickname must contain between 1 and 32 characters")
            body["nickname"] = None if clear_nickname else nickname
        if role_ids is not None:
            body["roleIds"] = list(role_ids)
        if timeout_until is not None or clear_timeout:
            body["timeoutUntil"] = None if clear_timeout else timeout_until
        if pending is not None:
            body["pending"] = pending
        if not body:
            raise ValueError("at least one member field must be supplied")
        headers = {"X-Audit-Log-Reason": quote(reason, safe="")} if reason is not None else None
        payload = await self._transport.request(
            "PATCH",
            f"/api/v1/communities/{community_id}/members/{user_id}",
            json=body,
            headers=headers,
            if_match=if_match,
            idempotency_key=str(idempotency_key or uuid.uuid4()),
        )
        if payload is None:
            raise RuntimeError("VoiceRoute returned no member after update")
        return _member_from_payload(payload, community_id=community_id, fallback_user_id=user_id)

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
                _member_from_payload(item, community_id=community_id)
                for item in data.get("items", ())
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


def _member_from_payload(
    payload: dict[str, object], *, community_id: str, fallback_user_id: int | None = None
) -> Member:
    if isinstance(payload.get("user"), dict):
        return Member.from_dict(payload, community_id=community_id)
    normalized = dict(payload)
    username = str(payload.get("username", ""))
    normalized["user"] = {
        "id": payload.get("id", fallback_user_id),
        "username": username,
        "displayName": payload.get("displayName", username),
        "bot": payload.get("bot", False),
    }
    return Member.from_dict(normalized, community_id=community_id)
