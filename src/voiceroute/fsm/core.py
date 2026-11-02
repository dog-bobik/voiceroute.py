"""Storage protocol and isolated FSM context primitives."""

from __future__ import annotations

import asyncio
import time
from collections.abc import AsyncIterator, Mapping
from contextlib import asynccontextmanager
from dataclasses import dataclass
from typing import Protocol


@dataclass(frozen=True, slots=True)
class FSMKey:
    """Conversation identity; all scope dimensions are explicit and stable."""

    origin: str
    application_id: str
    community_id: str | None
    channel_id: str
    user_id: int

    def __post_init__(self) -> None:
        if not self.origin or not self.application_id or not self.channel_id or self.user_id <= 0:
            raise ValueError("FSM key requires origin, application, channel and positive user ID")


@dataclass(frozen=True, slots=True)
class FSMRecord:
    state: str | None
    data: Mapping[str, object]


class FSMStorage(Protocol):
    """Backend contract for durable or in-memory conversation state."""

    async def get(self, key: FSMKey) -> FSMRecord: ...

    async def set_state(self, key: FSMKey, state: str | None) -> None: ...

    async def update_data(self, key: FSMKey, values: Mapping[str, object]) -> dict[str, object]: ...

    async def clear(self, key: FSMKey) -> None: ...

    def isolate(self, key: FSMKey) -> AsyncIterator[None]: ...


class MemoryStorage:
    """Process-local storage with TTL and per-conversation atomic updates."""

    def __init__(self, *, ttl: float | None = 86_400.0) -> None:
        if ttl is not None and ttl <= 0:
            raise ValueError("ttl must be positive or None")
        self.ttl = ttl
        self._records: dict[FSMKey, tuple[str | None, dict[str, object], float | None]] = {}
        self._locks: dict[FSMKey, asyncio.Lock] = {}
        self._isolation_locks: dict[FSMKey, asyncio.Lock] = {}

    async def get(self, key: FSMKey) -> FSMRecord:
        async with self._lock_for(key):
            record = self._get_live_record(key)
            return FSMRecord(record[0], dict(record[1]))

    async def set_state(self, key: FSMKey, state: str | None) -> None:
        async with self._lock_for(key):
            _, data, _ = self._get_live_record(key)
            self._records[key] = (state, data, self._deadline())

    async def update_data(self, key: FSMKey, values: Mapping[str, object]) -> dict[str, object]:
        async with self._lock_for(key):
            state, data, _ = self._get_live_record(key)
            data.update(values)
            self._records[key] = (state, data, self._deadline())
            return dict(data)

    async def clear(self, key: FSMKey) -> None:
        async with self._lock_for(key):
            self._records.pop(key, None)

    @asynccontextmanager
    async def isolate(self, key: FSMKey) -> AsyncIterator[None]:
        lock = self._isolation_locks.setdefault(key, asyncio.Lock())
        async with lock:
            yield

    def _lock_for(self, key: FSMKey) -> asyncio.Lock:
        lock = self._locks.get(key)
        if lock is None:
            lock = self._locks[key] = asyncio.Lock()
        return lock

    def _get_live_record(self, key: FSMKey) -> tuple[str | None, dict[str, object], float | None]:
        record = self._records.get(key)
        if record is None or (record[2] is not None and time.monotonic() >= record[2]):
            self._records.pop(key, None)
            return None, {}, None
        return record

    def _deadline(self) -> float | None:
        return time.monotonic() + self.ttl if self.ttl is not None else None


class FSMContext:
    """Convenience methods scoped to one conversation key."""

    def __init__(self, storage: FSMStorage, key: FSMKey) -> None:
        self.storage = storage
        self.key = key

    async def get_state(self) -> str | None:
        return (await self.storage.get(self.key)).state

    async def set_state(self, state: str | State | None) -> None:
        value = state.name if isinstance(state, State) else state
        await self.storage.set_state(self.key, value)

    async def get_data(self) -> dict[str, object]:
        return dict((await self.storage.get(self.key)).data)

    async def update_data(self, **values: object) -> dict[str, object]:
        return await self.storage.update_data(self.key, values)

    async def clear(self) -> None:
        await self.storage.clear(self.key)

    def isolate(self) -> AsyncIterator[None]:
        """Serialize a multi-step read/modify/write handler for this key."""
        return self.storage.isolate(self.key)


class State:
    """Named state descriptor usable as a value on a ``StatesGroup``."""

    def __init__(self) -> None:
        self.name = ""

    def __set_name__(self, owner: type[object], name: str) -> None:
        self.name = f"{owner.__name__}:{name}"

    def __str__(self) -> str:
        if not self.name:
            raise RuntimeError("State must be declared on a StatesGroup")
        return self.name


class StatesGroup:
    """Namespace base for related state declarations."""

    __state_group__ = ""

    def __init_subclass__(cls, **kwargs: object) -> None:
        super().__init_subclass__(**kwargs)
        cls.__state_group__ = cls.__name__
