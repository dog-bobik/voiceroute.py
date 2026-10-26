import pytest

from voiceroute.models import PlatformEvent, PlatformEventType


def test_platform_event_preserves_large_sequence_as_string() -> None:
    event = PlatformEvent.from_gateway_frame(
        {
            "op": 0,
            "event": "MESSAGE_CREATED",
            "sequence": "9007199254740993",
            "deliveryId": "018f47a0-d4c0-7c73-a7cc-123456789abc",
            "data": {"id": "message-1"},
            "futureField": True,
        }
    )

    assert event.sequence == "9007199254740993"
    assert event.known_type is PlatformEventType.MESSAGE_CREATED
    assert event.raw is not None
    assert event.raw["futureField"] is True


def test_platform_event_accepts_unknown_future_event() -> None:
    event = PlatformEvent.from_gateway_frame(
        {"event": "FUTURE_EVENT", "sequence": "42", "data": {"new": "shape"}}
    )

    assert event.is_known is False
    assert event.known_type is None
    assert event.data == {"new": "shape"}


@pytest.mark.parametrize(
    "frame",
    [
        {"event": "READY", "sequence": 1, "data": {}},
        {"event": "READY", "sequence": "1", "data": []},
    ],
)
def test_platform_event_rejects_invalid_wire_types(frame: dict[str, object]) -> None:
    with pytest.raises(ValueError):
        PlatformEvent.from_gateway_frame(frame)
