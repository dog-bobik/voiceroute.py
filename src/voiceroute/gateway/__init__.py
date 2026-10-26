"""Bot Platform v1 Gateway public API."""

from voiceroute.gateway.client import GatewayClient, GatewayHandler
from voiceroute.gateway.intents import PRIVILEGED_INTENTS, Intent, Intents
from voiceroute.gateway.presence import Activity, ActivityType, Game, Presence, Status
from voiceroute.gateway.sharding import ShardManager
from voiceroute.gateway.store import (
    FileGatewayCheckpointStore,
    GatewayCheckpoint,
    GatewayCheckpointStore,
    MemoryGatewayCheckpointStore,
)

__all__ = [
    "PRIVILEGED_INTENTS",
    "Activity",
    "ActivityType",
    "FileGatewayCheckpointStore",
    "Game",
    "GatewayCheckpoint",
    "GatewayCheckpointStore",
    "GatewayClient",
    "GatewayHandler",
    "Intent",
    "Intents",
    "MemoryGatewayCheckpointStore",
    "Presence",
    "ShardManager",
    "Status",
]
