"""Bot-managed incoming webhooks and separate secret-authenticated clients."""

from __future__ import annotations

import uuid
from collections.abc import Mapping, Sequence

from voiceroute.models import RichMessage, Webhook
from voiceroute.transport import HTTPTransport, Transport, WebhookSecretAuth


class WebhooksAPI:
    """Manage incoming message webhooks with bot authorization."""

    def __init__(self, transport: Transport) -> None:
        self._transport = transport

    async def list(self, community_id: str) -> tuple[Webhook, ...]:
        payload = await self._transport.request("GET", _collection_path(community_id))
        values = (payload or {}).get("items", ())
        return tuple(Webhook.from_dict(item) for item in values if isinstance(item, dict))

    async def create(
        self,
        community_id: str,
        name: str,
        channel_id: str,
        *,
        allow_username_override: bool = False,
        allow_avatar_override: bool = False,
        avatar_expression_id: str | None = None,
        idempotency_key: str | uuid.UUID | None = None,
    ) -> Webhook:
        if not name or len(name) > 80:
            raise ValueError("webhook name must contain between 1 and 80 characters")
        payload = await self._transport.request(
            "POST",
            _collection_path(community_id),
            json={
                "name": name,
                "channelId": channel_id,
                "allowUsernameOverride": allow_username_override,
                "allowAvatarOverride": allow_avatar_override,
                "avatarExpressionId": avatar_expression_id,
            },
            idempotency_key=str(idempotency_key or uuid.uuid4()),
        )
        return Webhook.from_dict(_required_object(payload, "creation"))

    async def get(self, community_id: str, webhook_id: str) -> Webhook:
        payload = await self._transport.request("GET", _resource_path(community_id, webhook_id))
        return Webhook.from_dict(_required_object(payload, "lookup"))

    async def update(
        self,
        community_id: str,
        webhook_id: str,
        *,
        if_match: str,
        name: str | None = None,
        channel_id: str | None = None,
        allow_username_override: bool | None = None,
        allow_avatar_override: bool | None = None,
        avatar_expression_id: str | None = None,
        idempotency_key: str | uuid.UUID | None = None,
    ) -> Webhook:
        body: dict[str, object] = {}
        if name is not None:
            if not name or len(name) > 80:
                raise ValueError("webhook name must contain between 1 and 80 characters")
            body["name"] = name
        if channel_id is not None:
            body["channelId"] = channel_id
        if allow_username_override is not None:
            body["allowUsernameOverride"] = allow_username_override
        if allow_avatar_override is not None:
            body["allowAvatarOverride"] = allow_avatar_override
        if avatar_expression_id is not None:
            body["avatarExpressionId"] = avatar_expression_id
        if not body:
            raise ValueError("at least one webhook field must be supplied")
        payload = await self._transport.request(
            "PATCH",
            _resource_path(community_id, webhook_id),
            json=body,
            idempotency_key=str(idempotency_key or uuid.uuid4()),
            if_match=if_match,
        )
        return Webhook.from_dict(_required_object(payload, "update"))

    async def rotate(
        self,
        community_id: str,
        webhook_id: str,
        *,
        grace_period_seconds: int = 60,
        idempotency_key: str | uuid.UUID | None = None,
    ) -> Webhook:
        if not 0 <= grace_period_seconds <= 3600:
            raise ValueError("grace_period_seconds must be between 0 and 3600")
        payload = await self._transport.request(
            "POST",
            f"{_resource_path(community_id, webhook_id)}/rotate",
            json={"gracePeriodSeconds": grace_period_seconds},
            idempotency_key=str(idempotency_key or uuid.uuid4()),
        )
        return Webhook.from_dict(_required_object(payload, "secret rotation"))

    async def delete(
        self,
        community_id: str,
        webhook_id: str,
        *,
        if_match: str,
        idempotency_key: str | uuid.UUID | None = None,
    ) -> None:
        await self._transport.request(
            "DELETE",
            _resource_path(community_id, webhook_id),
            idempotency_key=str(idempotency_key or uuid.uuid4()),
            if_match=if_match,
            retryable=True,
        )


class MessageWebhookClient:
    """Execute incoming webhook messages without forwarding bot credentials."""

    def __init__(
        self,
        webhook_id: str,
        token: str,
        *,
        base_url: str = "https://voiceroute.cc",
        timeout: float = 30.0,
    ) -> None:
        self.webhook_id = webhook_id
        self._auth = WebhookSecretAuth(token)
        self._transport = HTTPTransport(
            auth=self._auth,
            base_url=base_url,
            timeout=timeout,
        )

    def __repr__(self) -> str:
        return f"MessageWebhookClient(webhook_id={self.webhook_id!r}, token=<redacted>)"

    async def send(
        self,
        *,
        content: str = "",
        embeds: Sequence[Mapping[str, object]] = (),
        allowed_mentions: Mapping[str, object] | None = None,
        idempotency_key: str | uuid.UUID | None = None,
    ) -> RichMessage:
        if len(content) > 4000:
            raise ValueError("message content cannot exceed 4000 characters")
        if not content and not embeds:
            raise ValueError("message must contain content or an embed")
        if len(embeds) > 10:
            raise ValueError("a message cannot contain more than 10 embeds")
        body: dict[str, object] = {"content": content}
        if embeds:
            body["embeds"] = [dict(embed) for embed in embeds]
        if allowed_mentions is not None:
            body["allowedMentions"] = dict(allowed_mentions)
        payload = await self._transport.request(
            "POST",
            self._path(),
            json=body,
            idempotency_key=str(idempotency_key or uuid.uuid4()),
        )
        return RichMessage.from_dict(_required_object(payload, "message creation"))

    async def edit(
        self,
        message_id: str,
        *,
        if_match: str,
        content: str | None = None,
        embeds: Sequence[Mapping[str, object]] | None = None,
        attachments: Sequence[Mapping[str, object]] | None = None,
        components: Sequence[Mapping[str, object]] | None = None,
        allowed_mentions: Mapping[str, object] | None = None,
        idempotency_key: str | uuid.UUID | None = None,
    ) -> RichMessage:
        if content is not None and len(content) > 4000:
            raise ValueError("message content cannot exceed 4000 characters")
        body: dict[str, object] = {}
        if content is not None:
            body["content"] = content
        if embeds is not None:
            if len(embeds) > 10:
                raise ValueError("a message cannot contain more than 10 embeds")
            body["embeds"] = [dict(embed) for embed in embeds]
        if attachments is not None:
            if len(attachments) > 10:
                raise ValueError("a message cannot contain more than 10 attachments")
            body["attachments"] = [dict(attachment) for attachment in attachments]
        if components is not None:
            if len(components) > 5:
                raise ValueError("a message cannot contain more than 5 component rows")
            body["components"] = [dict(component) for component in components]
        if allowed_mentions is not None:
            body["allowedMentions"] = dict(allowed_mentions)
        if not body:
            raise ValueError("at least one message field must be supplied")
        payload = await self._transport.request(
            "PATCH",
            f"{self._path()}/messages/{message_id}",
            json=body,
            idempotency_key=str(idempotency_key or uuid.uuid4()),
            if_match=if_match,
        )
        return RichMessage.from_dict(_required_object(payload, "message edit"))

    async def delete(
        self,
        message_id: str,
        *,
        if_match: str,
        idempotency_key: str | uuid.UUID | None = None,
    ) -> None:
        await self._transport.request(
            "DELETE",
            f"{self._path()}/messages/{message_id}",
            idempotency_key=str(idempotency_key or uuid.uuid4()),
            if_match=if_match,
            retryable=True,
        )

    async def close(self) -> None:
        await self._transport.close()

    async def __aenter__(self) -> MessageWebhookClient:
        return self

    async def __aexit__(self, *exc: object) -> None:
        await self.close()

    def _path(self) -> str:
        return f"/api/v1/message-webhooks/{self.webhook_id}/{self._auth.path_value()}"


def _collection_path(community_id: str) -> str:
    return f"/api/v1/communities/{community_id}/webhooks"


def _resource_path(community_id: str, webhook_id: str) -> str:
    return f"{_collection_path(community_id)}/{webhook_id}"


def _required_object(payload: dict[str, object] | None, operation: str) -> dict[str, object]:
    if payload is None:
        raise RuntimeError(f"VoiceRoute returned no webhook after {operation}")
    webhook = payload.get("webhook", payload)
    if not isinstance(webhook, dict):
        raise RuntimeError(f"VoiceRoute returned an invalid webhook after {operation}")
    return webhook
