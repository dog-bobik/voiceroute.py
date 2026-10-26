"""Native VoiceRoute application-command models."""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import StrEnum
from typing import Any, Self

from voiceroute.models.user import User


class CommandOptionType(StrEnum):
    """Supported VoiceRoute application-command option types."""

    STRING = "string"
    INTEGER = "integer"
    NUMBER = "number"
    BOOLEAN = "boolean"
    USER = "user"
    CHANNEL = "channel"
    ROLE = "role"


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
    min_length: int | None = None
    max_length: int | None = None
    min_value: int | float | None = None
    max_value: int | float | None = None

    def to_dict(self) -> dict[str, object]:
        values: dict[str, object] = {
            "name": self.name,
            "description": self.description,
            "type": self.type.value,
            "required": self.required,
        }
        optional = {
            "choices": [choice.to_dict() for choice in self.choices] if self.choices else None,
            "minLength": self.min_length,
            "maxLength": self.max_length,
            "minValue": self.min_value,
            "maxValue": self.max_value,
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
            min_length=_optional_int(data.get("minLength")),
            max_length=_optional_int(data.get("maxLength")),
            min_value=_optional_number(data.get("minValue")),
            max_value=_optional_number(data.get("maxValue")),
        )


@dataclass(frozen=True, slots=True)
class CommandDefinition:
    """Definition used to replace an application's command registry."""

    name: str
    description: str
    options: tuple[CommandOption, ...] = ()
    default_member_permissions: tuple[str, ...] = ()

    def to_dict(self) -> dict[str, object]:
        return {
            "name": self.name,
            "description": self.description,
            "options": [option.to_dict() for option in self.options],
            "defaultMemberPermissions": list(self.default_member_permissions),
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> Self:
        return cls(
            name=str(data["name"]),
            description=str(data["description"]),
            options=tuple(CommandOption.from_dict(item) for item in data.get("options", ())),
            default_member_permissions=tuple(
                str(permission) for permission in data.get("defaultMemberPermissions", ())
            ),
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
    version: int
    name: str
    description: str
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
            version=int(data["version"]),
            name=definition.name,
            description=definition.description,
            options=definition.options,
            default_member_permissions=definition.default_member_permissions,
            application=(
                ApplicationSummary.from_dict(raw_application)
                if isinstance(raw_application, dict)
                else None
            ),
            extra={key: value for key, value in data.items() if key not in known},
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
