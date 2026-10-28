"""Bot Platform v1 Gateway public API."""

from voiceroute.gateway.client import GatewayClient, GatewayHandler, GatewayMetricHook
from voiceroute.gateway.intents import (
    PRIVILEGED_INTENTS,
    TRACKED_CAPABILITIES,
    Capabilities,
    Capability,
    Intent,
    Intents,
)
from voiceroute.gateway.presence import Activity, ActivityType, Game, Presence, Status
from voiceroute.gateway.sharding import ShardManager
from voiceroute.gateway.store import (
    FileGatewayCheckpointStore,
    GatewayCheckpoint,
    GatewayCheckpointCoordinator,
    GatewayCheckpointStore,
    MemoryGatewayCheckpointCoordinator,
    MemoryGatewayCheckpointStore,
    PostgreSQLGatewayCheckpointStore,
    RedisGatewayCheckpointCoordinator,
    RedisGatewayCheckpointStore,
)

__all__ = [
    "PRIVILEGED_INTENTS",
    "TRACKED_CAPABILITIES",
    "Activity",
    "ActivityType",
    "Capabilities",
    "Capability",
    "FileGatewayCheckpointStore",
    "Game",
    "GatewayCheckpoint",
    "GatewayCheckpointCoordinator",
    "GatewayCheckpointStore",
    "GatewayClient",
    "GatewayHandler",
    "GatewayMetricHook",
    "Intent",
    "Intents",
    "MemoryGatewayCheckpointCoordinator",
    "MemoryGatewayCheckpointStore",
    "PostgreSQLGatewayCheckpointStore",
    "Presence",
    "RedisGatewayCheckpointCoordinator",
    "RedisGatewayCheckpointStore",
    "ShardManager",
    "Status",
]
