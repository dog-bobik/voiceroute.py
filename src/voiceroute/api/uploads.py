"""Resumable, bounded-memory bot file uploads."""

from __future__ import annotations

import asyncio
import hashlib
import inspect
import uuid
from collections.abc import Awaitable, Callable
from dataclasses import dataclass
from pathlib import Path

from voiceroute.transport import HTTPTransport

PART_SIZE = 1_048_576
MAX_UPLOAD_SIZE = 10 * PART_SIZE
_UPLOAD_NAMESPACE = uuid.UUID("c49ba4ec-6c08-41c8-a48a-83a286ff9361")
ProgressCallback = Callable[[int, int], Awaitable[None] | None]


@dataclass(frozen=True, slots=True)
class Upload:
    """Server state for one upload session."""

    id: str
    status: str
    part_size: int
    part_count: int
    received_size: int
    received_parts: tuple[int, ...]

    @classmethod
    def from_dict(cls, data: dict[str, object]) -> Upload:
        parts = data.get("parts", ())
        received = (
            tuple(
                int(part_number)
                for part in parts
                if isinstance(part, dict)
                and isinstance(part_number := part.get("partNumber"), (int, str))
            )
            if isinstance(parts, list)
            else ()
        )
        return cls(
            id=str(data["id"]),
            status=str(data.get("status", "pending")),
            part_size=_integer(data.get("partSize", PART_SIZE)),
            part_count=_integer(data.get("partCount", 0)),
            received_size=_integer(data.get("receivedSize", 0)),
            received_parts=received,
        )


class UploadsAPI:
    """Create, resume, inspect, and cancel bot upload sessions."""

    def __init__(self, transport: HTTPTransport) -> None:
        self._transport = transport

    async def create(
        self,
        community_id: str,
        channel_id: str,
        filename: str,
        size: int,
        checksum_sha256: str,
        *,
        description: str = "",
        spoiler: bool = False,
        idempotency_key: str | uuid.UUID | None = None,
    ) -> Upload:
        if not filename or len(filename) > 120:
            raise ValueError("filename must contain between 1 and 120 characters")
        if not 0 <= size <= MAX_UPLOAD_SIZE:
            raise ValueError("upload size must be between 0 and 10 MiB")
        if len(checksum_sha256) != 64 or any(c not in "0123456789abcdef" for c in checksum_sha256):
            raise ValueError("checksum_sha256 must be a lowercase SHA-256 hex digest")
        if len(description) > 1024:
            raise ValueError("description cannot exceed 1024 characters")
        payload = await self._transport.request(
            "POST",
            "/api/v1/uploads",
            json={
                "communityId": community_id,
                "channelId": channel_id,
                "filename": filename,
                "size": str(size),
                "checksumSha256": checksum_sha256,
                "description": description,
                "spoiler": spoiler,
            },
            idempotency_key=str(idempotency_key or uuid.uuid4()),
        )
        return Upload.from_dict(_required_object(payload, "upload creation"))

    async def get(self, upload_id: str) -> Upload:
        payload = await self._transport.request("GET", f"/api/v1/uploads/{upload_id}")
        return Upload.from_dict(_required_object(payload, "upload lookup"))

    async def put_part(self, upload_id: str, part_number: int, content: bytes) -> None:
        if not 1 <= part_number <= 10:
            raise ValueError("part_number must be between 1 and 10")
        if not 1 <= len(content) <= PART_SIZE:
            raise ValueError("upload part must contain between 1 byte and 1 MiB")
        checksum = hashlib.sha256(content).hexdigest()
        await self._transport.request(
            "PUT",
            f"/api/v1/uploads/{upload_id}/parts/{part_number}",
            content=content,
            headers={
                "Content-Type": "application/octet-stream",
                "Content-Length": str(len(content)),
                "X-Part-SHA256": checksum,
            },
            idempotency_key=str(uuid.uuid5(_UPLOAD_NAMESPACE, f"{upload_id}:{part_number}")),
        )

    async def complete(self, upload_id: str) -> Upload:
        payload = await self._transport.request(
            "POST",
            f"/api/v1/uploads/{upload_id}/complete",
            json={},
            idempotency_key=str(uuid.uuid5(_UPLOAD_NAMESPACE, f"{upload_id}:complete")),
        )
        return Upload.from_dict(_required_object(payload, "upload completion"))

    async def cancel(self, upload_id: str) -> None:
        await self._transport.request(
            "DELETE",
            f"/api/v1/uploads/{upload_id}",
            idempotency_key=str(uuid.uuid5(_UPLOAD_NAMESPACE, f"{upload_id}:cancel")),
            retryable=True,
        )

    async def upload_file(
        self,
        community_id: str,
        channel_id: str,
        path: str | Path,
        *,
        description: str = "",
        spoiler: bool = False,
        progress: ProgressCallback | None = None,
    ) -> Upload:
        """Upload a local file in 1 MiB chunks without buffering it all in memory."""
        file_path = Path(path)
        size = (await asyncio.to_thread(file_path.stat)).st_size
        if size > MAX_UPLOAD_SIZE:
            raise ValueError("upload size cannot exceed 10 MiB")
        digest = hashlib.sha256()
        source = await asyncio.to_thread(file_path.open, "rb")
        try:
            while chunk := await asyncio.to_thread(source.read, PART_SIZE):
                digest.update(chunk)
        finally:
            await asyncio.to_thread(source.close)
        upload = await self.create(
            community_id,
            channel_id,
            file_path.name,
            size,
            digest.hexdigest(),
            description=description,
            spoiler=spoiler,
        )
        received = set(upload.received_parts)
        completed = upload.received_size
        source = await asyncio.to_thread(file_path.open, "rb")
        try:
            for number in range(1, upload.part_count + 1):
                chunk = await asyncio.to_thread(source.read, PART_SIZE)
                if number not in received:
                    await self.put_part(upload.id, number, chunk)
                completed += 0 if number in received else len(chunk)
                if progress is not None:
                    result = progress(completed, size)
                    if inspect.isawaitable(result):
                        await result
        finally:
            await asyncio.to_thread(source.close)
        return await self.complete(upload.id)


def _required_object(payload: dict[str, object] | None, operation: str) -> dict[str, object]:
    if payload is None:
        raise RuntimeError(f"VoiceRoute returned no upload after {operation}")
    raw = payload.get("upload", payload)
    if not isinstance(raw, dict):
        raise RuntimeError(f"VoiceRoute returned an invalid upload after {operation}")
    return raw


def _integer(value: object) -> int:
    return int(value) if isinstance(value, (int, str)) else 0
