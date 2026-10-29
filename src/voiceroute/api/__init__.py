"""Domain-specific VoiceRoute API clients."""

from voiceroute.api.application_commands import ApplicationCommandsAPI, CommandSyncDiff
from voiceroute.api.audit import AuditAPI
from voiceroute.api.automod import AutoModAPI
from voiceroute.api.bots import BotsAPI
from voiceroute.api.communities import CommunitiesAPI
from voiceroute.api.events import EventsAPI
from voiceroute.api.interactions import InteractionsAPI
from voiceroute.api.members import MembersAPI
from voiceroute.api.messages import MessagesAPI
from voiceroute.api.mini_apps import MiniAppsAPI, MiniAppState
from voiceroute.api.moderation import ModerationAPI
from voiceroute.api.platform import PlatformAPI
from voiceroute.api.roles import RolesAPI
from voiceroute.api.voice import VoiceAPI

__all__ = [
    "ApplicationCommandsAPI",
    "AuditAPI",
    "AutoModAPI",
    "BotsAPI",
    "CommandSyncDiff",
    "CommunitiesAPI",
    "EventsAPI",
    "InteractionsAPI",
    "MembersAPI",
    "MessagesAPI",
    "MiniAppState",
    "MiniAppsAPI",
    "ModerationAPI",
    "PlatformAPI",
    "RolesAPI",
    "VoiceAPI",
]
