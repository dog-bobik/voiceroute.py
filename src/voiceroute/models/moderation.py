"""Community moderation models."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Self

from voiceroute.models.user import User


@dataclass(frozen=True, slots=True)
class MemberTimeout:
    """An active timeout applied to a community member."""

    expires_at: str
    created_at: str
    reason: str
    actor_id: int

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> Self:
        return cls(
            expires_at=str(data["expiresAt"]),
            created_at=str(data["createdAt"]),
            reason=str(data.get("reason", "")),
            actor_id=int(data["actorId"]),
        )


@dataclass(frozen=True, slots=True)
class Ban:
    """A community ban and its audit metadata."""

    user: User
    reason: str
    created_at: str
    actor_id: int

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> Self:
        return cls(
            user=User.from_dict(data["user"]),
            reason=str(data.get("reason", "")),
            created_at=str(data["createdAt"]),
            actor_id=int(data["actorId"]),
        )


@dataclass(frozen=True, slots=True)
class ModerationMember:
    """A member together with actions available to the current bot."""

    user: User
    role: str
    highest_role_position: int
    can_ban: bool
    can_timeout: bool
    timeout: MemberTimeout | None

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> Self:
        raw_timeout = data.get("timeout")
        return cls(
            user=User.from_dict(data["user"]),
            role=str(data["role"]),
            highest_role_position=int(data.get("highestRolePosition", 0)),
            can_ban=bool(data.get("canBan", False)),
            can_timeout=bool(data.get("canTimeout", False)),
            timeout=(
                MemberTimeout.from_dict(raw_timeout) if isinstance(raw_timeout, dict) else None
            ),
        )


@dataclass(frozen=True, slots=True)
class ModerationSnapshot:
    """Moderation targets and the bot's global capabilities."""

    items: tuple[ModerationMember, ...]
    can_ban: bool
    can_timeout: bool

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> Self:
        return cls(
            items=tuple(ModerationMember.from_dict(item) for item in data.get("items", ())),
            can_ban=bool(data.get("canBan", False)),
            can_timeout=bool(data.get("canTimeout", False)),
        )
