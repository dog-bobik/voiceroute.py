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
