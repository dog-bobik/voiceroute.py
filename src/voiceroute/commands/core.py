"""Transport-independent command declarations and invocation."""

from __future__ import annotations

import inspect
import types
from collections.abc import Awaitable, Callable, Sequence
from dataclasses import dataclass
from typing import Union, get_args, get_origin, get_type_hints

from voiceroute.commands.context import Context
from voiceroute.commands.pipeline import (
    Check,
    ConcurrencyLimit,
    Cooldown,
    command_checks,
    command_concurrency,
    command_cooldown,
)
from voiceroute.errors import (
    BadArgument,
    CommandNotFound,
    MissingRequiredArgument,
    TooManyArguments,
    UnsupportedCommandParameter,
)

CommandCallback = Callable[..., Awaitable[None]]


@dataclass(frozen=True, slots=True)
class CommandInvocation:
    """A transport-neutral request to invoke a registered command."""

    path: tuple[str, ...]
    arguments: tuple[str, ...]
    invoked_with: str
    prefix: str


@dataclass(frozen=True, slots=True)
class CommandParameter:
    """One validated positional command parameter."""

    name: str
    annotation: object
    required: bool
    default: object
    variadic: bool = False


@dataclass(frozen=True, slots=True)
class Command:
    """Metadata and callback for a prefix or future interaction command."""

    path: tuple[str, ...]
    callback: CommandCallback
    aliases: tuple[tuple[str, ...], ...] = ()
    description: str = ""
    usage: str | None = None
    parameters: tuple[CommandParameter, ...] = ()
    checks: tuple[Check, ...] = ()
    cooldown: Cooldown | None = None
    concurrency: ConcurrencyLimit | None = None

    @property
    def name(self) -> str:
        return " ".join(self.path)

    @classmethod
    def from_callback(
        cls,
        callback: CommandCallback,
        *,
        name: str | None = None,
        aliases: Sequence[str] = (),
        description: str | None = None,
        usage: str | None = None,
    ) -> Command:
        path = _normalize_path(name or callback.__name__)
        alias_paths = tuple(_alias_path(path, alias) for alias in aliases)
        parameters = _inspect_parameters(callback)
        return cls(
            path=path,
            callback=callback,
            aliases=alias_paths,
            description=description if description is not None else inspect.getdoc(callback) or "",
            usage=usage,
            parameters=parameters,
            checks=command_checks(callback),
            cooldown=command_cooldown(callback),
            concurrency=command_concurrency(callback),
        )

    async def invoke(self, context: Context, arguments: Sequence[str]) -> None:
        converted = self.convert_arguments(arguments)
        await self.callback(context, *converted)

    def convert_arguments(self, arguments: Sequence[str]) -> tuple[object, ...]:
        # Context-only callbacks keep the original framework behavior: raw arguments
        # remain available through Context.args without being passed positionally.
        if not self.parameters:
            return ()
        values: list[object] = []
        position = 0
        for parameter in self.parameters:
            if parameter.variadic:
                values.extend(
                    _convert(argument, parameter.annotation, parameter.name)
                    for argument in arguments[position:]
                )
                position = len(arguments)
                continue
            if position < len(arguments):
                values.append(_convert(arguments[position], parameter.annotation, parameter.name))
                position += 1
                continue
            if parameter.required:
                raise MissingRequiredArgument(self.name, parameter.name)
            values.append(parameter.default)

        if position < len(arguments):
            raise TooManyArguments(self.name, tuple(arguments[position:]))
        return tuple(values)


class CommandRegistry:
    """Store commands and resolve the longest registered command path."""

    def __init__(self) -> None:
        self._commands: dict[tuple[str, ...], Command] = {}
        self._lookups: dict[tuple[str, ...], Command] = {}

    @property
    def commands(self) -> tuple[Command, ...]:
        return tuple(self._commands.values())

    def add(self, command: Command) -> None:
        paths = (command.path, *command.aliases)
        duplicate = next((path for path in paths if path in self._lookups), None)
        if duplicate is not None:
            raise ValueError(f"command path is already registered: {' '.join(duplicate)}")
        if len(set(paths)) != len(paths):
            raise ValueError("command aliases must be unique")
        self._commands[command.path] = command
        for path in paths:
            self._lookups[path] = command

    def get(self, name: str) -> Command | None:
        return self._lookups.get(_normalize_path(name))

    def resolve(self, tokens: Sequence[str]) -> tuple[Command, CommandInvocation]:
        normalized = tuple(token.casefold() for token in tokens)
        for size in range(len(normalized), 0, -1):
            path = normalized[:size]
            command = self._lookups.get(path)
            if command is not None:
                return command, CommandInvocation(
                    path=command.path,
                    arguments=tuple(tokens[size:]),
                    invoked_with=" ".join(tokens[:size]),
                    prefix="",
                )
        attempted = tokens[0] if tokens else ""
        raise CommandNotFound(attempted)


def _inspect_parameters(callback: CommandCallback) -> tuple[CommandParameter, ...]:
    signature = inspect.signature(callback)
    raw_parameters = tuple(signature.parameters.values())
    if not raw_parameters:
        raise TypeError("command callback must accept a Context parameter")
    if all(
        parameter.kind in (parameter.VAR_POSITIONAL, parameter.VAR_KEYWORD)
        for parameter in raw_parameters
    ):
        return ()

    try:
        hints = get_type_hints(callback)
    except (NameError, TypeError):
        hints = {}

    result: list[CommandParameter] = []
    for parameter in raw_parameters[1:]:
        if parameter.kind in (parameter.KEYWORD_ONLY, parameter.VAR_KEYWORD):
            raise UnsupportedCommandParameter(parameter.name, "keyword-only parameters")
        annotation = hints.get(parameter.name, parameter.annotation)
        if annotation is inspect.Parameter.empty:
            annotation = str
        if not _is_supported_annotation(annotation):
            raise UnsupportedCommandParameter(parameter.name, repr(annotation))
        result.append(
            CommandParameter(
                name=parameter.name,
                annotation=annotation,
                required=(
                    parameter.default is inspect.Parameter.empty
                    and parameter.kind != parameter.VAR_POSITIONAL
                ),
                default=None if parameter.default is inspect.Parameter.empty else parameter.default,
                variadic=parameter.kind == parameter.VAR_POSITIONAL,
            )
        )
    return tuple(result)


def _normalize_path(value: str) -> tuple[str, ...]:
    path = tuple(part.casefold() for part in value.split())
    if not path:
        raise ValueError("command name must contain at least one word")
    return path


def _alias_path(command_path: tuple[str, ...], alias: str) -> tuple[str, ...]:
    alias_path = _normalize_path(alias)
    if len(alias_path) > 1 or len(command_path) == 1:
        return alias_path
    return (*command_path[:-1], *alias_path)


def _is_supported_annotation(annotation: object) -> bool:
    if annotation in (str, int, float, bool):
        return True
    origin = get_origin(annotation)
    if origin in (Union, types.UnionType):
        options = tuple(item for item in get_args(annotation) if item is not type(None))
        return len(options) == 1 and options[0] in (str, int, float, bool)
    return False


def _convert(value: str, annotation: object, parameter_name: str) -> object:
    origin = get_origin(annotation)
    if origin in (Union, types.UnionType):
        annotation = next(item for item in get_args(annotation) if item is not type(None))
    try:
        if annotation is str:
            return value
        if annotation is int:
            return int(value)
        if annotation is float:
            return float(value)
        if annotation is bool:
            normalized = value.casefold()
            if normalized in {"1", "true", "yes", "on"}:
                return True
            if normalized in {"0", "false", "no", "off"}:
                return False
            raise ValueError
    except ValueError as exc:
        type_name = getattr(annotation, "__name__", str(annotation))
        raise BadArgument(parameter_name, value, type_name) from exc
    raise UnsupportedCommandParameter(parameter_name, repr(annotation))
