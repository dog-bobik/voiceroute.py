"""Native VoiceRoute application-command models."""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import StrEnum
from typing import Any, Self

from voiceroute.models.user import User


class CommandOptionType(StrEnum):
    """Supported VoiceRoute application-command option types."""

    SUB_COMMAND = "SUB_COMMAND"
    SUB_COMMAND_GROUP = "SUB_COMMAND_GROUP"
    STRING = "STRING"
    INTEGER = "INTEGER"
    NUMBER = "NUMBER"
    BOOLEAN = "BOOLEAN"
    USER = "USER"
    CHANNEL = "CHANNEL"
    ROLE = "ROLE"
    MENTIONABLE = "MENTIONABLE"
    ATTACHMENT = "ATTACHMENT"

    @classmethod
    def _missing_(cls, value: object) -> CommandOptionType | None:
        if isinstance(value, str):
            return cls.__members__.get(value.upper())
        return None


class CommandType(StrEnum):
    CHAT_INPUT = "CHAT_INPUT"
    USER = "USER"
    MESSAGE = "MESSAGE"


class CommandContext(StrEnum):
    COMMUNITY = "COMMUNITY"
    BOT_DM = "BOT_DM"
    PRIVATE_CHANNEL = "PRIVATE_CHANNEL"


@dataclass(frozen=True, slots=True)
class CommandChoice:
    """One fixed value offered for an application-command option."""

    name: str
    value: str | int | float

    def to_dict(self) -> dict[str, object]:
        return {"name": self.name, "value": self.value}

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> Self:
        value = data["value"]
        if not isinstance(value, (str, int, float)) or isinstance(value, bool):
            raise ValueError("command choice value must be a string or number")
        return cls(name=str(data["name"]), value=value)


@dataclass(frozen=True, slots=True)
class CommandOption:
    """Typed input declared by an application command."""

    name: str
    description: str
    type: CommandOptionType
    required: bool = False
    choices: tuple[CommandChoice, ...] = ()
    options: tuple[CommandOption, ...] = ()
    autocomplete: bool = False
    min_length: int | None = None
    max_length: int | None = None
    min_value: int | float | None = None
    max_value: int | float | None = None
    channel_types: tuple[str, ...] = ()
    name_localizations: dict[str, str] = field(default_factory=dict)
    description_localizations: dict[str, str] = field(default_factory=dict)

    def __post_init__(self) -> None:
        if self.choices and self.autocomplete:
            raise ValueError("command option choices and autocomplete are mutually exclusive")
        if self.type in {CommandOptionType.SUB_COMMAND, CommandOptionType.SUB_COMMAND_GROUP}:
            if not self.options:
                raise ValueError("subcommands and groups require nested options")
        elif self.options:
            raise ValueError("only subcommands and groups may contain nested options")

    def to_dict(self) -> dict[str, object]:
        values: dict[str, object] = {
            "name": self.name,
            "description": self.description,
            "type": self.type.value,
            "required": self.required,
        }
        optional = {
            "choices": [choice.to_dict() for choice in self.choices] if self.choices else None,
            "options": [option.to_dict() for option in self.options] if self.options else None,
            "autocomplete": self.autocomplete or None,
            "minLength": self.min_length,
            "maxLength": self.max_length,
            "minValue": self.min_value,
            "maxValue": self.max_value,
            "channelTypes": list(self.channel_types) if self.channel_types else None,
            "nameLocalizations": self.name_localizations or None,
            "descriptionLocalizations": self.description_localizations or None,
        }
        values.update({key: value for key, value in optional.items() if value is not None})
        return values

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> Self:
        return cls(
            name=str(data["name"]),
            description=str(data["description"]),
            type=CommandOptionType(str(data["type"])),
            required=bool(data.get("required", False)),
            choices=tuple(CommandChoice.from_dict(item) for item in data.get("choices", ())),
            options=tuple(CommandOption.from_dict(item) for item in data.get("options", ())),
            autocomplete=bool(data.get("autocomplete", False)),
            min_length=_optional_int(data.get("minLength")),
            max_length=_optional_int(data.get("maxLength")),
            min_value=_optional_number(data.get("minValue")),
            max_value=_optional_number(data.get("maxValue")),
            channel_types=tuple(str(item) for item in data.get("channelTypes", ())),
            name_localizations=dict(data.get("nameLocalizations", {})),
            description_localizations=dict(data.get("descriptionLocalizations", {})),
        )


@dataclass(frozen=True, slots=True)
class CommandDefinition:
    """Definition used to replace an application's command registry."""

    name: str
    description: str = ""
    type: CommandType = CommandType.CHAT_INPUT
    options: tuple[CommandOption, ...] = ()
    contexts: tuple[CommandContext, ...] = (CommandContext.COMMUNITY,)
    default_member_permissions: tuple[str, ...] = ()
    name_localizations: dict[str, str] = field(default_factory=dict)
    description_localizations: dict[str, str] = field(default_factory=dict)
    nsfw: bool = False

    def __post_init__(self) -> None:
        if self.type is CommandType.CHAT_INPUT and not self.description:
            raise ValueError("CHAT_INPUT commands require a description")
        if self.type is not CommandType.CHAT_INPUT and (self.description or self.options):
            raise ValueError("USER and MESSAGE commands cannot have descriptions or options")

    def to_dict(self) -> dict[str, object]:
        return {
            "name": self.name,
            "description": self.description,
            "type": self.type.value,
            "options": [option.to_dict() for option in self.options],
            "contexts": [context.value for context in self.contexts],
            "defaultMemberPermissions": list(self.default_member_permissions),
            "nameLocalizations": self.name_localizations,
            "descriptionLocalizations": self.description_localizations,
            "nsfw": self.nsfw,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> Self:
        return cls(
            name=str(data["name"]),
            description=str(data["description"]),
            type=CommandType(str(data.get("type", "CHAT_INPUT"))),
            options=tuple(CommandOption.from_dict(item) for item in data.get("options", ())),
            contexts=tuple(
                CommandContext(str(context)) for context in data.get("contexts", ("COMMUNITY",))
            ),
            default_member_permissions=tuple(
                str(permission) for permission in data.get("defaultMemberPermissions", ())
            ),
            name_localizations=dict(data.get("nameLocalizations", {})),
            description_localizations=dict(data.get("descriptionLocalizations", {})),
            nsfw=bool(data.get("nsfw", False)),
        )


@dataclass(frozen=True, slots=True)
class ApplicationSummary:
    """Application identity embedded in a registered command."""

    id: str
    name: str
    bot: User

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> Self:
        return cls(id=str(data["id"]), name=str(data["name"]), bot=User.from_dict(data["bot"]))


@dataclass(frozen=True, slots=True)
class ApplicationCommand:
    """Command registered for one VoiceRoute application."""

    id: str
    application_id: str
    version: str
    name: str
    description: str
    type: CommandType = CommandType.CHAT_INPUT
    contexts: tuple[CommandContext, ...] = (CommandContext.COMMUNITY,)
    scope: dict[str, str] = field(default_factory=lambda: {"type": "global"})
    options: tuple[CommandOption, ...] = ()
    default_member_permissions: tuple[str, ...] = ()
    application: ApplicationSummary | None = None
    extra: dict[str, Any] = field(default_factory=dict)

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> Self:
        definition = CommandDefinition.from_dict(data)
        known = {
            "id",
            "applicationId",
            "version",
            "name",
            "description",
            "options",
            "defaultMemberPermissions",
            "application",
        }
        raw_application = data.get("application")
        return cls(
            id=str(data["id"]),
            application_id=str(data["applicationId"]),
            version=str(data["version"]),
            name=definition.name,
            description=definition.description,
            type=definition.type,
            contexts=definition.contexts,
            scope=dict(data.get("scope", {"type": "global"})),
            options=definition.options,
            default_member_permissions=definition.default_member_permissions,
            application=(
                ApplicationSummary.from_dict(raw_application)
                if isinstance(raw_application, dict)
                else None
            ),
            extra={key: value for key, value in data.items() if key not in known},
        )


@dataclass(frozen=True, slots=True)
class CommandPermissionTarget:
    type: str
    allow: bool
    id: str | None = None

    def to_dict(self) -> dict[str, object]:
        values: dict[str, object] = {"type": self.type, "allow": self.allow}
        if self.id is not None:
            values["id"] = self.id
        return values

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> Self:
        return cls(
            type=str(data["type"]),
            allow=bool(data["allow"]),
            id=_optional_string(data.get("id")),
        )


@dataclass(frozen=True, slots=True)
class CommandPermissions:
    command_id: str
    community_id: str
    version: str
    targets: tuple[CommandPermissionTarget, ...]

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> Self:
        return cls(
            command_id=str(data["commandId"]),
            community_id=str(data["communityId"]),
            version=str(data["version"]),
            targets=tuple(CommandPermissionTarget.from_dict(item) for item in data["targets"]),
        )


def _optional_int(value: object) -> int | None:
    if value is None:
        return None
    if not isinstance(value, int) or isinstance(value, bool):
        raise ValueError("command option length bound must be an integer")
    return value


def _optional_number(value: object) -> int | float | None:
    if value is None:
        return None
    if not isinstance(value, (int, float)) or isinstance(value, bool):
        raise ValueError("command option bound must be a number")
    return value


def _optional_string(value: object) -> str | None:
    return None if value is None else str(value)
