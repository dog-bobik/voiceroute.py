"""Durable event subscriptions with pull leases and explicit acknowledgement."""

from __future__ import annotations

import uuid

from voiceroute.models import (
    DeliveryAttempt,
    DeliveryDetails,
    DeliveryLease,
    DeliveryLog,
    DeliveryLogPage,
    EventSubscription,
)
from voiceroute.transport import Transport


class SubscriptionsAPI:
    """Manage application event delivery separately from Gateway cursors."""

    def __init__(self, transport: Transport) -> None:
        self._transport = transport

    async def list(self, application_id: str) -> tuple[EventSubscription, ...]:
        payload = await self._transport.request("GET", _collection(application_id))
        items = (payload or {}).get("items", ())
        return tuple(EventSubscription.from_dict(item) for item in items if isinstance(item, dict))

    async def get(self, application_id: str, subscription_id: str) -> EventSubscription:
        payload = await self._transport.request("GET", _resource(application_id, subscription_id))
        return EventSubscription.from_dict(_required_object(payload, "subscription lookup"))

    async def create(
        self,
        application_id: str,
        event_types: tuple[str, ...],
        *,
        transport: str = "pull",
        url: str | None = None,
        community_ids: tuple[str, ...] = (),
        max_attempts: int = 12,
        enabled: bool = True,
        current_password: str | None = None,
        code: str | None = None,
        idempotency_key: str | uuid.UUID | None = None,
    ) -> EventSubscription:
        if transport not in {"pull", "webhook", "websocket"}:
            raise ValueError("transport must be pull, webhook, or websocket")
        if not event_types or len(event_types) > 100 or len(set(event_types)) != len(event_types):
            raise ValueError("event_types must contain 1 to 100 unique event names")
        if len(community_ids) > 100 or len(set(community_ids)) != len(community_ids):
            raise ValueError("community_ids must contain at most 100 unique IDs")
        if not 1 <= max_attempts <= 12:
            raise ValueError("max_attempts must be between 1 and 12")
        payload = await self._transport.request(
            "POST",
            _collection(application_id),
            json={
                "transport": transport,
                "url": url,
                "eventTypes": list(event_types),
                "communityIds": list(community_ids),
                "maxAttempts": max_attempts,
                "enabled": enabled,
                "currentPassword": current_password,
                "code": code,
            },
            idempotency_key=str(idempotency_key or uuid.uuid4()),
        )
        return EventSubscription.from_dict(_required_object(payload, "subscription creation"))

    async def update(
        self,
        application_id: str,
        subscription_id: str,
        *,
        if_match: str,
        transport: str | None = None,
        url: str | None = None,
        event_types: tuple[str, ...] | None = None,
        community_ids: tuple[str, ...] | None = None,
        max_attempts: int | None = None,
        enabled: bool | None = None,
        idempotency_key: str | uuid.UUID | None = None,
    ) -> EventSubscription:
        body: dict[str, object] = {}
        if transport is not None:
            if transport not in {"pull", "webhook", "websocket"}:
                raise ValueError("transport must be pull, webhook, or websocket")
            body["transport"] = transport
        if url is not None:
            body["url"] = url
        if event_types is not None:
            if (
                not event_types
                or len(event_types) > 100
                or len(set(event_types)) != len(event_types)
            ):
                raise ValueError("event_types must contain 1 to 100 unique event names")
            body["eventTypes"] = list(event_types)
        if community_ids is not None:
            if len(community_ids) > 100 or len(set(community_ids)) != len(community_ids):
                raise ValueError("community_ids must contain at most 100 unique IDs")
            body["communityIds"] = list(community_ids)
        if max_attempts is not None:
            if not 1 <= max_attempts <= 12:
                raise ValueError("max_attempts must be between 1 and 12")
            body["maxAttempts"] = max_attempts
        if enabled is not None:
            body["enabled"] = enabled
        if not body:
            raise ValueError("at least one subscription field must be supplied")
        payload = await self._transport.request(
            "PATCH",
            _resource(application_id, subscription_id),
            json=body,
            idempotency_key=str(idempotency_key or uuid.uuid4()),
            if_match=if_match,
        )
        return EventSubscription.from_dict(_required_object(payload, "subscription update"))

    async def delete(
        self,
        application_id: str,
        subscription_id: str,
        *,
        if_match: str,
        current_password: str | None = None,
        code: str | None = None,
        idempotency_key: str | uuid.UUID | None = None,
    ) -> None:
        await self._transport.request(
            "DELETE",
            _resource(application_id, subscription_id),
            json={"currentPassword": current_password, "code": code},
            idempotency_key=str(idempotency_key or uuid.uuid4()),
            if_match=if_match,
            retryable=True,
        )

    async def pull(
        self,
        application_id: str,
        subscription_id: str,
        *,
        limit: int = 20,
        idempotency_key: str | uuid.UUID | None = None,
    ) -> tuple[DeliveryLease, ...]:
        if not 1 <= limit <= 100:
            raise ValueError("limit must be between 1 and 100")
        payload = await self._transport.request(
            "POST",
            f"{_resource(application_id, subscription_id)}/pull",
            json={"limit": limit},
            idempotency_key=str(idempotency_key or uuid.uuid4()),
        )
        items = (payload or {}).get("items", ())
        return tuple(DeliveryLease.from_dict(item) for item in items if isinstance(item, dict))

    async def deliveries(
        self,
        application_id: str,
        subscription_id: str,
        *,
        cursor: str | None = None,
        limit: int = 50,
    ) -> DeliveryLogPage:
        """Read durable delivery metadata, never event payload contents."""
        if not 1 <= limit <= 100:
            raise ValueError("limit must be between 1 and 100")
        payload = (
            await self._transport.request(
                "GET",
                f"{_resource(application_id, subscription_id)}/deliveries",
                params={"cursor": cursor, "limit": limit},
            )
            or {}
        )
        values = payload.get("items", ())
        return DeliveryLogPage(
            tuple(DeliveryLog.from_dict(item) for item in values if isinstance(item, dict)),
            str(payload["nextCursor"]) if payload.get("nextCursor") is not None else None,
        )

    async def get_delivery(
        self, application_id: str, subscription_id: str, delivery_id: str
    ) -> DeliveryDetails:
        payload = (
            await self._transport.request(
                "GET", f"{_resource(application_id, subscription_id)}/deliveries/{delivery_id}"
            )
            or {}
        )
        delivery = payload.get("delivery")
        attempts = payload.get("attempts", ())
        if not isinstance(delivery, dict) or not isinstance(attempts, list):
            raise RuntimeError("VoiceRoute returned an invalid delivery detail response")
        return DeliveryDetails(
            DeliveryLog.from_dict(delivery),
            tuple(DeliveryAttempt.from_dict(item) for item in attempts if isinstance(item, dict)),
        )

    async def acknowledge(
        self,
        application_id: str,
        subscription_id: str,
        delivery_id: str,
        lease_id: str,
        *,
        idempotency_key: str | uuid.UUID | None = None,
    ) -> None:
        await self._transport.request(
            "POST",
            f"{_resource(application_id, subscription_id)}/deliveries/{delivery_id}/ack",
            json={"leaseId": lease_id},
            idempotency_key=str(idempotency_key or uuid.uuid4()),
            retryable=True,
        )

    async def replay(
        self,
        application_id: str,
        subscription_id: str,
        delivery_id: str,
        *,
        idempotency_key: str | uuid.UUID | None = None,
    ) -> None:
        await self._transport.request(
            "POST",
            f"{_resource(application_id, subscription_id)}/deliveries/{delivery_id}/replay",
            json={},
            idempotency_key=str(idempotency_key or uuid.uuid4()),
            retryable=True,
        )


def _collection(application_id: str) -> str:
    return f"/api/v1/applications/{application_id}/event-subscriptions"


def _resource(application_id: str, subscription_id: str) -> str:
    return f"{_collection(application_id)}/{subscription_id}"


def _required_object(payload: dict[str, object] | None, operation: str) -> dict[str, object]:
    if payload is None:
        raise RuntimeError(f"VoiceRoute returned no event subscription after {operation}")
    value = payload.get("subscription", payload)
    if not isinstance(value, dict):
        raise RuntimeError(f"VoiceRoute returned an invalid event subscription after {operation}")
    return value
