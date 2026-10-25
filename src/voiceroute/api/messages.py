"""Community text message endpoints."""

from __future__ import annotations

import uuid
from collections.abc import Sequence

from voiceroute.models import Message, MessagePage
from voiceroute.transport import HTTPTransport


class MessagesAPI:
    """Read and send messages in bot-visible text channels."""

    def __init__(self, transport: HTTPTransport) -> None:
        self._transport = transport

    async def history(
        self,
        community_id: str,
        channel_id: str,
        *,
        limit: int = 50,
        before_seq: str | None = None,
        after_seq: str | None = None,
    ) -> MessagePage:
        _validate_limit(limit)
        if before_seq is not None and after_seq is not None:
            raise ValueError("before_seq and after_seq cannot be used together")

        params: dict[str, str | int | None] = {
            "limit": limit,
            "beforeSeq": before_seq,
            "afterSeq": after_seq,
        }
        payload = await self._transport.request(
            "GET",
            self._messages_path(community_id, channel_id),
            params=params,
        )
        if payload is None:
            return MessagePage(())
        return _message_page(payload)

    async def send(
        self,
        community_id: str,
        channel_id: str,
        body: str = "",
        *,
        reply_to_seq: str | None = None,
        attachment_ids: Sequence[str] = (),
        sticker_ids: Sequence[str] = (),
        client_message_id: str | uuid.UUID | None = None,
    ) -> Message:
        if len(body) > 4000:
            raise ValueError("message body cannot exceed 4000 characters")
        if len(attachment_ids) > 4:
            raise ValueError("a message cannot contain more than four attachments")
        if not body and not attachment_ids and not sticker_ids:
            raise ValueError("a message must contain text, an attachment, or a sticker")

        operation_id = str(client_message_id or uuid.uuid4())
        payload = await self._transport.request(
            "POST",
            self._messages_path(community_id, channel_id),
            json={
                "clientMessageId": operation_id,
                "body": body,
                "replyToSeq": reply_to_seq,
                "attachmentIds": list(attachment_ids),
                "stickerIds": list(sticker_ids),
            },
            retryable=True,
        )
        if payload is None:
            raise RuntimeError("VoiceRoute returned no sent message")
        return Message.from_dict(payload["message"])

    async def edit(
        self,
        community_id: str,
        channel_id: str,
        message_seq: str,
        body: str,
        *,
        version: int,
    ) -> Message:
        """Replace the text of an existing message."""
        if not body:
            raise ValueError("edited message body cannot be empty")
        if len(body) > 4000:
            raise ValueError("message body cannot exceed 4000 characters")
        payload = await self._transport.request(
            "PATCH",
            self._message_path(community_id, channel_id, message_seq),
            json={"body": body, "version": version},
        )
        return _required_message(payload, "edited")

    async def delete(self, community_id: str, channel_id: str, message_seq: str) -> None:
        """Delete a message. Repeating the same request is safe at transport level."""
        await self._transport.request(
            "DELETE",
            self._message_path(community_id, channel_id, message_seq),
            retryable=True,
        )

    async def set_pin(
        self,
        community_id: str,
        channel_id: str,
        message_seq: str,
        *,
        pinned: bool = True,
    ) -> Message:
        """Set the desired pin state for a message."""
        payload = await self._transport.request(
            "PUT",
            f"{self._message_path(community_id, channel_id, message_seq)}/pin",
            json={"pinned": pinned},
            retryable=True,
        )
        return _required_message(payload, "pin update")

    async def set_reaction(
        self,
        community_id: str,
        channel_id: str,
        message_seq: str,
        emoji: str,
        *,
        active: bool = True,
    ) -> Message:
        """Set the current bot's desired reaction state."""
        if not emoji or len(emoji) > 64:
            raise ValueError("emoji must contain between 1 and 64 characters")
        payload = await self._transport.request(
            "PUT",
            f"{self._message_path(community_id, channel_id, message_seq)}/reactions",
            json={"emoji": emoji, "active": active},
            retryable=True,
        )
        return _required_message(payload, "reaction update")

    async def pins(
        self,
        community_id: str,
        channel_id: str,
    ) -> MessagePage:
        """Read pinned messages in a channel."""
        payload = await self._transport.request(
            "GET",
            f"{self._channel_path(community_id, channel_id)}/pins",
        )
        return _message_page(payload)

    async def search(
        self,
        community_id: str,
        channel_id: str,
        query: str,
        *,
        before_seq: str | None = None,
    ) -> MessagePage:
        """Search visible messages in a channel."""
        if not query.strip():
            raise ValueError("search query cannot be empty")
        payload = await self._transport.request(
            "GET",
            f"{self._channel_path(community_id, channel_id)}/search",
            params={"q": query, "beforeSeq": before_seq},
        )
        return _message_page(payload)

    @staticmethod
    def _messages_path(community_id: str, channel_id: str) -> str:
        return f"/api/communities/{community_id}/channels/{channel_id}/messages"

    @staticmethod
    def _channel_path(community_id: str, channel_id: str) -> str:
        return f"/api/communities/{community_id}/channels/{channel_id}"

    @classmethod
    def _message_path(cls, community_id: str, channel_id: str, message_seq: str) -> str:
        return f"{cls._messages_path(community_id, channel_id)}/{message_seq}"


def _optional_cursor(value: object) -> str | None:
    return None if value is None else str(value)


def _validate_limit(limit: int) -> None:
    if not 1 <= limit <= 100:
        raise ValueError("limit must be between 1 and 100")


def _message_page(payload: dict[str, object] | None) -> MessagePage:
    if payload is None:
        return MessagePage(())
    raw_items = payload.get("items", payload.get("messages", []))
    items = raw_items if isinstance(raw_items, list) else []
    return MessagePage(
        items=tuple(Message.from_dict(item) for item in items if isinstance(item, dict)),
        next_before_seq=_optional_cursor(payload.get("nextBeforeSeq")),
    )


def _required_message(payload: dict[str, object] | None, operation: str) -> Message:
    if payload is None:
        raise RuntimeError(f"VoiceRoute returned no message after {operation}")
    raw_message = payload.get("message", payload)
    if not isinstance(raw_message, dict):
        raise RuntimeError(f"VoiceRoute returned an invalid message after {operation}")
    return Message.from_dict(raw_message)
