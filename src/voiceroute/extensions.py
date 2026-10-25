"""Reusable command and listener extensions."""

from __future__ import annotations

from collections.abc import Awaitable, Callable, Sequence
from dataclasses import dataclass
from typing import TYPE_CHECKING, TypeVar, cast

if TYPE_CHECKING:
    from voiceroute.bot import Bot

ExtensionCallback = Callable[..., Awaitable[None]]
CallbackT = TypeVar("CallbackT", bound=ExtensionCallback)


@dataclass(frozen=True, slots=True)
class ExtensionCommand:
    """Command metadata declared on an extension method."""

    name: str | None = None
    aliases: tuple[str, ...] = ()
    description: str | None = None
    usage: str | None = None


class Extension:
    """Base class for a reusable group of commands and event listeners."""

    @property
    def qualified_name(self) -> str:
        return f"{self.__class__.__module__}.{self.__class__.__qualname__}"

    async def setup(self, bot: Bot) -> None:
        """Initialize resources before handlers are registered."""

    async def teardown(self, bot: Bot) -> None:
        """Release resources after handlers are unregistered."""


def command(
    name: str | None = None,
    *,
    aliases: Sequence[str] = (),
    description: str | None = None,
    usage: str | None = None,
) -> Callable[[CallbackT], CallbackT]:
    """Declare an extension method as a command."""
    metadata = ExtensionCommand(
        name=name,
        aliases=tuple(aliases),
        description=description,
        usage=usage,
    )

    def decorator(callback: CallbackT) -> CallbackT:
        vars(callback)["__vr_extension_command__"] = metadata
        return callback

    return decorator


def listener(name: str | None = None) -> Callable[[CallbackT], CallbackT]:
    """Declare an extension method as an event listener."""

    def decorator(callback: CallbackT) -> CallbackT:
        vars(callback)["__vr_listener_name__"] = name or callback.__name__
        return callback

    return decorator


def extension_command(callback: Callable[..., object]) -> ExtensionCommand | None:
    """Return extension command metadata attached to a bound method."""
    return cast(ExtensionCommand | None, getattr(callback, "__vr_extension_command__", None))


def listener_name(callback: Callable[..., object]) -> str | None:
    """Return the event name attached to a bound method."""
    return cast(str | None, getattr(callback, "__vr_listener_name__", None))
