from __future__ import annotations

from collections.abc import AsyncIterator
from unittest.mock import AsyncMock

from voiceroute import Bot, CommandOption, CommandOptionType, MemoryCursorStore
from voiceroute.commands import InteractionContext
from voiceroute.events import (
    EventDelivery,
    EventSource,
    InteractionCreated,
    InteractionTarget,
    StreamCheckpoint,
)
from voiceroute.models import Interaction, InteractionCommand, User


def interaction() -> Interaction:
    return Interaction(
        id="interaction-id",
        application_id="application-id",
        community_id="community-id",
        channel_id="channel-id",
        user=User(7, "member", "Member"),
        command=InteractionCommand("command-id", "echo", 1),
        options={"text": "hello"},
    )


class FakeInteractionTransport:
    def __init__(self, deliveries: tuple[EventDelivery, ...]) -> None:
        self.deliveries = deliveries

    def stream_key(self, target: InteractionTarget) -> str:
        return "fake:interactions"

    async def listen(
        self,
        target: InteractionTarget,
        *,
        checkpoint: StreamCheckpoint | None,
        initial_after_seq: str | None,
    ) -> AsyncIterator[EventDelivery]:
        for delivery in self.deliveries:
            yield delivery


async def test_slash_command_receives_typed_context_and_responds() -> None:
    runtime = Bot(token="vrb_test")
    runtime.client.interactions.respond = AsyncMock()
    received: list[InteractionContext] = []

    @runtime.slash_command(
        "echo",
        description="Repeat text",
        options=(CommandOption("text", "Text", CommandOptionType.STRING, required=True),),
    )
    async def echo(context: InteractionContext) -> None:
        received.append(context)
        await context.respond(str(context.options["text"]), ephemeral=True)

    event = InteractionCreated(interaction(), "12")
    await runtime._handle_interaction(event)
    await runtime._handle_interaction(event)
    await runtime.close()

    assert len(received) == 1
    runtime.client.interactions.respond.assert_awaited_once_with(
        "interaction-id", "hello", ephemeral=True
    )


async def test_interaction_checkpoint_advances_after_success() -> None:
    checkpoint = StreamCheckpoint(change_cursor="12")
    transport = FakeInteractionTransport(
        (
            EventDelivery(
                InteractionCreated(interaction(), "12"),
                checkpoint,
                EventSource.INTERACTION_SSE,
            ),
        )
    )
    store = MemoryCursorStore()
    runtime = Bot(
        token="vrb_test",
        cursor_store=store,
        interaction_event_transport=transport,
    )

    @runtime.slash_command("echo", description="Repeat text")
    async def echo(context: InteractionContext) -> None:
        pass

    target = InteractionTarget()
    await runtime._consume_interactions(target)
    await runtime.close()

    assert await store.load(transport.stream_key(target)) == checkpoint
