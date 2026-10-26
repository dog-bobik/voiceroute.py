"""Community and channel models."""

from dataclasses import dataclass, field
from types import MappingProxyType
from typing import Any, Self

from voiceroute.models.permissions import Permissions


def _extra_fields(data: dict[str, Any], known: set[str]) -> MappingProxyType[str, Any]:
    return MappingProxyType({key: value for key, value in data.items() if key not in known})


@dataclass(frozen=True, slots=True)
class Community:
    """A community in which the bot is an active member."""

    id: str
    name: str
    permissions: Permissions = field(default_factory=Permissions)
    extra: MappingProxyType[str, Any] = field(default_factory=lambda: MappingProxyType({}))

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> Self:
        permissions = data.get("permissions", ())
        return cls(
            id=str(data["id"]),
            name=str(data["name"]),
            permissions=Permissions(str(permission) for permission in permissions),
            extra=_extra_fields(data, {"id", "name", "permissions"}),
        )


@dataclass(frozen=True, slots=True)
class Channel:
    """A channel visible to the current bot."""

    id: str
    name: str
    kind: str
    community_id: str | None = None
    category_id: str | None = None
    position: int | None = None
    permissions: Permissions = field(default_factory=Permissions)
    extra: MappingProxyType[str, Any] = field(default_factory=lambda: MappingProxyType({}))

    @property
    def type(self) -> str:
        """Compatibility alias for the channel kind."""
        return self.kind

    @classmethod
    def from_dict(cls, data: dict[str, Any], *, community_id: str | None = None) -> Self:
        raw_position = data.get("position")
        known = {
            "id",
            "name",
            "kind",
            "type",
            "communityId",
            "categoryId",
            "position",
            "permissions",
        }
        raw_kind = data.get("kind", data.get("type"))
        if raw_kind is None:
            raise ValueError("channel payload is missing kind")
        return cls(
            id=str(data["id"]),
            name=str(data["name"]),
            kind=str(raw_kind),
            community_id=community_id or _optional_string(data.get("communityId")),
            category_id=_optional_string(data.get("categoryId")),
            position=int(raw_position) if raw_position is not None else None,
            permissions=Permissions(str(value) for value in data.get("permissions", ())),
            extra=_extra_fields(data, known),
        )


def _optional_string(value: Any) -> str | None:
    return None if value is None else str(value)
