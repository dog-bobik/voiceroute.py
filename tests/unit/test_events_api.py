import pytest

from voiceroute.api.events import EventsAPI
from voiceroute.errors import SSEError
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
