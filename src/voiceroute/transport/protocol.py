"""Structural transport contract used by resources and injected clients."""

from __future__ import annotations

from collections.abc import Mapping
from contextlib import AbstractAsyncContextManager
from typing import Any, Protocol

import httpx


class Transport(Protocol):
    """Minimal HTTP surface required by VoiceRoute API resources."""

    async def request(
        self,
        method: str,
        path: str,
        *,
        params: Mapping[str, str | int | None] | None = None,
        json: Any = None,
        content: bytes | None = None,
        retryable: bool | None = None,
        idempotency_key: str | None = None,
        if_match: str | None = None,
        headers: Mapping[str, str] | None = None,
        generate_idempotency_key: bool = False,
        request_id: str | None = None,
    ) -> dict[str, Any] | None: ...

    def stream(
        self,
        path: str,
        *,
        params: Mapping[str, str | int | None] | None = None,
        headers: Mapping[str, str] | None = None,
    ) -> AbstractAsyncContextManager[httpx.Response]: ...

    async def close(self) -> None: ...
