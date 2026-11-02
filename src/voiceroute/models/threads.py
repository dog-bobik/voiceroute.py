"""Typed thread DTO and cursor page."""

from __future__ import annotations

from dataclasses import dataclass, field
from types import MappingProxyType
from typing import Any, Self


@dataclass(frozen=True, slots=True)
class Thread:
    id: str
    community_id: str
    channel_id: str
    name: str
    archived: bool
    private: bool
    invitable: bool
    version: str
    data: MappingProxyType[str, Any] = field(default_factory=lambda: MappingProxyType({}))

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> Self:
        known = {
            "id",
            "communityId",
            "channelId",
            "name",
            "archived",
            "private",
            "invitable",
            "version",
        }
        return cls(
            id=str(data["id"]),
            community_id=str(data["communityId"]),
            channel_id=str(data["channelId"]),
            name=str(data.get("name", "")),
            archived=bool(data.get("archived", False)),
            private=bool(data.get("private", False)),
            invitable=bool(data.get("invitable", True)),
            version=str(data.get("version", "")),
            data=MappingProxyType({key: value for key, value in data.items() if key not in known}),
        )

    @property
    def etag(self) -> str:
        """Return the resource ETag suitable for a subsequent conditional write."""
        if not self.version:
            raise RuntimeError("thread version is missing from the response")
        return f'"thread-{self.version}"'


@dataclass(frozen=True, slots=True)
class ThreadPage:
    items: tuple[Thread, ...]
    next_cursor: str | None = None


@dataclass(frozen=True, slots=True)
class ThreadMember:
    user_id: int
    joined_at: str

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> Self:
        return cls(user_id=int(data["userId"]), joined_at=str(data["joinedAt"]))


@dataclass(frozen=True, slots=True)
class ThreadMemberPage:
    items: tuple[ThreadMember, ...]
    next_cursor: str | None = None
