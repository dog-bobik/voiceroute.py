"""Automatic moderation models."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Self


@dataclass(frozen=True, slots=True)
class AutoModConfig:
    """Complete automatic moderation configuration for a community."""

    enabled: bool = False
    blocked_words: tuple[str, ...] = ()
    max_mentions: int = 5
    spam_limit: int = 5
    block_duplicates: bool = True
    slowmode_seconds: int = 0

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> Self:
        return cls(
            enabled=bool(data.get("enabled", False)),
            blocked_words=tuple(str(word) for word in data.get("blockedWords", ())),
            max_mentions=int(data.get("maxMentions", 5)),
            spam_limit=int(data.get("spamLimit", 5)),
            block_duplicates=bool(data.get("blockDuplicates", True)),
            slowmode_seconds=int(data.get("slowmodeSeconds", 0)),
        )

    def to_dict(self) -> dict[str, object]:
        """Serialize the full configuration expected by VoiceRoute."""
        return {
            "enabled": self.enabled,
            "blockedWords": list(self.blocked_words),
            "maxMentions": self.max_mentions,
            "spamLimit": self.spam_limit,
            "blockDuplicates": self.block_duplicates,
            "slowmodeSeconds": self.slowmode_seconds,
        }
