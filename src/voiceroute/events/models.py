"""High-level bot event models."""

from dataclasses import dataclass

from voiceroute.models import Interaction, Message


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


@dataclass(frozen=True, slots=True)
class InteractionCreated:
    """A native application-command invocation ready for a response."""

    interaction: Interaction
    cursor: str | None


BotEvent = MessageUpserted | InteractionCreated | AccessLost
