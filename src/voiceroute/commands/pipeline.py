"""Checks, middleware, cooldowns, and concurrency for commands."""

from __future__ import annotations

import asyncio
import inspect
import time
from collections import defaultdict, deque
from collections.abc import Awaitable, Callable, Sequence
from dataclasses import dataclass
from enum import StrEnum
from typing import Protocol, TypeVar, cast

from voiceroute.commands.context import Context
from voiceroute.errors import CheckFailure, CommandOnCooldown, MaxConcurrencyReached

Check = Callable[[Context], bool | Awaitable[bool]]
NextMiddleware = Callable[[], Awaitable[None]]
Middleware = Callable[[Context, NextMiddleware], Awaitable[None]]
CallbackT = TypeVar("CallbackT", bound=Callable[..., Awaitable[None]])


class BucketType(StrEnum):
    """Scope used to partition cooldown and concurrency state."""

    GLOBAL = "global"
    USER = "user"
    CHANNEL = "channel"
    COMMUNITY = "community"


@dataclass(frozen=True, slots=True)
class Cooldown:
    """Allow ``rate`` invocations in each ``per`` second window."""

    rate: int
    per: float
    bucket: BucketType = BucketType.USER

    def __post_init__(self) -> None:
        if self.rate <= 0:
            raise ValueError("cooldown rate must be positive")
        if self.per <= 0:
            raise ValueError("cooldown period must be positive")


@dataclass(frozen=True, slots=True)
class ConcurrencyLimit:
    """Maximum active invocations in one bucket."""

    number: int
    bucket: BucketType = BucketType.USER

    def __post_init__(self) -> None:
        if self.number <= 0:
            raise ValueError("concurrency limit must be positive")


class PipelineCommand(Protocol):
    """Command surface consumed by the pipeline."""

    @property
    def name(self) -> str: ...

    @property
    def checks(self) -> Sequence[Check]: ...

    @property
    def cooldown(self) -> Cooldown | None: ...

    @property
    def concurrency(self) -> ConcurrencyLimit | None: ...

    async def invoke(self, context: Context, arguments: Sequence[str]) -> None: ...


class CommandPipeline:
    """Execute checks and middleware around a command invocation."""

    def __init__(self) -> None:
        self._middleware: list[Middleware] = []
        self._cooldowns: dict[tuple[str, str], deque[float]] = defaultdict(deque)
        self._active: dict[tuple[str, str], int] = defaultdict(int)
        self._state_lock = asyncio.Lock()

    @property
    def middleware(self) -> tuple[Middleware, ...]:
        return tuple(self._middleware)

    def add_middleware(self, middleware: Middleware) -> None:
        if not inspect.iscoroutinefunction(middleware):
            raise TypeError("command middleware must be an async function")
        self._middleware.append(middleware)

    def remove_middleware(self, middleware: Middleware) -> None:
        self._middleware.remove(middleware)

    async def invoke(
        self,
        command: PipelineCommand,
        context: Context,
        arguments: Sequence[str],
    ) -> None:
        await self._run_checks(command, context)
        await self._acquire_cooldown(command, context)
        concurrency_key = await self._acquire_concurrency(command, context)
        try:
            await self._run_middleware(command, context, arguments)
        finally:
            if concurrency_key is not None:
                await self._release_concurrency(concurrency_key)

    async def _run_checks(self, command: PipelineCommand, context: Context) -> None:
        for predicate in command.checks:
            result = predicate(context)
            if inspect.isawaitable(result):
                result = await result
            if not result:
                name = getattr(predicate, "__name__", predicate.__class__.__name__)
                raise CheckFailure(command.name, name)

    async def _acquire_cooldown(
        self,
        command: PipelineCommand,
        context: Context,
    ) -> None:
        config = command.cooldown
        if config is None:
            return
        key = (command.name, _bucket_key(config.bucket, context))
        now = time.monotonic()
        async with self._state_lock:
            timestamps = self._cooldowns[key]
            threshold = now - config.per
            while timestamps and timestamps[0] <= threshold:
                timestamps.popleft()
            if len(timestamps) >= config.rate:
                retry_after = max(0.0, config.per - (now - timestamps[0]))
                raise CommandOnCooldown(command.name, retry_after)
            timestamps.append(now)

    async def _acquire_concurrency(
        self,
        command: PipelineCommand,
        context: Context,
    ) -> tuple[str, str] | None:
        config = command.concurrency
        if config is None:
            return None
        key = (command.name, _bucket_key(config.bucket, context))
        async with self._state_lock:
            if self._active[key] >= config.number:
                raise MaxConcurrencyReached(command.name, config.number, config.bucket.value)
            self._active[key] += 1
        return key

    async def _release_concurrency(self, key: tuple[str, str]) -> None:
        async with self._state_lock:
            self._active[key] -= 1
            if self._active[key] == 0:
                del self._active[key]

    async def _run_middleware(
        self,
        command: PipelineCommand,
        context: Context,
        arguments: Sequence[str],
    ) -> None:
        async def call_at(index: int) -> None:
            if index == len(self._middleware):
                await command.invoke(context, arguments)
                return

            called = False

            async def call_next() -> None:
                nonlocal called
                if called:
                    raise RuntimeError("command middleware called next more than once")
                called = True
                await call_at(index + 1)

            await self._middleware[index](context, call_next)

        await call_at(0)


def check(predicate: Check) -> Callable[[CallbackT], CallbackT]:
    """Attach a predicate that must pass before invoking a command."""

    def decorator(callback: CallbackT) -> CallbackT:
        checks = (*_callback_checks(callback), predicate)
        vars(callback)["__vr_checks__"] = checks
        return callback

    return decorator


def cooldown(
    rate: int,
    per: float,
    *,
    bucket: BucketType = BucketType.USER,
) -> Callable[[CallbackT], CallbackT]:
    """Attach a fixed-window cooldown declaration to a command callback."""
    config = Cooldown(rate=rate, per=per, bucket=bucket)

    def decorator(callback: CallbackT) -> CallbackT:
        vars(callback)["__vr_cooldown__"] = config
        return callback

    return decorator


def max_concurrency(
    number: int,
    *,
    bucket: BucketType = BucketType.USER,
) -> Callable[[CallbackT], CallbackT]:
    """Limit simultaneously running command callbacks in one bucket."""
    config = ConcurrencyLimit(number=number, bucket=bucket)

    def decorator(callback: CallbackT) -> CallbackT:
        vars(callback)["__vr_concurrency__"] = config
        return callback

    return decorator


def command_checks(callback: Callable[..., object]) -> tuple[Check, ...]:
    """Return checks declared on a callback."""
    return _callback_checks(callback)


def command_cooldown(callback: Callable[..., object]) -> Cooldown | None:
    """Return a cooldown declared on a callback."""
    return cast(Cooldown | None, getattr(callback, "__vr_cooldown__", None))


def command_concurrency(callback: Callable[..., object]) -> ConcurrencyLimit | None:
    """Return a concurrency limit declared on a callback."""
    return cast(ConcurrencyLimit | None, getattr(callback, "__vr_concurrency__", None))


def _callback_checks(callback: Callable[..., object]) -> tuple[Check, ...]:
    return cast(tuple[Check, ...], getattr(callback, "__vr_checks__", ()))


def _bucket_key(bucket: BucketType, context: Context) -> str:
    if bucket is BucketType.GLOBAL:
        return "global"
    if bucket is BucketType.COMMUNITY:
        return context.message.community_id
    if bucket is BucketType.CHANNEL:
        return f"{context.message.community_id}:{context.message.channel_id}"
    author = context.message.author
    return str(author.id) if author is not None else "unknown"
