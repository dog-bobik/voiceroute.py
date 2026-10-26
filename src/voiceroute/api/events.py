"""Resumable bot event streams."""

from __future__ import annotations

import asyncio
import json
from collections.abc import AsyncIterator

from voiceroute.errors import RateLimited, ServiceUnavailable, SSEError, TransportError
from voiceroute.events.models import AccessLost, BotEvent, InteractionCreated, MessageUpserted
from voiceroute.events.sse import SSEDecoder
from voiceroute.models import Interaction, Message
from voiceroute.transport import HTTPTransport


class EventsAPI:
    """Consume authenticated channel message events with cursor recovery."""

    def __init__(self, transport: HTTPTransport) -> None:
        self._transport = transport

    async def listen_interactions(
        self,
        *,
        cursor: str | None = "0",
        reconnect: bool = True,
        max_backoff: float = 30.0,
    ) -> AsyncIterator[BotEvent]:
        """Consume the current bot's native interaction stream."""
        async for event in self._listen(
            "/api/bots/@me/events",
            cursor=cursor,
            reconnect=reconnect,
            max_backoff=max_backoff,
            allowed_events={"interaction", "access-lost"},
        ):
            yield event

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
        path = f"/api/communities/{community_id}/channels/{channel_id}/events"

        async for event in self._listen(
            path,
            cursor=cursor,
            after_seq=after_seq,
            reconnect=reconnect,
            max_backoff=max_backoff,
            allowed_events={"message", "access-lost"},
        ):
            yield event

    async def _listen(
        self,
        path: str,
        *,
        cursor: str | None,
        reconnect: bool,
        max_backoff: float,
        allowed_events: set[str],
        after_seq: str | None = None,
    ) -> AsyncIterator[BotEvent]:
        if max_backoff <= 0:
            raise ValueError("max_backoff must be positive")

        last_cursor = cursor
        backoff = 1.0

        while True:
            params = {
                "after": after_seq if last_cursor is None else last_cursor,
            }
            if after_seq is not None:
                params = {
                    "after": after_seq if last_cursor is None else None,
                    "changeCursor": last_cursor,
                }
            headers = {"Last-Event-ID": last_cursor} if last_cursor is not None else None
            decoder = SSEDecoder()

            retry_delay: float | None = None
            try:
                async with self._transport.stream(path, params=params, headers=headers) as response:
                    async for line in response.aiter_lines():
                        frame = decoder.feed_line(line)
                        if frame is None:
                            continue
                        if frame.id is not None:
                            last_cursor = frame.id
                        backoff = 1.0

                        if frame.event not in allowed_events:
                            raise SSEError(f"unsupported VoiceRoute SSE event: {frame.event}")
                        event = self._decode(frame.event, frame.data, last_cursor)
                        yield event
                        if isinstance(event, AccessLost):
                            return
            except RateLimited as exc:
                retry_delay = exc.retry_after
            except (ServiceUnavailable, TransportError):
                pass

            if not reconnect:
                return
            await asyncio.sleep(retry_delay if retry_delay is not None else backoff)
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
        if event_name == "interaction":
            if not isinstance(payload, dict):
                raise SSEError("VoiceRoute interaction event must contain a JSON object")
            return InteractionCreated(Interaction.from_dict(payload), cursor)
        if event_name == "access-lost":
            reason = payload.get("reason") if isinstance(payload, dict) else None
            return AccessLost(cursor=cursor, reason=str(reason) if reason is not None else None)
        raise SSEError(f"unsupported VoiceRoute SSE event: {event_name}")
