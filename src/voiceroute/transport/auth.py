"""Authentication helpers."""


class BotAuth:
    """Build the VoiceRoute bot authorization header without exposing the token."""

    __slots__ = ("_token",)

    def __init__(self, token: str) -> None:
        if not token or not token.startswith("vrb_"):
            raise ValueError("token must be a VoiceRoute bot token starting with 'vrb_'")
        self._token = token

    def headers(self) -> dict[str, str]:
        return {"Authorization": f"Bot {self._token}"}

    def __repr__(self) -> str:
        return "BotAuth(token=<redacted>)"
