"""Transport-independent event delivery contracts."""

from __future__ import annotations

from collections.abc import AsyncIterator
from dataclasses import dataclass
from enum import StrEnum
from typing import Protocol

from voiceroute.events.cursors import StreamCheckpoint
from voiceroute.events.models import AccessLost, BotEvent, MessageUpserted
from voiceroute.models import MessagePage


class EventStreamAPI(Protocol):
    """Minimal event API required by the legacy transport."""

    def listen_messages(
        self,
        community_id: str,
        channel_id: str,
        *,
        after_seq: str | None = None,
        cursor: str | None = None,
        reconnect: bool = True,
        max_backoff: float = 30.0,
    ) -> AsyncIterator[BotEvent]: ...


class MessageHistoryAPI(Protocol):
    """Minimal message API required for history catch-up."""

    async def history(
        self,
        community_id: str,
        channel_id: str,
        *,
        limit: int = 50,
        before_seq: str | None = None,
        after_seq: str | None = None,
    ) -> MessagePage: ...


@dataclass(frozen=True, slots=True)
class ChannelTarget:
    """A community channel selected for event consumption."""

    community_id: str
    channel_id: str


class EventSource(StrEnum):
    """Network source from which a normalized event was delivered."""

    HISTORY = "history"
    LEGACY_SSE = "legacy_sse"


@dataclass(frozen=True, slots=True)
class EventDelivery:
    """One normalized event and the checkpoint to persist after handling it."""

    event: BotEvent
    checkpoint: StreamCheckpoint
    source: EventSource


class EventTransport(Protocol):
    """Produce normalized bot events without exposing a wire protocol to the runtime."""

    def stream_key(self, target: ChannelTarget) -> str:
        """Return the stable persistence key for a target stream."""
        ...

    def listen(
        self,
        target: ChannelTarget,
        *,
        checkpoint: StreamCheckpoint | None,
        initial_after_seq: str | None,
    ) -> AsyncIterator[EventDelivery]:
        """Yield normalized events beginning at a persisted checkpoint."""
        ...


class LegacySSETransport:
    """Adapt the current per-channel history and SSE APIs to normalized deliveries."""

    def __init__(
        self,
        events: EventStreamAPI,
        messages: MessageHistoryAPI,
        *,
        base_url: str,
    ) -> None:
        self._events = events
        self._messages = messages
        self._base_url = base_url.rstrip("/")

    def stream_key(self, target: ChannelTarget) -> str:
        return f"{self._base_url}|messages|{target.community_id}|{target.channel_id}"

    async def listen(
        self,
        target: ChannelTarget,
        *,
        checkpoint: StreamCheckpoint | None,
        initial_after_seq: str | None,
    ) -> AsyncIterator[EventDelivery]:
        change_cursor = checkpoint.change_cursor if checkpoint is not None else None
        message_seq = checkpoint.message_seq if checkpoint is not None else initial_after_seq

        if change_cursor is None and message_seq is not None:
            async for delivery in self._history(target, after_seq=message_seq):
                message_seq = delivery.checkpoint.message_seq
                yield delivery

        async for event in self._events.listen_messages(
            target.community_id,
            target.channel_id,
            after_seq=message_seq,
            cursor=change_cursor,
        ):
            if isinstance(event, AccessLost):
                yield EventDelivery(
                    event=event,
                    checkpoint=StreamCheckpoint(
                        change_cursor=event.cursor,
                        message_seq=message_seq,
                    ),
                    source=EventSource.LEGACY_SSE,
                )
                return
            if not isinstance(event, MessageUpserted):
                continue

            message_seq = event.message.seq
            yield EventDelivery(
                event=event,
                checkpoint=StreamCheckpoint(
                    change_cursor=event.cursor,
                    message_seq=message_seq,
                ),
                source=EventSource.LEGACY_SSE,
            )

    async def _history(
        self,
        target: ChannelTarget,
        *,
        after_seq: str,
    ) -> AsyncIterator[EventDelivery]:
        current_seq = after_seq
        while True:
            page = await self._messages.history(
                target.community_id,
                target.channel_id,
                limit=100,
                after_seq=current_seq,
            )
            if not page.items:
                return
            for message in page.items:
                current_seq = message.seq
                yield EventDelivery(
                    event=MessageUpserted(message=message, cursor=None),
                    checkpoint=StreamCheckpoint(
                        change_cursor=None,
                        message_seq=current_seq,
                    ),
                    source=EventSource.HISTORY,
                )
            if len(page.items) < 100:
                return
