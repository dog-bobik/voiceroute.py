from voiceroute.events import SSEDecoder, SSEEvent


def test_decoder_ignores_keepalive_and_joins_data_lines() -> None:
    decoder = SSEDecoder()

    assert decoder.feed_line(": keepalive") is None
    assert decoder.feed_line("id: 83") is None
    assert decoder.feed_line("event: message") is None
    assert decoder.feed_line('data: {"body":') is None
    assert decoder.feed_line('data: "hello"}') is None
    assert decoder.feed_line("") == SSEEvent(
        event="message",
        data='{"body":\n"hello"}',
        id="83",
    )


def test_decoder_keeps_last_event_id_across_frames() -> None:
    decoder = SSEDecoder()
    decoder.feed_line("id: 10")
    decoder.feed_line("data: first")
    decoder.feed_line("")
    decoder.feed_line("data: second")

    event = decoder.feed_line("")

    assert event is not None and event.id == "10"
