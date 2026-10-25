"""Resumable bot event streams."""

from __future__ import annotations

import asyncio
import json
from collections.abc import AsyncIterator

from voiceroute.errors import SSEError
from voiceroute.events.models import AccessLost, BotEvent, MessageUpserted
from voiceroute.events.sse import SSEDecoder
from voiceroute.models import Message
from voiceroute.transport import HTTPTransport


class EventsAPI:
    """Consume authenticated channel message events with cursor recovery."""

    def __init__(self, transport: HTTPTransport) -> None:
        self._transport = transport

    async def listen_messages(
        self,
        community_id: str,
        channel_id: str,
        *,
        after_seq: str | None = None,
        cursor: str | None = None,
        reconnect: bool = True,
        max_backoff: float = 30.0,
    ) -> AsyncIterator[BotEvent]:
        if max_backoff <= 0:
            raise ValueError("max_backoff must be positive")

        last_cursor = cursor
        backoff = 1.0
        path = f"/api/communities/{community_id}/channels/{channel_id}/events"

        while True:
            params = {
                "after": after_seq if last_cursor is None else None,
                "changeCursor": last_cursor,
            }
            headers = {"Last-Event-ID": last_cursor} if last_cursor is not None else None
            decoder = SSEDecoder()

            async with self._transport.stream(path, params=params, headers=headers) as response:
                async for line in response.aiter_lines():
                    frame = decoder.feed_line(line)
                    if frame is None:
                        continue
                    if frame.id is not None:
                        last_cursor = frame.id
                    backoff = 1.0

                    event = self._decode(frame.event, frame.data, last_cursor)
                    yield event
                    if isinstance(event, AccessLost):
                        return

            if not reconnect:
                return
            await asyncio.sleep(backoff)
            backoff = min(backoff * 2, max_backoff)

    @staticmethod
    def _decode(event_name: str, data: str, cursor: str | None) -> BotEvent:
        try:
            payload = json.loads(data)
        except json.JSONDecodeError as exc:
            raise SSEError("VoiceRoute SSE event contains invalid JSON") from exc

        if event_name == "message":
            if not isinstance(payload, dict):
                raise SSEError("VoiceRoute message event must contain a JSON object")
            return MessageUpserted(Message.from_dict(payload), cursor)
        if event_name == "access-lost":
            reason = payload.get("reason") if isinstance(payload, dict) else None
            return AccessLost(cursor=cursor, reason=str(reason) if reason is not None else None)
        raise SSEError(f"unsupported VoiceRoute SSE event: {event_name}")
