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
    version: str = ""
    managed: bool = False
    unicode_emoji: str | None = None

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
            version=str(data.get("version", "")),
            managed=bool(data.get("managed", data.get("managedApplicationId") is not None)),
            unicode_emoji=_optional_string(data.get("unicodeEmoji")),
        )

    @property
    def etag(self) -> str:
        if not self.version:
            raise RuntimeError("role version is missing from the response")
        return f'"role-{self.version}"'


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


@dataclass(frozen=True, slots=True)
class EffectivePermissions:
    community_id: str
    user_id: int
    channel_id: str | None
    registry_version: str
    permissions: Permissions
    role_ids: tuple[str, ...]
    timeout_until: str | None

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> Self:
        return cls(
            community_id=str(data["communityId"]),
            user_id=int(data["userId"]),
            channel_id=_optional_string(data.get("channelId")),
            registry_version=str(data["registryVersion"]),
            permissions=Permissions(str(value) for value in data.get("permissions", ())),
            role_ids=tuple(map(str, data.get("roleIds", ()))),
            timeout_until=_optional_string(data.get("timeoutUntil")),
        )


@dataclass(frozen=True, slots=True)
class PermissionRegistry:
    version: str
    items: tuple[tuple[str, str], ...]

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> Self:
        return cls(
            version=str(data["version"]),
            items=tuple(
                (str(item["id"]), str(item["scope"]))
                for item in data.get("items", ())
                if isinstance(item, dict)
            ),
        )


@dataclass(frozen=True, slots=True)
class PermissionSimulation:
    effective: EffectivePermissions
    added: Permissions
    removed: Permissions
    dry_run: bool

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> Self:
        return cls(
            effective=EffectivePermissions.from_dict(data),
            added=Permissions(str(value) for value in data.get("added", ())),
            removed=Permissions(str(value) for value in data.get("removed", ())),
            dry_run=bool(data.get("dryRun", False)),
        )


def _optional_string(value: object) -> str | None:
    return None if value is None else str(value)
