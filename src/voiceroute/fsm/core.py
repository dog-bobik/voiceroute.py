"""Storage protocol and isolated FSM context primitives."""

from __future__ import annotations

import asyncio
import base64
import json
import time
from collections.abc import AsyncIterator, Mapping
from contextlib import AbstractAsyncContextManager, asynccontextmanager
from dataclasses import dataclass
from typing import Any, Protocol


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

    def isolate(self, key: FSMKey) -> AbstractAsyncContextManager[None]: ...


class RedisStorage:
    """Redis-backed storage with atomic state updates and distributed isolation.

    Construct it with a ``redis.asyncio.Redis`` client from the optional ``redis``
    extra. The caller retains ownership of that connection pool.
    """

    def __init__(
        self,
        redis: object,
        *,
        prefix: str = "voiceroute:fsm",
        ttl: float | None = 86_400.0,
        lock_timeout: float = 30.0,
    ) -> None:
        if not prefix:
            raise ValueError("Redis key prefix cannot be empty")
        if ttl is not None and ttl <= 0:
            raise ValueError("ttl must be positive or None")
        if lock_timeout <= 0:
            raise ValueError("lock_timeout must be positive")
        if not hasattr(redis, "get") or not hasattr(redis, "eval") or not hasattr(redis, "lock"):
            raise TypeError("redis must provide async get, eval, and lock methods")
        self._redis: Any = redis
        self._prefix = prefix.rstrip(":")
        self._ttl = ttl
        self._lock_timeout = lock_timeout

    async def get(self, key: FSMKey) -> FSMRecord:
        raw = await self._redis.get(self._key(key))
        if raw is None:
            return FSMRecord(None, {})
        if isinstance(raw, bytes):
            raw = raw.decode("utf-8")
        value = json.loads(raw)
        state = value.get("state")
        data = value.get("data", {})
        return FSMRecord(str(state) if state is not None else None, data)

    async def set_state(self, key: FSMKey, state: str | None) -> None:
        await self._redis.eval(
            _REDIS_SET_STATE,
            1,
            self._key(key),
            json.dumps(state),
            _ttl_ms(self._ttl),
        )

    async def update_data(self, key: FSMKey, values: Mapping[str, object]) -> dict[str, object]:
        raw = await self._redis.eval(
            _REDIS_UPDATE_DATA,
            1,
            self._key(key),
            json.dumps(dict(values)),
            _ttl_ms(self._ttl),
        )
        if isinstance(raw, bytes):
            raw = raw.decode("utf-8")
        result = json.loads(raw)
        return dict(result)

    async def clear(self, key: FSMKey) -> None:
        await self._redis.delete(self._key(key))

    @asynccontextmanager
    async def isolate(self, key: FSMKey) -> AsyncIterator[None]:
        lock = self._redis.lock(
            self._key(key) + ":isolation",
            timeout=self._lock_timeout,
            blocking_timeout=self._lock_timeout,
        )
        async with lock:
            yield

    def _key(self, key: FSMKey) -> str:
        raw = json.dumps(
            [key.origin, key.application_id, key.community_id, key.channel_id, key.user_id],
            ensure_ascii=False,
            separators=(",", ":"),
        ).encode("utf-8")
        return f"{self._prefix}:{base64.urlsafe_b64encode(raw).decode().rstrip('=')}"


_REDIS_SET_STATE = """
local raw = redis.call('GET', KEYS[1])
local record = {state = cjson.null, data = {}}
if raw then record = cjson.decode(raw) end
record.state = cjson.decode(ARGV[1])
local encoded = cjson.encode(record)
if tonumber(ARGV[2]) > 0 then
  redis.call('SET', KEYS[1], encoded, 'PX', ARGV[2])
else
  redis.call('SET', KEYS[1], encoded)
end
return 1
"""

_REDIS_UPDATE_DATA = """
local raw = redis.call('GET', KEYS[1])
local record = {state = cjson.null, data = {}}
if raw then record = cjson.decode(raw) end
local values = cjson.decode(ARGV[1])
for key, value in pairs(values) do record.data[key] = value end
local encoded = cjson.encode(record)
if tonumber(ARGV[2]) > 0 then
  redis.call('SET', KEYS[1], encoded, 'PX', ARGV[2])
else
  redis.call('SET', KEYS[1], encoded)
end
return cjson.encode(record.data)
"""


def _ttl_ms(ttl: float | None) -> int:
    return 0 if ttl is None else max(1, int(ttl * 1000))


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

    def isolate(self) -> AbstractAsyncContextManager[None]:
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
