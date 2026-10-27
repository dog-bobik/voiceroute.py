"""Public bot event models and SSE primitives."""

from voiceroute.events.catalog import EVENT_CATALOG, EventDefinition, event_definition
from voiceroute.events.cursors import (
    CursorStore,
    FileCursorStore,
    MemoryCursorStore,
    RedisCursorStore,
    SQLiteCursorStore,
    StreamCheckpoint,
)
from voiceroute.events.dispatcher import EventDispatcher
from voiceroute.events.models import AccessLost, BotEvent, InteractionCreated, MessageUpserted
from voiceroute.events.sse import SSEDecoder, SSEEvent
from voiceroute.events.transport import (
    ChannelTarget,
    EventDelivery,
    EventSource,
    EventTransport,
    InteractionEventTransport,
    InteractionSSETransport,
    InteractionTarget,
    LegacySSETransport,
)

__all__ = [
    "EVENT_CATALOG",
    "AccessLost",
    "BotEvent",
    "ChannelTarget",
    "CursorStore",
    "EventDefinition",
    "EventDelivery",
    "EventDispatcher",
    "EventSource",
    "EventTransport",
    "FileCursorStore",
    "InteractionCreated",
    "InteractionEventTransport",
    "InteractionSSETransport",
    "InteractionTarget",
    "LegacySSETransport",
    "MemoryCursorStore",
    "MessageUpserted",
    "RedisCursorStore",
    "SQLiteCursorStore",
    "SSEDecoder",
    "SSEEvent",
    "StreamCheckpoint",
    "event_definition",
]
