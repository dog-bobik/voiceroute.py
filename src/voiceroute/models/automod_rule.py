"""Versioned v1 automatic moderation rule DTOs."""

from __future__ import annotations

from dataclasses import dataclass
from types import MappingProxyType
from typing import Any, Self


@dataclass(frozen=True, slots=True)
class AutoModRule:
    id: str
    community_id: str
    name: str
    enabled: bool
    trigger: str
    metadata: MappingProxyType[str, Any]
    actions: tuple[MappingProxyType[str, Any], ...]
    exempt_role_ids: tuple[str, ...]
    exempt_channel_ids: tuple[str, ...]
    version: str

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> Self:
        return cls(
            id=str(data["id"]),
            community_id=str(data["communityId"]),
            name=str(data["name"]),
            enabled=bool(data["enabled"]),
            trigger=str(data["trigger"]),
            metadata=MappingProxyType(dict(data.get("metadata", {}))),
            actions=tuple(MappingProxyType(dict(item)) for item in data.get("actions", ())),
            exempt_role_ids=tuple(map(str, data.get("exemptRoleIds", ()))),
            exempt_channel_ids=tuple(map(str, data.get("exemptChannelIds", ()))),
            version=str(data["version"]),
        )

    @property
    def etag(self) -> str:
        return f'"automod-{self.version}"'


@dataclass(frozen=True, slots=True)
class AutoModRulePage:
    items: tuple[AutoModRule, ...]
    next_cursor: str | None = None
