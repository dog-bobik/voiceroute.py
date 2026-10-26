"""Gateway presence payloads."""

from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum
from typing import Any


class Status(StrEnum):
    ONLINE = "online"
    IDLE = "idle"
    DND = "dnd"
    INVISIBLE = "invisible"


class ActivityType(StrEnum):
    CUSTOM = "CUSTOM"
    PLAYING = "PLAYING"
    LISTENING = "LISTENING"
    WATCHING = "WATCHING"


@dataclass(frozen=True, slots=True)
class Activity:
    name: str
    type: ActivityType = ActivityType.PLAYING

    def __post_init__(self) -> None:
        if not 1 <= len(self.name) <= 128:
            raise ValueError("activity name must contain 1 to 128 characters")

    def to_dict(self) -> dict[str, str]:
        return {"type": self.type.value, "name": self.name}


class Game(Activity):
    def __init__(self, name: str) -> None:
        super().__init__(name=name, type=ActivityType.PLAYING)


@dataclass(frozen=True, slots=True)
class Presence:
    status: Status
    activities: tuple[Activity, ...] = ()
    since: str | None = None

    def __post_init__(self) -> None:
        if len(self.activities) > 4:
            raise ValueError("presence supports at most four activities")
        if self.status is Status.INVISIBLE and self.activities:
            raise ValueError("invisible presence cannot publish activities")

    def to_dict(self) -> dict[str, Any]:
        data: dict[str, Any] = {"status": self.status.value}
        if self.since is not None:
            data["since"] = self.since
        if self.activities:
            data["activities"] = [activity.to_dict() for activity in self.activities]
        return data
