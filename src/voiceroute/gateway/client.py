"""VoiceRoute Bot Platform v1 WebSocket Gateway transport."""

from __future__ import annotations

import asyncio
import hashlib
import json
import platform
from collections.abc import AsyncIterator, Awaitable, Callable, Sequence
from contextlib import suppress
from typing import Any, Protocol
from urllib.parse import parse_qs, urlparse

from websockets.asyncio.client import connect
from websockets.exceptions import ConnectionClosed

from voiceroute.api import PlatformAPI
from voiceroute.errors import (
    GatewayClosed,
    GatewayError,
    GatewayProtocolError,
    PrivilegedIntentRequired,
)
from voiceroute.gateway.intents import Intents
from voiceroute.gateway.presence import Activity, Presence, Status
from voiceroute.gateway.store import (
    GatewayCheckpoint,
    GatewayCheckpointStore,
    MemoryGatewayCheckpointStore,
)
from voiceroute.models import PlatformEvent

_TERMINAL_CLOSE_CODES = {4001, 4002, 4003, 4004, 4005, 4010, 4011, 4013, 4014, 4015}
_CLEAR_SESSION_CLOSE_CODES = {4007, 4009}


class GatewaySocket(Protocol):
    def __aiter__(self) -> AsyncIterator[str | bytes]: ...

    async def send(self, message: str) -> None: ...

    async def close(self, code: int = 1000, reason: str = "") -> None: ...


GatewayConnector = Callable[[str], Awaitable[GatewaySocket]]
GatewayHandler = Callable[[PlatformEvent], Awaitable[None]]


async def _default_connector(url: str) -> GatewaySocket:
    return await connect(url, max_size=1_048_576, compression=None)


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
    ) -> None:
        shard_id, shard_count = shard
        if shard_count not in {1, 2, 4, 8, 16} or not 0 <= shard_id < shard_count:
            raise ValueError("invalid Gateway shard")
        intent_values = intents.values if isinstance(intents, Intents) else tuple(intents)
        if len(set(intent_values)) != len(intent_values):
            raise ValueError("Gateway intents must be unique")
        self._token = token
        self._platform = platform_api
        self._base_url = base_url
        self.intents = tuple(intent_values)
        self.shard = shard
        self._store = store or MemoryGatewayCheckpointStore()
        self._connector = connector
        self._library_version = library_version
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
        socket = await self._connector(url)
        self._socket = socket
        self._heartbeat_acknowledged = True
        heartbeat: asyncio.Task[None] | None = None
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
            await self._send(self._resume(checkpoint) if checkpoint else self._identify())
            self._identified.set()
            heartbeat = asyncio.create_task(self._heartbeat_loop(interval_ms / 1000))

            async for message in iterator:
                frame = self._decode(message)
                opcode = frame.get("op")
                if opcode == 11:
                    self._heartbeat_acknowledged = True
                    continue
                if opcode == 7:
                    await socket.close(4000, "Reconnect requested")
                    return
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
                await handler(event)
                checkpoint = GatewayCheckpoint(
                    session_id=checkpoint.session_id,
                    sequence=event.sequence,
                    shard_id=checkpoint.shard_id,
                    shard_count=checkpoint.shard_count,
                    credential_fingerprint=checkpoint.credential_fingerprint,
                    resume_gateway_url=checkpoint.resume_gateway_url,
                )
                await self._store.save(checkpoint)
        except ConnectionClosed as exc:
            if exc.code in _CLEAR_SESSION_CLOSE_CODES:
                await self._store.clear(*self.shard)
                if self.on_session_invalidated is not None:
                    await self.on_session_invalidated()
            if exc.code in _TERMINAL_CLOSE_CODES:
                raise GatewayClosed(exc.code, exc.reason) from exc
        finally:
            if heartbeat is not None:
                heartbeat.cancel()
                with suppress(asyncio.CancelledError):
                    await heartbeat
            self._socket = None

    async def run(self, handler: GatewayHandler) -> None:
        """Reconnect with bounded exponential backoff until explicitly stopped."""
        self._stopping = False
        attempt = 0
        while not self._stopping:
            try:
                await self.run_once(handler)
                attempt = 0
            except GatewayClosed:
                raise
            except (GatewayError, OSError, ConnectionClosed):
                attempt += 1
            if not self._stopping:
                await asyncio.sleep(min(60.0, 2 ** min(attempt, 6)))

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
        if not privileged:
            return
        application = await self._platform.current_application()
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
            if not self._heartbeat_acknowledged:
                if self._socket is not None:
                    await self._socket.close(4009, "Heartbeat ACK timeout")
                return
            self._heartbeat_acknowledged = False
            await self._send({"op": 1, "data": {"sequence": self._last_sequence}})

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
