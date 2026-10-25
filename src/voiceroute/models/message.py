"""Text message models."""

from dataclasses import dataclass, field
from types import MappingProxyType
from typing import Any, Self

from voiceroute.models.community import _extra_fields, _optional_string
from voiceroute.models.user import User


@dataclass(frozen=True, slots=True)
class Message:
    """A message returned by a community text channel."""

    seq: str
    community_id: str
    channel_id: str
    body: str
    author: User | None
    client_message_id: str | None = None
    reply_to_seq: str | None = None
    edited_at: str | None = None
    deleted_at: str | None = None
    webhook: bool = False
    attachment_ids: tuple[str, ...] = ()
    sticker_ids: tuple[str, ...] = ()
    extra: MappingProxyType[str, Any] = field(default_factory=lambda: MappingProxyType({}))

    @property
    def deleted(self) -> bool:
        return self.deleted_at is not None

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> Self:
        author_data = data.get("author")
        known = {
            "seq",
            "communityId",
            "channelId",
            "body",
            "author",
            "clientMessageId",
            "replyToSeq",
            "editedAt",
            "deletedAt",
            "webhook",
            "attachmentIds",
            "stickerIds",
        }
        return cls(
            seq=str(data["seq"]),
            community_id=str(data["communityId"]),
            channel_id=str(data["channelId"]),
            body=str(data.get("body", "")),
            author=User.from_dict(author_data) if isinstance(author_data, dict) else None,
            client_message_id=_optional_string(data.get("clientMessageId")),
            reply_to_seq=_optional_string(data.get("replyToSeq")),
            edited_at=_optional_string(data.get("editedAt")),
            deleted_at=_optional_string(data.get("deletedAt")),
            webhook=bool(data.get("webhook", False)),
            attachment_ids=tuple(str(value) for value in data.get("attachmentIds", ())),
            sticker_ids=tuple(str(value) for value in data.get("stickerIds", ())),
            extra=_extra_fields(data, known),
        )


@dataclass(frozen=True, slots=True)
class MessagePage:
    """One ascending page of channel messages."""

    items: tuple[Message, ...]
    next_before_seq: str | None = None
