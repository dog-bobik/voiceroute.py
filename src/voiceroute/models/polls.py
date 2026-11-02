"""Typed poll payloads that preserve evolving server fields."""

from __future__ import annotations

from dataclasses import dataclass, field
from types import MappingProxyType
from typing import Any, Self

from voiceroute.models.rich_message import RichMessage


@dataclass(frozen=True, slots=True)
class Poll:
    id: str
    message_id: str
    question: str
    version: str
    anonymous: bool
    multiple: bool
    data: MappingProxyType[str, Any] = field(default_factory=lambda: MappingProxyType({}))

    @property
    def etag(self) -> str:
        if not self.version:
            raise RuntimeError("poll version is missing from the response")
        return f'"poll-{self.version}"'

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> Self:
        known = {"id", "messageId", "question", "version", "anonymous", "multiple"}
        return cls(
            id=str(data["id"]),
            message_id=str(data["messageId"]),
            question=str(data.get("question", "")),
            version=str(data.get("version", "")),
            anonymous=bool(data.get("anonymous", False)),
            multiple=bool(data.get("multiple", False)),
            data=MappingProxyType({key: value for key, value in data.items() if key not in known}),
        )


@dataclass(frozen=True, slots=True)
class PollCreation:
    poll: Poll
    message: RichMessage


@dataclass(frozen=True, slots=True)
class PollVoter:
    user_id: int
    username: str
    display_name: str
    answer_ids: tuple[str, ...]

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> Self:
        return cls(
            user_id=int(data["userId"]),
            username=str(data["username"]),
            display_name=str(data["displayName"]),
            answer_ids=tuple(str(value) for value in data.get("answerIds", ())),
        )


@dataclass(frozen=True, slots=True)
class PollVoterPage:
    items: tuple[PollVoter, ...]
    next_cursor: str | None = None
