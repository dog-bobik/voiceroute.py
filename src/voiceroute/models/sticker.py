"""Community sticker DTO."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Self


@dataclass(frozen=True, slots=True)
class CommunityExpression:
    id: str
    community_id: str
    kind: str
    name: str
    description: str
    tag: str
    format: str
    mime: str
    size: int
    animated: bool
    available: bool
    usable: bool
    role_ids: tuple[str, ...]
    version: str
    url: str

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> Self:
        return cls(
            id=str(data["id"]),
            community_id=str(data["communityId"]),
            kind=str(data.get("kind", "sticker")),
            name=str(data["name"]),
            description=str(data.get("description", "")),
            tag=str(data.get("tag", "")),
            format=str(data["format"]),
            mime=str(data["mime"]),
            size=int(data["size"]),
            animated=bool(data["animated"]),
            available=bool(data["available"]),
            usable=bool(data["usable"]),
            role_ids=tuple(map(str, data.get("roleIds", ()))),
            version=str(data["version"]),
            url=str(data["url"]),
        )

    @property
    def etag(self) -> str:
        if not self.version:
            raise RuntimeError("expression version is missing from the response")
        return f'"{self.kind}-{self.version}"'


Sticker = CommunityExpression
