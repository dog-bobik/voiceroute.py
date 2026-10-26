"""Durable Gateway session checkpoints."""

from __future__ import annotations

import asyncio
import json
import os
import tempfile
import time
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any, Protocol

from voiceroute.errors import CursorStoreError


@dataclass(frozen=True, slots=True)
class GatewayCheckpoint:
    session_id: str
    sequence: str
    shard_id: int
    shard_count: int
    credential_fingerprint: str
    resume_gateway_url: str | None = None


class GatewayCheckpointStore(Protocol):
    async def load(self, shard_id: int, shard_count: int) -> GatewayCheckpoint | None: ...

    async def save(self, checkpoint: GatewayCheckpoint) -> None: ...

    async def clear(self, shard_id: int, shard_count: int) -> None: ...


class GatewayCheckpointCoordinator(Protocol):
    """Lease ownership for one shard checkpoint across multiple processes."""

    async def acquire(self, shard_id: int, shard_count: int, owner: str, *, ttl: float) -> bool: ...

    async def renew(self, shard_id: int, shard_count: int, owner: str, *, ttl: float) -> bool: ...

    async def release(self, shard_id: int, shard_count: int, owner: str) -> None: ...


class MemoryGatewayCheckpointCoordinator:
    """Process-local implementation useful for tests and task-level coordination."""

    def __init__(self) -> None:
        self._leases: dict[tuple[int, int], tuple[str, float]] = {}
        self._lock = asyncio.Lock()

    async def acquire(self, shard_id: int, shard_count: int, owner: str, *, ttl: float) -> bool:
        if ttl <= 0:
            raise ValueError("lease ttl must be positive")
        async with self._lock:
            key = (shard_id, shard_count)
            current = self._leases.get(key)
            now = time.monotonic()
            if current is not None and current[0] != owner and current[1] > now:
                return False
            self._leases[key] = (owner, now + ttl)
            return True

    async def release(self, shard_id: int, shard_count: int, owner: str) -> None:
        async with self._lock:
            key = (shard_id, shard_count)
            if self._leases.get(key, (None, 0))[0] == owner:
                self._leases.pop(key, None)

    async def renew(self, shard_id: int, shard_count: int, owner: str, *, ttl: float) -> bool:
        async with self._lock:
            key = (shard_id, shard_count)
            if self._leases.get(key, (None, 0))[0] != owner:
                return False
            self._leases[key] = (owner, time.monotonic() + ttl)
            return True


class MemoryGatewayCheckpointStore:
    def __init__(self) -> None:
        self._values: dict[tuple[int, int], GatewayCheckpoint] = {}
        self._lock = asyncio.Lock()

    async def load(self, shard_id: int, shard_count: int) -> GatewayCheckpoint | None:
        async with self._lock:
            return self._values.get((shard_id, shard_count))

    async def save(self, checkpoint: GatewayCheckpoint) -> None:
        async with self._lock:
            self._values[(checkpoint.shard_id, checkpoint.shard_count)] = checkpoint

    async def clear(self, shard_id: int, shard_count: int) -> None:
        async with self._lock:
            self._values.pop((shard_id, shard_count), None)


class FileGatewayCheckpointStore:
    """A small atomic JSON store suitable for one bot process."""

    def __init__(self, path: str | Path) -> None:
        self.path = Path(path)
        self._lock = asyncio.Lock()

    async def load(self, shard_id: int, shard_count: int) -> GatewayCheckpoint | None:
        async with self._lock:
            return await asyncio.to_thread(self._load, shard_id, shard_count)

    async def save(self, checkpoint: GatewayCheckpoint) -> None:
        async with self._lock:
            await asyncio.to_thread(self._save, checkpoint)

    async def clear(self, shard_id: int, shard_count: int) -> None:
        async with self._lock:
            await asyncio.to_thread(self._clear, shard_id, shard_count)

    def _load(self, shard_id: int, shard_count: int) -> GatewayCheckpoint | None:
        try:
            if not self.path.exists():
                return None
            document = json.loads(self.path.read_text(encoding="utf-8"))
            value = document.get(f"{shard_id}:{shard_count}")
            return GatewayCheckpoint(**value) if isinstance(value, dict) else None
        except (OSError, TypeError, ValueError) as exc:
            raise CursorStoreError("failed to load Gateway checkpoint") from exc

    def _save(self, checkpoint: GatewayCheckpoint) -> None:
        document = self._document()
        document[f"{checkpoint.shard_id}:{checkpoint.shard_count}"] = asdict(checkpoint)
        self._write(document)

    def _clear(self, shard_id: int, shard_count: int) -> None:
        document = self._document()
        document.pop(f"{shard_id}:{shard_count}", None)
        self._write(document)

    def _document(self) -> dict[str, object]:
        if not self.path.exists():
            return {}
        try:
            value = json.loads(self.path.read_text(encoding="utf-8"))
            if not isinstance(value, dict):
                raise ValueError
            return value
        except (OSError, ValueError) as exc:
            raise CursorStoreError("failed to read Gateway checkpoint file") from exc

    def _write(self, document: dict[str, object]) -> None:
        try:
            self.path.parent.mkdir(parents=True, exist_ok=True)
            descriptor, temporary = tempfile.mkstemp(dir=self.path.parent, prefix=".gateway-")
            try:
                with os.fdopen(descriptor, "w", encoding="utf-8") as file:
                    json.dump(document, file, separators=(",", ":"), sort_keys=True)
                os.chmod(temporary, 0o600)
                os.replace(temporary, self.path)
            except BaseException:
                Path(temporary).unlink(missing_ok=True)
                raise
        except OSError as exc:
            raise CursorStoreError("failed to save Gateway checkpoint") from exc


class RedisGatewayCheckpointStore:
    """Cross-process checkpoint store for an async Redis-compatible client."""

    def __init__(self, redis: Any, *, prefix: str = "voiceroute:gateway") -> None:
        self._redis = redis
        self._prefix = prefix.rstrip(":")

    def _key(self, shard_id: int, shard_count: int) -> str:
        return f"{self._prefix}:{shard_id}:{shard_count}"

    async def load(self, shard_id: int, shard_count: int) -> GatewayCheckpoint | None:
        try:
            raw = await self._redis.get(self._key(shard_id, shard_count))
            if raw is None:
                return None
            if isinstance(raw, bytes):
                raw = raw.decode("utf-8")
            value = json.loads(raw)
            return GatewayCheckpoint(**value)
        except (OSError, TypeError, ValueError) as exc:
            raise CursorStoreError("failed to load Redis Gateway checkpoint") from exc

    async def save(self, checkpoint: GatewayCheckpoint) -> None:
        try:
            await self._redis.set(
                self._key(checkpoint.shard_id, checkpoint.shard_count),
                json.dumps(asdict(checkpoint), separators=(",", ":"), sort_keys=True),
            )
        except OSError as exc:
            raise CursorStoreError("failed to save Redis Gateway checkpoint") from exc

    async def clear(self, shard_id: int, shard_count: int) -> None:
        try:
            await self._redis.delete(self._key(shard_id, shard_count))
        except OSError as exc:
            raise CursorStoreError("failed to clear Redis Gateway checkpoint") from exc


class RedisGatewayCheckpointCoordinator:
    """Distributed shard lease implemented with Redis SET NX and compare-delete."""

    _RELEASE = """
    if redis.call('get', KEYS[1]) == ARGV[1] then
      return redis.call('del', KEYS[1])
    end
    return 0
    """
    _RENEW = """
    if redis.call('get', KEYS[1]) == ARGV[1] then
      return redis.call('pexpire', KEYS[1], ARGV[2])
    end
    return 0
    """

    def __init__(self, redis: Any, *, prefix: str = "voiceroute:gateway:lease") -> None:
        self._redis = redis
        self._prefix = prefix.rstrip(":")

    def _key(self, shard_id: int, shard_count: int) -> str:
        return f"{self._prefix}:{shard_id}:{shard_count}"

    async def acquire(self, shard_id: int, shard_count: int, owner: str, *, ttl: float) -> bool:
        if ttl <= 0:
            raise ValueError("lease ttl must be positive")
        result = await self._redis.set(
            self._key(shard_id, shard_count), owner, nx=True, px=max(1, int(ttl * 1000))
        )
        return bool(result)

    async def release(self, shard_id: int, shard_count: int, owner: str) -> None:
        await self._redis.eval(self._RELEASE, 1, self._key(shard_id, shard_count), owner)

    async def renew(self, shard_id: int, shard_count: int, owner: str, *, ttl: float) -> bool:
        result = await self._redis.eval(
            self._RENEW,
            1,
            self._key(shard_id, shard_count),
            owner,
            max(1, int(ttl * 1000)),
        )
        return bool(result)


class PostgreSQLGatewayCheckpointStore:
    """Cross-process checkpoint store for an asyncpg-compatible pool or connection."""

    def __init__(self, database: Any, *, table: str = "voiceroute_gateway_checkpoints") -> None:
        if not table.replace("_", "").isalnum():
            raise ValueError("table must be a simple SQL identifier")
        self._database = database
        self._table = table

    async def initialize(self) -> None:
        await self._database.execute(
            f"""CREATE TABLE IF NOT EXISTS {self._table} (
                shard_id integer NOT NULL,
                shard_count integer NOT NULL,
                checkpoint jsonb NOT NULL,
                PRIMARY KEY (shard_id, shard_count)
            )"""
        )

    async def load(self, shard_id: int, shard_count: int) -> GatewayCheckpoint | None:
        try:
            row = await self._database.fetchrow(
                f"SELECT checkpoint FROM {self._table} WHERE shard_id = $1 AND shard_count = $2",
                shard_id,
                shard_count,
            )
            if row is None:
                return None
            value = row["checkpoint"]
            if isinstance(value, str):
                value = json.loads(value)
            return GatewayCheckpoint(**dict(value))
        except (OSError, TypeError, ValueError) as exc:
            raise CursorStoreError("failed to load PostgreSQL Gateway checkpoint") from exc

    async def save(self, checkpoint: GatewayCheckpoint) -> None:
        try:
            await self._database.execute(
                f"""INSERT INTO {self._table} (shard_id, shard_count, checkpoint)
                VALUES ($1, $2, $3::jsonb)
                ON CONFLICT (shard_id, shard_count)
                DO UPDATE SET checkpoint = EXCLUDED.checkpoint""",
                checkpoint.shard_id,
                checkpoint.shard_count,
                json.dumps(asdict(checkpoint), separators=(",", ":"), sort_keys=True),
            )
        except OSError as exc:
            raise CursorStoreError("failed to save PostgreSQL Gateway checkpoint") from exc

    async def clear(self, shard_id: int, shard_count: int) -> None:
        try:
            await self._database.execute(
                f"DELETE FROM {self._table} WHERE shard_id = $1 AND shard_count = $2",
                shard_id,
                shard_count,
            )
        except OSError as exc:
            raise CursorStoreError("failed to clear PostgreSQL Gateway checkpoint") from exc
