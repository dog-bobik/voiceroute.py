"""Domain-specific VoiceRoute API clients."""

from voiceroute.api.bots import BotsAPI
from voiceroute.api.communities import CommunitiesAPI
from voiceroute.api.messages import MessagesAPI

__all__ = ["BotsAPI", "CommunitiesAPI", "MessagesAPI"]
