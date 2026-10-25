"""Bot identity models."""

from dataclasses import dataclass
from typing import Any, Self

from voiceroute.models.user import User


@dataclass(frozen=True, slots=True)
class BotIdentity:
    """Authenticated bot and its owning application identifier."""

    user: User
    application_id: str

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> Self:
        return cls(
            user=User.from_dict(data["user"]),
            application_id=str(data["applicationId"]),
        )
