"""Tracked installation capabilities selected for Gateway delivery."""

from __future__ import annotations

from collections.abc import Iterable, Iterator
from enum import StrEnum


class Capability(StrEnum):
    MODERATION = "moderation"
    THREADS = "threads"
    PRESENCE = "presence"
    VOICE_STATES = "voiceStates"
    AUDIT_LOG = "auditLog"
    MEMBERS = "members"
    MESSAGES = "messages"
    MESSAGE_CONTENT = "messageContent"
    REACTIONS = "reactions"
    POLLS = "polls"


TRACKED_CAPABILITIES = frozenset(Capability)


class Capabilities:
    """Immutable, type-safe set of tracked installation capabilities."""

    __slots__ = ("_values",)

    def __init__(
        self,
        *,
        moderation: bool = False,
        threads: bool = False,
        presence: bool = False,
        voice_states: bool = False,
        audit_log: bool = False,
        members: bool = False,
        messages: bool = False,
        message_content: bool = False,
        reactions: bool = False,
        polls: bool = False,
    ) -> None:
        flags = {
            Capability.MODERATION: moderation,
            Capability.THREADS: threads,
            Capability.PRESENCE: presence,
            Capability.VOICE_STATES: voice_states,
            Capability.AUDIT_LOG: audit_log,
            Capability.MEMBERS: members,
            Capability.MESSAGES: messages,
            Capability.MESSAGE_CONTENT: message_content,
            Capability.REACTIONS: reactions,
            Capability.POLLS: polls,
        }
        self._values = frozenset(capability for capability, enabled in flags.items() if enabled)

    @classmethod
    def from_values(cls, values: Iterable[Capability | str]) -> Capabilities:
        instance = cls()
        instance._values = frozenset(Capability(value) for value in values)
        return instance

    @classmethod
    def default(cls) -> Capabilities:
        return cls()

    @classmethod
    def all(cls) -> Capabilities:
        return cls.from_values(Capability)

    @property
    def values(self) -> tuple[str, ...]:
        return tuple(capability.value for capability in Capability if capability in self._values)

    @property
    def tracked(self) -> frozenset[Capability]:
        return self._values

    def __contains__(self, capability: object) -> bool:
        try:
            return Capability(capability) in self._values  # type: ignore[arg-type]
        except (TypeError, ValueError):
            return False

    def __iter__(self) -> Iterator[Capability]:
        return iter(capability for capability in Capability if capability in self._values)

    def __len__(self) -> int:
        return len(self._values)

    def __repr__(self) -> str:
        names = ", ".join(capability.name for capability in self)
        return f"Capabilities({names})"


# Compatibility aliases for the pre-installation-grants experimental API.
Intent = Capability
Intents = Capabilities
PRIVILEGED_INTENTS: frozenset[Capability] = frozenset()
