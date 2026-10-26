"""Automatic moderation endpoints."""

import unicodedata

from voiceroute.models import AutoModConfig
from voiceroute.transport import HTTPTransport


class AutoModAPI:
    """Read and replace a community's automatic moderation policy."""

    def __init__(self, transport: HTTPTransport) -> None:
        self._transport = transport

    async def get(self, community_id: str) -> AutoModConfig:
        payload = await self._transport.request("GET", f"/api/communities/{community_id}/automod")
        raw_config = payload.get("config") if payload else None
        return AutoModConfig.from_dict(raw_config if isinstance(raw_config, dict) else {})

    async def update(self, community_id: str, config: AutoModConfig) -> AutoModConfig:
        normalized = _validate(config)
        payload = await self._transport.request(
            "PUT",
            f"/api/communities/{community_id}/automod",
            json=normalized.to_dict(),
        )
        raw_config = payload.get("config") if payload else None
        if not isinstance(raw_config, dict):
            raise RuntimeError("VoiceRoute returned no AutoMod configuration")
        return AutoModConfig.from_dict(raw_config)


def _validate(config: AutoModConfig) -> AutoModConfig:
    words = tuple(
        dict.fromkeys(unicodedata.normalize("NFC", word.strip()) for word in config.blocked_words)
    )
    if len(words) > 100 or any(not word or len(word) > 64 for word in words):
        raise ValueError("blocked_words must contain up to 100 non-empty words of 64 characters")
    limits = {
        "max_mentions": (config.max_mentions, 100),
        "spam_limit": (config.spam_limit, 30),
        "slowmode_seconds": (config.slowmode_seconds, 21600),
    }
    for name, (value, maximum) in limits.items():
        if isinstance(value, bool) or not 0 <= value <= maximum:
            raise ValueError(f"{name} must be between 0 and {maximum}")
    return AutoModConfig(
        enabled=config.enabled,
        blocked_words=words,
        max_mentions=config.max_mentions,
        spam_limit=config.spam_limit,
        block_duplicates=config.block_duplicates,
        slowmode_seconds=config.slowmode_seconds,
    )
