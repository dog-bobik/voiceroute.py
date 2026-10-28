from __future__ import annotations

import asyncio
from collections.abc import Callable, Mapping, Sequence
from typing import Any, cast

import pytest

from voiceroute import VoiceAccessDenied, VoiceSession
from voiceroute.gateway import GatewayClient
from voiceroute.models import VoiceServerGrant

COMMUNITY_ID = "00000000-0000-4000-8000-000000000001"
CHANNEL_ID = "00000000-0000-4000-8000-000000000002"
SESSION_ID = "00000000-0000-4000-8000-000000000003"


class FakePlatform:
    async def require(self, feature: str) -> None:
        assert feature == "voiceTransport"


class FakeGateway:
    capabilities = ("voiceStates",)
    intents = ("voiceStates",)
    platform = FakePlatform()

    def __init__(self, *, error: str | None = None, transmit: bool = True) -> None:
        self.handler: Callable[[Mapping[str, Any]], None] | None = None
        self.requests: list[dict[str, Any]] = []
        self.error = error
        self.transmit = transmit

    def subscribe_voice(self, handler: Callable[[Mapping[str, Any]], None]) -> Callable[[], None]:
        self.handler = handler
        return lambda: setattr(self, "handler", None)

    async def set_voice_state(
        self,
        community_id: str,
        channel_id: str | None,
        **data: Any,
    ) -> str:
        request_id = str(data.get("request_id", "00000000-0000-4000-8000-000000000099"))
        self.requests.append({"communityId": community_id, "channelId": channel_id, **data})
        if channel_id is not None:
            assert self.handler is not None
            if self.error is not None:
                self.handler(
                    {
                        "op": 4,
                        "data": {"requestId": request_id, "error": {"code": self.error}},
                    }
                )
            else:
                self.handler(
                    {
                        "op": 0,
                        "event": "VOICE_SERVER_UPDATED",
                        "data": {
                            "requestId": request_id,
                            "sessionId": SESSION_ID,
                            "communityId": community_id,
                            "channelId": channel_id,
                            "identity": "application-identity",
                            "endpoint": "wss://voice.voiceroute.cc",
                            "token": "short-lived-token",
                            "sessionExpiresAt": "2026-10-27T12:00:00Z",
                            "receive": False,
                            "transmit": self.transmit,
                        },
                    }
                )
        return request_id


class FakeMediaTransport:
    def __init__(self) -> None:
        self.grant: VoiceServerGrant | None = None
        self.frames: list[tuple[int, ...]] = []
        self.drained = False
        self.closed = False

    async def connect(self, grant: VoiceServerGrant) -> None:
        self.grant = grant

    async def write_pcm(self, samples: Sequence[int]) -> None:
        self.frames.append(tuple(samples))

    async def drain(self) -> None:
        self.drained = True

    async def close(self) -> None:
        self.closed = True


async def test_voice_session_joins_streams_and_disconnects() -> None:
    gateway = FakeGateway()
    media = FakeMediaTransport()
    session = VoiceSession(
        cast(GatewayClient, gateway),
        allowed_media_origins=("https://voice.voiceroute.cc",),
        transport_factory=lambda: media,
    )

    grant = await session.join(COMMUNITY_ID, CHANNEL_ID)
    await session.write_pcm([0] * 960)
    await session.drain()
    await session.close()

    assert grant.session_id == SESSION_ID
    assert media.frames == [(0,) * 960]
    assert media.drained is True
    assert media.closed is True
    assert gateway.requests[-1]["channelId"] is None
    assert gateway.handler is None


async def test_voice_session_surfaces_gateway_denial() -> None:
    gateway = FakeGateway(error="VOICE_TRANSMIT_FORBIDDEN")
    session = VoiceSession(
        cast(GatewayClient, gateway),
        allowed_media_origins=("https://voice.voiceroute.cc",),
        transport_factory=FakeMediaTransport,
    )

    with pytest.raises(VoiceAccessDenied, match="VOICE_TRANSMIT_FORBIDDEN"):
        await session.join(COMMUNITY_ID, CHANNEL_ID)

    await session.close()


async def test_voice_session_rejects_narrowed_grant_before_media_connect() -> None:
    gateway = FakeGateway(transmit=False)
    media = FakeMediaTransport()
    session = VoiceSession(
        cast(GatewayClient, gateway),
        allowed_media_origins=("https://voice.voiceroute.cc",),
        transport_factory=lambda: media,
    )

    with pytest.raises(VoiceAccessDenied, match="transmit"):
        await session.join(COMMUNITY_ID, CHANNEL_ID)

    assert media.grant is None
    await session.close()


async def test_voice_session_requires_exact_pcm_frame_size() -> None:
    gateway = FakeGateway()
    session = VoiceSession(
        cast(GatewayClient, gateway),
        allowed_media_origins=("https://voice.voiceroute.cc",),
        transport_factory=FakeMediaTransport,
    )
    await session.join(COMMUNITY_ID, CHANNEL_ID)

    with pytest.raises(ValueError, match="960"):
        await session.write_pcm([0] * 959)

    await session.close()


def test_voice_session_rejects_untrusted_media_origin() -> None:
    gateway = FakeGateway()
    session = VoiceSession(
        cast(GatewayClient, gateway),
        allowed_media_origins=("https://voiceroute.cc",),
        transport_factory=FakeMediaTransport,
    )

    with pytest.raises(Exception, match="untrusted"):
        asyncio.run(session.join(COMMUNITY_ID, CHANNEL_ID))
