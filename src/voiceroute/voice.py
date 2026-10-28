"""High-level outgoing VoiceRoute voice session."""

from __future__ import annotations

import asyncio
import importlib
import struct
import uuid
from collections.abc import Callable, Mapping, Sequence
from typing import Any, Protocol
from urllib.parse import urlparse

from voiceroute.errors import VoiceRouteError
from voiceroute.gateway import Capability, GatewayClient
from voiceroute.models.voice import VoiceServerGrant


class VoiceError(VoiceRouteError):
    """Base error for the voice transport."""


class VoiceRuntimeMissing(VoiceError):
    """The optional LiveKit runtime is not installed."""


class VoiceAccessDenied(VoiceError):
    """VoiceRoute rejected a voice state request."""


class VoiceMediaTransport(Protocol):
    async def connect(self, grant: VoiceServerGrant) -> None: ...

    async def write_pcm(self, samples: Sequence[int]) -> None: ...

    async def drain(self) -> None: ...

    async def close(self) -> None: ...


MediaTransportFactory = Callable[[], VoiceMediaTransport]


class LiveKitMediaTransport:
    """Publish 48 kHz mono PCM through the official LiveKit Python runtime."""

    def __init__(self) -> None:
        self._rtc: Any = None
        self._room: Any = None
        self._source: Any = None
        self._track: Any = None

    async def connect(self, grant: VoiceServerGrant) -> None:
        try:
            rtc = importlib.import_module("livekit.rtc")
        except ImportError as error:
            raise VoiceRuntimeMissing("install voiceroute.py[voice] to use VoiceSession") from error
        room = rtc.Room()
        await room.connect(
            grant.endpoint,
            grant.token,
            rtc.RoomOptions(auto_subscribe=False, dynacast=True),
        )
        source = rtc.AudioSource(sample_rate=48_000, num_channels=1, queue_size_ms=200)
        track = rtc.LocalAudioTrack.create_audio_track("voiceroute-bot-audio", source)
        options = rtc.TrackPublishOptions(source=rtc.TrackSource.SOURCE_MICROPHONE)
        await room.local_participant.publish_track(track, options)
        self._rtc = rtc
        self._room = room
        self._source = source
        self._track = track

    async def write_pcm(self, samples: Sequence[int]) -> None:
        if self._source is None or self._rtc is None:
            raise VoiceError("voice media transport is not connected")
        pcm = struct.pack(f"<{len(samples)}h", *samples)
        frame = self._rtc.AudioFrame(
            data=pcm,
            sample_rate=48_000,
            num_channels=1,
            samples_per_channel=len(samples),
        )
        await self._source.capture_frame(frame)

    async def drain(self) -> None:
        if self._source is not None:
            await self._source.wait_for_playout()

    async def close(self) -> None:
        room, source = self._room, self._source
        self._room = self._track = self._source = self._rtc = None
        if source is not None:
            await source.aclose()
        if room is not None:
            await room.disconnect()


class VoiceSession:
    """Join one channel and publish 20 ms PCM frames through a Gateway session."""

    FRAME_SAMPLES = 960

    def __init__(
        self,
        gateway: GatewayClient,
        *,
        allowed_media_origins: Sequence[str],
        transport_factory: MediaTransportFactory = LiveKitMediaTransport,
        join_timeout: float = 15.0,
    ) -> None:
        if not allowed_media_origins:
            raise ValueError("allowed_media_origins must not be empty")
        if join_timeout <= 0:
            raise ValueError("join_timeout must be positive")
        self.gateway = gateway
        self._origins = frozenset(_origin(value) for value in allowed_media_origins)
        self._transport_factory = transport_factory
        self._join_timeout = join_timeout
        self._pending: dict[str, asyncio.Future[VoiceServerGrant]] = {}
        self._transport: VoiceMediaTransport | None = None
        self._grant: VoiceServerGrant | None = None
        self._unsubscribe = gateway.subscribe_voice(self._handle_gateway_frame)
        self._closed = False

    @property
    def connected(self) -> bool:
        return self._grant is not None and self._transport is not None

    @property
    def state(self) -> VoiceServerGrant | None:
        return self._grant

    async def join(
        self,
        community_id: str,
        channel_id: str,
        *,
        receive: bool = False,
        transmit: bool = True,
        self_mute: bool = False,
        self_deaf: bool = True,
        purpose: str = "LISTENING",
    ) -> VoiceServerGrant:
        if self._closed:
            raise VoiceError("voice session is closed")
        capabilities = getattr(self.gateway, "capabilities", None)
        if capabilities is None:
            capabilities = self.gateway.intents
        if Capability.VOICE_STATES.value not in capabilities:
            raise VoiceAccessDenied("Gateway voiceStates capability is required")
        await self.gateway.platform.require("voiceTransport")
        await self.disconnect()
        request_id = str(uuid.uuid4())
        future: asyncio.Future[VoiceServerGrant] = asyncio.get_running_loop().create_future()
        self._pending[request_id] = future
        try:
            await self.gateway.set_voice_state(
                community_id,
                channel_id,
                request_id=request_id,
                receive=receive,
                transmit=transmit,
                self_mute=self_mute,
                self_deaf=self_deaf,
                purpose=purpose,
            )
            grant = await asyncio.wait_for(future, timeout=self._join_timeout)
            self._validate_grant(grant)
            transport = self._transport_factory()
            await transport.connect(grant)
        except TimeoutError as error:
            raise VoiceError("VoiceRoute voice join timed out") from error
        finally:
            self._pending.pop(request_id, None)
        self._transport = transport
        self._grant = grant
        return grant

    async def write_pcm(self, samples: Sequence[int]) -> None:
        if self._transport is None or self._grant is None:
            raise VoiceError("voice session is not connected")
        if not self._grant.transmit:
            raise VoiceAccessDenied("VoiceRoute did not grant voice transmit access")
        if len(samples) != self.FRAME_SAMPLES:
            raise ValueError(f"PCM frame must contain exactly {self.FRAME_SAMPLES} samples")
        if any(sample < -32768 or sample > 32767 for sample in samples):
            raise ValueError("PCM samples must be signed 16-bit integers")
        await self._transport.write_pcm(samples)

    async def drain(self) -> None:
        if self._transport is not None:
            await self._transport.drain()

    async def disconnect(self) -> None:
        grant, transport = self._grant, self._transport
        self._grant = None
        self._transport = None
        if transport is not None:
            await transport.close()
        if grant is not None:
            await self.gateway.set_voice_state(grant.community_id, None)

    async def close(self) -> None:
        if self._closed:
            return
        await self.disconnect()
        self._closed = True
        self._unsubscribe()
        for future in self._pending.values():
            if not future.done():
                future.set_exception(VoiceError("voice session closed"))
        self._pending.clear()

    async def __aenter__(self) -> VoiceSession:
        return self

    async def __aexit__(self, *_: object) -> None:
        await self.close()

    def _handle_gateway_frame(self, frame: Mapping[str, Any]) -> None:
        data = frame.get("data")
        if not isinstance(data, dict):
            return
        request_id = data.get("requestId")
        if not isinstance(request_id, str):
            return
        future = self._pending.get(request_id)
        if future is None or future.done():
            return
        error = data.get("error")
        if frame.get("op") == 4 and isinstance(error, dict):
            future.set_exception(VoiceAccessDenied(str(error.get("code", "VOICE_ACCESS_DENIED"))))
            return
        if frame.get("event") == "VOICE_SERVER_UPDATED":
            try:
                future.set_result(VoiceServerGrant.from_dict(data))
            except ValueError as error_value:
                future.set_exception(error_value)

    def _validate_grant(self, grant: VoiceServerGrant) -> None:
        if _origin(grant.endpoint) not in self._origins:
            raise VoiceError("VoiceRoute returned an untrusted media endpoint")
        endpoint = urlparse(grant.endpoint)
        if (
            endpoint.path not in {"", "/"}
            or endpoint.username
            or endpoint.password
            or endpoint.query
            or endpoint.fragment
        ):
            raise VoiceError("VoiceRoute returned an unsafe media endpoint")


def _origin(value: str) -> tuple[str, str, int]:
    parsed = urlparse(value)
    scheme = {"http": "http", "https": "https", "ws": "http", "wss": "https"}.get(parsed.scheme)
    if scheme is None or parsed.hostname is None:
        raise ValueError("media origin must be an HTTP(S) or WS(S) URL")
    port = parsed.port or (443 if scheme == "https" else 80)
    return scheme, parsed.hostname.casefold(), port
