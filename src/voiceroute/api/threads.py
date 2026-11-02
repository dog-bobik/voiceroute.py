"""Bot-visible v1 thread lifecycle and history endpoints."""

from __future__ import annotations

import uuid
from collections.abc import AsyncIterator, Mapping, Sequence

from voiceroute.models import (
    RichMessage,
    RichMessagePage,
    Thread,
    ThreadMember,
    ThreadMemberPage,
    ThreadPage,
)
from voiceroute.transport import Transport


class ThreadsAPI:
    def __init__(self, transport: Transport) -> None:
        self._transport = transport

    async def list(
        self,
        community_id: str,
        channel_id: str,
        *,
        archived: str = "false",
        cursor: str | None = None,
        limit: int = 50,
    ) -> ThreadPage:
        if archived not in {"true", "false", "all"}:
            raise ValueError("archived must be 'true', 'false', or 'all'")
        _validate_limit(limit)
        payload = await self._transport.request(
            "GET",
            _channel_threads_path(community_id, channel_id),
            params={"archived": archived, "cursor": cursor, "limit": limit},
        )
        data = payload or {}
        values = data.get("items", ())
        items = values if isinstance(values, list) else []
        next_cursor = data.get("nextCursor")
        return ThreadPage(
            tuple(Thread.from_dict(item) for item in items if isinstance(item, dict)),
            str(next_cursor) if next_cursor is not None else None,
        )

    async def create(
        self,
        community_id: str,
        channel_id: str,
        name: str,
        *,
        private: bool = False,
        invitable: bool = True,
        parent_message_id: str | None = None,
        tag_ids: tuple[str, ...] = (),
        idempotency_key: str | uuid.UUID | None = None,
    ) -> Thread:
        if not name or len(name) > 100:
            raise ValueError("thread name must contain between 1 and 100 characters")
        if len(tag_ids) > 5 or len(set(tag_ids)) != len(tag_ids):
            raise ValueError("tag_ids must contain at most five unique IDs")
        body: dict[str, object] = {"name": name, "private": private, "invitable": invitable}
        if parent_message_id is not None:
            body["parentMessageId"] = parent_message_id
        if tag_ids:
            body["tagIds"] = list(tag_ids)
        payload = await self._transport.request(
            "POST",
            _channel_threads_path(community_id, channel_id),
            json=body,
            idempotency_key=str(idempotency_key or uuid.uuid4()),
        )
        return Thread.from_dict(_required_object(payload, "thread creation"))

    async def get(self, community_id: str, thread_id: str) -> Thread:
        payload = await self._transport.request("GET", _thread_path(community_id, thread_id))
        return Thread.from_dict(_required_object(payload, "thread lookup"))

    async def update(
        self,
        community_id: str,
        thread_id: str,
        *,
        if_match: str,
        name: str | None = None,
        archived: bool | None = None,
        invitable: bool | None = None,
        tag_ids: tuple[str, ...] | None = None,
        idempotency_key: str | uuid.UUID | None = None,
    ) -> Thread:
        body: dict[str, object] = {}
        if name is not None:
            if not name or len(name) > 100:
                raise ValueError("thread name must contain between 1 and 100 characters")
            body["name"] = name
        if archived is not None:
            body["archived"] = archived
        if invitable is not None:
            body["invitable"] = invitable
        if tag_ids is not None:
            if len(tag_ids) > 5 or len(set(tag_ids)) != len(tag_ids):
                raise ValueError("tag_ids must contain at most five unique IDs")
            body["tagIds"] = list(tag_ids)
        if not body:
            raise ValueError("at least one thread field must be supplied")
        payload = await self._transport.request(
            "PATCH",
            _thread_path(community_id, thread_id),
            json=body,
            idempotency_key=str(idempotency_key or uuid.uuid4()),
            if_match=if_match,
        )
        return Thread.from_dict(_required_object(payload, "thread update"))

    async def delete(
        self,
        community_id: str,
        thread_id: str,
        *,
        if_match: str,
        idempotency_key: str | uuid.UUID | None = None,
    ) -> None:
        await self._transport.request(
            "DELETE",
            _thread_path(community_id, thread_id),
            idempotency_key=str(idempotency_key or uuid.uuid4()),
            if_match=if_match,
            retryable=True,
        )

    async def join(self, community_id: str, thread_id: str) -> None:
        await self._transport.request(
            "PUT",
            f"{_thread_path(community_id, thread_id)}/members/@me",
            idempotency_key=str(uuid.uuid4()),
            retryable=True,
        )

    async def leave(self, community_id: str, thread_id: str) -> None:
        await self._transport.request(
            "DELETE",
            f"{_thread_path(community_id, thread_id)}/members/@me",
            idempotency_key=str(uuid.uuid4()),
            retryable=True,
        )

    async def members(
        self,
        community_id: str,
        thread_id: str,
        *,
        cursor: str | None = None,
        limit: int = 50,
    ) -> ThreadMemberPage:
        _validate_limit(limit)
        payload = await self._transport.request(
            "GET",
            f"{_thread_path(community_id, thread_id)}/members",
            params={"cursor": cursor, "limit": limit},
        )
        data = payload or {}
        values = data.get("items", ())
        items = values if isinstance(values, list) else []
        next_cursor = data.get("nextCursor")
        return ThreadMemberPage(
            tuple(ThreadMember.from_dict(item) for item in items if isinstance(item, dict)),
            str(next_cursor) if next_cursor is not None else None,
        )

    async def add_member(
        self,
        community_id: str,
        thread_id: str,
        user_id: int,
        *,
        if_match: str,
        idempotency_key: str | uuid.UUID | None = None,
    ) -> None:
        if user_id <= 0:
            raise ValueError("user_id must be positive")
        await self._transport.request(
            "PUT",
            f"{_thread_path(community_id, thread_id)}/members/{user_id}",
            idempotency_key=str(idempotency_key or uuid.uuid4()),
            if_match=if_match,
            retryable=True,
        )

    async def remove_member(
        self,
        community_id: str,
        thread_id: str,
        user_id: int,
        *,
        if_match: str,
        idempotency_key: str | uuid.UUID | None = None,
    ) -> None:
        if user_id <= 0:
            raise ValueError("user_id must be positive")
        await self._transport.request(
            "DELETE",
            f"{_thread_path(community_id, thread_id)}/members/{user_id}",
            idempotency_key=str(idempotency_key or uuid.uuid4()),
            if_match=if_match,
            retryable=True,
        )

    async def history(
        self,
        community_id: str,
        thread_id: str,
        *,
        cursor: str | None = None,
        limit: int = 50,
    ) -> RichMessagePage:
        _validate_limit(limit)
        payload = await self._transport.request(
            "GET",
            f"{_thread_path(community_id, thread_id)}/messages",
            params={"cursor": cursor, "limit": limit},
        )
        data = payload or {}
        values = data.get("items", ())
        items = values if isinstance(values, list) else []
        next_cursor = data.get("nextCursor")
        return RichMessagePage(
            tuple(RichMessage.from_dict(item) for item in items if isinstance(item, dict)),
            str(next_cursor) if next_cursor is not None else None,
        )

    async def iter_history(
        self, community_id: str, thread_id: str, *, limit: int = 50
    ) -> AsyncIterator[RichMessage]:
        """Yield thread messages page by page without retaining the full history."""
        cursor = None
        while True:
            page = await self.history(community_id, thread_id, cursor=cursor, limit=limit)
            for message in page.items:
                yield message
            if page.next_cursor is None:
                break
            cursor = page.next_cursor

    async def send(
        self,
        community_id: str,
        thread_id: str,
        *,
        content: str = "",
        embeds: Sequence[Mapping[str, object]] = (),
        attachments: Sequence[Mapping[str, object]] = (),
        allowed_mentions: Mapping[str, object] | None = None,
        reply_to_message_id: str | None = None,
        idempotency_key: str | uuid.UUID | None = None,
    ) -> RichMessage:
        if len(content) > 4000 or len(embeds) > 10 or len(attachments) > 10:
            raise ValueError("thread message exceeds the v1 content or rich payload limits")
        if not content and not embeds and not attachments:
            raise ValueError("thread message must contain content or an attachment/embed")
        body: dict[str, object] = {"content": content}
        if embeds:
            body["embeds"] = [dict(item) for item in embeds]
        if attachments:
            body["attachments"] = [dict(item) for item in attachments]
        if allowed_mentions is not None:
            body["allowedMentions"] = dict(allowed_mentions)
        if reply_to_message_id is not None:
            body["reply"] = {"messageId": reply_to_message_id}
        payload = await self._transport.request(
            "POST",
            f"{_thread_path(community_id, thread_id)}/messages",
            json=body,
            idempotency_key=str(idempotency_key or uuid.uuid4()),
        )
        return RichMessage.from_dict(_required_object(payload, "thread message creation"))


def _channel_threads_path(community_id: str, channel_id: str) -> str:
    return f"/api/v1/communities/{community_id}/channels/{channel_id}/threads"


def _thread_path(community_id: str, thread_id: str) -> str:
    return f"/api/v1/communities/{community_id}/threads/{thread_id}"


def _required_object(payload: dict[str, object] | None, operation: str) -> dict[str, object]:
    if payload is None:
        raise RuntimeError(f"VoiceRoute returned no resource after {operation}")
    resource = payload.get("thread", payload)
    if not isinstance(resource, dict):
        raise RuntimeError(f"VoiceRoute returned an invalid resource after {operation}")
    return resource


def _validate_limit(limit: int) -> None:
    if not 1 <= limit <= 100:
        raise ValueError("limit must be between 1 and 100")
