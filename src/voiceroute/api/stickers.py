"""Bot-accessible community sticker management."""

from __future__ import annotations

import uuid
from collections.abc import Sequence

from voiceroute.models import Sticker
from voiceroute.transport import Transport


class StickersAPI:
    def __init__(self, transport: Transport) -> None:
        self._transport = transport

    async def list(
        self, community_id: str, *, cursor: str | None = None, limit: int = 50
    ) -> tuple[Sticker, ...]:
        _validate_limit(limit)
        payload = (
            await self._transport.request(
                "GET", _collection(community_id), params={"cursor": cursor, "limit": limit}
            )
            or {}
        )
        values = payload.get("items", ())
        return tuple(Sticker.from_dict(item) for item in values if isinstance(item, dict))

    async def get(self, community_id: str, sticker_id: str) -> Sticker:
        payload = await self._transport.request("GET", _resource(community_id, sticker_id))
        return Sticker.from_dict(_required(payload, "sticker lookup"))

    async def create(
        self,
        community_id: str,
        *,
        name: str,
        description: str,
        tag: str,
        upload_id: str,
        role_ids: Sequence[str] = (),
        available: bool = True,
        audit_reason: str | None = None,
        idempotency_key: str | uuid.UUID | None = None,
    ) -> Sticker:
        _validate_fields(name, description, tag, role_ids)
        payload = await self._transport.request(
            "POST",
            _collection(community_id),
            json={
                "name": name,
                "description": description,
                "tag": tag,
                "roleIds": list(role_ids),
                "available": available,
                "uploadId": upload_id,
            },
            headers=_audit_headers(audit_reason),
            idempotency_key=str(idempotency_key or uuid.uuid4()),
        )
        return Sticker.from_dict(_required(payload, "sticker creation"))

    async def update(
        self,
        community_id: str,
        sticker_id: str,
        *,
        if_match: str,
        name: str | None = None,
        description: str | None = None,
        tag: str | None = None,
        role_ids: Sequence[str] | None = None,
        available: bool | None = None,
        audit_reason: str | None = None,
        idempotency_key: str | uuid.UUID | None = None,
    ) -> Sticker:
        body: dict[str, object] = {}
        if name is not None:
            if not 2 <= len(name) <= 30:
                raise ValueError("sticker name must contain 2 to 30 characters")
            body["name"] = name
        if description is not None:
            if not 1 <= len(description) <= 200:
                raise ValueError("sticker description must contain 1 to 200 characters")
            body["description"] = description
        if tag is not None:
            if len(tag) > 32:
                raise ValueError("sticker tag cannot exceed 32 characters")
            body["tag"] = tag
        if role_ids is not None:
            if len(role_ids) > 100 or len(set(role_ids)) != len(role_ids):
                raise ValueError("role_ids must contain at most 100 unique IDs")
            body["roleIds"] = list(role_ids)
        if available is not None:
            body["available"] = available
        if not body:
            raise ValueError("at least one sticker field must be supplied")
        payload = await self._transport.request(
            "PATCH",
            _resource(community_id, sticker_id),
            json=body,
            headers=_audit_headers(audit_reason),
            if_match=if_match,
            idempotency_key=str(idempotency_key or uuid.uuid4()),
        )
        return Sticker.from_dict(_required(payload, "sticker update"))

    async def delete(
        self,
        community_id: str,
        sticker_id: str,
        *,
        if_match: str,
        audit_reason: str | None = None,
        idempotency_key: str | uuid.UUID | None = None,
    ) -> None:
        await self._transport.request(
            "DELETE",
            _resource(community_id, sticker_id),
            headers=_audit_headers(audit_reason),
            if_match=if_match,
            idempotency_key=str(idempotency_key or uuid.uuid4()),
            retryable=True,
        )


def _collection(community_id: str) -> str:
    return f"/api/v1/communities/{community_id}/stickers"


def _resource(community_id: str, sticker_id: str) -> str:
    return f"{_collection(community_id)}/{sticker_id}"


def _required(payload: dict[str, object] | None, operation: str) -> dict[str, object]:
    if payload is None:
        raise RuntimeError(f"VoiceRoute returned no sticker after {operation}")
    value = payload.get("sticker", payload)
    if not isinstance(value, dict):
        raise RuntimeError(f"VoiceRoute returned an invalid sticker after {operation}")
    return value


def _validate_fields(name: str, description: str, tag: str, role_ids: Sequence[str]) -> None:
    if not 2 <= len(name) <= 30:
        raise ValueError("sticker name must contain 2 to 30 characters")
    if not 1 <= len(description) <= 200:
        raise ValueError("sticker description must contain 1 to 200 characters")
    if len(tag) > 32:
        raise ValueError("sticker tag cannot exceed 32 characters")
    if len(role_ids) > 100 or len(set(role_ids)) != len(role_ids):
        raise ValueError("role_ids must contain at most 100 unique IDs")


def _validate_limit(limit: int) -> None:
    if not 1 <= limit <= 100:
        raise ValueError("limit must be between 1 and 100")


def _audit_headers(reason: str | None) -> dict[str, str]:
    if reason is None:
        return {}
    if len(reason) > 512:
        raise ValueError("audit_reason cannot exceed 512 characters")
    return {"X-Audit-Log-Reason": reason}
