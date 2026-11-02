"""Version 1 message DTOs, kept separate from legacy sequence messages."""

from __future__ import annotations

from dataclasses import dataclass, field
from types import MappingProxyType
from typing import Any, Self


@dataclass(frozen=True, slots=True)
class RichMessage:
    """V1 UUID-addressed message with the complete server payload preserved."""

    id: str
    sequence: str
    community_id: str
    channel_id: str
    content: str
    data: MappingProxyType[str, Any] = field(default_factory=lambda: MappingProxyType({}))

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> Self:
        known = {"id", "sequence", "communityId", "channelId", "content"}
        return cls(
            id=str(data["id"]),
            sequence=str(data["sequence"]),
            community_id=str(data["communityId"]),
            channel_id=str(data["channelId"]),
            content=str(data.get("content", "")),
            data=MappingProxyType({key: value for key, value in data.items() if key not in known}),
        )


@dataclass(frozen=True, slots=True)
class RichMessagePage:
    """Cursor page of UUID-addressed messages."""

    items: tuple[RichMessage, ...]
    next_cursor: str | None = None
