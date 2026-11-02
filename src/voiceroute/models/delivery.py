"""Durable event subscription and lease DTOs."""

from __future__ import annotations

from dataclasses import dataclass, field
from types import MappingProxyType
from typing import Any, Self

from voiceroute.models.platform_event import PlatformEvent


@dataclass(frozen=True, slots=True)
class EventSubscription:
    id: str
    application_id: str
    transport: str
    event_types: tuple[str, ...]
    community_ids: tuple[str, ...]
    enabled: bool
    version: str
    data: MappingProxyType[str, Any] = field(default_factory=lambda: MappingProxyType({}))

    @property
    def etag(self) -> str:
        if not self.version:
            raise RuntimeError("subscription version is missing from the response")
        return f'"subscription-{self.version}"'

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> Self:
        known = {
            "id",
            "applicationId",
            "transport",
            "eventTypes",
            "communityIds",
            "enabled",
            "version",
        }
        return cls(
            id=str(data["id"]),
            application_id=str(data["applicationId"]),
            transport=str(data["transport"]),
            event_types=tuple(str(value) for value in data.get("eventTypes", ())),
            community_ids=tuple(str(value) for value in data.get("communityIds", ())),
            enabled=bool(data.get("enabled", True)),
            version=str(data.get("version", "")),
            data=MappingProxyType({key: value for key, value in data.items() if key not in known}),
        )


@dataclass(frozen=True, slots=True)
class DeliveryLease:
    event: PlatformEvent
    lease_id: str
    lease_expires_at: str

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> Self:
        event = data.get("event")
        if not isinstance(event, dict):
            raise ValueError("delivery lease is missing its event envelope")
        return cls(
            event=PlatformEvent.from_gateway_frame(event),
            lease_id=str(data["leaseId"]),
            lease_expires_at=str(data["leaseExpiresAt"]),
        )


@dataclass(frozen=True, slots=True)
class DeliveryLog:
    id: str
    sequence: str
    event: str
    status: str
    attempts: int
    last_code: str | None
    last_status: int | None
    last_latency_ms: int | None
    occurred_at: str
    acknowledged_at: str | None
    expires_at: str

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> Self:
        return cls(
            id=str(data["id"]),
            sequence=str(data["sequence"]),
            event=str(data["event"]),
            status=str(data["status"]),
            attempts=int(data["attempts"]),
            last_code=str(data["lastCode"]) if data.get("lastCode") is not None else None,
            last_status=int(data["lastStatus"]) if data.get("lastStatus") is not None else None,
            last_latency_ms=(
                int(data["lastLatencyMs"]) if data.get("lastLatencyMs") is not None else None
            ),
            occurred_at=str(data["occurredAt"]),
            acknowledged_at=(
                str(data["acknowledgedAt"]) if data.get("acknowledgedAt") is not None else None
            ),
            expires_at=str(data["expiresAt"]),
        )


@dataclass(frozen=True, slots=True)
class DeliveryAttempt:
    attempt: int
    code: str
    http_status: int | None
    latency_ms: int | None
    created_at: str

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> Self:
        return cls(
            attempt=int(data["attempt"]),
            code=str(data["code"]),
            http_status=int(data["httpStatus"]) if data.get("httpStatus") is not None else None,
            latency_ms=int(data["latencyMs"]) if data.get("latencyMs") is not None else None,
            created_at=str(data["createdAt"]),
        )


@dataclass(frozen=True, slots=True)
class DeliveryLogPage:
    items: tuple[DeliveryLog, ...]
    next_cursor: str | None = None


@dataclass(frozen=True, slots=True)
class DeliveryDetails:
    delivery: DeliveryLog
    attempts: tuple[DeliveryAttempt, ...]
