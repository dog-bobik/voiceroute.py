"""Native VoiceRoute interaction models."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Self

from voiceroute.models.user import User


@dataclass(frozen=True, slots=True)
class InteractionCommand:
    """Command metadata delivered with an interaction."""

    id: str
    name: str
    version: int

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> Self:
        return cls(id=str(data["id"]), name=str(data["name"]), version=int(data["version"]))


@dataclass(frozen=True, slots=True)
class Interaction:
    """A pending application-command invocation delivered to a bot."""

    id: str
    application_id: str
    community_id: str
    channel_id: str
    user: User
    command: InteractionCommand
    options: dict[str, object] = field(default_factory=dict)
    created_at: str | None = None
    expires_at: str | None = None

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> Self:
        raw_options = data.get("options", {})
        return cls(
            id=str(data["id"]),
            application_id=str(data["applicationId"]),
            community_id=str(data["communityId"]),
            channel_id=str(data["channelId"]),
            user=User.from_dict(data["user"]),
            command=InteractionCommand.from_dict(data["command"]),
            options=dict(raw_options) if isinstance(raw_options, dict) else {},
            created_at=_optional_string(data.get("createdAt")),
            expires_at=_optional_string(data.get("expiresAt")),
        )


@dataclass(frozen=True, slots=True)
class InteractionResponse:
    """Server state returned after responding to an interaction."""

    id: str
    status: str
    ephemeral: bool
    message_seq: str | None = None

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> Self:
        return cls(
            id=str(data["id"]),
            status=str(data["status"]),
            ephemeral=bool(data.get("ephemeral", False)),
            message_seq=_optional_string(data.get("messageSeq")),
        )


def _optional_string(value: object) -> str | None:
    return None if value is None else str(value)
