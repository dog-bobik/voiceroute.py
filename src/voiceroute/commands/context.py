"""Command invocation context."""

from __future__ import annotations

import uuid
from dataclasses import dataclass, field

from voiceroute.api.messages import MessagesAPI
from voiceroute.errors import Conflict
from voiceroute.models import Message

_REPLY_NAMESPACE = uuid.UUID("88769cac-916c-4a4a-a370-a1f971729e7b")


@dataclass(slots=True)
class Context:
    """Information and helpers for one command invocation."""

    message: Message
    command: str
    args: tuple[str, ...]
    _messages: MessagesAPI = field(repr=False)
    invoked_with: str | None = None
    prefix: str | None = None
    _reply_index: int = field(default=0, init=False, repr=False)

    async def reply(self, body: str) -> Message:
        """Reply idempotently to the invoking message."""
        operation_id = uuid.uuid5(
            _REPLY_NAMESPACE,
            ":".join(
                (
                    self.message.community_id,
                    self.message.channel_id,
                    self.message.seq,
                    self.command,
                    str(self._reply_index),
                )
            ),
        )
        try:
            message = await self._messages.send(
                self.message.community_id,
                self.message.channel_id,
                body,
                reply_to_seq=self.message.seq,
                client_message_id=operation_id,
            )
        except Conflict:
            existing = await self._find_reply(operation_id)
            self._reply_index += 1
            if existing is not None:
                return existing
            raise
        else:
            self._reply_index += 1
            return message

    async def _find_reply(self, operation_id: uuid.UUID) -> Message | None:
        """Recover the response created by an earlier delivery of this command."""
        before_seq: str | None = None
        visited_cursors: set[str] = set()
        while True:
            page = await self._messages.history(
                self.message.community_id,
                self.message.channel_id,
                limit=100,
                before_seq=before_seq,
            )
            expected_id = str(operation_id)
            existing = next(
                (item for item in page.items if item.client_message_id == expected_id),
                None,
            )
            if existing is not None:
                return existing
            cursor = page.next_before_seq
            if cursor is None or cursor in visited_cursors:
                return None
            visited_cursors.add(cursor)
            before_seq = cursor
