"""Explicitly consented application private-message resources."""

from __future__ import annotations

import uuid
from typing import Any

from voiceroute.transport import Transport


class PrivateMessagesAPI:
    """Application DM access; authorization and consent are checked by VoiceRoute."""

    def __init__(self, transport: Transport, application_id: str) -> None:
        self._transport = transport
        self.application_id = application_id

    async def open(
        self, user_id: str = "@me", *, idempotency_key: str | uuid.UUID | None = None
    ) -> dict[str, Any]:
        if user_id != "@me" and (not user_id.isdecimal() or user_id.startswith("0")):
            raise ValueError("user_id must be @me or a positive decimal user ID")
        payload = await self._transport.request(
            "POST",
            f"/api/v1/applications/{self.application_id}/users/{user_id}/dm",
            json={},
            idempotency_key=str(idempotency_key or uuid.uuid4()),
        )
        return _object(payload, "open private channel")

    async def get(self, user_id: str = "@me") -> dict[str, Any]:
        if user_id != "@me" and (not user_id.isdecimal() or user_id.startswith("0")):
            raise ValueError("user_id must be @me or a positive decimal user ID")
        payload = await self._transport.request(
            "GET", f"/api/v1/applications/{self.application_id}/users/{user_id}/dm"
        )
        return _object(payload, "private channel lookup")

    async def history(
        self,
        channel_id: str,
        *,
        cursor: str | None = None,
        limit: int = 50,
        direction: str = "before",
    ) -> tuple[tuple[dict[str, Any], ...], str | None]:
        if not 1 <= limit <= 100 or direction not in {"before", "after"}:
            raise ValueError("limit must be 1..100 and direction must be before or after")
        payload = (
            await self._transport.request(
                "GET",
                f"/api/v1/application-dms/{channel_id}/messages",
                params={"cursor": cursor, "limit": limit, "direction": direction},
            )
            or {}
        )
        items = payload.get("items", ())
        return tuple(item for item in items if isinstance(item, dict)), payload.get("nextCursor")

    async def get_message(self, channel_id: str, message_id: str) -> dict[str, Any]:
        """Fetch one private message in a currently authorized conversation."""
        payload = await self._transport.request(
            "GET", f"/api/v1/application-dms/{channel_id}/messages/{message_id}"
        )
        return _object(payload, "private message lookup")

    async def send(
        self,
        channel_id: str,
        *,
        content: str = "",
        embeds: tuple[dict[str, Any], ...] = (),
        idempotency_key: str | uuid.UUID | None = None,
    ) -> dict[str, Any]:
        if len(content) > 4000 or len(embeds) > 10 or (not content and not embeds):
            raise ValueError("provide content or embeds; content <= 4000 chars and embeds <= 10")
        body: dict[str, Any] = {"content": content}
        if embeds:
            body["embeds"] = list(embeds)
        payload = await self._transport.request(
            "POST",
            f"/api/v1/application-dms/{channel_id}/messages",
            json=body,
            idempotency_key=str(idempotency_key or uuid.uuid4()),
        )
        return _object(payload, "private message creation")

    async def edit(
        self,
        channel_id: str,
        message_id: str,
        *,
        if_match: str,
        content: str,
        idempotency_key: str | uuid.UUID | None = None,
    ) -> dict[str, Any]:
        if len(content) > 4000 or not if_match:
            raise ValueError("content must be <= 4000 chars and if_match is required")
        payload = await self._transport.request(
            "PATCH",
            f"/api/v1/application-dms/{channel_id}/messages/{message_id}",
            json={"content": content},
            if_match=if_match,
            idempotency_key=str(idempotency_key or uuid.uuid4()),
        )
        return _object(payload, "private message edit")

    async def delete(
        self,
        channel_id: str,
        message_id: str,
        *,
        if_match: str,
        idempotency_key: str | uuid.UUID | None = None,
    ) -> None:
        await self._transport.request(
            "DELETE",
            f"/api/v1/application-dms/{channel_id}/messages/{message_id}",
            if_match=if_match,
            idempotency_key=str(idempotency_key or uuid.uuid4()),
            retryable=True,
        )


def _object(payload: dict[str, Any] | None, operation: str) -> dict[str, Any]:
    if payload is None:
        raise RuntimeError(f"VoiceRoute returned no object after {operation}")
    value = payload.get("channel", payload.get("message", payload))
    if not isinstance(value, dict):
        raise RuntimeError(f"VoiceRoute returned an invalid object after {operation}")
    return value
