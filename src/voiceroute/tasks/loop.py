"""A small supervised periodic task primitive."""

from __future__ import annotations

import asyncio
import inspect
import time
from collections.abc import Awaitable, Callable
from typing import Any, Generic, TypeVar

Callback = Callable[..., Awaitable[None]]
T = TypeVar("T")


class Loop(Generic[T]):
    """Descriptor configured with an async callback and optional lifecycle hooks."""

    def __init__(self, callback: Callback, *, seconds: float, count: int | None, reconnect: bool):
        if seconds <= 0:
            raise ValueError("loop interval must be positive")
        if count is not None and count <= 0:
            raise ValueError("loop count must be positive or None")
        if not inspect.iscoroutinefunction(callback):
            raise TypeError("loop callback must be async")
        self.callback = callback
        self.seconds = seconds
        self.count = count
        self.reconnect = reconnect
        self.before: Callback | None = None
        self.after: Callback | None = None
        self.error: Callable[..., Awaitable[None]] | None = None
        self.name = callback.__name__
        self._cache_key = f"__vr_bound_loop_{self.name}"

    def __set_name__(self, owner: type[object], name: str) -> None:
        self.name = name
        self._cache_key = f"__vr_bound_loop_{name}"

    def __get__(self, instance: T | None, owner: type[T] | None = None) -> Loop[T] | BoundLoop[T]:
        if instance is None:
            return self
        cached = vars(instance).get(self._cache_key)
        if isinstance(cached, BoundLoop):
            return cached
        bound = BoundLoop(self, instance)
        vars(instance)[self._cache_key] = bound
        return bound

    def before_loop(self, callback: Callback) -> Callback:
        self.before = callback
        return callback

    def after_loop(self, callback: Callback) -> Callback:
        self.after = callback
        return callback

    def error_handler(
        self, callback: Callable[..., Awaitable[None]]
    ) -> Callable[..., Awaitable[None]]:
        self.error = callback
        return callback


class BoundLoop(Generic[T]):
    """One loop instance bound to an extension or service object."""

    def __init__(self, loop: Loop[T], instance: T) -> None:
        self.loop = loop
        self.instance = instance
        self.task: asyncio.Task[None] | None = None
        self._stop = asyncio.Event()
        self.current_iteration = 0

    @property
    def is_running(self) -> bool:
        return self.task is not None and not self.task.done()

    def start(self, *args: object, **kwargs: object) -> asyncio.Task[None]:
        if self.is_running:
            raise RuntimeError(f"background loop {self.loop.name!r} is already running")
        self._stop = asyncio.Event()
        self.current_iteration = 0
        self.task = asyncio.create_task(
            self._run(*args, **kwargs), name=f"voiceroute:loop:{self.loop.name}"
        )
        return self.task

    def stop(self) -> None:
        self._stop.set()

    def cancel(self) -> None:
        if self.task is not None:
            self.task.cancel()

    async def wait(self) -> None:
        if self.task is not None:
            await self.task

    async def _run(self, *args: object, **kwargs: object) -> None:
        callback = self.loop.callback.__get__(self.instance, type(self.instance))
        before = self.loop.before
        after = self.loop.after
        error_hook = self.loop.error
        try:
            if before is not None:
                await before.__get__(self.instance, type(self.instance))()
            while not self._stop.is_set():
                started = time.monotonic()
                try:
                    await callback(*args, **kwargs)
                    self.current_iteration += 1
                    if self.loop.count is not None and self.current_iteration >= self.loop.count:
                        break
                except asyncio.CancelledError:
                    raise
                except Exception as exc:
                    if error_hook is not None:
                        await error_hook.__get__(self.instance, type(self.instance))(exc)
                    if not self.loop.reconnect:
                        break
                delay = max(0.0, self.loop.seconds - (time.monotonic() - started))
                try:
                    await asyncio.wait_for(self._stop.wait(), timeout=delay)
                except TimeoutError:
                    pass
        finally:
            if after is not None:
                await after.__get__(self.instance, type(self.instance))()


def loop(
    *, seconds: float, count: int | None = None, reconnect: bool = True
) -> Callable[[Callback], Loop[Any]]:
    """Declare a supervised periodic task on a class or create one on an object."""

    def decorator(callback: Callback) -> Loop[Any]:
        return Loop(callback, seconds=seconds, count=count, reconnect=reconnect)

    return decorator
