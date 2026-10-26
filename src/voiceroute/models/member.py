"""Community member and role summary models."""

from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum
from typing import Any, Self

from voiceroute.models.permissions import Permissions
from voiceroute.models.user import User


class PresenceStatus(StrEnum):
    """Presence value exposed by the community member endpoint."""

    AVAILABLE = "available"
    IDLE = "idle"
    DND = "dnd"
    OFFLINE = "offline"


@dataclass(frozen=True, slots=True)
class MemberPresence:
    """Snapshot of one member's visible presence."""

    id: int
    status: PresenceStatus

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> Self:
        return cls(id=int(data["id"]), status=PresenceStatus(str(data["status"])))


@dataclass(frozen=True, slots=True)
class MemberRole:
    """Public role summary embedded in a community member."""

    id: str
    name: str
    color: str | None
    position: int
    builtin: str | None = None

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> Self:
        return cls(
            id=str(data["id"]),
            name=str(data["name"]),
            color=_optional_string(data.get("color")),
            position=int(data["position"]),
            builtin=_optional_string(data.get("builtin")),
        )


@dataclass(frozen=True, slots=True)
class Member:
    """An active member visible to the current bot."""

    community_id: str
    user: User
    role: str
    joined_at: str | None
    role_ids: tuple[str, ...]
    roles: tuple[MemberRole, ...]
    timeout_until: str | None
    can_ban: bool
    can_timeout: bool
    highest_role_position: int
    presence: MemberPresence | None = None
    permissions: Permissions | None = None

    @property
    def id(self) -> int:
        return self.user.id

    @property
    def display_name(self) -> str:
        return self.user.display_name

    @property
    def bot(self) -> bool:
        return self.user.bot

    @classmethod
    def from_dict(cls, data: dict[str, Any], *, community_id: str) -> Self:
        raw_presence = data.get("presence")
        return cls(
            community_id=community_id,
            user=User.from_dict(data["user"]),
            role=str(data["role"]),
            joined_at=_optional_string(data.get("joinedAt")),
            role_ids=tuple(str(value) for value in data.get("roleIds", ())),
            roles=tuple(MemberRole.from_dict(item) for item in data.get("roles", ())),
            timeout_until=_optional_string(data.get("timeoutUntil")),
            can_ban=bool(data.get("canBan", False)),
            can_timeout=bool(data.get("canTimeout", False)),
            highest_role_position=int(data.get("highestRolePosition", 0)),
            presence=(
                MemberPresence.from_dict(raw_presence) if isinstance(raw_presence, dict) else None
            ),
            permissions=(
                Permissions(str(value) for value in data["permissions"])
                if isinstance(data.get("permissions"), list)
                else None
            ),
        )


def _optional_string(value: object) -> str | None:
    return None if value is None else str(value)
