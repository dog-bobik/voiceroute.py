"""Bot Platform v1 discovery and bootstrap models."""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass
from types import MappingProxyType
from typing import Any, Self


@dataclass(frozen=True, slots=True)
class BotAccessCapabilities:
    catalog_version: int
    manifest_schema_version: int
    installation_schema_version: int


@dataclass(frozen=True, slots=True)
class HTTPCapabilities:
    max_json_bytes: int
    max_concurrent_json_parsers_per_node: int
    body_read_timeout_ms: int


@dataclass(frozen=True, slots=True)
class VoiceCapabilities:
    media_token_ttl_seconds: int
    session_ttl_seconds: int
    max_sessions_per_application: int
    max_receive_sessions_per_application: int
    max_receive_sessions_global: int
    max_receive_tracks: int
    pcm_sample_rate: int
    pcm_channels: int
    pcm_frame_ms: int
    video_receive: bool
    active_authorization_recheck_ms: int


@dataclass(frozen=True, slots=True)
class FileCapabilities:
    max_bytes: int
    part_bytes: int
    max_attachments_per_message: int
    staging_ttl_ms: int
    max_active_uploads_per_application: int
    max_application_bytes: int


@dataclass(frozen=True, slots=True)
class CommandCapabilities:
    types: tuple[str, ...]
    scopes: tuple[str, ...]
    contexts: tuple[str, ...]
    callback_types: tuple[str, ...]
    max_per_scope: int
    global_propagation_ms: int
    initial_response_deadline_ms: int
    interaction_token_ttl_ms: int
    max_responses: int
    components: bool
    modals: bool


@dataclass(frozen=True, slots=True)
class OAuthCapabilities:
    grant_types: tuple[str, ...]
    pkce_methods: tuple[str, ...]
    access_token_ttl_seconds: int
    refresh_token_ttl_seconds: int
    user_consent: bool
    community_consent: bool
    user_commands: bool
    dm_interactions: bool
    max_active_client_secrets: int
    refresh_reuse_revokes_grant: bool


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
    http: HTTPCapabilities
    voice: VoiceCapabilities
    files: FileCapabilities
    commands: CommandCapabilities
    oauth2: OAuthCapabilities
    features: Mapping[str, bool]
    events: tuple[str, ...]
    event_capabilities: tuple[str, ...]
    automatic_event_families: tuple[str, ...]
    bot_access: BotAccessCapabilities
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
        legacy_value = data.get("legacy")
        raw_legacy: dict[str, Any] = legacy_value if isinstance(legacy_value, dict) else {}
        environment_value = data.get("environment")
        raw_environment: dict[str, Any] = (
            environment_value if isinstance(environment_value, dict) else {}
        )
        gateway_value = data.get("gateway")
        raw_gateway: dict[str, Any] = gateway_value if isinstance(gateway_value, dict) else {}
        raw_http = _object(data.get("http"))
        raw_voice = _object(data.get("voice"))
        raw_files = _object(data.get("files"))
        raw_commands = _object(data.get("commands"))
        raw_oauth = _object(data.get("oauth2"))
        raw_bot_access = _object(data.get("botAccess"))
        return cls(
            api_version=str(data.get("apiVersion", "")),
            maturity=str(data.get("maturity", "unknown")),
            stage=str(data.get("stage", "")),
            environment=str(raw_environment.get("mode", "unknown")),
            gateway=GatewayCapabilities.from_dict(raw_gateway),
            http=HTTPCapabilities(
                max_json_bytes=int(raw_http.get("maxJsonBytes", 0)),
                max_concurrent_json_parsers_per_node=int(
                    raw_http.get("maxConcurrentJsonParsersPerNode", 0)
                ),
                body_read_timeout_ms=int(raw_http.get("bodyReadTimeoutMs", 0)),
            ),
            voice=VoiceCapabilities(
                media_token_ttl_seconds=int(raw_voice.get("mediaTokenTtlSeconds", 0)),
                session_ttl_seconds=int(raw_voice.get("sessionTtlSeconds", 0)),
                max_sessions_per_application=int(raw_voice.get("maxSessionsPerApplication", 0)),
                max_receive_sessions_per_application=int(
                    raw_voice.get("maxReceiveSessionsPerApplication", 0)
                ),
                max_receive_sessions_global=int(raw_voice.get("maxReceiveSessionsGlobal", 0)),
                max_receive_tracks=int(raw_voice.get("maxReceiveTracks", 0)),
                pcm_sample_rate=int(raw_voice.get("pcmSampleRate", 0)),
                pcm_channels=int(raw_voice.get("pcmChannels", 0)),
                pcm_frame_ms=int(raw_voice.get("pcmFrameMs", 0)),
                video_receive=bool(raw_voice.get("videoReceive", False)),
                active_authorization_recheck_ms=int(
                    raw_voice.get("activeAuthorizationRecheckMs", 0)
                ),
            ),
            files=FileCapabilities(
                max_bytes=int(raw_files.get("maxBytes", 0)),
                part_bytes=int(raw_files.get("partBytes", 0)),
                max_attachments_per_message=int(raw_files.get("maxAttachmentsPerMessage", 0)),
                staging_ttl_ms=int(raw_files.get("stagingTtlMs", 0)),
                max_active_uploads_per_application=int(
                    raw_files.get("maxActiveUploadsPerApplication", 0)
                ),
                max_application_bytes=int(raw_files.get("maxApplicationBytes", 0)),
            ),
            commands=CommandCapabilities(
                types=_strings(raw_commands.get("types")),
                scopes=_strings(raw_commands.get("scopes")),
                contexts=_strings(raw_commands.get("contexts")),
                callback_types=_strings(raw_commands.get("callbackTypes")),
                max_per_scope=int(raw_commands.get("maxPerScope", 0)),
                global_propagation_ms=int(raw_commands.get("globalPropagationMs", 0)),
                initial_response_deadline_ms=int(raw_commands.get("initialResponseDeadlineMs", 0)),
                interaction_token_ttl_ms=int(raw_commands.get("interactionTokenTtlMs", 0)),
                max_responses=int(raw_commands.get("maxResponses", 0)),
                components=bool(raw_commands.get("components", False)),
                modals=bool(raw_commands.get("modals", False)),
            ),
            oauth2=OAuthCapabilities(
                grant_types=_strings(raw_oauth.get("grantTypes")),
                pkce_methods=_strings(raw_oauth.get("pkceMethods")),
                access_token_ttl_seconds=int(raw_oauth.get("accessTokenTtlSeconds", 0)),
                refresh_token_ttl_seconds=int(raw_oauth.get("refreshTokenTtlSeconds", 0)),
                user_consent=bool(raw_oauth.get("userConsent", False)),
                community_consent=bool(raw_oauth.get("communityConsent", False)),
                user_commands=bool(raw_oauth.get("userCommands", False)),
                dm_interactions=bool(raw_oauth.get("dmInteractions", False)),
                max_active_client_secrets=int(raw_oauth.get("maxActiveClientSecrets", 0)),
                refresh_reuse_revokes_grant=bool(raw_oauth.get("refreshReuseRevokesGrant", False)),
            ),
            features=MappingProxyType(features),
            events=tuple(str(item) for item in data.get("events", ())),
            event_capabilities=_strings(data.get("eventCapabilities")),
            automatic_event_families=_strings(data.get("automaticEventFamilies")),
            bot_access=BotAccessCapabilities(
                catalog_version=int(raw_bot_access.get("catalogVersion", 0)),
                manifest_schema_version=int(raw_bot_access.get("manifestSchemaVersion", 0)),
                installation_schema_version=int(raw_bot_access.get("installationSchemaVersion", 0)),
            ),
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
class ServiceIncident:
    id: str
    component: str
    impact: str
    state: str
    title: str
    message: str
    version: str
    created_at: str
    updated_at: str
    resolved_at: str | None

    @classmethod
    def from_dict(cls, data: Mapping[str, Any]) -> Self:
        return cls(
            id=str(data["id"]),
            component=str(data["component"]),
            impact=str(data["impact"]),
            state=str(data["state"]),
            title=str(data["title"]),
            message=str(data["message"]),
            version=str(data["version"]),
            created_at=str(data["createdAt"]),
            updated_at=str(data["updatedAt"]),
            resolved_at=(str(data["resolvedAt"]) if data.get("resolvedAt") is not None else None),
        )


@dataclass(frozen=True, slots=True)
class PlatformServiceStatus:
    status: str
    checked_at: str
    components: Mapping[str, str]
    incidents: tuple[ServiceIncident, ...]

    @property
    def operational(self) -> bool:
        return self.status == "operational"

    @property
    def degraded(self) -> bool:
        return self.status == "degraded"

    @property
    def unavailable(self) -> bool:
        return self.status == "unavailable"

    def component_available(self, component: str) -> bool:
        return self.components.get(component) not in {"unavailable", "unknown", None}

    @classmethod
    def from_dict(cls, data: Mapping[str, Any]) -> Self:
        components = _object(data.get("components"))
        incidents = data.get("incidents")
        return cls(
            status=str(data.get("status", "unknown")),
            checked_at=str(data.get("checkedAt", "")),
            components=MappingProxyType({str(k): str(v) for k, v in components.items()}),
            incidents=tuple(
                ServiceIncident.from_dict(item) for item in incidents if isinstance(item, dict)
            )
            if isinstance(incidents, list)
            else (),
        )


def _object(value: Any) -> dict[str, Any]:
    return dict(value) if isinstance(value, Mapping) else {}


def _strings(value: Any) -> tuple[str, ...]:
    return tuple(str(item) for item in value) if isinstance(value, list) else ()


@dataclass(frozen=True, slots=True)
class PlatformBotIdentity:
    id: str
    username: str
    display_name: str


@dataclass(frozen=True, slots=True)
class AccessManifest:
    schema_version: int
    catalog_version: int
    version: str
    hash: str
    permissions: tuple[str, ...]
    capabilities: tuple[str, ...]
    scopes: tuple[str, ...]

    @classmethod
    def from_dict(cls, data: Mapping[str, Any]) -> Self:
        return cls(
            schema_version=int(data.get("schemaVersion", 0)),
            catalog_version=int(data.get("catalogVersion", 0)),
            version=str(data.get("version", "")),
            hash=str(data.get("hash", "")),
            permissions=_strings(data.get("permissions")),
            capabilities=_strings(data.get("capabilities")),
            scopes=_strings(data.get("scopes")),
        )


@dataclass(frozen=True, slots=True)
class InstallationSnapshot:
    schema_version: int
    id: str
    application_id: str
    community_id: str
    granted_permissions: tuple[str, ...]
    granted_capabilities: tuple[str, ...]
    scopes: tuple[str, ...]
    catalog_version: int
    manifest_hash: str
    manifest_version: str
    installed_by: str
    installed_at: str

    @classmethod
    def from_dict(cls, data: Mapping[str, Any]) -> Self:
        return cls(
            schema_version=int(data.get("schemaVersion", 0)),
            id=str(data.get("id", "")),
            application_id=str(data.get("applicationId", "")),
            community_id=str(data.get("communityId", "")),
            granted_permissions=_strings(data.get("grantedPermissions")),
            granted_capabilities=_strings(data.get("grantedCapabilities")),
            scopes=_strings(data.get("scopes")),
            catalog_version=int(data.get("catalogVersion", 0)),
            manifest_hash=str(data.get("manifestHash", "")),
            manifest_version=str(data.get("manifestVersion", "")),
            installed_by=str(data.get("installedBy", "")),
            installed_at=str(data.get("installedAt", "")),
        )


@dataclass(frozen=True, slots=True)
class CurrentApplication:
    """Application and bot identity associated with the current credential."""

    id: str
    name: str
    description: str
    public: bool
    permissions: tuple[str, ...]
    bot: PlatformBotIdentity
    access_manifest: AccessManifest
    installations: tuple[InstallationSnapshot, ...]

    @property
    def granted_capabilities(self) -> tuple[str, ...]:
        return tuple(
            dict.fromkeys(
                capability
                for installation in self.installations
                for capability in installation.granted_capabilities
            )
        )

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
            access_manifest=AccessManifest.from_dict(_object(data.get("accessManifest"))),
            installations=tuple(
                InstallationSnapshot.from_dict(item)
                for item in data.get("installations", ())
                if isinstance(item, Mapping)
            ),
        )


@dataclass(frozen=True, slots=True)
class StartupDiagnostics:
    application_id: str
    bot_id: str
    api_version: str
    environment: str
    service_status: str
    manifest_capabilities: tuple[str, ...]
    granted_capabilities: tuple[str, ...]
    unavailable_capabilities: tuple[str, ...]
    enabled_features: tuple[str, ...]


@dataclass(frozen=True, slots=True)
class GatewaySessionStartLimit:
    total: int
    remaining: int
    reset_after_ms: int
    max_concurrency: int


@dataclass(frozen=True, slots=True)
class GatewayDiscovery:
    url: str
    recommended_shards: int
    session_start_limit: GatewaySessionStartLimit

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> Self:
        limit = data.get("sessionStartLimit")
        if not isinstance(limit, dict):
            raise ValueError("gateway discovery is missing sessionStartLimit")
        return cls(
            url=str(data["url"]),
            recommended_shards=int(data["recommendedShards"]),
            session_start_limit=GatewaySessionStartLimit(
                total=int(limit["total"]),
                remaining=int(limit["remaining"]),
                reset_after_ms=int(limit["resetAfterMs"]),
                max_concurrency=int(limit["maxConcurrency"]),
            ),
        )
