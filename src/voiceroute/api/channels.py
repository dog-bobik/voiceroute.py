"""Version 1 channel and category lifecycle operations."""

from __future__ import annotations

import uuid
from collections.abc import Mapping, Sequence
from dataclasses import dataclass

from voiceroute.models import Category, Channel
from voiceroute.transport import Transport


@dataclass(frozen=True, slots=True)
class TypingIndicator:
    """An active, short-lived typing lease in a channel."""

    user_id: str
    expires_at: str

    @classmethod
    def from_dict(cls, data: Mapping[str, object]) -> TypingIndicator:
        return cls(user_id=str(data["userId"]), expires_at=str(data["expiresAt"]))


class ChannelsAPI:
    def __init__(self, transport: Transport) -> None:
        self._transport = transport

    async def list(self, community_id: str) -> tuple[Channel, ...]:
        payload = await self._transport.request("GET", _channels_path(community_id))
        items = (payload or {}).get("items", ())
        return tuple(
            Channel.from_dict(item, community_id=community_id)
            for item in items
            if isinstance(item, dict)
        )

    async def get(self, community_id: str, channel_id: str) -> Channel:
        payload = await self._transport.request("GET", _channel_path(community_id, channel_id))
        return Channel.from_dict(
            _required_object(payload, "channel lookup"), community_id=community_id
        )

    async def start_typing(self, community_id: str, channel_id: str) -> None:
        """Start or refresh the bot's ephemeral typing lease."""
        await self._transport.request(
            "POST", f"{_channel_path(community_id, channel_id)}/typing", json={}
        )

    async def typing(self, community_id: str, channel_id: str) -> tuple[TypingIndicator, ...]:
        """List currently active typing leases in a channel."""
        payload = await self._transport.request(
            "GET", f"{_channel_path(community_id, channel_id)}/typing"
        )
        items = (payload or {}).get("items", ())
        return tuple(TypingIndicator.from_dict(item) for item in items if isinstance(item, Mapping))

    async def create(
        self,
        community_id: str,
        name: str,
        kind: str = "text",
        *,
        category_id: str | None = None,
        permissions_synced: bool | None = None,
        settings: Mapping[str, object] | None = None,
        idempotency_key: str | uuid.UUID | None = None,
    ) -> Channel:
        if not name or len(name) > 80:
            raise ValueError("channel name must contain between 1 and 80 characters")
        if kind not in {"text", "voice", "forum", "stage"}:
            raise ValueError("unsupported VoiceRoute channel kind")
        body: dict[str, object] = {"name": name, "kind": kind}
        if category_id is not None:
            body["categoryId"] = category_id
        if permissions_synced is not None:
            body["permissionsSynced"] = permissions_synced
        if settings is not None:
            body["settings"] = dict(settings)
        payload = await self._transport.request(
            "POST",
            _channels_path(community_id),
            json=body,
            idempotency_key=str(idempotency_key or uuid.uuid4()),
        )
        return Channel.from_dict(
            _required_object(payload, "channel creation"), community_id=community_id
        )

    async def update(
        self,
        community_id: str,
        channel_id: str,
        *,
        if_match: str,
        name: str | None = None,
        category_id: str | None = None,
        clear_category: bool = False,
        permissions_synced: bool | None = None,
        settings: Mapping[str, object] | None = None,
        idempotency_key: str | uuid.UUID | None = None,
    ) -> Channel:
        if category_id is not None and clear_category:
            raise ValueError("category_id and clear_category cannot be used together")
        body: dict[str, object] = {}
        if name is not None:
            if not name or len(name) > 80:
                raise ValueError("channel name must contain between 1 and 80 characters")
            body["name"] = name
        if category_id is not None or clear_category:
            body["categoryId"] = None if clear_category else category_id
        if permissions_synced is not None:
            body["permissionsSynced"] = permissions_synced
        if settings is not None:
            body["settings"] = dict(settings)
        if not body:
            raise ValueError("at least one channel field must be supplied")
        payload = await self._transport.request(
            "PATCH",
            _channel_path(community_id, channel_id),
            json=body,
            idempotency_key=str(idempotency_key or uuid.uuid4()),
            if_match=if_match,
        )
        return Channel.from_dict(
            _required_object(payload, "channel update"), community_id=community_id
        )

    async def delete(
        self,
        community_id: str,
        channel_id: str,
        *,
        if_match: str,
        idempotency_key: str | uuid.UUID | None = None,
    ) -> None:
        await self._transport.request(
            "DELETE",
            _channel_path(community_id, channel_id),
            idempotency_key=str(idempotency_key or uuid.uuid4()),
            if_match=if_match,
            retryable=True,
        )

    async def clone(
        self,
        community_id: str,
        channel_id: str,
        *,
        if_match: str,
        name: str | None = None,
        category_id: str | None = None,
        clear_category: bool = False,
        permissions_synced: bool | None = None,
        idempotency_key: str | uuid.UUID | None = None,
    ) -> Channel:
        body: dict[str, object] = {}
        if name is not None:
            body["name"] = name
        if category_id is not None or clear_category:
            body["categoryId"] = None if clear_category else category_id
        if permissions_synced is not None:
            body["permissionsSynced"] = permissions_synced
        payload = await self._transport.request(
            "POST",
            f"{_channel_path(community_id, channel_id)}/clone",
            json=body,
            idempotency_key=str(idempotency_key or uuid.uuid4()),
            if_match=if_match,
        )
        return Channel.from_dict(
            _required_object(payload, "channel clone"), community_id=community_id
        )

    async def reorder(
        self,
        community_id: str,
        items: Sequence[Mapping[str, object]],
        *,
        if_match: str,
        idempotency_key: str | uuid.UUID | None = None,
    ) -> tuple[Channel, ...]:
        if not items or len(items) > 50:
            raise ValueError("channel order must contain between 1 and 50 items")
        payload = await self._transport.request(
            "PUT",
            f"{_channels_path(community_id)}/order",
            json={"items": [dict(item) for item in items]},
            idempotency_key=str(idempotency_key or uuid.uuid4()),
            if_match=if_match,
        )
        values = (payload or {}).get("items", ())
        return tuple(
            Channel.from_dict(item, community_id=community_id)
            for item in values
            if isinstance(item, dict)
        )


class CategoriesAPI:
    def __init__(self, transport: Transport) -> None:
        self._transport = transport

    async def list(self, community_id: str) -> tuple[Category, ...]:
        payload = await self._transport.request("GET", _categories_path(community_id))
        items = (payload or {}).get("items", ())
        return tuple(Category.from_dict(item) for item in items if isinstance(item, dict))

    async def get(self, community_id: str, category_id: str) -> Category:
        payload = await self._transport.request("GET", _category_path(community_id, category_id))
        return Category.from_dict(_required_object(payload, "category lookup"))

    async def create(
        self,
        community_id: str,
        name: str,
        *,
        idempotency_key: str | uuid.UUID | None = None,
    ) -> Category:
        _validate_category_name(name)
        payload = await self._transport.request(
            "POST",
            _categories_path(community_id),
            json={"name": name},
            idempotency_key=str(idempotency_key or uuid.uuid4()),
        )
        return Category.from_dict(_required_object(payload, "category creation"))

    async def update(
        self,
        community_id: str,
        category_id: str,
        name: str,
        *,
        if_match: str,
        idempotency_key: str | uuid.UUID | None = None,
    ) -> Category:
        _validate_category_name(name)
        payload = await self._transport.request(
            "PATCH",
            _category_path(community_id, category_id),
            json={"name": name},
            idempotency_key=str(idempotency_key or uuid.uuid4()),
            if_match=if_match,
        )
        return Category.from_dict(_required_object(payload, "category update"))

    async def delete(
        self,
        community_id: str,
        category_id: str,
        *,
        if_match: str,
        idempotency_key: str | uuid.UUID | None = None,
    ) -> None:
        await self._transport.request(
            "DELETE",
            _category_path(community_id, category_id),
            idempotency_key=str(idempotency_key or uuid.uuid4()),
            if_match=if_match,
            retryable=True,
        )

    async def reorder(
        self,
        community_id: str,
        category_ids: Sequence[str],
        *,
        if_match: str,
        idempotency_key: str | uuid.UUID | None = None,
    ) -> tuple[Category, ...]:
        if (
            not category_ids
            or len(category_ids) > 50
            or len(set(category_ids)) != len(category_ids)
        ):
            raise ValueError("category_ids must contain 1 to 50 unique IDs")
        payload = await self._transport.request(
            "PUT",
            f"{_categories_path(community_id)}/order",
            json={"categoryIds": list(category_ids)},
            idempotency_key=str(idempotency_key or uuid.uuid4()),
            if_match=if_match,
        )
        items = (payload or {}).get("items", ())
        return tuple(Category.from_dict(item) for item in items if isinstance(item, dict))


def _channels_path(community_id: str) -> str:
    return f"/api/v1/communities/{community_id}/channels"


def _channel_path(community_id: str, channel_id: str) -> str:
    return f"{_channels_path(community_id)}/{channel_id}"


def _categories_path(community_id: str) -> str:
    return f"/api/v1/communities/{community_id}/categories"


def _category_path(community_id: str, category_id: str) -> str:
    return f"{_categories_path(community_id)}/{category_id}"


def _required_object(payload: dict[str, object] | None, operation: str) -> dict[str, object]:
    if payload is None:
        raise RuntimeError(f"VoiceRoute returned no resource after {operation}")
    value = payload.get("channel", payload.get("category", payload))
    if not isinstance(value, dict):
        raise RuntimeError(f"VoiceRoute returned an invalid resource after {operation}")
    return value


def _validate_category_name(name: str) -> None:
    if not name or len(name) > 80:
        raise ValueError("category name must contain between 1 and 80 characters")
