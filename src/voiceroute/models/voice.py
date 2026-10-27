"""Voice state and media grant models."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Self


@dataclass(frozen=True, slots=True)
class VoiceTrack:
    id: str
    source: int
    muted: bool
    mime_type: str

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> Self:
        return cls(
            id=str(data["id"]),
            source=int(data["source"]),
            muted=bool(data["muted"]),
            mime_type=str(data["mimeType"]),
        )


@dataclass(frozen=True, slots=True)
class VoiceState:
    community_id: str
    user_id: int
    channel_id: str | None = None
    session_id: str | None = None
    application_id: str | None = None
    status: str | None = None
    self_mute: bool = False
    self_deaf: bool = False
    server_muted: bool = False
    server_deafened: bool = False
    can_receive: bool = False
    can_transmit: bool = False
    tracks: tuple[VoiceTrack, ...] = ()

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> Self:
        return cls(
            community_id=str(data["communityId"]),
            user_id=int(data["userId"]),
            channel_id=_optional(data.get("channelId")),
            session_id=_optional(data.get("sessionId")),
            application_id=_optional(data.get("applicationId")),
            status=_optional(data.get("status")),
            self_mute=bool(data.get("selfMute", False)),
            self_deaf=bool(data.get("selfDeaf", False)),
            server_muted=bool(data.get("serverMuted", False)),
            server_deafened=bool(data.get("serverDeafened", False)),
            can_receive=bool(data.get("canReceive", False)),
            can_transmit=bool(data.get("canTransmit", False)),
            tracks=tuple(VoiceTrack.from_dict(item) for item in data.get("tracks", ())),
        )


@dataclass(frozen=True, slots=True)
class VoiceStatePage:
    items: tuple[VoiceState, ...]
    next_cursor: str | None = None


@dataclass(frozen=True, slots=True)
class VoiceServerGrant:
    request_id: str
    session_id: str
    community_id: str
    channel_id: str
    identity: str
    endpoint: str
    token: str
    session_expires_at: str
    receive: bool
    transmit: bool
    receive_endpoint: str | None = None

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> Self:
        required = (
            "requestId",
            "sessionId",
            "communityId",
            "channelId",
            "identity",
            "endpoint",
            "token",
            "sessionExpiresAt",
            "receive",
            "transmit",
        )
        if any(key not in data for key in required):
            raise ValueError("VOICE_SERVER_UPDATED is missing required fields")
        return cls(
            request_id=str(data["requestId"]),
            session_id=str(data["sessionId"]),
            community_id=str(data["communityId"]),
            channel_id=str(data["channelId"]),
            identity=str(data["identity"]),
            endpoint=str(data["endpoint"]),
            token=str(data["token"]),
            session_expires_at=str(data["sessionExpiresAt"]),
            receive=bool(data["receive"]),
            transmit=bool(data["transmit"]),
            receive_endpoint=_optional(data.get("receiveEndpoint")),
        )


def _optional(value: object) -> str | None:
    return None if value is None else str(value)
