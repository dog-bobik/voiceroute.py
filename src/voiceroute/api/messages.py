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
        if not 1 <= limit <= 100:
            raise ValueError("limit must be between 1 and 100")
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
        return MessagePage(
            items=tuple(Message.from_dict(item) for item in payload.get("items", [])),
            next_before_seq=_optional_cursor(payload.get("nextBeforeSeq")),
        )

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
        )
        if payload is None:
            raise RuntimeError("VoiceRoute returned no sent message")
        return Message.from_dict(payload["message"])

    @staticmethod
    def _messages_path(community_id: str, channel_id: str) -> str:
        return f"/api/communities/{community_id}/channels/{channel_id}/messages"


def _optional_cursor(value: object) -> str | None:
    return None if value is None else str(value)
