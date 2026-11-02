"""Strict fake transports for unit and contract tests."""

from __future__ import annotations

import copy
from collections import deque
from collections.abc import AsyncIterator, Mapping
from contextlib import asynccontextmanager
from dataclasses import dataclass
from typing import Any

import httpx


@dataclass(frozen=True, slots=True)
class RecordedRequest:
    method: str
    path: str
    params: Mapping[str, str | int | None] | None
    json: object
    content: bytes | None
    headers: Mapping[str, str] | None
    idempotency_key: str | None
    if_match: str | None


@dataclass(frozen=True, slots=True)
class _Route:
    method: str
    path: str
    payload: dict[str, Any] | None
    stream_body: str | None = None


class FakeTransport:
    """FIFO strict transport that records calls and rejects unmatched requests."""

    def __init__(self) -> None:
        self.requests: list[RecordedRequest] = []
        self._routes: deque[_Route] = deque()
        self.closed = False

    def add_response(
        self,
        method: str,
        path: str,
        payload: dict[str, Any] | None = None,
    ) -> None:
        self._routes.append(_Route(method.upper(), path, copy.deepcopy(payload)))

    def add_stream(self, method: str, path: str, body: str) -> None:
        self._routes.append(_Route(method.upper(), path, None, body))

    @property
    def pending(self) -> tuple[tuple[str, str], ...]:
        return tuple((route.method, route.path) for route in self._routes)

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
    ) -> dict[str, Any] | None:
        del retryable, generate_idempotency_key, request_id
        self._ensure_open()
        self.requests.append(
            RecordedRequest(
                method=method.upper(),
                path=path,
                params=copy.deepcopy(params),
                json=copy.deepcopy(json),
                content=content,
                headers=copy.deepcopy(headers),
                idempotency_key=idempotency_key,
                if_match=if_match,
            )
        )
        route = self._pop(method.upper(), path)
        if route.stream_body is not None:
            raise AssertionError(f"expected a streaming request, got {method} {path}")
        return copy.deepcopy(route.payload)

    @asynccontextmanager
    async def stream(
        self,
        path: str,
        *,
        params: Mapping[str, str | int | None] | None = None,
        headers: Mapping[str, str] | None = None,
    ) -> AsyncIterator[httpx.Response]:
        self._ensure_open()
        self.requests.append(
            RecordedRequest(
                method="GET",
                path=path,
                params=copy.deepcopy(params),
                json=None,
                content=None,
                headers=copy.deepcopy(headers),
                idempotency_key=None,
                if_match=None,
            )
        )
        route = self._pop("GET", path)
        if route.stream_body is None:
            raise AssertionError(f"expected a JSON request, got stream GET {path}")
        request = httpx.Request("GET", f"https://voiceroute.test{path}")
        response = httpx.Response(200, text=route.stream_body, request=request)
        yield response

    async def close(self) -> None:
        self.closed = True

    def assert_complete(self) -> None:
        if self._routes:
            raise AssertionError(f"unconsumed fake responses: {self.pending}")

    def _pop(self, method: str, path: str) -> _Route:
        for index, route in enumerate(self._routes):
            if route.method == method and route.path == path:
                del self._routes[index]
                return route
        raise AssertionError(f"unexpected fake request: {method} {path}; pending={self.pending}")

    def _ensure_open(self) -> None:
        if self.closed:
            raise RuntimeError("fake transport is closed")
