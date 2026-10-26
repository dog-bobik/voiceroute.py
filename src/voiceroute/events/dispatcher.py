"""Unified Gateway event dispatch, waiters, deduplication, and error isolation."""

from __future__ import annotations

import asyncio
import inspect
from collections import deque
from collections.abc import Awaitable, Callable
from dataclasses import dataclass

from voiceroute.models import PlatformEvent

EventListener = Callable[[PlatformEvent], Awaitable[None]]
EventCheck = Callable[[PlatformEvent], bool]
DispatchHook = Callable[[PlatformEvent], Awaitable[None]]
DispatchErrorHandler = Callable[[Exception, PlatformEvent], Awaitable[None]]


@dataclass(slots=True)
class _Waiter:
    name: str
    future: asyncio.Future[PlatformEvent]
    check: EventCheck | None


class EventDispatcher:
    """Dispatch every advertised event while accepting unknown future events."""

    def __init__(
        self,
        *,
        deduplication_size: int = 10_000,
        before_dispatch: DispatchHook | None = None,
        after_dispatch: DispatchHook | None = None,
        error_handler: DispatchErrorHandler | None = None,
    ) -> None:
        if deduplication_size <= 0:
            raise ValueError("deduplication_size must be positive")
        self._listeners: dict[str, list[EventListener]] = {}
        self._waiters: list[_Waiter] = []
        self._delivery_ids: set[str] = set()
        self._delivery_order: deque[str] = deque()
        self._deduplication_size = deduplication_size
        self.before_dispatch = before_dispatch
        self.after_dispatch = after_dispatch
        self.error_handler = error_handler

    @staticmethod
    def event_name(value: str) -> str:
        value = value.removeprefix("on_")
        return value.upper()

    def add_listener(self, listener: EventListener, name: str = "*") -> None:
        if not inspect.iscoroutinefunction(listener):
            raise TypeError("event listeners must be async functions")
        key = "*" if name == "*" else self.event_name(name)
        self._listeners.setdefault(key, []).append(listener)

    def remove_listener(self, listener: EventListener, name: str = "*") -> None:
        key = "*" if name == "*" else self.event_name(name)
        listeners = self._listeners.get(key)
        if listeners is None or listener not in listeners:
            raise ValueError("event listener is not registered")
        listeners.remove(listener)
        if not listeners:
            del self._listeners[key]

    async def dispatch(self, event: PlatformEvent) -> bool:
        """Return false for a duplicate delivery, otherwise run listeners serially."""
        if event.delivery_id is not None and event.delivery_id in self._delivery_ids:
            return False
        if self.before_dispatch is not None:
            await self.before_dispatch(event)
        self._resolve_waiters(event)
        listeners = tuple(self._listeners.get(event.name, ())) + tuple(self._listeners.get("*", ()))
        for listener in listeners:
            try:
                await listener(event)
            except Exception as exc:
                if self.error_handler is None:
                    raise
                await self.error_handler(exc, event)
        if self.after_dispatch is not None:
            await self.after_dispatch(event)
        self._remember(event.delivery_id)
        return True

    async def wait_for(
        self,
        name: str,
        *,
        check: EventCheck | None = None,
        timeout: float | None = None,  # noqa: ASYNC109 - public wait_for convention
    ) -> PlatformEvent:
        loop = asyncio.get_running_loop()
        future: asyncio.Future[PlatformEvent] = loop.create_future()
        waiter = _Waiter(self.event_name(name), future, check)
        self._waiters.append(waiter)
        try:
            return await asyncio.wait_for(future, timeout)
        finally:
            if waiter in self._waiters:
                self._waiters.remove(waiter)

    def _resolve_waiters(self, event: PlatformEvent) -> None:
        for waiter in tuple(self._waiters):
            if waiter.name != event.name or waiter.future.done():
                continue
            try:
                accepted = waiter.check is None or waiter.check(event)
            except Exception as exc:
                waiter.future.set_exception(exc)
                self._waiters.remove(waiter)
                continue
            if accepted:
                waiter.future.set_result(event)
                self._waiters.remove(waiter)

    def _remember(self, delivery_id: str | None) -> None:
        if delivery_id is None:
            return
        self._delivery_ids.add(delivery_id)
        self._delivery_order.append(delivery_id)
        if len(self._delivery_order) > self._deduplication_size:
            expired = self._delivery_order.popleft()
            self._delivery_ids.remove(expired)
