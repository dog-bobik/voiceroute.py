"""Reusable command and listener extensions."""

from __future__ import annotations

import asyncio
from collections.abc import Awaitable, Callable, Sequence
from dataclasses import dataclass
from typing import TYPE_CHECKING, TypeVar, cast

from voiceroute.tasks import BoundLoop, Loop

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

    def __init__(self) -> None:
        self._bot: Bot | None = None

    @property
    def bot(self) -> Bot:
        if self._bot is None:
            raise RuntimeError("extension has not been added to a bot")
        return self._bot

    def _bind(self, bot: Bot) -> None:
        self._bot = bot

    @property
    def qualified_name(self) -> str:
        return f"{self.__class__.__module__}.{self.__class__.__qualname__}"

    async def setup(self, bot: Bot) -> None:
        """Initialize resources before handlers are registered."""

    async def teardown(self, bot: Bot) -> None:
        """Release resources after handlers are unregistered."""

    def start_tasks(self) -> tuple[BoundLoop[object], ...]:
        """Start declared loops after setup, preserving one shared loop per instance."""
        loops: list[BoundLoop[object]] = []
        seen: set[str] = set()
        for cls in reversed(type(self).__mro__):
            for name, declaration in vars(cls).items():
                if name in seen or not isinstance(declaration, Loop):
                    continue
                seen.add(name)
                bound = getattr(self, name)
                if not isinstance(bound, BoundLoop):
                    continue
                if not bound.is_running:
                    bound.start()
                loops.append(cast(BoundLoop[object], bound))
        return tuple(loops)

    async def stop_tasks(self) -> None:
        """Cancel and await every started loop before extension teardown."""
        loops: list[BoundLoop[object]] = []
        seen: set[str] = set()
        for cls in reversed(type(self).__mro__):
            for name, declaration in vars(cls).items():
                if name in seen or not isinstance(declaration, Loop):
                    continue
                seen.add(name)
                bound = getattr(self, name)
                if isinstance(bound, BoundLoop):
                    loops.append(cast(BoundLoop[object], bound))
        for bound in loops:
            bound.cancel()
        if loops:
            await asyncio.gather(*(bound.wait() for bound in loops), return_exceptions=True)


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
