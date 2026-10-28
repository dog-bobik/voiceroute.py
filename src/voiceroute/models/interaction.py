"""Bot Platform v1 interactions, components, messages, and modals."""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import StrEnum
from typing import Any, Self

from voiceroute.models.application_command import CommandChoice
from voiceroute.models.user import User


class InteractionCallbackType(StrEnum):
    MESSAGE = "MESSAGE"
    DEFERRED_MESSAGE = "DEFERRED_MESSAGE"
    AUTOCOMPLETE_RESULT = "AUTOCOMPLETE_RESULT"
    MODAL = "MODAL"
    UPDATE_MESSAGE = "UPDATE_MESSAGE"
    DEFERRED_UPDATE = "DEFERRED_UPDATE"


class ButtonStyle(StrEnum):
    PRIMARY = "PRIMARY"
    SECONDARY = "SECONDARY"
    SUCCESS = "SUCCESS"
    DANGER = "DANGER"
    LINK = "LINK"


@dataclass(frozen=True, slots=True)
class SelectOption:
    label: str
    value: str
    description: str | None = None
    emoji: str | None = None
    default: bool = False

    def to_dict(self) -> dict[str, object]:
        return _defined(
            label=self.label,
            value=self.value,
            description=self.description,
            emoji=self.emoji,
            default=self.default or None,
        )


@dataclass(frozen=True, slots=True)
class Component:
    type: str
    custom_id: str | None = None
    style: ButtonStyle | None = None
    label: str | None = None
    url: str | None = None
    emoji: str | None = None
    disabled: bool = False
    accessibility_label: str | None = None
    placeholder: str | None = None
    min_values: int | None = None
    max_values: int | None = None
    channel_types: tuple[str, ...] = ()
    options: tuple[SelectOption, ...] = ()

    def to_dict(self) -> dict[str, object]:
        return _defined(
            type=self.type,
            customId=self.custom_id,
            style=self.style.value if self.style is not None else None,
            label=self.label,
            url=self.url,
            emoji=self.emoji,
            disabled=self.disabled or None,
            accessibilityLabel=self.accessibility_label,
            placeholder=self.placeholder,
            minValues=self.min_values,
            maxValues=self.max_values,
            channelTypes=list(self.channel_types) if self.channel_types else None,
            options=[option.to_dict() for option in self.options] if self.options else None,
        )


@dataclass(frozen=True, slots=True)
class ActionRow:
    components: tuple[Component, ...]

    def to_dict(self) -> dict[str, object]:
        return {"type": "ACTION_ROW", "components": [item.to_dict() for item in self.components]}


@dataclass(frozen=True, slots=True)
class TextInput:
    custom_id: str
    label: str
    style: str = "SHORT"
    required: bool = True
    min_length: int | None = None
    max_length: int | None = None
    placeholder: str | None = None
    value: str | None = None

    def to_dict(self) -> dict[str, object]:
        return _defined(
            type="TEXT_INPUT",
            customId=self.custom_id,
            label=self.label,
            style=self.style,
            required=self.required,
            minLength=self.min_length,
            maxLength=self.max_length,
            placeholder=self.placeholder,
            value=self.value,
        )


@dataclass(frozen=True, slots=True)
class Modal:
    title: str
    custom_id: str
    components: tuple[TextInput, ...]

    def to_dict(self) -> dict[str, object]:
        return {
            "title": self.title,
            "customId": self.custom_id,
            "components": [item.to_dict() for item in self.components],
        }


@dataclass(frozen=True, slots=True)
class InteractionMessage:
    content: str = ""
    components: tuple[ActionRow, ...] = ()
    flags: tuple[str, ...] = ()
    embeds: tuple[dict[str, object], ...] = ()
    attachments: tuple[dict[str, object], ...] = ()

    def to_dict(self) -> dict[str, object]:
        return _defined(
            content=self.content or None,
            components=[row.to_dict() for row in self.components] if self.components else None,
            flags=list(self.flags) if self.flags else None,
            embeds=list(self.embeds) if self.embeds else None,
            attachments=list(self.attachments) if self.attachments else None,
        )


@dataclass(frozen=True, slots=True)
class InteractionCommand:
    id: str
    name: str
    version: str
    type: str = "CHAT_INPUT"
    path: tuple[str, ...] = ()

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> Self:
        return cls(
            id=str(data.get("id", data.get("commandId"))),
            name=str(data["name"]),
            version=str(data.get("version", data.get("commandVersion", "1"))),
            type=str(data.get("type", "CHAT_INPUT")),
            path=tuple(str(item) for item in data.get("path", ())),
        )


@dataclass(frozen=True, slots=True)
class Interaction:
    id: str
    application_id: str
    channel_id: str
    user: User
    command: InteractionCommand
    token: str | None = field(default=None, repr=False)
    community_id: str | None = None
    options: dict[str, object] = field(default_factory=dict)
    resolved: dict[str, object] = field(default_factory=dict)
    type: str = "APPLICATION_COMMAND"
    context: str = "COMMUNITY"
    custom_id: str | None = None
    values: tuple[str, ...] | dict[str, str] = ()
    component_type: str | None = None
    message_id: str | None = None
    message_seq: str | None = None
    source_version: str | None = None
    parent_interaction_id: str | None = None
    created_at: str | None = None
    expires_at: str | None = None

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> Self:
        raw_nested = data.get("data")
        nested: dict[str, Any] = raw_nested if isinstance(raw_nested, dict) else {}
        raw_command = data.get("command")
        legacy_command: dict[str, Any] | None = (
            raw_command if isinstance(raw_command, dict) else None
        )
        command_data = legacy_command or {
            "commandId": nested.get("commandId", ""),
            "name": nested.get("name", ""),
            "commandVersion": nested.get("commandVersion", data.get("version", "1")),
            "type": nested.get("type", "CHAT_INPUT"),
            "path": nested.get("path", ()),
        }
        raw_options = data.get("options", nested.get("options", {}))
        raw_resolved = nested.get("resolved", {})
        raw_values = nested.get("values", data.get("values", ()))
        if isinstance(raw_values, dict):
            values: tuple[str, ...] | dict[str, str] = {
                str(key): str(value) for key, value in raw_values.items()
            }
        elif isinstance(raw_values, list):
            values = tuple(str(value) for value in raw_values)
        else:
            values = ()
        return cls(
            id=str(data["id"]),
            application_id=str(data["applicationId"]),
            community_id=_optional_string(data.get("communityId")),
            channel_id=str(data["channelId"]),
            user=User.from_dict(data["user"]),
            command=InteractionCommand.from_dict(command_data),
            token=_optional_string(data.get("token")),
            options=dict(raw_options) if isinstance(raw_options, dict) else {},
            resolved=dict(raw_resolved) if isinstance(raw_resolved, dict) else {},
            type=str(data.get("type", "APPLICATION_COMMAND")),
            context=str(data.get("context", "COMMUNITY")),
            custom_id=_optional_string(nested.get("customId", data.get("customId"))),
            values=values,
            component_type=_optional_string(nested.get("componentType")),
            message_id=_optional_string(
                nested.get("messageId", nested.get("sourceMessageId"))
            ),
            message_seq=_optional_string(nested.get("messageSeq")),
            source_version=_optional_string(nested.get("sourceVersion")),
            parent_interaction_id=_optional_string(nested.get("parentInteractionId")),
            created_at=_optional_string(data.get("createdAt")),
            expires_at=_optional_string(data.get("expiresAt")),
        )


@dataclass(frozen=True, slots=True)
class InteractionResponse:
    id: str
    status: str = "completed"
    ephemeral: bool = False
    message_seq: str | None = None
    version: str | None = None
    content: str = ""

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> Self:
        flags = data.get("flags", ())
        return cls(
            id=str(data["id"]),
            status=str(data.get("status", "completed")),
            ephemeral=bool(data.get("ephemeral", "EPHEMERAL" in flags)),
            message_seq=_optional_string(data.get("messageSeq")),
            version=_optional_string(data.get("version")),
            content=str(data.get("content", "")),
        )


def autocomplete_payload(choices: tuple[CommandChoice, ...]) -> dict[str, object]:
    return {"choices": [choice.to_dict() for choice in choices]}


def _optional_string(value: object) -> str | None:
    return None if value is None else str(value)


def _defined(**values: object) -> dict[str, object]:
    return {key: value for key, value in values.items() if value is not None}
