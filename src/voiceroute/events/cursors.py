"""Durable checkpoints for resumable VoiceRoute event streams."""

from __future__ import annotations

import asyncio
import json
import os
import tempfile
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Protocol

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


def _optional_string(value: object) -> str | None:
    return None if value is None else str(value)
