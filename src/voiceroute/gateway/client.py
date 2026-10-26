"""VoiceRoute Bot Platform v1 WebSocket Gateway transport."""

from __future__ import annotations

import asyncio
import hashlib
import json
import logging
import platform
import random
import ssl
import uuid
from collections.abc import AsyncIterator, Awaitable, Callable, Sequence
from contextlib import suppress
from typing import Any, Protocol
from urllib.parse import parse_qs, urlparse

import certifi
from websockets.asyncio.client import connect
from websockets.exceptions import ConnectionClosed

from voiceroute.api import PlatformAPI
from voiceroute.errors import (
    GatewayClosed,
    GatewayError,
    GatewayProtocolError,
    IntentNotEnabled,
    PrivilegedIntentRequired,
)
from voiceroute.gateway.intents import Intents
from voiceroute.gateway.presence import Activity, Presence, Status
from voiceroute.gateway.store import (
    GatewayCheckpoint,
    GatewayCheckpointCoordinator,
    GatewayCheckpointStore,
    MemoryGatewayCheckpointStore,
)
from voiceroute.models import PlatformEvent

logger = logging.getLogger(__name__)

_TERMINAL_CLOSE_CODES = {1009, 4001, 4002, 4003, 4004, 4010, 4011, 4013, 4014, 4015}
_CLEAR_SESSION_CLOSE_CODES = {4007}
_MINIMUM_RECONNECT_DELAYS = {1012: 1.0, 4000: 1.0, 4005: 1.0, 4007: 5.0, 4008: 60.0, 4009: 1.0}


class _GatewayReconnect(GatewayError):
    def __init__(self, minimum_delay: float) -> None:
        self.minimum_delay = minimum_delay
        super().__init__("Gateway requested a reconnect")


class GatewaySocket(Protocol):
    def __aiter__(self) -> AsyncIterator[str | bytes]: ...

    async def send(self, message: str) -> None: ...

    async def close(self, code: int = 1000, reason: str = "") -> None: ...


GatewayConnector = Callable[[str], Awaitable[GatewaySocket]]
GatewayHandler = Callable[[PlatformEvent], Awaitable[None]]
GatewayMetricHook = Callable[[str, dict[str, int | float | str]], None]


async def _default_connector(url: str) -> GatewaySocket:
    ssl_context = ssl.create_default_context(cafile=certifi.where())
    return await connect(url, max_size=1_048_576, compression=None, ssl=ssl_context)


class GatewayClient:
    """Connect, identify/resume, heartbeat, and commit dispatch checkpoints."""

    def __init__(
        self,
        *,
        token: str,
        platform_api: PlatformAPI,
        base_url: str,
        intents: Intents | Sequence[str] = (),
        shard: tuple[int, int] = (0, 1),
        store: GatewayCheckpointStore | None = None,
        connector: GatewayConnector = _default_connector,
        library_version: str = "0.1.0.dev1",
        dispatch_queue_size: int = 1_000,
        metric_hook: GatewayMetricHook | None = None,
        max_reconnect_delay: float = 60.0,
        coordinator: GatewayCheckpointCoordinator | None = None,
        checkpoint_lease_ttl: float = 120.0,
        drain_timeout: float = 30.0,
    ) -> None:
        shard_id, shard_count = shard
        if shard_count not in {1, 2, 4, 8, 16} or not 0 <= shard_id < shard_count:
            raise ValueError("invalid Gateway shard")
        intent_values = intents.values if isinstance(intents, Intents) else tuple(intents)
        if len(set(intent_values)) != len(intent_values):
            raise ValueError("Gateway intents must be unique")
        if dispatch_queue_size <= 0:
            raise ValueError("dispatch_queue_size must be positive")
        if max_reconnect_delay <= 0:
            raise ValueError("max_reconnect_delay must be positive")
        if checkpoint_lease_ttl <= 0:
            raise ValueError("checkpoint_lease_ttl must be positive")
        if drain_timeout <= 0:
            raise ValueError("drain_timeout must be positive")
        self._token = token
        self._platform = platform_api
        self._base_url = base_url
        self.intents = tuple(intent_values)
        self.shard = shard
        self._store = store or MemoryGatewayCheckpointStore()
        self._connector = connector
        self._library_version = library_version
        self._dispatch_queue_size = dispatch_queue_size
        self._metric_hook = metric_hook
        self._max_reconnect_delay = max_reconnect_delay
        self._coordinator = coordinator
        self._checkpoint_lease_ttl = checkpoint_lease_ttl
        self._checkpoint_owner = str(uuid.uuid4())
        self._drain_timeout = drain_timeout
        self._fingerprint = hashlib.sha256(token.encode()).hexdigest()[:16]
        self._socket: GatewaySocket | None = None
        self._stopping = False
        self._last_sequence = "0"
        self._heartbeat_acknowledged = True
        self._identified = asyncio.Event()
        self._ready = asyncio.Event()
        self.on_session_invalidated: Callable[[], Awaitable[None]] | None = None

    async def run_once(self, handler: GatewayHandler) -> None:
        """Run one connection until it closes, committing only handled events."""
        discovery = await self._platform.gateway()
        await self._validate_intents()
        if discovery.recommended_shards > self.shard[1]:
            raise GatewayError("VoiceRoute requires more Gateway shards")
        checkpoint = await self._valid_checkpoint()
        self._last_sequence = checkpoint.sequence if checkpoint is not None else "0"
        url = (
            checkpoint.resume_gateway_url
            if checkpoint and checkpoint.resume_gateway_url
            else discovery.url
        )
        self._validate_gateway_url(url)
        owns_checkpoint = False
        if self._coordinator is not None:
            owns_checkpoint = await self._coordinator.acquire(
                *self.shard, self._checkpoint_owner, ttl=self._checkpoint_lease_ttl
            )
            if not owns_checkpoint:
                raise GatewayError(f"Gateway shard {self.shard[0]} is owned by another process")
        try:
            socket = await self._connector(url)
        except BaseException:
            if owns_checkpoint and self._coordinator is not None:
                await self._coordinator.release(*self.shard, self._checkpoint_owner)
            raise
        self._socket = socket
        self._heartbeat_acknowledged = True
        heartbeat: asyncio.Task[None] | None = None
        dispatch_worker: asyncio.Task[None] | None = None
        queue: asyncio.Queue[PlatformEvent | None] = asyncio.Queue(
            maxsize=self._dispatch_queue_size
        )
        handler_error: asyncio.Future[BaseException] = asyncio.get_running_loop().create_future()

        async def dispatch_events() -> None:
            nonlocal checkpoint
            while True:
                event = await queue.get()
                try:
                    if event is None:
                        return
                    if handler_error.done():
                        continue
                    try:
                        await handler(event)
                        if checkpoint is None:
                            raise GatewayProtocolError("dispatch received before READY")
                        checkpoint = GatewayCheckpoint(
                            session_id=checkpoint.session_id,
                            sequence=event.sequence,
                            shard_id=checkpoint.shard_id,
                            shard_count=checkpoint.shard_count,
                            credential_fingerprint=checkpoint.credential_fingerprint,
                            resume_gateway_url=checkpoint.resume_gateway_url,
                        )
                        await self._store.save(checkpoint)
                    except Exception as exc:
                        handler_error.set_result(exc)
                        await socket.close(4000, "Dispatch handler failed")
                        continue
                    self._metric("dispatch_handled", sequence=event.sequence)
                finally:
                    queue.task_done()

        try:
            iterator = aiter(socket)
            hello = self._decode(await anext(iterator))
            if hello.get("op") != 10:
                raise GatewayProtocolError("first Gateway frame must be HELLO")
            hello_data = hello.get("data")
            if not isinstance(hello_data, dict):
                raise GatewayProtocolError("HELLO data must be an object")
            interval_ms = hello_data.get("heartbeatIntervalMs")
            if not isinstance(interval_ms, int) or not 100 <= interval_ms <= 120_000:
                raise GatewayProtocolError("invalid heartbeat interval")
            if checkpoint is None and discovery.session_start_limit.remaining <= 0:
                delay = max(0.0, discovery.session_start_limit.reset_after_ms / 1000)
                self._metric("identify_wait", delay=delay)
                await asyncio.sleep(delay)
            await self._send(self._resume(checkpoint) if checkpoint else self._identify())
            self._identified.set()
            heartbeat = asyncio.create_task(self._heartbeat_loop(interval_ms / 1000))
            dispatch_worker = asyncio.create_task(
                dispatch_events(), name=f"voiceroute:gateway-dispatch:{self.shard[0]}"
            )

            async for message in iterator:
                frame = self._decode(message)
                opcode = frame.get("op")
                if opcode == 11:
                    self._heartbeat_acknowledged = True
                    self._metric("heartbeat_ack")
                    continue
                if opcode == 7:
                    reconnect_data = frame.get("data")
                    retry_after_ms = (
                        reconnect_data.get("retryAfterMs")
                        if isinstance(reconnect_data, dict)
                        else None
                    )
                    await socket.close(4000, "Reconnect requested")
                    server_delay = (
                        retry_after_ms / 1000
                        if isinstance(retry_after_ms, int) and retry_after_ms > 0
                        else 1.0
                    )
                    raise _GatewayReconnect(server_delay)
                if opcode != 0:
                    continue
                event = PlatformEvent.from_gateway_frame(frame)
                self._last_sequence = event.sequence
                if event.name in {"READY", "RESUMED"}:
                    checkpoint = self._checkpoint_from_ready(event, checkpoint)
                    await self._store.save(checkpoint)
                    self._ready.set()
                    continue
                if checkpoint is None:
                    raise GatewayProtocolError("dispatch received before READY")
                await queue.put(event)
                self._metric("dispatch_queued", depth=queue.qsize())
            await queue.join()
            if handler_error.done():
                raise handler_error.result()
        except ConnectionClosed as exc:
            if handler_error.done():
                raise handler_error.result() from exc
            self._metric("connection_closed", code=exc.code)
            if exc.code in _CLEAR_SESSION_CLOSE_CODES:
                await self._store.clear(*self.shard)
                if self.on_session_invalidated is not None:
                    await self.on_session_invalidated()
            if exc.code in _TERMINAL_CLOSE_CODES:
                if exc.code in {4014, 4015}:
                    self._platform.invalidate_capabilities()
                    await self._platform.capabilities(force=True)
                raise GatewayClosed(exc.code, exc.reason) from exc
            raise _GatewayReconnect(_MINIMUM_RECONNECT_DELAYS.get(exc.code, 1.0)) from exc
        finally:
            if heartbeat is not None:
                heartbeat.cancel()
                with suppress(asyncio.CancelledError):
                    await heartbeat
            if dispatch_worker is not None:
                try:
                    await asyncio.wait_for(queue.join(), timeout=self._drain_timeout)
                except TimeoutError:
                    self._metric("dispatch_drain_timeout", depth=queue.qsize())
                    dispatch_worker.cancel()
                    with suppress(asyncio.CancelledError):
                        await dispatch_worker
                else:
                    await queue.put(None)
                    await dispatch_worker
            self._socket = None
            if owns_checkpoint and self._coordinator is not None:
                await self._coordinator.release(*self.shard, self._checkpoint_owner)

    async def run(self, handler: GatewayHandler) -> None:
        """Reconnect with bounded exponential backoff until explicitly stopped."""
        self._stopping = False
        attempt = 0
        while not self._stopping:
            minimum_delay = 0.0
            try:
                await self.run_once(handler)
                attempt = 0
            except GatewayClosed:
                raise
            except _GatewayReconnect as exc:
                attempt += 1
                minimum_delay = exc.minimum_delay
            except (GatewayError, OSError, ConnectionClosed) as exc:
                attempt += 1
                logger.warning(
                    "Gateway connection failed (%s: %s); reconnecting",
                    type(exc).__name__,
                    exc,
                    extra={
                        "error_type": type(exc).__name__,
                        "close_code": getattr(exc, "code", None),
                        "shard_id": self.shard[0],
                    },
                )
            if not self._stopping:
                maximum = min(self._max_reconnect_delay, 2 ** min(attempt, 10))
                delay = max(minimum_delay, random.uniform(0.0, maximum))
                self._metric("reconnect_wait", attempt=attempt, delay=delay)
                await asyncio.sleep(delay)

    async def close(self) -> None:
        self._stopping = True
        if self._socket is not None:
            await self._socket.close(1000, "Client stopped")

    async def wait_until_identified(self) -> None:
        await self._identified.wait()

    async def wait_until_ready(self) -> None:
        await self._ready.wait()

    async def change_presence(
        self,
        *,
        status: Status,
        activities: Sequence[Activity] = (),
        since: str | None = None,
    ) -> None:
        presence = Presence(status=status, activities=tuple(activities), since=since)
        await self._send({"op": 3, "data": presence.to_dict()})

    async def request_members(
        self,
        community_id: str,
        *,
        nonce: str,
        cursor: str | None = None,
        limit: int = 100,
    ) -> None:
        if not 1 <= len(nonce) <= 64 or not nonce.replace("_", "").replace("-", "").isalnum():
            raise ValueError("nonce must contain 1 to 64 URL-safe characters")
        if not 1 <= limit <= 100:
            raise ValueError("member request limit must be between 1 and 100")
        data: dict[str, Any] = {"communityId": community_id, "nonce": nonce, "limit": limit}
        if cursor is not None:
            data["cursor"] = cursor
        await self._send({"op": 8, "data": data})

    async def update_subscriptions(self, subscription_ids: Sequence[str]) -> None:
        values = tuple(subscription_ids)
        if len(values) > 10 or len(values) != len(set(values)):
            raise ValueError("subscriptions must be unique and contain at most ten IDs")
        await self._send({"op": 12, "data": {"subscriptionIds": list(values)}})

    async def _validate_intents(self) -> None:
        if not self.intents:
            return
        capabilities = await self._platform.capabilities()
        unknown = tuple(intent for intent in self.intents if intent not in capabilities.intents)
        if unknown:
            names = ", ".join(unknown)
            raise GatewayError(f"VoiceRoute does not advertise Gateway intents: {names}")
        privileged = tuple(
            intent for intent in self.intents if capabilities.intents[intent].privileged
        )
        application = await self._platform.current_application()
        disabled = tuple(
            intent for intent in self.intents if intent not in application.requested_intents
        )
        if disabled:
            raise IntentNotEnabled(disabled)
        if not privileged:
            return
        missing = tuple(
            intent for intent in privileged if intent not in application.approved_intents
        )
        if missing:
            raise PrivilegedIntentRequired(missing)

    async def _valid_checkpoint(self) -> GatewayCheckpoint | None:
        checkpoint = await self._store.load(*self.shard)
        if checkpoint is None:
            return None
        if checkpoint.credential_fingerprint != self._fingerprint:
            await self._store.clear(*self.shard)
            return None
        return checkpoint

    def _identify(self) -> dict[str, Any]:
        return {
            "op": 2,
            "data": {
                "token": self._token,
                "intents": list(self.intents),
                "shard": list(self.shard),
                "properties": {
                    "os": platform.system().lower(),
                    "library": "voiceroute.py",
                    "libraryVersion": self._library_version,
                },
            },
        }

    def _resume(self, checkpoint: GatewayCheckpoint) -> dict[str, Any]:
        return {
            "op": 6,
            "data": {
                "token": self._token,
                "sessionId": checkpoint.session_id,
                "sequence": checkpoint.sequence,
            },
        }

    def _checkpoint_from_ready(
        self, event: PlatformEvent, existing: GatewayCheckpoint | None
    ) -> GatewayCheckpoint:
        session_id = event.data.get("sessionId")
        resume_url = event.data.get("resumeGatewayUrl")
        if not isinstance(session_id, str):
            if event.name == "RESUMED" and existing is not None:
                session_id = existing.session_id
                resume_url = existing.resume_gateway_url
            else:
                raise GatewayProtocolError("READY is missing sessionId")
        if resume_url is not None and not isinstance(resume_url, str):
            raise GatewayProtocolError("invalid resumeGatewayUrl")
        return GatewayCheckpoint(
            session_id=session_id,
            sequence=event.sequence,
            shard_id=self.shard[0],
            shard_count=self.shard[1],
            credential_fingerprint=self._fingerprint,
            resume_gateway_url=resume_url,
        )

    async def _heartbeat_loop(self, interval: float) -> None:
        while True:
            await asyncio.sleep(interval)
            if self._coordinator is not None:
                renewed = await self._coordinator.renew(
                    *self.shard,
                    self._checkpoint_owner,
                    ttl=self._checkpoint_lease_ttl,
                )
                if not renewed:
                    if self._socket is not None:
                        await self._socket.close(4000, "Checkpoint ownership lost")
                    return
            if not self._heartbeat_acknowledged:
                if self._socket is not None:
                    await self._socket.close(4009, "Heartbeat ACK timeout")
                return
            self._heartbeat_acknowledged = False
            self._metric("heartbeat_sent", sequence=self._last_sequence)
            await self._send({"op": 1, "data": {"sequence": self._last_sequence}})

    def _metric(self, name: str, **values: int | float | str) -> None:
        if self._metric_hook is not None:
            self._metric_hook(name, values)

    async def _send(self, frame: dict[str, Any]) -> None:
        if self._socket is None:
            raise GatewayError("Gateway is not connected")
        encoded = json.dumps(frame, separators=(",", ":"))
        if len(encoded.encode()) > 16_384:
            raise GatewayProtocolError("Gateway client frame is too large")
        await self._socket.send(encoded)

    @staticmethod
    def _decode(message: str | bytes) -> dict[str, Any]:
        if not isinstance(message, str):
            raise GatewayProtocolError("binary Gateway frames are not supported")
        try:
            frame = json.loads(message)
        except json.JSONDecodeError as exc:
            raise GatewayProtocolError("Gateway returned invalid JSON") from exc
        if not isinstance(frame, dict) or not isinstance(frame.get("op"), int):
            raise GatewayProtocolError("Gateway frame is invalid")
        return frame

    def _validate_gateway_url(self, url: str) -> None:
        gateway = urlparse(url)
        origin = urlparse(self._base_url)
        expected_scheme = "wss" if origin.scheme == "https" else "ws"
        expected_port = origin.port or (443 if origin.scheme == "https" else 80)
        gateway_port = gateway.port or (443 if gateway.scheme == "wss" else 80)
        query = parse_qs(gateway.query, keep_blank_values=True)
        if (
            gateway.scheme != expected_scheme
            or gateway.hostname != origin.hostname
            or gateway_port != expected_port
            or gateway.username is not None
            or gateway.password is not None
            or gateway.fragment
            or gateway.path != "/api/v1/gateway/socket"
            or query != {"v": ["1"], "encoding": ["json"]}
        ):
            raise GatewayError("VoiceRoute returned an untrusted Gateway URL")
