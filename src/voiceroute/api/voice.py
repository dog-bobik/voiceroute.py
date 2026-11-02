"""Bot-compatible VoiceRoute voice state resources."""

from __future__ import annotations

import uuid
from dataclasses import dataclass, field
from typing import Any

from voiceroute.models.voice import VoiceState, VoiceStatePage
from voiceroute.transport import Transport


@dataclass(frozen=True, slots=True)
class VoiceConnection:
    """Single-use outbound media credential; its token is hidden from repr."""

    connection_id: str
    media_websocket_url: str
    media_token: str = field(repr=False)
    expires_at: str
    audio: dict[str, Any]

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> VoiceConnection:
        audio = data.get("audio")
        return cls(
            connection_id=str(data["connectionId"]),
            media_websocket_url=str(data["mediaWebSocketUrl"]),
            media_token=str(data["mediaToken"]),
            expires_at=str(data["expiresAt"]),
            audio=dict(audio) if isinstance(audio, dict) else {},
        )


@dataclass(frozen=True, slots=True)
class VoicePolicy:
    community_id: str
    allow_application_receive: bool
    version: str
    updated_at: str | None

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> VoicePolicy:
        return cls(
            community_id=str(data["communityId"]),
            allow_application_receive=bool(data["allowApplicationReceive"]),
            version=str(data["version"]),
            updated_at=str(data["updatedAt"]) if data.get("updatedAt") is not None else None,
        )


class VoiceAPI:
    def __init__(self, transport: Transport) -> None:
        self._transport = transport

    async def connect(
        self,
        community_id: str,
        channel_id: str,
        *,
        self_deaf: bool = True,
        idempotency_key: str | uuid.UUID | None = None,
    ) -> VoiceConnection:
        """Create a single-use media connection for this bot installation."""
        payload = await self._transport.request(
            "POST",
            f"/api/v1/communities/{community_id}/voice-connections",
            json={"channelId": channel_id, "selfDeaf": self_deaf},
            idempotency_key=str(idempotency_key or uuid.uuid4()),
        )
        if payload is None:
            raise RuntimeError("VoiceRoute returned no voice connection")
        return VoiceConnection.from_dict(payload)

    async def disconnect(self, community_id: str, connection_id: str) -> None:
        await self._transport.request(
            "DELETE",
            f"/api/v1/communities/{community_id}/voice-connections/{connection_id}",
            retryable=True,
        )

    async def policy(self, community_id: str) -> VoicePolicy:
        payload = await self._transport.request(
            "GET", f"/api/v1/communities/{community_id}/voice-policy"
        )
        if payload is None or not isinstance(payload.get("policy"), dict):
            raise RuntimeError("VoiceRoute returned no voice policy")
        return VoicePolicy.from_dict(payload["policy"])

    async def list_states(
        self,
        community_id: str,
        *,
        cursor: str | None = None,
        limit: int = 100,
    ) -> VoiceStatePage:
        if not 1 <= limit <= 100:
            raise ValueError("limit must be between 1 and 100")
        payload = await self._transport.request(
            "GET",
            f"/api/v1/communities/{community_id}/voice-states",
            params={"cursor": cursor, "limit": limit},
        )
        data = payload or {}
        return VoiceStatePage(
            items=tuple(VoiceState.from_dict(item) for item in data.get("items", ())),
            next_cursor=(str(data["nextCursor"]) if data.get("nextCursor") is not None else None),
        )

    async def get_state(self, community_id: str, user_id: int) -> VoiceState:
        """Fetch a single user's current voice state."""
        if user_id <= 0:
            raise ValueError("user_id must be positive")
        payload = await self._transport.request(
            "GET", f"/api/v1/communities/{community_id}/voice-states/{user_id}"
        )
        if payload is None:
            raise RuntimeError("VoiceRoute returned no voice state")
        return VoiceState.from_dict(payload)

    async def find_member_channel(self, community_id: str, user_id: int) -> str | None:
        cursor: str | None = None
        visited: set[str] = set()
        while True:
            page = await self.list_states(community_id, cursor=cursor)
            state = next(
                (
                    item
                    for item in page.items
                    if item.user_id == user_id
                    and item.channel_id is not None
                    and item.status != "DISCONNECTED"
                ),
                None,
            )
            if state is not None:
                return state.channel_id
            cursor = page.next_cursor
            if cursor is None or cursor in visited:
                return None
            visited.add(cursor)
