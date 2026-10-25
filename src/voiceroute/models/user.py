"""User models."""

from dataclasses import dataclass
from typing import Any, Self


@dataclass(frozen=True, slots=True)
class User:
    """A VoiceRoute user visible to the current bot."""

    id: int
    username: str
    display_name: str
    bot: bool = False

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> Self:
        return cls(
            id=int(data["id"]),
            username=str(data["username"]),
            display_name=str(data["displayName"]),
            bot=bool(data.get("bot", False)),
        )
