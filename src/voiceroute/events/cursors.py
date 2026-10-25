"""Durable checkpoints for resumable VoiceRoute event streams."""

from __future__ import annotations

import asyncio
import importlib
import json
import os
import sqlite3
import tempfile
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any, Protocol

from voiceroute.errors import CursorStoreError


@dataclass(frozen=True, slots=True)
class StreamCheckpoint:
    """Last successfully handled message and change cursor for one stream."""

    change_cursor: str | None = None
    message_seq: str | None = None


class CursorStore(Protocol):
    """Persistence boundary used by the bot runtime after successful handling."""

    async def load(self, stream_key: str) -> StreamCheckpoint | None: ...

    async def save(self, stream_key: str, checkpoint: StreamCheckpoint) -> None: ...


class MemoryCursorStore:
    """Process-local cursor store suitable for tests and disposable bots."""

    def __init__(self) -> None:
        self._checkpoints: dict[str, StreamCheckpoint] = {}
        self._lock = asyncio.Lock()

    async def load(self, stream_key: str) -> StreamCheckpoint | None:
        async with self._lock:
            return self._checkpoints.get(stream_key)

    async def save(self, stream_key: str, checkpoint: StreamCheckpoint) -> None:
        async with self._lock:
            self._checkpoints[stream_key] = checkpoint


class FileCursorStore:
    """Atomic JSON cursor storage for a single bot process."""

    def __init__(self, path: str | Path) -> None:
        self.path = Path(path)
        self._lock = asyncio.Lock()

    async def load(self, stream_key: str) -> StreamCheckpoint | None:
        async with self._lock:
            data = await asyncio.to_thread(self._read_all)
            raw = data.get(stream_key)
            if raw is None:
                return None
            if not isinstance(raw, dict):
                raise CursorStoreError(f"invalid checkpoint for stream {stream_key!r}")
            return StreamCheckpoint(
                change_cursor=_optional_string(raw.get("change_cursor")),
                message_seq=_optional_string(raw.get("message_seq")),
            )

    async def save(self, stream_key: str, checkpoint: StreamCheckpoint) -> None:
        async with self._lock:
            await asyncio.to_thread(self._save_sync, stream_key, checkpoint)

    def _save_sync(self, stream_key: str, checkpoint: StreamCheckpoint) -> None:
        data = self._read_all()
        data[stream_key] = asdict(checkpoint)
        self.path.parent.mkdir(parents=True, exist_ok=True)

        temporary_path: str | None = None
        try:
            with tempfile.NamedTemporaryFile(
                mode="w",
                encoding="utf-8",
                dir=self.path.parent,
                prefix=f".{self.path.name}.",
                delete=False,
            ) as temporary:
                temporary_path = temporary.name
                json.dump(data, temporary, ensure_ascii=False, indent=2, sort_keys=True)
                temporary.write("\n")
                temporary.flush()
                os.fsync(temporary.fileno())
            os.chmod(temporary_path, 0o600)
            os.replace(temporary_path, self.path)
        finally:
            if temporary_path is not None and os.path.exists(temporary_path):
                os.unlink(temporary_path)

    def _read_all(self) -> dict[str, object]:
        if not self.path.exists():
            return {}
        try:
            with self.path.open(encoding="utf-8") as source:
                data = json.load(source)
        except (OSError, json.JSONDecodeError) as exc:
            raise CursorStoreError(f"cannot read cursor store: {self.path}") from exc
        if not isinstance(data, dict):
            raise CursorStoreError(f"cursor store must contain a JSON object: {self.path}")
        return data


class SQLiteCursorStore:
    """Transactional cursor storage shared by processes on one host."""

    def __init__(self, path: str | Path) -> None:
        self.path = Path(path)
        self._initialized = False
        self._lock = asyncio.Lock()

    async def load(self, stream_key: str) -> StreamCheckpoint | None:
        async with self._lock:
            return await asyncio.to_thread(self._load_sync, stream_key)

    async def save(self, stream_key: str, checkpoint: StreamCheckpoint) -> None:
        async with self._lock:
            await asyncio.to_thread(self._save_sync, stream_key, checkpoint)

    def _connect(self) -> sqlite3.Connection:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        connection = sqlite3.connect(self.path, timeout=30)
        if not self._initialized:
            connection.execute("PRAGMA journal_mode=WAL")
            connection.execute(
                """CREATE TABLE IF NOT EXISTS voiceroute_cursors (
                    stream_key TEXT PRIMARY KEY,
                    change_cursor TEXT,
                    message_seq TEXT,
                    updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
                )"""
            )
            connection.commit()
            self._initialized = True
        return connection

    def _load_sync(self, stream_key: str) -> StreamCheckpoint | None:
        connection: sqlite3.Connection | None = None
        try:
            connection = self._connect()
            row = connection.execute(
                """SELECT change_cursor, message_seq
                   FROM voiceroute_cursors WHERE stream_key = ?""",
                (stream_key,),
            ).fetchone()
        except sqlite3.Error as exc:
            raise CursorStoreError(f"cannot read SQLite cursor store: {self.path}") from exc
        finally:
            if connection is not None:
                connection.close()
        if row is None:
            return None
        return StreamCheckpoint(change_cursor=row[0], message_seq=row[1])

    def _save_sync(self, stream_key: str, checkpoint: StreamCheckpoint) -> None:
        connection: sqlite3.Connection | None = None
        try:
            connection = self._connect()
            connection.execute(
                """INSERT INTO voiceroute_cursors
                   (stream_key, change_cursor, message_seq, updated_at)
                   VALUES (?, ?, ?, CURRENT_TIMESTAMP)
                   ON CONFLICT(stream_key) DO UPDATE SET
                       change_cursor = excluded.change_cursor,
                       message_seq = excluded.message_seq,
                       updated_at = CURRENT_TIMESTAMP""",
                (stream_key, checkpoint.change_cursor, checkpoint.message_seq),
            )
            connection.commit()
        except sqlite3.Error as exc:
            raise CursorStoreError(f"cannot write SQLite cursor store: {self.path}") from exc
        finally:
            if connection is not None:
                connection.close()


class RedisCursorStore:
    """Distributed cursor storage backed by an async Redis-compatible client."""

    def __init__(self, client: Any, *, key_prefix: str = "voiceroute:cursors:") -> None:
        if not key_prefix:
            raise ValueError("key_prefix cannot be empty")
        self._client = client
        self._key_prefix = key_prefix

    @classmethod
    def from_url(cls, url: str, *, key_prefix: str = "voiceroute:cursors:") -> RedisCursorStore:
        try:
            redis_module = importlib.import_module("redis.asyncio")
        except ImportError as exc:
            raise RuntimeError(
                "Redis support requires the 'redis' extra: pip install 'voiceroute.py[redis]'"
            ) from exc
        return cls(
            redis_module.Redis.from_url(url, decode_responses=True),
            key_prefix=key_prefix,
        )

    async def load(self, stream_key: str) -> StreamCheckpoint | None:
        try:
            raw = await self._client.get(self._key(stream_key))
            if raw is None:
                return None
            if isinstance(raw, bytes):
                raw = raw.decode("utf-8")
            data = json.loads(raw)
            if not isinstance(data, dict):
                raise ValueError("checkpoint is not an object")
            return StreamCheckpoint(
                change_cursor=_optional_string(data.get("change_cursor")),
                message_seq=_optional_string(data.get("message_seq")),
            )
        except Exception as exc:
            if isinstance(exc, CursorStoreError):
                raise
            raise CursorStoreError(f"cannot read Redis cursor for stream {stream_key!r}") from exc

    async def save(self, stream_key: str, checkpoint: StreamCheckpoint) -> None:
        try:
            await self._client.set(
                self._key(stream_key),
                json.dumps(asdict(checkpoint), separators=(",", ":"), sort_keys=True),
            )
        except Exception as exc:
            raise CursorStoreError(f"cannot write Redis cursor for stream {stream_key!r}") from exc

    async def close(self) -> None:
        close = getattr(self._client, "aclose", None)
        if close is not None:
            await close()

    def _key(self, stream_key: str) -> str:
        return f"{self._key_prefix}{stream_key}"


def _optional_string(value: object) -> str | None:
    return None if value is None else str(value)
