"""Community role and permission override models."""

from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum
from typing import Any, Self

from voiceroute.models.permissions import Permissions


@dataclass(frozen=True, slots=True)
class Role:
    """A community role visible to the current bot."""

    id: str
    community_id: str
    name: str
    color: str | None
    position: int
    builtin: str | None
    managed_application_id: str | None
    permissions: Permissions
    can_manage: bool

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> Self:
        return cls(
            id=str(data["id"]),
            community_id=str(data["communityId"]),
            name=str(data["name"]),
            color=_optional_string(data.get("color")),
            position=int(data["position"]),
            builtin=_optional_string(data.get("builtin")),
            managed_application_id=_optional_string(data.get("managedApplicationId")),
            permissions=Permissions(str(value) for value in data.get("permissions", ())),
            can_manage=bool(data.get("canManage", False)),
        )


class PermissionTargetType(StrEnum):
    """Supported channel override targets."""

    ROLE = "role"
    MEMBER = "member"


@dataclass(frozen=True, slots=True)
class PermissionOverride:
    """One channel permission override."""

    target_type: PermissionTargetType
    target_id: str
    allow: Permissions
    deny: Permissions

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> Self:
        return cls(
            target_type=PermissionTargetType(str(data["targetType"])),
            target_id=str(data["targetId"]),
            allow=Permissions(str(value) for value in data.get("allow", ())),
            deny=Permissions(str(value) for value in data.get("deny", ())),
        )


@dataclass(frozen=True, slots=True)
class ChannelPermissionSnapshot:
    """Overrides and category inheritance metadata for one channel."""

    items: tuple[PermissionOverride, ...]
    permissions: Permissions
    category_id: str | None
    category_name: str | None
    permissions_synced: bool

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> Self:
        return cls(
            items=tuple(PermissionOverride.from_dict(item) for item in data.get("items", ())),
            permissions=Permissions(str(value) for value in data.get("permissions", ())),
            category_id=_optional_string(data.get("categoryId")),
            category_name=_optional_string(data.get("categoryName")),
            permissions_synced=bool(data.get("permissionsSynced", False)),
        )


def _optional_string(value: object) -> str | None:
    return None if value is None else str(value)
