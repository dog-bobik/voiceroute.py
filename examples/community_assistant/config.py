"""Environment-backed configuration for the community assistant."""

from __future__ import annotations

import os
from collections.abc import Mapping
from dataclasses import dataclass
from pathlib import Path


@dataclass(frozen=True, slots=True)
class CommunityAssistantConfig:
    """Validated runtime settings loaded without exposing the bot token."""

    token: str
    base_url: str = "https://voiceroute.cc"
    community_id: str | None = None
    channel_id: str | None = None
    command_prefix: str = "/"
    cursor_path: Path = Path(".voiceroute/community-assistant.sqlite3")

    @classmethod
    def from_env(cls, environ: Mapping[str, str] | None = None) -> CommunityAssistantConfig:
        values = os.environ if environ is None else environ
        token = values.get("VOICEROUTE_BOT_TOKEN", "").strip()
        if not token:
            raise ValueError("VOICEROUTE_BOT_TOKEN is required")

        community_id = _optional(values.get("VOICEROUTE_COMMUNITY_ID"))
        channel_id = _optional(values.get("VOICEROUTE_CHANNEL_ID"))
        if channel_id is not None and community_id is None:
            raise ValueError("VOICEROUTE_COMMUNITY_ID is required when channel ID is set")

        prefix = values.get("VOICEROUTE_COMMAND_PREFIX", "/").strip()
        if not prefix or any(character.isspace() for character in prefix):
            raise ValueError("VOICEROUTE_COMMAND_PREFIX must be non-empty and contain no spaces")

        return cls(
            token=token,
            base_url=values.get("VOICEROUTE_BASE_URL", "https://voiceroute.cc").rstrip("/"),
            community_id=community_id,
            channel_id=channel_id,
            command_prefix=prefix,
            cursor_path=Path(
                values.get(
                    "VOICEROUTE_CURSOR_PATH",
                    ".voiceroute/community-assistant.sqlite3",
                )
            ),
        )


def _optional(value: str | None) -> str | None:
    if value is None:
        return None
    stripped = value.strip()
    return stripped or None
