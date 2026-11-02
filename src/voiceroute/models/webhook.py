"""Incoming message webhook metadata with secret-safe representations."""

from __future__ import annotations

from dataclasses import dataclass, field
from types import MappingProxyType
from typing import Any, Self


@dataclass(frozen=True, slots=True)
class Webhook:
    id: str
    community_id: str
    channel_id: str
    name: str
    version: str
    token: str | None = field(default=None, repr=False)
    url: str | None = field(default=None, repr=False)
    data: MappingProxyType[str, Any] = field(default_factory=lambda: MappingProxyType({}))

    @property
    def etag(self) -> str:
        if not self.version:
            raise RuntimeError("webhook version is missing from the response")
        return f'"webhook-{self.version}"'

    def __repr__(self) -> str:
        return (
            f"Webhook(id={self.id!r}, community_id={self.community_id!r}, "
            f"channel_id={self.channel_id!r}, name={self.name!r}, token=<redacted>)"
        )

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> Self:
        known = {"id", "communityId", "channelId", "name", "version", "token", "url"}
        return cls(
            id=str(data["id"]),
            community_id=str(data["communityId"]),
            channel_id=str(data["channelId"]),
            name=str(data.get("name", "")),
            version=str(data.get("version", "")),
            token=str(data["token"]) if data.get("token") is not None else None,
            url=str(data["url"]) if data.get("url") is not None else None,
            data=MappingProxyType({key: value for key, value in data.items() if key not in known}),
        )
