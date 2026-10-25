"""High-level bot event models."""

from dataclasses import dataclass

from voiceroute.models import Message


@dataclass(frozen=True, slots=True)
class MessageUpserted:
    """A created, edited, deleted, or initially replayed message."""

    message: Message
    cursor: str | None


@dataclass(frozen=True, slots=True)
class AccessLost:
    """The bot lost authentication, membership, or channel access."""

    cursor: str | None
    reason: str | None = None


BotEvent = MessageUpserted | AccessLost
