"""Application-command interaction endpoints."""

from voiceroute.models import InteractionResponse
from voiceroute.transport import HTTPTransport


class InteractionsAPI:
    """Respond to interactions delivered to the current bot."""

    def __init__(self, transport: HTTPTransport) -> None:
        self._transport = transport

    async def respond(
        self,
        interaction_id: str,
        body: str,
        *,
        ephemeral: bool = False,
    ) -> InteractionResponse:
        if not body:
            raise ValueError("interaction response body cannot be empty")
        if len(body) > 4000:
            raise ValueError("interaction response body cannot exceed 4000 characters")
        payload = await self._transport.request(
            "POST",
            f"/api/bots/@me/interactions/{interaction_id}/response",
            json={"body": body, "ephemeral": ephemeral},
            retryable=True,
        )
        if payload is None or not isinstance(payload.get("interaction"), dict):
            raise RuntimeError("VoiceRoute returned no interaction response")
        return InteractionResponse.from_dict(payload["interaction"])
