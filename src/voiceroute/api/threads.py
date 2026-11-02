"""Bot-visible v1 thread lifecycle and history endpoints."""

from __future__ import annotations

import uuid
from collections.abc import AsyncIterator, Mapping, Sequence
from dataclasses import dataclass

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

    async def own_membership(self, community_id: str, thread_id: str) -> OwnThreadMembership:
        """Fetch whether the current bot is a member of a thread."""
        payload = await self._transport.request(
            "GET", f"{_thread_path(community_id, thread_id)}/members/@me"
        )
        if payload is None:
            raise RuntimeError("VoiceRoute returned no current thread membership")
        return OwnThreadMembership.from_dict(payload)

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

    async def get_message(self, community_id: str, thread_id: str, message_id: str) -> RichMessage:
        payload = await self._transport.request(
            "GET", f"{_thread_path(community_id, thread_id)}/messages/{message_id}"
        )
        return RichMessage.from_dict(_required_object(payload, "thread message lookup"))

    async def edit_message(
        self,
        community_id: str,
        thread_id: str,
        message_id: str,
        *,
        if_match: str,
        content: str | None = None,
        embeds: Sequence[Mapping[str, object]] | None = None,
        attachments: Sequence[Mapping[str, object]] | None = None,
        allowed_mentions: Mapping[str, object] | None = None,
        components: Sequence[Mapping[str, object]] | None = None,
        idempotency_key: str | uuid.UUID | None = None,
    ) -> RichMessage:
        if not if_match:
            raise ValueError("if_match is required to edit a thread message")
        body: dict[str, object] = {}
        if content is not None:
            if len(content) > 4000:
                raise ValueError("message content cannot exceed 4000 characters")
            body["content"] = content
        if embeds is not None:
            body["embeds"] = [dict(item) for item in embeds]
        if attachments is not None:
            body["attachments"] = [dict(item) for item in attachments]
        if allowed_mentions is not None:
            body["allowedMentions"] = dict(allowed_mentions)
        if components is not None:
            if len(components) > 5:
                raise ValueError("a message cannot contain more than five component rows")
            body["components"] = [dict(item) for item in components]
        if not body:
            raise ValueError("at least one message field must be supplied")
        payload = await self._transport.request(
            "PATCH",
            f"{_thread_path(community_id, thread_id)}/messages/{message_id}",
            json=body,
            if_match=if_match,
            idempotency_key=str(idempotency_key or uuid.uuid4()),
        )
        return RichMessage.from_dict(_required_object(payload, "thread message edit"))

    async def delete_message(
        self,
        community_id: str,
        thread_id: str,
        message_id: str,
        *,
        if_match: str,
        reason: str | None = None,
        idempotency_key: str | uuid.UUID | None = None,
    ) -> None:
        if not if_match:
            raise ValueError("if_match is required to delete a thread message")
        if reason is not None and (len(reason) > 512 or "\x00" in reason):
            raise ValueError("reason must contain at most 512 characters and no null character")
        await self._transport.request(
            "DELETE",
            f"{_thread_path(community_id, thread_id)}/messages/{message_id}",
            json={"reason": reason} if reason is not None else {},
            if_match=if_match,
            idempotency_key=str(idempotency_key or uuid.uuid4()),
            retryable=True,
        )

    async def bulk_delete_messages(
        self,
        community_id: str,
        thread_id: str,
        messages: Sequence[RichMessage],
        *,
        reason: str | None = None,
        idempotency_key: str | uuid.UUID | None = None,
    ) -> None:
        if not 2 <= len(messages) <= 100:
            raise ValueError("bulk deletion requires between 2 and 100 messages")
        if len({message.id for message in messages}) != len(messages):
            raise ValueError("messages must have unique IDs")
        if any(
            message.community_id != community_id or message.data.get("threadId") != thread_id
            for message in messages
        ):
            raise ValueError("all messages must belong to the supplied community and thread")
        if any(not message.version for message in messages):
            raise ValueError("all messages must include a current version")
        if reason is not None and (len(reason) > 512 or "\x00" in reason):
            raise ValueError("reason must contain at most 512 characters and no null character")
        body: dict[str, object] = {
            "messages": [{"id": message.id, "version": message.version} for message in messages]
        }
        if reason is not None:
            body["reason"] = reason
        await self._transport.request(
            "POST",
            f"{_thread_path(community_id, thread_id)}/messages/bulk-delete",
            json=body,
            idempotency_key=str(idempotency_key or uuid.uuid4()),
        )


@dataclass(frozen=True, slots=True)
class OwnThreadMembership:
    community_id: str
    thread_id: str
    user_id: int
    joined: bool
    member_count: int

    @classmethod
    def from_dict(cls, data: dict[str, object]) -> OwnThreadMembership:
        return cls(
            community_id=str(data["communityId"]),
            thread_id=str(data["threadId"]),
            user_id=int(str(data["userId"])),
            joined=bool(data["joined"]),
            member_count=int(str(data["memberCount"])),
        )


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
