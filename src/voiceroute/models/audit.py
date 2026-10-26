"""Community audit log models."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Self


@dataclass(frozen=True, slots=True)
class AuditActor:
    id: int | None
    username: str | None
    display_name: str

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> Self:
        return cls(
            id=int(data["id"]) if data.get("id") is not None else None,
            username=str(data["username"]) if data.get("username") is not None else None,
            display_name=str(data["displayName"]),
        )


@dataclass(frozen=True, slots=True)
class AuditTarget:
    type: str
    id: str | None
    label: str | None

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> Self:
        return cls(
            type=str(data["type"]),
            id=str(data["id"]) if data.get("id") is not None else None,
            label=str(data["label"]) if data.get("label") is not None else None,
        )


@dataclass(frozen=True, slots=True)
class AuditEntry:
    id: str
    community_id: str
    action: str
    action_label: str
    actor: AuditActor
    target: AuditTarget
    reason: str | None
    before: dict[str, Any] | None
    after: dict[str, Any] | None
    created_at: str

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> Self:
        return cls(
            id=str(data["id"]),
            community_id=str(data["communityId"]),
            action=str(data["action"]),
            action_label=str(data["actionLabel"]),
            actor=AuditActor.from_dict(data["actor"]),
            target=AuditTarget.from_dict(data["target"]),
            reason=str(data["reason"]) if data.get("reason") is not None else None,
            before=data.get("before") if isinstance(data.get("before"), dict) else None,
            after=data.get("after") if isinstance(data.get("after"), dict) else None,
            created_at=str(data["createdAt"]),
        )


@dataclass(frozen=True, slots=True)
class AuditActionOption:
    id: str
    label: str

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> Self:
        return cls(id=str(data["id"]), label=str(data["label"]))


@dataclass(frozen=True, slots=True)
class AuditPage:
    items: tuple[AuditEntry, ...]
    next_before: str | None
    actors: tuple[AuditActor, ...]
    actions: tuple[AuditActionOption, ...]
    retention_days: int

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> Self:
        return cls(
            items=tuple(AuditEntry.from_dict(item) for item in data.get("items", ())),
            next_before=(str(data["nextBefore"]) if data.get("nextBefore") is not None else None),
            actors=tuple(AuditActor.from_dict(item) for item in data.get("actors", ())),
            actions=tuple(AuditActionOption.from_dict(item) for item in data.get("actions", ())),
            retention_days=int(data.get("retentionDays", 0)),
        )
