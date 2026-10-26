"""Gateway intent selection and privileged-intent metadata."""

from __future__ import annotations

from collections.abc import Iterable, Iterator
from enum import StrEnum


class Intent(StrEnum):
    MODERATION = "moderation"
    THREADS = "threads"
    PRESENCE = "presence"
    VOICE_STATES = "voiceStates"
    WEBHOOKS = "webhooks"
    AUDIT_LOG = "auditLog"
    COMMUNITIES = "communities"
    MEMBERS = "members"
    MESSAGES = "messages"
    MESSAGE_CONTENT = "messageContent"
    REACTIONS = "reactions"
    POLLS = "polls"
    INTERACTIONS = "interactions"


PRIVILEGED_INTENTS = frozenset(
    {
        Intent.MODERATION,
        Intent.PRESENCE,
        Intent.VOICE_STATES,
        Intent.AUDIT_LOG,
        Intent.MEMBERS,
        Intent.MESSAGE_CONTENT,
    }
)


class Intents:
    """Immutable, type-safe set of Gateway intents."""

    __slots__ = ("_values",)

    def __init__(
        self,
        *,
        moderation: bool = False,
        threads: bool = False,
        presence: bool = False,
        voice_states: bool = False,
        webhooks: bool = False,
        audit_log: bool = False,
        communities: bool = False,
        members: bool = False,
        messages: bool = False,
        message_content: bool = False,
        reactions: bool = False,
        polls: bool = False,
        interactions: bool = False,
    ) -> None:
        flags = {
            Intent.MODERATION: moderation,
            Intent.THREADS: threads,
            Intent.PRESENCE: presence,
            Intent.VOICE_STATES: voice_states,
            Intent.WEBHOOKS: webhooks,
            Intent.AUDIT_LOG: audit_log,
            Intent.COMMUNITIES: communities,
            Intent.MEMBERS: members,
            Intent.MESSAGES: messages,
            Intent.MESSAGE_CONTENT: message_content,
            Intent.REACTIONS: reactions,
            Intent.POLLS: polls,
            Intent.INTERACTIONS: interactions,
        }
        self._values = frozenset(intent for intent, enabled in flags.items() if enabled)

    @classmethod
    def from_values(cls, values: Iterable[Intent | str]) -> Intents:
        instance = cls()
        instance._values = frozenset(Intent(value) for value in values)
        return instance

    @classmethod
    def default(cls) -> Intents:
        return cls(
            threads=True,
            webhooks=True,
            communities=True,
            messages=True,
            reactions=True,
            polls=True,
            interactions=True,
        )

    @classmethod
    def all(cls) -> Intents:
        return cls.from_values(Intent)

    @property
    def values(self) -> tuple[str, ...]:
        return tuple(intent.value for intent in Intent if intent in self._values)

    @property
    def privileged(self) -> frozenset[Intent]:
        return self._values & PRIVILEGED_INTENTS

    def __contains__(self, intent: object) -> bool:
        try:
            return Intent(intent) in self._values  # type: ignore[arg-type]
        except (TypeError, ValueError):
            return False

    def __iter__(self) -> Iterator[Intent]:
        return iter(intent for intent in Intent if intent in self._values)

    def __len__(self) -> int:
        return len(self._values)

    def __repr__(self) -> str:
        names = ", ".join(intent.name for intent in self)
        return f"Intents({names})"
