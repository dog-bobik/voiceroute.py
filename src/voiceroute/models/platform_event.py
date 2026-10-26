"""Forward-compatible models shared by Gateway and durable deliveries."""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass
from types import MappingProxyType
from typing import Any, Self

from voiceroute.models.generated_events import KNOWN_EVENT_TYPES, PlatformEventType


@dataclass(frozen=True, slots=True)
class PlatformEvent:
    """A dispatch envelope that keeps unknown future events and fields intact."""

    name: str
    sequence: str
    data: Mapping[str, Any]
    delivery_id: str | None = None
    raw: Mapping[str, Any] | None = None

    @property
    def known_type(self) -> PlatformEventType | None:
        try:
            return PlatformEventType(self.name)
        except ValueError:
            return None

    @property
    def is_known(self) -> bool:
        return self.name in KNOWN_EVENT_TYPES

    @classmethod
    def from_gateway_frame(cls, frame: Mapping[str, Any]) -> Self:
        name = frame.get("event")
        sequence = frame.get("sequence")
        data = frame.get("data")
        if not isinstance(name, str) or not isinstance(sequence, str):
            raise ValueError("dispatch must contain string event and sequence")
        if not isinstance(data, dict):
            raise ValueError("dispatch data must be an object")
        delivery_id = frame.get("deliveryId")
        if delivery_id is not None and not isinstance(delivery_id, str):
            raise ValueError("deliveryId must be a string")
        return cls(
            name=name,
            sequence=sequence,
            data=MappingProxyType(dict(data)),
            delivery_id=delivery_id,
            raw=MappingProxyType(dict(frame)),
        )
