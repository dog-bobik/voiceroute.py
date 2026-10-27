"""Typed cached entities and explicit, network-free domain converters."""

from __future__ import annotations

from dataclasses import dataclass
from types import MappingProxyType
from typing import Any, Literal, TypeAlias

from voiceroute.models import Channel, Community, Member, Message, Role, User

EntityKind = Literal[
    "community",
    "category",
    "channel",
    "role",
    "member",
    "thread",
    "message",
    "poll",
    "expression",
    "ban",
    "voice_state",
    "installation",
]


@dataclass(frozen=True, slots=True)
class CachedEntity:
    """Possibly partial or redacted resource snapshot; properties never perform I/O."""

    kind: EntityKind
    id: str
    data: MappingProxyType[str, Any]
    sequence: str | None = None
    community_id: str | None = None
    channel_id: str | None = None
    partial: bool = True
    redacted: bool = False

    def __getattr__(self, name: str) -> Any:
        try:
            return self.data[name]
        except KeyError as exc:
            raise AttributeError(name) from exc


@dataclass(frozen=True, slots=True)
class CachedCommunity(CachedEntity):
    def to_domain(self) -> Community:
        return Community.from_dict(dict(self.data))


@dataclass(frozen=True, slots=True)
class CachedChannel(CachedEntity):
    def to_domain(self) -> Channel:
        return Channel.from_dict(dict(self.data), community_id=self.community_id)


@dataclass(frozen=True, slots=True)
class CachedRole(CachedEntity):
    def to_domain(self) -> Role:
        return Role.from_dict(dict(self.data))


@dataclass(frozen=True, slots=True)
class CachedMember(CachedEntity):
    def to_domain(self) -> Member:
        if self.community_id is None:
            raise ValueError("cached member is missing communityId")
        data = dict(self.data)
        if "user" not in data and data.get("userId") is not None:
            data["user"] = {
                "id": data["userId"],
                "username": data.get("username", ""),
                "displayName": data.get("displayName", data.get("username", "")),
                "bot": data.get("bot", False),
            }
        return Member.from_dict(data, community_id=self.community_id)


@dataclass(frozen=True, slots=True)
class CachedMessage(CachedEntity):
    def to_domain(self) -> Message:
        return Message.from_dict(dict(self.data))


@dataclass(frozen=True, slots=True)
class CachedUser(CachedEntity):
    def to_domain(self) -> User:
        return User.from_dict(dict(self.data))


@dataclass(frozen=True, slots=True)
class CachedResource(CachedEntity):
    """Typed snapshot for domains whose public resource API is implemented later."""


CachedDomainEntity: TypeAlias = (
    CachedCommunity
    | CachedChannel
    | CachedRole
    | CachedMember
    | CachedMessage
    | CachedUser
    | CachedResource
)


_ENTITY_TYPES: dict[EntityKind, type[CachedEntity]] = {
    "community": CachedCommunity,
    "channel": CachedChannel,
    "role": CachedRole,
    "member": CachedMember,
    "message": CachedMessage,
}


def cached_entity(
    kind: EntityKind,
    entity_id: str,
    data: dict[str, Any],
    *,
    sequence: str | None = None,
    community_id: str | None = None,
    channel_id: str | None = None,
    partial: bool = True,
    redacted: bool = False,
) -> CachedEntity:
    entity_type = _ENTITY_TYPES.get(kind, CachedResource)
    return entity_type(
        kind=kind,
        id=entity_id,
        data=MappingProxyType(data),
        sequence=sequence,
        community_id=community_id,
        channel_id=channel_id,
        partial=partial,
        redacted=redacted,
    )
