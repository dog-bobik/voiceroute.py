"""Metadata and ergonomic handler aliases for every platform event."""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass
from types import MappingProxyType
from typing import Any

from voiceroute.models import PlatformEventType


@dataclass(frozen=True, slots=True)
class EventDefinition:
    type: PlatformEventType
    handlers: tuple[str, ...]
    resource: str
    ordering_fields: tuple[str, ...]

    def resource_key(self, data: Mapping[str, Any]) -> str:
        values = tuple(
            str(data[field]) for field in self.ordering_fields if data.get(field) is not None
        )
        return ":".join((self.resource, *values)) if values else self.resource


_ACTION_ALIASES = {
    "CREATED": "create",
    "UPDATED": "update",
    "DELETED": "delete",
    "ADDED": "add",
    "REMOVED": "remove",
    "JOINED": "join",
    "LEFT": "remove",
    "STARTED": "start",
    "STOPPED": "stop",
    "PLAYED": "play",
    "CLOSED": "close",
    "EXECUTED": "action",
}

_RESOURCE_FIELDS: dict[str, tuple[str, ...]] = {
    "APPLICATION": ("applicationId",),
    "INSTALLATION": ("installationId",),
    "USER_INSTALLATION": ("installationId", "userId"),
    "COMMUNITY": ("communityId",),
    "CATEGORY": ("communityId", "categoryId"),
    "CHANNEL": ("communityId", "channelId"),
    "ROLE": ("communityId", "roleId"),
    "MEMBER": ("communityId", "userId"),
    "PRESENCE": ("communityId", "userId"),
    "MESSAGE": ("communityId", "channelId", "messageId", "messageSeq"),
    "REACTION": ("communityId", "channelId", "messageId", "messageSeq"),
    "THREAD": ("communityId", "threadId"),
    "POLL": ("communityId", "channelId", "pollId"),
    "VOICE": ("communityId", "channelId", "userId"),
    "INTERACTION": ("interactionId",),
}


def _resource(name: str) -> str:
    for candidate in sorted(_RESOURCE_FIELDS, key=len, reverse=True):
        if name.startswith(candidate + "_"):
            return candidate.casefold()
    return name.split("_", 1)[0].casefold()


def _handlers(event_type: PlatformEventType) -> tuple[str, ...]:
    raw = event_type.value.casefold()
    handlers = [f"on_{raw}"]
    prefix, separator, action = raw.rpartition("_")
    alias = _ACTION_ALIASES.get(action.upper()) if separator else None
    if alias is not None:
        handlers.append(f"on_{prefix}_{alias}")
    if event_type is PlatformEventType.MEMBER_LEFT:
        handlers.append("on_member_leave")
    if event_type is PlatformEventType.AUTOMOD_ACTION_EXECUTED:
        handlers.append("on_automod_action")
    return tuple(dict.fromkeys(handlers))


def _definition(event_type: PlatformEventType) -> EventDefinition:
    resource = _resource(event_type.value)
    field_key = resource.upper()
    return EventDefinition(
        type=event_type,
        handlers=_handlers(event_type),
        resource=resource,
        ordering_fields=_RESOURCE_FIELDS.get(field_key, ()),
    )


EVENT_CATALOG: Mapping[PlatformEventType, EventDefinition] = MappingProxyType(
    {event_type: _definition(event_type) for event_type in PlatformEventType}
)


def event_definition(name: str | PlatformEventType) -> EventDefinition | None:
    try:
        return EVENT_CATALOG[PlatformEventType(name)]
    except ValueError:
        return None
