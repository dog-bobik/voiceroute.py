from contextlib import asynccontextmanager
from unittest.mock import AsyncMock, patch

import pytest

from voiceroute.api.events import EventsAPI
from voiceroute.errors import RateLimited, SSEError
from voiceroute.events import AccessLost, MessageUpserted


def test_decode_message_upsert() -> None:
    event = EventsAPI._decode(
        "message",
        '{"seq":"17","communityId":"c","channelId":"ch","body":"hello"}',
        "83",
    )

    assert isinstance(event, MessageUpserted)
    assert event.message.seq == "17"
    assert event.cursor == "83"


def test_decode_access_lost() -> None:
    event = EventsAPI._decode("access-lost", '{"reason":"permissions"}', "84")

    assert event == AccessLost(cursor="84", reason="permissions")


def test_decode_rejects_unknown_event() -> None:
    with pytest.raises(SSEError, match="unsupported"):
        EventsAPI._decode("unknown", "{}", None)


async def test_event_stream_reconnects_after_rate_limit() -> None:
    class Response:
        async def aiter_lines(self):
            yield "event: access-lost"
            yield 'data: {"reason":"permissions"}'
            yield ""

    class Transport:
        def __init__(self) -> None:
            self.calls = 0

        @asynccontextmanager
        async def stream(self, *args, **kwargs):
            self.calls += 1
            if self.calls == 1:
                raise RateLimited(429, "slow down", retry_after=2.0)
            yield Response()

    transport = Transport()
    events = EventsAPI(transport)  # type: ignore[arg-type]

    with patch("voiceroute.api.events.asyncio.sleep", new=AsyncMock()) as sleep:
        received = [event async for event in events.listen_messages("community", "channel")]

    assert received == [AccessLost(cursor=None, reason="permissions")]
    assert transport.calls == 2
    sleep.assert_awaited_once_with(2.0)
