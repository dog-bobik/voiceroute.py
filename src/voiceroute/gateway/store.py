"""Durable Gateway session checkpoints."""

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
