"""Domain-specific VoiceRoute API clients."""

from voiceroute.api.application_commands import ApplicationCommandsAPI, CommandSyncDiff
from voiceroute.api.audit import AuditAPI
from voiceroute.api.automod import AutoModAPI
from voiceroute.api.bots import BotsAPI
from voiceroute.api.channels import CategoriesAPI, ChannelsAPI, TypingIndicator
from voiceroute.api.communities import CommunitiesAPI
from voiceroute.api.events import EventsAPI
from voiceroute.api.files import FileResource, FilesAPI
from voiceroute.api.interactions import InteractionsAPI
from voiceroute.api.members import MembersAPI
from voiceroute.api.messages import MessagesAPI
from voiceroute.api.mini_apps import MiniAppsAPI, MiniAppState
from voiceroute.api.moderation import ModerationAPI
from voiceroute.api.platform import PlatformAPI
from voiceroute.api.polls import PollsAPI
from voiceroute.api.private_messages import PrivateMessagesAPI
from voiceroute.api.roles import RolesAPI
from voiceroute.api.stickers import ExpressionsAPI, StickersAPI
from voiceroute.api.subscriptions import SubscriptionsAPI
from voiceroute.api.threads import ThreadsAPI
from voiceroute.api.uploads import Upload, UploadsAPI
from voiceroute.api.voice import VoiceAPI
from voiceroute.api.webhooks import MessageWebhookClient, WebhooksAPI

__all__ = [
    "ApplicationCommandsAPI",
    "AuditAPI",
    "AutoModAPI",
    "BotsAPI",
    "CategoriesAPI",
    "ChannelsAPI",
    "CommandSyncDiff",
    "CommunitiesAPI",
    "EventsAPI",
    "ExpressionsAPI",
    "FileResource",
    "FilesAPI",
    "InteractionsAPI",
    "MembersAPI",
    "MessageWebhookClient",
    "MessagesAPI",
    "MiniAppState",
    "MiniAppsAPI",
    "ModerationAPI",
    "PlatformAPI",
    "PollsAPI",
    "PrivateMessagesAPI",
    "RolesAPI",
    "StickersAPI",
    "SubscriptionsAPI",
    "ThreadsAPI",
    "TypingIndicator",
    "Upload",
    "UploadsAPI",
    "VoiceAPI",
    "WebhooksAPI",
]
