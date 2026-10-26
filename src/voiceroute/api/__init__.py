"""Domain-specific VoiceRoute API clients."""

from voiceroute.api.application_commands import ApplicationCommandsAPI
from voiceroute.api.bots import BotsAPI
from voiceroute.api.communities import CommunitiesAPI
from voiceroute.api.events import EventsAPI
from voiceroute.api.interactions import InteractionsAPI
from voiceroute.api.members import MembersAPI
from voiceroute.api.messages import MessagesAPI
from voiceroute.api.moderation import ModerationAPI
from voiceroute.api.roles import RolesAPI

__all__ = [
    "ApplicationCommandsAPI",
    "BotsAPI",
    "CommunitiesAPI",
    "EventsAPI",
    "InteractionsAPI",
    "MembersAPI",
    "MessagesAPI",
    "ModerationAPI",
    "RolesAPI",
]
