import asyncio
import hashlib
import json
from collections.abc import AsyncIterator
from types import SimpleNamespace
from typing import Any

import pytest

from voiceroute.errors import GatewayError, InstallationGrantRequired
from voiceroute.gateway import GatewayCheckpoint, GatewayClient, MemoryGatewayCheckpointStore
from voiceroute.gateway import client as gateway_client_module
from voiceroute.models import GatewayDiscovery, GatewaySessionStartLimit, PlatformEvent


async def test_default_gateway_connector_uses_tls_only_for_wss(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    calls: list[tuple[str, object]] = []

    async def fake_connect(url: str, **kwargs: Any) -> Any:
        calls.append((url, kwargs["ssl"]))
        return object()

    monkeypatch.setattr(gateway_client_module, "connect", fake_connect)

    await gateway_client_module._default_connector("ws://localhost:3000/api/v1/gateway/socket")
    await gateway_client_module._default_connector(
        "wss://voiceroute.cc/api/v1/gateway/socket"
    )

    assert calls[0][1] is None
    assert calls[1][1] is not None


class FakePlatformAPI:
    async def gateway(self) -> GatewayDiscovery:
        return GatewayDiscovery(
            url="wss://voiceroute.cc/api/v1/gateway/socket?v=1&encoding=json",
            recommended_shards=1,
            session_start_limit=GatewaySessionStartLimit(1000, 999, 0, 1),
        )

    async def capabilities(self) -> Any:
        return SimpleNamespace(event_capabilities=("messages", "members", "voiceStates"))

    async def current_application(self) -> Any:
        return SimpleNamespace(granted_capabilities=("messages", "members"))


class FakeSocket:
    def __init__(self, frames: list[dict[str, Any]]) -> None:
        self.frames = [json.dumps(frame) for frame in frames]
        self.sent: list[dict[str, Any]] = []
        self.closed: tuple[int, str] | None = None

    def __aiter__(self) -> AsyncIterator[str | bytes]:
        return self._frames()

    async def _frames(self) -> AsyncIterator[str | bytes]:
        for frame in self.frames:
            yield frame

    async def send(self, message: str) -> None:
        self.sent.append(json.loads(message))

    async def close(self, code: int = 1000, reason: str = "") -> None:
        self.closed = (code, reason)


def hello() -> dict[str, Any]:
    return {"op": 10, "data": {"heartbeatIntervalMs": 30_000}}


def ready() -> dict[str, Any]:
    return {
        "op": 0,
        "event": "READY",
        "sequence": "1",
        "data": {
            "sessionId": "00000000-0000-4000-8000-000000000001",
            "resumeGatewayUrl": "wss://voiceroute.cc/api/v1/gateway/socket?v=1&encoding=json",
        },
    }


def message(sequence: str = "2") -> dict[str, Any]:
    return {
        "op": 0,
        "event": "MESSAGE_CREATED",
        "sequence": sequence,
        "deliveryId": "00000000-0000-4000-8000-000000000002",
        "data": {"messageId": "message-1"},
    }


async def test_gateway_identifies_handles_and_commits_dispatch() -> None:
    socket = FakeSocket([hello(), ready(), message()])
    store = MemoryGatewayCheckpointStore()
    handled: list[PlatformEvent] = []

    async def handle(event: PlatformEvent) -> None:
        handled.append(event)

    async def connector(url: str) -> FakeSocket:
        assert url.startswith("wss://voiceroute.cc/")
        return socket

    client = GatewayClient(
        token="vrb_test",
        platform_api=FakePlatformAPI(),  # type: ignore[arg-type]
        base_url="https://voiceroute.cc",
        capabilities=("messages",),
        store=store,
        connector=connector,
    )
    await client.run_once(handle)

    checkpoint = await store.load(0, 1)
    assert socket.sent[0]["op"] == 2
    assert socket.sent[0]["data"]["capabilities"] == ["messages"]
    assert [event.name for event in handled] == ["MESSAGE_CREATED"]
    assert checkpoint is not None
    assert checkpoint.sequence == "2"


async def test_gateway_does_not_commit_failed_handler() -> None:
    socket = FakeSocket([hello(), ready(), message()])
    store = MemoryGatewayCheckpointStore()

    async def connector(url: str) -> FakeSocket:
        return socket

    async def fail(event: PlatformEvent) -> None:
        raise RuntimeError("database failed")

    client = GatewayClient(
        token="vrb_test",
        platform_api=FakePlatformAPI(),  # type: ignore[arg-type]
        base_url="https://voiceroute.cc",
        store=store,
        connector=connector,
    )
    with pytest.raises(RuntimeError, match="database failed"):
        await client.run_once(fail)

    checkpoint = await store.load(0, 1)
    assert checkpoint is not None
    assert checkpoint.sequence == "1"


async def test_gateway_resumes_matching_checkpoint() -> None:
    socket = FakeSocket([hello()])
    store = MemoryGatewayCheckpointStore()
    client = GatewayClient(
        token="vrb_test",
        platform_api=FakePlatformAPI(),  # type: ignore[arg-type]
        base_url="https://voiceroute.cc",
        store=store,
        connector=lambda url: _socket(socket),
    )
    await store.save(
        GatewayCheckpoint(
            session_id="00000000-0000-4000-8000-000000000001",
            sequence="9007199254740993",
            shard_id=0,
            shard_count=1,
            credential_fingerprint=hashlib.sha256(b"vrb_test").hexdigest()[:16],
            resume_gateway_url="wss://voiceroute.cc/api/v1/gateway/socket?v=1&encoding=json",
        )
    )

    async def ignore(event: PlatformEvent) -> None:
        return None

    await client.run_once(ignore)

    assert socket.sent[0]["op"] == 6
    assert socket.sent[0]["data"]["sequence"] == "9007199254740993"
    assert client._last_sequence == "9007199254740993"


async def test_gateway_control_frames_are_not_blocked_by_slow_handler() -> None:
    socket = FakeSocket([hello(), ready(), message(), {"op": 11, "data": {"sequence": "2"}}])
    entered = asyncio.Event()
    release = asyncio.Event()
    acknowledged = asyncio.Event()

    async def connector(url: str) -> FakeSocket:
        return socket

    async def slow_handler(event: PlatformEvent) -> None:
        entered.set()
        await release.wait()

    def metric(name: str, values: dict[str, int | float | str]) -> None:
        if name == "heartbeat_ack":
            acknowledged.set()

    client = GatewayClient(
        token="vrb_test",
        platform_api=FakePlatformAPI(),  # type: ignore[arg-type]
        base_url="https://voiceroute.cc",
        connector=connector,
        metric_hook=metric,
        dispatch_queue_size=1,
    )
    running = asyncio.create_task(client.run_once(slow_handler))

    await asyncio.wait_for(entered.wait(), timeout=1)
    await asyncio.wait_for(acknowledged.wait(), timeout=1)
    release.set()
    await running


async def test_gateway_routes_voice_control_frames_without_dispatching_them() -> None:
    request_id = "00000000-0000-4000-8000-000000000010"
    socket = FakeSocket(
        [
            hello(),
            ready(),
            {"op": 4, "data": {"requestId": request_id, "sessionId": "session-id"}},
        ]
    )
    seen: list[dict[str, Any]] = []
    dispatched: list[PlatformEvent] = []

    async def connector(url: str) -> FakeSocket:
        return socket

    async def handle(event: PlatformEvent) -> None:
        dispatched.append(event)

    client = GatewayClient(
        token="vrb_test",
        platform_api=FakePlatformAPI(),  # type: ignore[arg-type]
        base_url="https://voiceroute.cc",
        connector=connector,
    )
    client.subscribe_voice(lambda frame: seen.append(dict(frame)))
    await client.run_once(handle)

    assert seen == [{"op": 4, "data": {"requestId": request_id, "sessionId": "session-id"}}]
    assert dispatched == []


async def test_gateway_does_not_retry_missing_installation_grant() -> None:
    class UnapprovedPlatform(FakePlatformAPI):
        async def capabilities(self) -> Any:
            return SimpleNamespace(event_capabilities=("voiceStates",))

        async def current_application(self) -> Any:
            return SimpleNamespace(granted_capabilities=())

    connections = 0

    async def connector(url: str) -> FakeSocket:
        nonlocal connections
        connections += 1
        return FakeSocket([])

    async def ignore(event: PlatformEvent) -> None:
        return None

    client = GatewayClient(
        token="vrb_test",
        platform_api=UnapprovedPlatform(),  # type: ignore[arg-type]
        base_url="https://voiceroute.cc",
        capabilities=("voiceStates",),
        connector=connector,
    )

    with pytest.raises(InstallationGrantRequired, match="voiceStates"):
        await client.run(ignore)

    assert connections == 0


async def _socket(socket: FakeSocket) -> FakeSocket:
    return socket


@pytest.mark.parametrize(
    "url",
    [
        "wss://attacker.example/api/v1/gateway/socket?v=1&encoding=json",
        "wss://voiceroute.cc:8443/api/v1/gateway/socket?v=1&encoding=json",
        "wss://voiceroute.cc/api/v1/gateway/socket?v=1&encoding=json&redirect=evil",
    ],
)
async def test_gateway_rejects_untrusted_discovery_url(url: str) -> None:
    class UntrustedPlatformAPI:
        async def gateway(self) -> GatewayDiscovery:
            return GatewayDiscovery(
                url=url,
                recommended_shards=1,
                session_start_limit=GatewaySessionStartLimit(1000, 999, 0, 1),
            )

    client = GatewayClient(
        token="vrb_test",
        platform_api=UntrustedPlatformAPI(),  # type: ignore[arg-type]
        base_url="https://voiceroute.cc",
    )

    async def ignore(event: PlatformEvent) -> None:
        return None

    with pytest.raises(GatewayError, match="untrusted"):
        await client.run_once(ignore)
