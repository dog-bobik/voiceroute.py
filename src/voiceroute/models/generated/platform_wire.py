# ruff: noqa: E501, I001
# fmt: off
"""Generated VoiceRoute wire DTOs; do not edit."""

from __future__ import annotations

from typing import Any, Literal, NotRequired, TypeAlias, TypedDict


SOURCE_HASHES = (
    '52046f405d55f938223f5695fcbb644eaaad687b0df943e1af1b19700bd921be',
)


class AccessManifestV1(TypedDict):
    capabilities: list[Literal['messages', 'messageContent', 'members', 'reactions', 'polls', 'threads', 'moderation', 'presence', 'voiceStates', 'auditLog'] | str]
    catalog_version: Any
    hash: str
    permissions: list[Literal['viewChannel', 'readMessageHistory', 'sendMessages', 'attachFiles', 'addReactions', 'manageMessages', 'createPublicThreads', 'createPrivateThreads', 'sendMessagesInThreads', 'manageThreads', 'connect', 'speak', 'stream', 'listen', 'useApplicationCommands', 'mentionEveryone', 'muteMembers', 'deafenMembers', 'moveMembers', 'manageChannels', 'manageRoles', 'manageCommunity', 'createInvites', 'kickMembers', 'banMembers', 'moderateMembers', 'changeNickname', 'manageNicknames', 'viewAuditLog', 'manageStage', 'requestToSpeak', 'manageExpressions', 'useSoundboard', 'administrator'] | str]
    schema_version: Any
    scopes: list[str]
    version: str


class ActionRow(TypedDict):
    components: list[MessageComponent]
    type: Any


class AllowedMentions(TypedDict):
    parse: NotRequired[list[Literal['users', 'roles', 'everyone'] | str]]
    replied_user: NotRequired[bool]
    roles: NotRequired[list[str]]
    users: NotRequired[list[str]]


class ApplicationDiagnostics(TypedDict):
    installations: int
    publisher: dict[str, Any]
    sessions: list[dict[str, Any]]


class ApplicationDm(TypedDict):
    application: dict[str, Any]
    application_id: str
    blocked: bool
    can_send: bool
    created_at: str
    id: str
    owner_user_id: str
    sequence: str
    type: Any
    updated_at: str
    version: str


class ApplicationMetadata(TypedDict):
    application_id: str
    audio_retention_days: int | None
    banner: dict[str, Any] | Any
    deletion_url: str | None
    icon: dict[str, Any] | Any
    privacy_url: str | None
    support_url: str | None
    terms_url: str | None
    updated_at: str | None
    version: str


class ApplicationPrivacy(TypedDict):
    application_id: str
    blocked: bool
    deletion_request: dict[str, Any] | Any
    history_count: int
    version: str


class ApplicationProfile(TypedDict):
    application_id: str
    audio_retention_days: int | None
    banner: dict[str, Any] | Any
    deletion_url: str | None
    description: str
    icon: dict[str, Any] | Any
    id: str
    name: str
    privacy_url: str | None
    support_url: str | None
    terms_url: str | None
    updated_at: str | None
    version: str


class ApplicationTeam(TypedDict):
    application_id: str
    invitations: list[dict[str, Any]]
    members: list[dict[str, Any]]
    owner: dict[str, Any]
    role: Literal['owner', 'administrator', 'developer', 'security_manager', 'analyst'] | str
    transfers: list[dict[str, Any]]
    version: str


class Capabilities(TypedDict):
    api_version: Any
    automatic_event_families: list[Literal['communities', 'interactions', 'miniApps', 'webhooks'] | str]
    event_capabilities: list[Literal['messages', 'messageContent', 'members', 'reactions', 'polls', 'threads', 'moderation', 'presence', 'voiceStates', 'auditLog'] | str]
    events: list[Literal['APPLICATION_UPDATED', 'CHANNEL_ORDER_UPDATED', 'ROLE_ORDER_UPDATED', 'CATEGORY_CREATED', 'CATEGORY_UPDATED', 'CATEGORY_DELETED', 'CATEGORY_ORDER_UPDATED', 'THREAD_CREATED', 'THREAD_UPDATED', 'THREAD_DELETED', 'FORUM_UPDATED', 'INVITE_CREATED', 'INVITE_DELETED', 'BAN_CREATED', 'BAN_DELETED', 'TIMEOUT_UPDATED', 'AUTOMOD_RULE_CREATED', 'AUTOMOD_RULE_UPDATED', 'AUTOMOD_RULE_DELETED', 'AUDIT_LOG_ENTRY_CREATED', 'WEBHOOK_CREATED', 'WEBHOOK_UPDATED', 'WEBHOOK_DELETED', 'VOICE_STATE_UPDATED', 'VOICE_SERVER_UPDATED', 'VOICE_RECEIVE_STARTED', 'VOICE_RECEIVE_STOPPED', 'STAGE_UPDATED', 'SOUNDBOARD_PLAYED', 'EXPRESSION_CREATED', 'EXPRESSION_UPDATED', 'EXPRESSION_DELETED', 'MINI_APP_SESSION_OPENED', 'MINI_APP_SESSION_CLOSED', 'MINI_APP_ACTION_CREATED', 'MINI_APP_ACTION_CANCELLED', 'MINI_APP_STATE_UPDATED', 'MINI_APP_POLICY_UPDATED', 'MINI_APP_ACCESS_REVOKED', 'PRESENCE_UPDATED', 'COMMUNITY_AVAILABLE', 'COMMUNITY_UPDATED', 'COMMUNITY_DELETED', 'CHANNEL_CREATED', 'CHANNEL_UPDATED', 'CHANNEL_DELETED', 'CHANNEL_PERMISSIONS_UPDATED', 'ROLE_CREATED', 'ROLE_UPDATED', 'ROLE_DELETED', 'MEMBER_JOINED', 'MEMBER_UPDATED', 'MEMBER_LEFT', 'MESSAGE_CREATED', 'MESSAGE_UPDATED', 'MESSAGE_DELETED', 'MESSAGE_PINS_UPDATED', 'REACTION_ADDED', 'REACTION_REMOVED', 'INSTALLATION_CREATED', 'INSTALLATION_UPDATED', 'INSTALLATION_DELETED', 'INTERACTION_CREATED', 'DIRECT_MESSAGE_CREATED', 'DIRECT_MESSAGE_UPDATED', 'DIRECT_MESSAGE_DELETED', 'USER_INSTALLATION_CREATED', 'USER_INSTALLATION_UPDATED', 'USER_INSTALLATION_DELETED', 'APPLICATION_USER_DATA_DELETION_REQUESTED', 'ATTACHMENT_SCAN_COMPLETED', 'MESSAGES_BULK_DELETED', 'TYPING_STARTED', 'REACTIONS_CLEARED', 'THREAD_MEMBER_UPDATED', 'THREAD_MEMBERS_UPDATED', 'COMMUNITY_UNAVAILABLE', 'MEMBERS_CHUNK', 'AUTOMOD_ACTION_EXECUTED', 'POLL_CREATED', 'POLL_VOTE_ADDED', 'POLL_VOTE_REMOVED', 'POLL_CLOSED'] | str]
    features: dict[str, Any]
    gateway: dict[str, Any]
    legacy: dict[str, Any]
    maturity: Any
    stage: NotRequired[str]


class Command(TypedDict):
    application_id: str
    contexts: list[Literal['COMMUNITY', 'BOT_DM', 'PRIVATE_CHANNEL'] | str]
    default_member_permissions: list[Literal['viewChannel', 'readMessageHistory', 'sendMessages', 'attachFiles', 'addReactions', 'manageMessages', 'createPublicThreads', 'createPrivateThreads', 'sendMessagesInThreads', 'manageThreads', 'connect', 'speak', 'stream', 'listen', 'useApplicationCommands', 'mentionEveryone', 'muteMembers', 'deafenMembers', 'moveMembers', 'manageChannels', 'manageRoles', 'manageCommunity', 'createInvites', 'kickMembers', 'banMembers', 'moderateMembers', 'changeNickname', 'manageNicknames', 'viewAuditLog', 'manageStage', 'requestToSpeak', 'manageExpressions', 'useSoundboard', 'administrator'] | str]
    description: str
    description_localizations: dict[str, Any]
    id: str
    name: str
    name_localizations: dict[str, Any]
    nsfw: Any
    options: list[CommandOption]
    scope: dict[str, Any]
    type: Literal['CHAT_INPUT', 'USER', 'MESSAGE'] | str
    version: str


class CommandChoice(TypedDict):
    name: str
    name_localizations: NotRequired[dict[str, Any]]
    value: Any


class CommandInput(TypedDict):
    contexts: NotRequired[list[Literal['COMMUNITY', 'BOT_DM', 'PRIVATE_CHANNEL'] | str]]
    default_member_permissions: NotRequired[list[Literal['viewChannel', 'readMessageHistory', 'sendMessages', 'attachFiles', 'addReactions', 'manageMessages', 'createPublicThreads', 'createPrivateThreads', 'sendMessagesInThreads', 'manageThreads', 'connect', 'speak', 'stream', 'listen', 'useApplicationCommands', 'mentionEveryone', 'muteMembers', 'deafenMembers', 'moveMembers', 'manageChannels', 'manageRoles', 'manageCommunity', 'createInvites', 'kickMembers', 'banMembers', 'moderateMembers', 'changeNickname', 'manageNicknames', 'viewAuditLog', 'manageStage', 'requestToSpeak', 'manageExpressions', 'useSoundboard', 'administrator'] | str]]
    description: NotRequired[str]
    description_localizations: NotRequired[dict[str, Any]]
    name: str
    name_localizations: NotRequired[dict[str, Any]]
    nsfw: NotRequired[Any]
    options: NotRequired[list[CommandOption]]
    type: NotRequired[Literal['CHAT_INPUT', 'USER', 'MESSAGE'] | str]


class CommandOption(TypedDict):
    autocomplete: NotRequired[bool]
    channel_types: NotRequired[list[Literal['text', 'voice'] | str]]
    choices: NotRequired[list[CommandChoice]]
    description: str
    description_localizations: NotRequired[dict[str, Any]]
    max_length: NotRequired[int]
    max_value: NotRequired[float]
    min_length: NotRequired[int]
    min_value: NotRequired[float]
    name: str
    name_localizations: NotRequired[dict[str, Any]]
    options: NotRequired[list[CommandOption]]
    required: NotRequired[bool]
    type: Literal['SUB_COMMAND', 'SUB_COMMAND_GROUP', 'STRING', 'INTEGER', 'NUMBER', 'BOOLEAN', 'USER', 'CHANNEL', 'ROLE', 'MENTIONABLE', 'ATTACHMENT'] | str


class CommandPatch(TypedDict):
    contexts: NotRequired[list[Literal['COMMUNITY', 'BOT_DM', 'PRIVATE_CHANNEL'] | str]]
    default_member_permissions: NotRequired[list[Literal['viewChannel', 'readMessageHistory', 'sendMessages', 'attachFiles', 'addReactions', 'manageMessages', 'createPublicThreads', 'createPrivateThreads', 'sendMessagesInThreads', 'manageThreads', 'connect', 'speak', 'stream', 'listen', 'useApplicationCommands', 'mentionEveryone', 'muteMembers', 'deafenMembers', 'moveMembers', 'manageChannels', 'manageRoles', 'manageCommunity', 'createInvites', 'kickMembers', 'banMembers', 'moderateMembers', 'changeNickname', 'manageNicknames', 'viewAuditLog', 'manageStage', 'requestToSpeak', 'manageExpressions', 'useSoundboard', 'administrator'] | str]]
    description: NotRequired[str]
    description_localizations: NotRequired[dict[str, Any]]
    name: NotRequired[str]
    name_localizations: NotRequired[dict[str, Any]]
    nsfw: NotRequired[Any]
    options: NotRequired[list[CommandOption]]
    type: NotRequired[Literal['CHAT_INPUT', 'USER', 'MESSAGE'] | str]


class CommandPermissionTarget(TypedDict):
    allow: bool
    id: NotRequired[str]
    type: Literal['role', 'user', 'channel', 'allMembers', 'allChannels'] | str


class CommandPermissions(TypedDict):
    command_id: str
    community_id: str
    targets: list[CommandPermissionTarget]
    version: str


class CommunityMention(TypedDict):
    author_name: str
    channel_id: str
    channel_name: str
    community_id: str
    community_name: str
    created_at: str
    id: str
    message_id: str
    message_seq: str
    read_at: str | None
    silent: bool
    thread_id: str | None


class DeliveryLease(TypedDict):
    event: EventEnvelope
    lease_expires_at: str
    lease_id: str


class DeliveryLog(TypedDict):
    acknowledged_at: str | None
    attempts: int
    event: Literal['APPLICATION_UPDATED', 'CHANNEL_ORDER_UPDATED', 'ROLE_ORDER_UPDATED', 'CATEGORY_CREATED', 'CATEGORY_UPDATED', 'CATEGORY_DELETED', 'CATEGORY_ORDER_UPDATED', 'THREAD_CREATED', 'THREAD_UPDATED', 'THREAD_DELETED', 'FORUM_UPDATED', 'INVITE_CREATED', 'INVITE_DELETED', 'BAN_CREATED', 'BAN_DELETED', 'TIMEOUT_UPDATED', 'AUTOMOD_RULE_CREATED', 'AUTOMOD_RULE_UPDATED', 'AUTOMOD_RULE_DELETED', 'AUDIT_LOG_ENTRY_CREATED', 'WEBHOOK_CREATED', 'WEBHOOK_UPDATED', 'WEBHOOK_DELETED', 'VOICE_STATE_UPDATED', 'VOICE_SERVER_UPDATED', 'VOICE_RECEIVE_STARTED', 'VOICE_RECEIVE_STOPPED', 'STAGE_UPDATED', 'SOUNDBOARD_PLAYED', 'EXPRESSION_CREATED', 'EXPRESSION_UPDATED', 'EXPRESSION_DELETED', 'MINI_APP_SESSION_OPENED', 'MINI_APP_SESSION_CLOSED', 'MINI_APP_ACTION_CREATED', 'MINI_APP_ACTION_CANCELLED', 'MINI_APP_STATE_UPDATED', 'MINI_APP_POLICY_UPDATED', 'MINI_APP_ACCESS_REVOKED', 'PRESENCE_UPDATED', 'COMMUNITY_AVAILABLE', 'COMMUNITY_UPDATED', 'COMMUNITY_DELETED', 'CHANNEL_CREATED', 'CHANNEL_UPDATED', 'CHANNEL_DELETED', 'CHANNEL_PERMISSIONS_UPDATED', 'ROLE_CREATED', 'ROLE_UPDATED', 'ROLE_DELETED', 'MEMBER_JOINED', 'MEMBER_UPDATED', 'MEMBER_LEFT', 'MESSAGE_CREATED', 'MESSAGE_UPDATED', 'MESSAGE_DELETED', 'MESSAGE_PINS_UPDATED', 'REACTION_ADDED', 'REACTION_REMOVED', 'INSTALLATION_CREATED', 'INSTALLATION_UPDATED', 'INSTALLATION_DELETED', 'INTERACTION_CREATED', 'DIRECT_MESSAGE_CREATED', 'DIRECT_MESSAGE_UPDATED', 'DIRECT_MESSAGE_DELETED', 'USER_INSTALLATION_CREATED', 'USER_INSTALLATION_UPDATED', 'USER_INSTALLATION_DELETED', 'APPLICATION_USER_DATA_DELETION_REQUESTED', 'ATTACHMENT_SCAN_COMPLETED', 'MESSAGES_BULK_DELETED', 'TYPING_STARTED', 'REACTIONS_CLEARED', 'THREAD_MEMBER_UPDATED', 'THREAD_MEMBERS_UPDATED', 'COMMUNITY_UNAVAILABLE', 'MEMBERS_CHUNK', 'AUTOMOD_ACTION_EXECUTED', 'POLL_CREATED', 'POLL_VOTE_ADDED', 'POLL_VOTE_REMOVED', 'POLL_CLOSED'] | str
    expires_at: str
    id: str
    last_code: str | None
    last_latency_ms: int | None
    last_status: int | None
    occurred_at: str
    sequence: str
    status: Literal['pending', 'inflight', 'acknowledged', 'dead', 'skipped'] | str


class DeliveryStatus(TypedDict):
    attempts: dict[str, Any]
    deliveries: dict[str, Any]
    disconnects: list[dict[str, Any]]
    interactions: dict[str, Any]
    rate_limit: dict[str, Any]
    retention_hours: Any
    window_hours: Any


class DeveloperApplication(TypedDict):
    access_manifest: NotRequired[dict[str, Any]]
    actions: list[Literal['read', 'commands', 'general', 'install', 'security', 'credentials', 'team', 'transfer', 'delete', 'analytics', 'audit'] | str]
    bot: dict[str, Any] | Any
    capabilities: list[Literal['messages', 'messageContent', 'members', 'reactions', 'polls', 'threads', 'moderation', 'presence', 'voiceStates', 'auditLog'] | str]
    created_at: str
    description: str
    has_token: bool
    id: str
    install_url: str
    installation_gaps: NotRequired[list[dict[str, Any]]]
    last_used_at: str | None
    manifest_version: str
    name: str
    owner_user_id: str
    permissions: list[Literal['viewChannel', 'readMessageHistory', 'sendMessages', 'attachFiles', 'addReactions', 'manageMessages', 'createPublicThreads', 'createPrivateThreads', 'sendMessagesInThreads', 'manageThreads', 'connect', 'speak', 'stream', 'listen', 'useApplicationCommands', 'mentionEveryone', 'muteMembers', 'deafenMembers', 'moveMembers', 'manageChannels', 'manageRoles', 'manageCommunity', 'createInvites', 'kickMembers', 'banMembers', 'moderateMembers', 'changeNickname', 'manageNicknames', 'viewAuditLog', 'manageStage', 'requestToSpeak', 'manageExpressions', 'useSoundboard', 'administrator'] | str]
    public: bool
    team_role: Literal['owner', 'administrator', 'developer', 'security_manager', 'analyst'] | str
    token_updated_at: str | None
    updated_at: str


class DeveloperAuditEntry(TypedDict):
    action: str
    actor: str
    actor_label: str
    created_at: str
    data: dict[str, Any]
    id: str
    reason: str | None
    trace_id: str | None


class EffectivePermissions(TypedDict):
    channel_id: str | None
    community_id: str
    permissions: list[Literal['viewChannel', 'readMessageHistory', 'sendMessages', 'attachFiles', 'addReactions', 'manageMessages', 'createPublicThreads', 'createPrivateThreads', 'sendMessagesInThreads', 'manageThreads', 'connect', 'speak', 'stream', 'listen', 'useApplicationCommands', 'mentionEveryone', 'muteMembers', 'deafenMembers', 'moveMembers', 'manageChannels', 'manageRoles', 'manageCommunity', 'createInvites', 'kickMembers', 'banMembers', 'moderateMembers', 'changeNickname', 'manageNicknames', 'viewAuditLog', 'manageStage', 'requestToSpeak', 'manageExpressions', 'useSoundboard', 'administrator'] | str]
    registry_version: Literal['2', '3'] | str
    role_ids: list[str]
    timeout_until: str | None
    user_id: str


class Embed(TypedDict):
    author: NotRequired[dict[str, Any]]
    color: NotRequired[int]
    description: NotRequired[str]
    fields: NotRequired[list[dict[str, Any]]]
    footer: NotRequired[dict[str, Any]]
    image: NotRequired[dict[str, Any]]
    thumbnail: NotRequired[dict[str, Any]]
    timestamp: NotRequired[str]
    title: NotRequired[str]
    url: NotRequired[str]


class Error(TypedDict):
    error: dict[str, Any]


EventEnvelope: TypeAlias = dict[str, Any]


class EventSubscription(TypedDict):
    application_id: str
    community_ids: list[str]
    created_at: str
    delivery_count: NotRequired[int]
    enabled: bool
    event_types: list[Literal['APPLICATION_UPDATED', 'CHANNEL_ORDER_UPDATED', 'ROLE_ORDER_UPDATED', 'CATEGORY_CREATED', 'CATEGORY_UPDATED', 'CATEGORY_DELETED', 'CATEGORY_ORDER_UPDATED', 'THREAD_CREATED', 'THREAD_UPDATED', 'THREAD_DELETED', 'FORUM_UPDATED', 'INVITE_CREATED', 'INVITE_DELETED', 'BAN_CREATED', 'BAN_DELETED', 'TIMEOUT_UPDATED', 'AUTOMOD_RULE_CREATED', 'AUTOMOD_RULE_UPDATED', 'AUTOMOD_RULE_DELETED', 'AUDIT_LOG_ENTRY_CREATED', 'WEBHOOK_CREATED', 'WEBHOOK_UPDATED', 'WEBHOOK_DELETED', 'VOICE_STATE_UPDATED', 'VOICE_SERVER_UPDATED', 'VOICE_RECEIVE_STARTED', 'VOICE_RECEIVE_STOPPED', 'STAGE_UPDATED', 'SOUNDBOARD_PLAYED', 'EXPRESSION_CREATED', 'EXPRESSION_UPDATED', 'EXPRESSION_DELETED', 'MINI_APP_SESSION_OPENED', 'MINI_APP_SESSION_CLOSED', 'MINI_APP_ACTION_CREATED', 'MINI_APP_ACTION_CANCELLED', 'MINI_APP_STATE_UPDATED', 'MINI_APP_POLICY_UPDATED', 'MINI_APP_ACCESS_REVOKED', 'PRESENCE_UPDATED', 'COMMUNITY_AVAILABLE', 'COMMUNITY_UPDATED', 'COMMUNITY_DELETED', 'CHANNEL_CREATED', 'CHANNEL_UPDATED', 'CHANNEL_DELETED', 'CHANNEL_PERMISSIONS_UPDATED', 'ROLE_CREATED', 'ROLE_UPDATED', 'ROLE_DELETED', 'MEMBER_JOINED', 'MEMBER_UPDATED', 'MEMBER_LEFT', 'MESSAGE_CREATED', 'MESSAGE_UPDATED', 'MESSAGE_DELETED', 'MESSAGE_PINS_UPDATED', 'REACTION_ADDED', 'REACTION_REMOVED', 'INSTALLATION_CREATED', 'INSTALLATION_UPDATED', 'INSTALLATION_DELETED', 'INTERACTION_CREATED', 'DIRECT_MESSAGE_CREATED', 'DIRECT_MESSAGE_UPDATED', 'DIRECT_MESSAGE_DELETED', 'USER_INSTALLATION_CREATED', 'USER_INSTALLATION_UPDATED', 'USER_INSTALLATION_DELETED', 'APPLICATION_USER_DATA_DELETION_REQUESTED', 'ATTACHMENT_SCAN_COMPLETED', 'MESSAGES_BULK_DELETED', 'TYPING_STARTED', 'REACTIONS_CLEARED', 'THREAD_MEMBER_UPDATED', 'THREAD_MEMBERS_UPDATED', 'COMMUNITY_UNAVAILABLE', 'AUTOMOD_ACTION_EXECUTED', 'POLL_CREATED', 'POLL_VOTE_ADDED', 'POLL_VOTE_REMOVED', 'POLL_CLOSED'] | str]
    id: str
    max_attempts: int
    transport: Literal['webhook', 'pull', 'websocket'] | str
    updated_at: str
    url: str | None
    version: str


class File(TypedDict):
    application_id: str | None
    author_user_id: str
    checksum_sha256: str
    content_type: str
    description: str
    expires_at: str | None
    filename: str
    height: int | None
    id: str
    scan_status: Any
    size: str
    spoiler: bool
    url: str
    width: int | None


class GatewayDiscovery(TypedDict):
    recommended_shards: Any
    session_start_limit: dict[str, Any]
    url: str


class Installation(TypedDict):
    application: dict[str, Any]
    application_id: str
    community_id: str | None
    created_at: str
    id: str
    owner_user_id: str
    permissions: list[str]
    revoked_at: str | None
    scopes: list[Literal['identify', 'profile.read', 'communities.read', 'communities.members.read', 'applications.commands', 'applications.commands.permissions.update', 'bot', 'webhook.incoming', 'dm.read', 'dm.write', 'voice.connect', 'voice.receive', 'voice.transmit'] | str]
    type: Literal['COMMUNITY', 'USER'] | str
    updated_at: str
    version: NotRequired[str]


class InstallationSnapshotV1(TypedDict):
    application_id: str
    catalog_version: Any
    community_id: str
    granted_capabilities: list[Literal['messages', 'messageContent', 'members', 'reactions', 'polls', 'threads', 'moderation', 'presence', 'voiceStates', 'auditLog'] | str]
    granted_permissions: list[Literal['viewChannel', 'readMessageHistory', 'sendMessages', 'attachFiles', 'addReactions', 'manageMessages', 'createPublicThreads', 'createPrivateThreads', 'sendMessagesInThreads', 'manageThreads', 'connect', 'speak', 'stream', 'listen', 'useApplicationCommands', 'mentionEveryone', 'muteMembers', 'deafenMembers', 'moveMembers', 'manageChannels', 'manageRoles', 'manageCommunity', 'createInvites', 'kickMembers', 'banMembers', 'moderateMembers', 'changeNickname', 'manageNicknames', 'viewAuditLog', 'manageStage', 'requestToSpeak', 'manageExpressions', 'useSoundboard', 'administrator'] | str]
    id: str
    installed_at: str
    installed_by: str
    manifest_hash: str
    manifest_version: str
    schema_version: Any
    scopes: list[str]


InteractionCallback: TypeAlias = dict[str, Any]


class InteractionMessage(TypedDict):
    allowed_mentions: AllowedMentions
    attachments: list[File]
    components: list[ActionRow]
    content: str
    embeds: list[Embed]
    flags: list[Literal['EPHEMERAL', 'SUPPRESS_EMBEDS', 'SUPPRESS_NOTIFICATIONS', 'HAS_COMPONENTS', 'LOADING', 'FAILED'] | str]
    id: str
    message_seq: str | None
    reply: dict[str, Any] | Any
    reply_snapshot: NotRequired[ReplySnapshot | Any]
    version: str


class InteractionMessageInput(TypedDict):
    allowed_mentions: NotRequired[AllowedMentions]
    attachments: NotRequired[list[dict[str, Any]]]
    components: NotRequired[list[ActionRow]]
    content: NotRequired[str]
    embeds: NotRequired[list[Embed]]
    flags: NotRequired[list[Literal['EPHEMERAL', 'SUPPRESS_EMBEDS', 'SUPPRESS_NOTIFICATIONS', 'FAILED'] | str]]
    reply: NotRequired[dict[str, Any] | Any]


class InteractionRequest(TypedDict):
    autocomplete_revision: NotRequired[str]
    autocomplete_session: NotRequired[str]
    command_id: str
    focused: NotRequired[str]
    locale: NotRequired[str]
    options: NotRequired[dict[str, Any]]
    path: NotRequired[list[str]]
    target_id: NotRequired[str]
    type: NotRequired[Literal['APPLICATION_COMMAND', 'AUTOCOMPLETE'] | str]
    version: str


class InteractionStatus(TypedDict):
    body: str | None
    choices: NotRequired[list[CommandChoice]]
    deferred: bool
    ephemeral: bool
    expires_at: str
    flags: NotRequired[list[Literal['EPHEMERAL', 'LOADING'] | str]]
    id: str
    message_seq: str | None
    messages: list[InteractionMessage]
    mini_app: NotRequired[dict[str, Any]]
    modal: NotRequired[Modal]
    status: Literal['pending', 'completed', 'expired'] | str


class Message(TypedDict):
    allowed_mentions: AllowedMentions
    application_id: str | None
    attachments: list[File]
    author: dict[str, Any]
    channel_id: str
    community_id: str
    components: list[ActionRow]
    content: str
    content_redacted: bool
    created_at: str
    edited_at: str | None
    embeds: list[Embed]
    flags: list[Literal['EPHEMERAL', 'SUPPRESS_EMBEDS', 'SUPPRESS_NOTIFICATIONS', 'HAS_COMPONENTS', 'LOADING', 'FAILED'] | str]
    id: str
    pinned: bool
    poll: NotRequired[Poll | Any]
    reply: dict[str, Any] | Any
    reply_snapshot: ReplySnapshot | Any
    sequence: str
    thread_id: NotRequired[str]
    version: str
    webhook: dict[str, Any] | Any


class MessageComponent(TypedDict):
    accessibility_label: NotRequired[str]
    channel_types: NotRequired[list[Literal['text', 'voice'] | str]]
    custom_id: NotRequired[str]
    disabled: NotRequired[bool]
    emoji: NotRequired[str]
    label: NotRequired[str]
    max_values: NotRequired[int]
    min_values: NotRequired[int]
    options: NotRequired[list[dict[str, Any]]]
    placeholder: NotRequired[str]
    style: NotRequired[Literal['PRIMARY', 'SECONDARY', 'SUCCESS', 'DANGER', 'LINK'] | str]
    type: Literal['BUTTON', 'STRING_SELECT', 'USER_SELECT', 'ROLE_SELECT', 'CHANNEL_SELECT', 'MENTIONABLE_SELECT'] | str
    url: NotRequired[str]


class MessageInput(TypedDict):
    allowed_mentions: NotRequired[AllowedMentions]
    attachments: NotRequired[list[dict[str, Any]]]
    components: NotRequired[list[ActionRow]]
    content: NotRequired[str]
    embeds: NotRequired[list[Embed]]
    flags: NotRequired[list[Literal['EPHEMERAL', 'SUPPRESS_EMBEDS', 'SUPPRESS_NOTIFICATIONS', 'FAILED'] | str]]
    reply: NotRequired[dict[str, Any] | Any]


class MiniAppAction(TypedDict):
    accepted_at: str
    action_id: str
    client_action_id: str
    expected_state_version: str
    expires_at: str
    instance_id: str
    name: str
    result: Any
    status: Literal['PENDING', 'ACKNOWLEDGED', 'COMPLETED', 'REJECTED', 'FAILED', 'EXPIRED'] | str


class MiniAppBridgeMessage(TypedDict):
    bridge_version: Any
    data: NotRequired[Any]
    request_id: NotRequired[str]
    type: Literal['VR_MINI_APP_READY', 'VR_MINI_APP_INIT', 'VR_MINI_APP_REQUEST', 'VR_MINI_APP_RESPONSE', 'VR_MINI_APP_EVENT'] | str


class MiniAppConfiguration(TypedDict):
    application_id: str
    draft: MiniAppManifest | Any
    origins: list[dict[str, Any]]
    published: MiniAppManifest | Any
    published_version: str | None
    version: str


class MiniAppLaunch(TypedDict):
    bridge_version: Any
    expires_at: str
    instance_id: str
    launch_code: str
    launch_url: str
    session_id: str
    target_origin: str


class MiniAppManifest(TypedDict):
    action_policies: NotRequired[dict[str, Any]]
    allowed_origins: list[str]
    contexts: list[Literal['COMMUNITY', 'CHANNEL'] | str]
    deletion_url: str
    description: str
    enabled: bool
    external_backend: bool
    instance_scope: Literal['APPLICATION', 'INSTALLATION', 'COMMUNITY', 'CHANNEL', 'VOICE_CHANNEL', 'USER'] | str
    launch_policy: NotRequired[dict[str, Any]]
    launch_url: str
    name: str
    open_mode: NotRequired[Any]
    privacy_url: str
    read_policy: NotRequired[dict[str, Any]]
    requested_capabilities: NotRequired[list[str]]
    requested_fields: NotRequired[list[str]]
    retention_days: int
    terms_url: str
    voice_fallback: NotRequired[Literal['DENY', 'COMMUNITY', 'USER', 'APPLICATION_VOICE'] | str]
    window: NotRequired[dict[str, Any]]


class MiniAppState(TypedDict):
    instance_id: str
    state: Any
    updated_at: str
    updated_by: dict[str, Any]
    version: str


class Modal(TypedDict):
    components: list[dict[str, Any]]
    custom_id: str
    title: str


class OAuthConsent(TypedDict):
    access_manifest: NotRequired[dict[str, Any]]
    application: dict[str, Any]
    community_id: str | None
    consent_id: str
    installation_type: Literal['COMMUNITY', 'USER'] | str
    permissions: list[str]
    redirect_uri: str
    scopes: list[Literal['identify', 'profile.read', 'communities.read', 'communities.members.read', 'applications.commands', 'applications.commands.permissions.update', 'bot', 'webhook.incoming', 'dm.read', 'dm.write', 'voice.connect', 'voice.receive', 'voice.transmit'] | str]


class OAuthSettings(TypedDict):
    allowed_origins: list[str]
    application_id: str
    client_type: Literal['public', 'confidential'] | str
    default_scopes: list[Literal['identify', 'profile.read', 'communities.read', 'communities.members.read', 'applications.commands', 'applications.commands.permissions.update', 'bot', 'webhook.incoming', 'dm.read', 'dm.write', 'voice.connect', 'voice.receive', 'voice.transmit'] | str]
    installation_contexts: list[Literal['COMMUNITY', 'USER'] | str]
    redirect_uris: list[str]
    secrets: NotRequired[list[dict[str, Any]]]
    version: str


class OAuthSettingsInput(TypedDict):
    allowed_origins: NotRequired[list[str]]
    client_type: NotRequired[Literal['public', 'confidential'] | str]
    default_scopes: NotRequired[list[Literal['identify', 'profile.read', 'communities.read', 'communities.members.read', 'applications.commands', 'applications.commands.permissions.update', 'bot', 'webhook.incoming', 'dm.read', 'dm.write', 'voice.connect', 'voice.receive', 'voice.transmit'] | str]]
    installation_contexts: NotRequired[list[Literal['COMMUNITY', 'USER'] | str]]
    redirect_uris: NotRequired[list[str]]


class OAuthTokenRequest(TypedDict):
    client_id: NotRequired[str]
    client_secret: NotRequired[str]
    code: NotRequired[str]
    code_verifier: NotRequired[str]
    grant_type: Literal['authorization_code', 'refresh_token', 'client_credentials'] | str
    redirect_uri: NotRequired[str]
    refresh_token: NotRequired[str]
    scope: NotRequired[str]


class OAuthTokens(TypedDict):
    access_token: str
    expires_in: Any
    refresh_token: NotRequired[str]
    scope: str
    token_type: Any


class PermissionSimulation(TypedDict):
    added: list[Literal['viewChannel', 'readMessageHistory', 'sendMessages', 'attachFiles', 'addReactions', 'manageMessages', 'createPublicThreads', 'createPrivateThreads', 'sendMessagesInThreads', 'manageThreads', 'connect', 'speak', 'stream', 'listen', 'useApplicationCommands', 'mentionEveryone', 'muteMembers', 'deafenMembers', 'moveMembers', 'manageChannels', 'manageRoles', 'manageCommunity', 'createInvites', 'kickMembers', 'banMembers', 'moderateMembers', 'changeNickname', 'manageNicknames', 'viewAuditLog', 'manageStage', 'requestToSpeak', 'manageExpressions', 'useSoundboard', 'administrator'] | str]
    channel_id: str | None
    community_id: str
    dry_run: Any
    permissions: list[Literal['viewChannel', 'readMessageHistory', 'sendMessages', 'attachFiles', 'addReactions', 'manageMessages', 'createPublicThreads', 'createPrivateThreads', 'sendMessagesInThreads', 'manageThreads', 'connect', 'speak', 'stream', 'listen', 'useApplicationCommands', 'mentionEveryone', 'muteMembers', 'deafenMembers', 'moveMembers', 'manageChannels', 'manageRoles', 'manageCommunity', 'createInvites', 'kickMembers', 'banMembers', 'moderateMembers', 'changeNickname', 'manageNicknames', 'viewAuditLog', 'manageStage', 'requestToSpeak', 'manageExpressions', 'useSoundboard', 'administrator'] | str]
    registry_version: Literal['2', '3'] | str
    removed: list[Literal['viewChannel', 'readMessageHistory', 'sendMessages', 'attachFiles', 'addReactions', 'manageMessages', 'createPublicThreads', 'createPrivateThreads', 'sendMessagesInThreads', 'manageThreads', 'connect', 'speak', 'stream', 'listen', 'useApplicationCommands', 'mentionEveryone', 'muteMembers', 'deafenMembers', 'moveMembers', 'manageChannels', 'manageRoles', 'manageCommunity', 'createInvites', 'kickMembers', 'banMembers', 'moderateMembers', 'changeNickname', 'manageNicknames', 'viewAuditLog', 'manageStage', 'requestToSpeak', 'manageExpressions', 'useSoundboard', 'administrator'] | str]
    user_id: str


class Poll(TypedDict):
    anonymous: bool
    answers: list[dict[str, Any]]
    application_id: str
    channel_id: str
    closed_at: str | None
    closes_at: str
    community_id: str
    id: str
    message_id: str
    multiple: bool
    question: str
    results: PollResults
    selected_answer_ids: list[str]
    version: str


class PollInput(TypedDict):
    anonymous: NotRequired[bool]
    answers: list[str]
    duration_seconds: int
    multiple: NotRequired[bool]
    question: str


class PollResults(TypedDict):
    answers: list[dict[str, Any]]
    closed_at: str | None
    total_voters: int


class PrivateInteractionRequest(TypedDict):
    autocomplete_revision: NotRequired[str]
    autocomplete_session: NotRequired[str]
    channel_id: NotRequired[str]
    command_id: str
    context: Literal['BOT_DM', 'PRIVATE_CHANNEL'] | str
    conversation_id: NotRequired[str]
    focused: NotRequired[str]
    locale: NotRequired[str]
    options: NotRequired[dict[str, Any]]
    path: NotRequired[list[str]]
    target_id: NotRequired[str]
    type: NotRequired[Literal['APPLICATION_COMMAND', 'AUTOCOMPLETE'] | str]
    version: str


class PrivateMessage(TypedDict):
    allowed_mentions: AllowedMentions
    application_id: str
    attachments: list[File]
    author: dict[str, Any]
    channel_id: str
    components: list[ActionRow]
    content: str | None
    created_at: str
    deleted_at: str | None
    edited_at: str | None
    embeds: list[Embed]
    flags: list[Literal['EPHEMERAL', 'SUPPRESS_EMBEDS', 'SUPPRESS_NOTIFICATIONS', 'HAS_COMPONENTS', 'LOADING', 'FAILED'] | str]
    id: str
    owner_user_id: str
    reply: dict[str, Any] | Any
    reply_snapshot: dict[str, Any] | Any
    sequence: str
    version: str


class PrivateMessageInput(TypedDict):
    allowed_mentions: NotRequired[AllowedMentions]
    attachments: NotRequired[list[dict[str, Any]]]
    components: NotRequired[list[ActionRow]]
    content: NotRequired[str]
    embeds: NotRequired[list[Embed]]
    flags: NotRequired[list[Literal['EPHEMERAL', 'SUPPRESS_EMBEDS', 'SUPPRESS_NOTIFICATIONS', 'FAILED'] | str]]
    reply: NotRequired[dict[str, Any] | Any]


class ReplySnapshot(TypedDict):
    author_id: str | None
    author_kind: NotRequired[Literal['USER', 'WEBHOOK'] | str]
    author_name: str
    content: str | None
    deleted: bool
    message_id: str
    webhook_id: NotRequired[str]


class SandboxFault(TypedDict):
    delay_ms: int
    expires_at: str
    id: str
    kind: Literal['RATE_LIMIT', 'SERVER_ERROR', 'DELAY'] | str
    path: Literal['/applications/@me', '/gateway'] | str
    remaining: int


class SandboxRun(TypedDict):
    application_id: str
    channel_id: str
    community_id: str
    created_at: str
    event_count: int
    expires_at: str
    faults: list[SandboxFault]
    id: str
    members: list[dict[str, Any]]


class Upload(TypedDict):
    application_id: str
    attachment: File | Any
    channel_id: str
    checksum_sha256: str
    community_id: str
    created_at: str
    description: str
    expires_at: str | None
    failure_code: str | None
    filename: str
    id: str
    part_count: int
    part_size: Any
    parts: list[dict[str, Any]]
    received_size: str
    size: str
    spoiler: bool
    status: Literal['pending', 'uploading', 'scanning', 'ready', 'rejected', 'expired'] | str
    thread_id: NotRequired[str]


class UploadInput(TypedDict):
    channel_id: str
    checksum_sha256: str
    community_id: str
    description: NotRequired[str]
    filename: str
    size: str
    spoiler: NotRequired[bool]
    thread_id: NotRequired[str]


class UserVoiceState(TypedDict):
    channel_id: str
    community_id: str
    user_id: str


class VoiceConnection(TypedDict):
    audio: dict[str, Any]
    connection_id: str
    expires_at: str
    media_token: str
    media_web_socket_url: str


class VoicePolicy(TypedDict):
    allow_application_receive: bool
    community_id: str
    updated_at: str | None
    version: str


VoiceStateSnapshot: TypeAlias = dict[str, Any]
