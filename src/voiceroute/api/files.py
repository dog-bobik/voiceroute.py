"""Scanned bot-visible file metadata and bounded-memory downloads."""

from __future__ import annotations

from collections.abc import AsyncIterator, Mapping
from dataclasses import dataclass

from voiceroute.transport import Transport


@dataclass(frozen=True, slots=True)
class FileResource:
    """Metadata for a file currently visible to the bot."""

    id: str
    filename: str
    description: str
    spoiler: bool
    content_type: str
    size: str
    checksum_sha256: str
    url: str
    width: int | None
    height: int | None
    author_user_id: str
    application_id: str | None
    expires_at: str | None

    @classmethod
    def from_dict(cls, data: Mapping[str, object]) -> FileResource:
        return cls(
            id=str(data["id"]),
            filename=str(data["filename"]),
            description=str(data.get("description", "")),
            spoiler=bool(data.get("spoiler", False)),
            content_type=str(data["contentType"]),
            size=str(data["size"]),
            checksum_sha256=str(data["checksumSha256"]),
            url=str(data["url"]),
            width=_optional_int(data.get("width")),
            height=_optional_int(data.get("height")),
            author_user_id=str(data["authorUserId"]),
            application_id=(
                str(data["applicationId"]) if data.get("applicationId") is not None else None
            ),
            expires_at=str(data["expiresAt"]) if data.get("expiresAt") is not None else None,
        )


class FilesAPI:
    """Fetch bot-visible file metadata and stream clean file contents."""

    def __init__(self, transport: Transport) -> None:
        self._transport = transport

    async def get(self, file_id: str) -> FileResource:
        payload = await self._transport.request("GET", f"/api/v1/files/{file_id}")
        if payload is None:
            raise RuntimeError("VoiceRoute returned no file metadata")
        return FileResource.from_dict(payload)

    async def download(
        self, file_id: str, *, byte_range: str | None = None, download: bool = False
    ) -> AsyncIterator[bytes]:
        """Yield response chunks; an optional range uses standard HTTP byte syntax."""
        headers = {"Range": byte_range} if byte_range is not None else None
        params = {"download": "1"} if download else None
        async with self._transport.stream(
            f"/api/v1/files/{file_id}/content", params=params, headers=headers
        ) as response:
            response.raise_for_status()
            async for chunk in response.aiter_bytes():
                yield chunk


def _optional_int(value: object) -> int | None:
    return int(value) if isinstance(value, int) else None
