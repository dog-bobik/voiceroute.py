"""Bot Platform v1 discovery and bootstrap models."""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass
from types import MappingProxyType
from typing import Any, Self


@dataclass(frozen=True, slots=True)
class IntentCapability:
    """One Gateway intent advertised by the connected deployment."""

    privileged: bool


@dataclass(frozen=True, slots=True)
class GatewayCapabilities:
    """Gateway limits needed before opening a session."""

    encodings: tuple[str, ...]
    compression: bool
    shard_counts: tuple[int, ...]
    replay_window_ms: int
    max_sessions_per_application: int
    heartbeat_interval_ms: int
    max_client_frame_bytes: int

    @classmethod
    def from_dict(cls, data: Mapping[str, Any]) -> Self:
        return cls(
            encodings=tuple(str(item) for item in data.get("encoding", ())),
            compression=bool(data.get("compression", False)),
            shard_counts=tuple(int(item) for item in data.get("shardCounts", ())),
            replay_window_ms=int(data.get("replayWindowMs", 0)),
            max_sessions_per_application=int(data.get("maxSessionsPerApplication", 0)),
            heartbeat_interval_ms=int(data.get("heartbeatIntervalMs", 0)),
            max_client_frame_bytes=int(data.get("maxClientFrameBytes", 0)),
        )


@dataclass(frozen=True, slots=True)
class LegacyCapabilities:
    """Availability and sunset state of the original REST/SSE contract."""

    rest: bool
    sse: bool
    sunset_at: str | None


@dataclass(frozen=True, slots=True)
class PlatformCapabilities:
    """Runtime source of truth returned by `/api/v1/capabilities`."""

    api_version: str
    maturity: str
    stage: str
    environment: str
    gateway: GatewayCapabilities
    features: Mapping[str, bool]
    events: tuple[str, ...]
    intents: Mapping[str, IntentCapability]
    legacy: LegacyCapabilities
    raw: Mapping[str, Any]

    def supports(self, feature: str) -> bool:
        """Return whether an optional platform feature is enabled in this deployment."""
        return self.features.get(feature, False)

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> Self:
        raw_features = data.get("features")
        features = (
            {
                str(key): bool(value)
                for key, value in raw_features.items()
                if isinstance(key, str) and isinstance(value, bool)
            }
            if isinstance(raw_features, dict)
            else {}
        )
        raw_intents = data.get("intents")
        intents = (
            {
                str(key): IntentCapability(privileged=bool(value.get("privileged", False)))
                for key, value in raw_intents.items()
                if isinstance(key, str) and isinstance(value, dict)
            }
            if isinstance(raw_intents, dict)
            else {}
        )
        legacy_value = data.get("legacy")
        raw_legacy: dict[str, Any] = legacy_value if isinstance(legacy_value, dict) else {}
        environment_value = data.get("environment")
        raw_environment: dict[str, Any] = (
            environment_value if isinstance(environment_value, dict) else {}
        )
        gateway_value = data.get("gateway")
        raw_gateway: dict[str, Any] = gateway_value if isinstance(gateway_value, dict) else {}
        return cls(
            api_version=str(data.get("apiVersion", "")),
            maturity=str(data.get("maturity", "unknown")),
            stage=str(data.get("stage", "")),
            environment=str(raw_environment.get("mode", "unknown")),
            gateway=GatewayCapabilities.from_dict(raw_gateway),
            features=MappingProxyType(features),
            events=tuple(str(item) for item in data.get("events", ())),
            intents=MappingProxyType(intents),
            legacy=LegacyCapabilities(
                rest=bool(raw_legacy.get("rest", False)),
                sse=bool(raw_legacy.get("sse", False)),
                sunset_at=(
                    str(raw_legacy["sunsetAt"]) if raw_legacy.get("sunsetAt") is not None else None
                ),
            ),
            raw=MappingProxyType(dict(data)),
        )


@dataclass(frozen=True, slots=True)
class PlatformBotIdentity:
    id: str
    username: str
    display_name: str


@dataclass(frozen=True, slots=True)
class CurrentApplication:
    """Application and bot identity associated with the current credential."""

    id: str
    name: str
    description: str
    public: bool
    permissions: tuple[str, ...]
    bot: PlatformBotIdentity
    requested_intents: tuple[str, ...]
    approved_intents: tuple[str, ...]

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> Self:
        bot = data["bot"]
        return cls(
            id=str(data["id"]),
            name=str(data["name"]),
            description=str(data["description"]),
            public=bool(data["public"]),
            permissions=tuple(str(item) for item in data.get("permissions", ())),
            bot=PlatformBotIdentity(
                id=str(bot["id"]),
                username=str(bot["username"]),
                display_name=str(bot["displayName"]),
            ),
            requested_intents=tuple(str(item) for item in data.get("requestedIntents", ())),
            approved_intents=tuple(str(item) for item in data.get("approvedIntents", ())),
        )
