from collections.abc import AsyncIterator

from voiceroute import Bot, MemoryCursorStore
from voiceroute.events import (
    ChannelTarget,
    EventDelivery,
    EventSource,
    MessageUpserted,
    StreamCheckpoint,
)
from voiceroute.models import Message, User


class FakeEventTransport:
    def __init__(self, deliveries: tuple[EventDelivery, ...]) -> None:
        self.deliveries = deliveries
        self.received_checkpoint: StreamCheckpoint | None = None
        self.received_initial_after_seq: str | None = None

    def stream_key(self, target: ChannelTarget) -> str:
        return f"fake:{target.community_id}:{target.channel_id}"

    async def listen(
        self,
        target: ChannelTarget,
        *,
        checkpoint: StreamCheckpoint | None,
        initial_after_seq: str | None,
    ) -> AsyncIterator[EventDelivery]:
        self.received_checkpoint = checkpoint
        self.received_initial_after_seq = initial_after_seq
        for delivery in self.deliveries:
            yield delivery


async def test_bot_consumes_injected_event_transport() -> None:
    message = Message(
        seq="17",
        community_id="community",
        channel_id="channel",
        body="hello",
        author=User(7, "member", "Member"),
    )
    checkpoint = StreamCheckpoint(change_cursor="83", message_seq="17")
    transport = FakeEventTransport(
        (
            EventDelivery(
                event=MessageUpserted(message=message, cursor="83"),
                checkpoint=checkpoint,
                source=EventSource.LEGACY_SSE,
            ),
        )
    )
    store = MemoryCursorStore()
    runtime = Bot(token="vrb_secret", event_transport=transport, cursor_store=store)
    received: list[Message] = []

    @runtime.event
    async def on_message(event_message: Message) -> None:
        received.append(event_message)

    target = ChannelTarget("community", "channel")
    await runtime._consume_channel(target)
    await runtime.close()

    assert received == [message]
    assert await store.load(transport.stream_key(target)) == checkpoint
    assert transport.received_checkpoint is None
    assert transport.received_initial_after_seq == "0"
