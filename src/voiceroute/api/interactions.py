"""Initial callbacks, follow-ups, message updates, and modal submissions."""

from __future__ import annotations

from voiceroute.models import (
    ActionRow,
    CommandChoice,
    Interaction,
    InteractionCallbackType,
    InteractionMessage,
    InteractionResponse,
    Modal,
)
from voiceroute.models.interaction import autocomplete_payload
from voiceroute.transport import HTTPTransport


class InteractionsAPI:
    def __init__(self, transport: HTTPTransport) -> None:
        self._transport = transport

    async def invoke(
        self,
        community_id: str,
        channel_id: str,
        command_id: str,
        version: str,
        *,
        options: dict[str, object] | None = None,
    ) -> Interaction:
        payload = await self._transport.request(
            "POST",
            f"/api/v1/communities/{community_id}/channels/{channel_id}/interactions",
            json={"commandId": command_id, "version": version, "options": options or {}},
            retryable=True,
        )
        if payload is None:
            raise RuntimeError("VoiceRoute returned no interaction")
        return Interaction.from_dict(payload)

    async def get(self, community_id: str, channel_id: str, interaction_id: str) -> Interaction:
        payload = await self._transport.request(
            "GET",
            f"/api/v1/communities/{community_id}/channels/{channel_id}"
            f"/interactions/{interaction_id}",
        )
        if payload is None:
            raise RuntimeError("VoiceRoute returned no interaction")
        return Interaction.from_dict(payload)

    async def invoke_private(
        self,
        application_id: str,
        command_id: str,
        version: str,
        *,
        options: dict[str, object] | None = None,
    ) -> Interaction:
        payload = await self._transport.request(
            "POST",
            f"/api/v1/applications/{application_id}/private-interactions",
            json={"commandId": command_id, "version": version, "options": options or {}},
            retryable=True,
        )
        if payload is None:
            raise RuntimeError("VoiceRoute returned no private interaction")
        return Interaction.from_dict(payload)

    async def get_private(self, application_id: str, interaction_id: str) -> Interaction:
        payload = await self._transport.request(
            "GET",
            f"/api/v1/applications/{application_id}/private-interactions/{interaction_id}",
        )
        if payload is None:
            raise RuntimeError("VoiceRoute returned no private interaction")
        return Interaction.from_dict(payload)

    async def callback(
        self,
        interaction_id: str,
        token: str,
        callback_type: InteractionCallbackType | str,
        data: dict[str, object] | None = None,
    ) -> InteractionResponse | None:
        payload = await self._transport.request(
            "POST",
            f"/api/v1/interactions/{interaction_id}/{token}/callback",
            json={"type": str(callback_type), **({"data": data} if data is not None else {})},
            retryable=True,
        )
        if payload is None:
            return None
        raw = payload.get("message", payload.get("interaction", payload))
        return InteractionResponse.from_dict(raw) if isinstance(raw, dict) else None

    async def respond(
        self,
        interaction_id: str,
        body: str,
        *,
        ephemeral: bool = False,
        token: str | None = None,
        components: tuple[ActionRow, ...] = (),
    ) -> InteractionResponse:
        if not body:
            raise ValueError("interaction response body cannot be empty")
        if len(body) > 4000:
            raise ValueError("interaction response body cannot exceed 4000 characters")
        if token is not None:
            message = InteractionMessage(
                content=body,
                flags=("EPHEMERAL",) if ephemeral else (),
                components=components,
            )
            response = await self.callback(
                interaction_id,
                token,
                InteractionCallbackType.MESSAGE,
                message.to_dict(),
            )
            if response is None:
                raise RuntimeError("VoiceRoute returned no interaction response")
            return response
        payload = await self._transport.request(
            "POST",
            f"/api/bots/@me/interactions/{interaction_id}/response",
            json={"body": body, "ephemeral": ephemeral},
            retryable=True,
        )
        if payload is None or not isinstance(payload.get("interaction"), dict):
            raise RuntimeError("VoiceRoute returned no interaction response")
        return InteractionResponse.from_dict(payload["interaction"])

    async def defer(self, interaction_id: str, token: str, *, ephemeral: bool = False) -> None:
        await self.callback(
            interaction_id,
            token,
            InteractionCallbackType.DEFERRED_MESSAGE,
            {"flags": ["EPHEMERAL"]} if ephemeral else {},
        )

    async def autocomplete(
        self, interaction_id: str, token: str, choices: tuple[CommandChoice, ...]
    ) -> None:
        await self.callback(
            interaction_id,
            token,
            InteractionCallbackType.AUTOCOMPLETE_RESULT,
            autocomplete_payload(choices),
        )

    async def show_modal(self, interaction_id: str, token: str, modal: Modal) -> None:
        await self.callback(interaction_id, token, InteractionCallbackType.MODAL, modal.to_dict())

    async def update_message(
        self, interaction_id: str, token: str, message: InteractionMessage
    ) -> InteractionResponse | None:
        return await self.callback(
            interaction_id,
            token,
            InteractionCallbackType.UPDATE_MESSAGE,
            message.to_dict(),
        )

    async def defer_update(self, interaction_id: str, token: str) -> None:
        await self.callback(interaction_id, token, InteractionCallbackType.DEFERRED_UPDATE)

    async def create_followup(
        self, application_id: str, token: str, message: InteractionMessage
    ) -> InteractionResponse:
        payload = await self._transport.request(
            "POST",
            f"/api/v1/webhooks/{application_id}/{token}",
            json=message.to_dict(),
            retryable=True,
        )
        if payload is None:
            raise RuntimeError("VoiceRoute returned no follow-up message")
        return InteractionResponse.from_dict(payload)

    async def get_response(
        self, application_id: str, token: str, message_id: str
    ) -> InteractionResponse:
        payload = await self._transport.request(
            "GET", f"/api/v1/webhooks/{application_id}/{token}/messages/{message_id}"
        )
        if payload is None:
            raise RuntimeError("VoiceRoute returned no interaction message")
        return InteractionResponse.from_dict(payload)

    async def edit_response(
        self,
        application_id: str,
        token: str,
        message_id: str,
        message: InteractionMessage,
    ) -> InteractionResponse:
        payload = await self._transport.request(
            "PATCH",
            f"/api/v1/webhooks/{application_id}/{token}/messages/{message_id}",
            json=message.to_dict(),
            retryable=True,
        )
        if payload is None:
            raise RuntimeError("VoiceRoute returned no edited interaction message")
        return InteractionResponse.from_dict(payload)

    async def delete_response(self, application_id: str, token: str, message_id: str) -> None:
        await self._transport.request(
            "DELETE",
            f"/api/v1/webhooks/{application_id}/{token}/messages/{message_id}",
            retryable=True,
        )

    async def submit_modal(
        self,
        community_id: str,
        channel_id: str,
        interaction_id: str,
        custom_id: str,
        values: dict[str, str],
    ) -> None:
        await self._transport.request(
            "POST",
            f"/api/v1/communities/{community_id}/channels/{channel_id}"
            f"/interactions/{interaction_id}/modal",
            json={"customId": custom_id, "values": values},
            retryable=True,
        )

    async def submit_private_modal(
        self,
        application_id: str,
        interaction_id: str,
        custom_id: str,
        values: dict[str, str],
    ) -> None:
        await self._transport.request(
            "POST",
            f"/api/v1/applications/{application_id}/private-interactions/{interaction_id}/modal",
            json={"customId": custom_id, "values": values},
            retryable=True,
        )
