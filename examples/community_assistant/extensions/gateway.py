"""Gateway presence and lifecycle-event demonstrations."""

from __future__ import annotations

import logging

from voiceroute import Bot, CachedEntity, Extension, Game, PlatformEvent, Status, listener

logger = logging.getLogger(__name__)


class GatewayFeatures(Extension):
    def __init__(self, bot: Bot) -> None:
        self.bot = bot

    @listener("on_ready")
    async def publish_presence(self) -> None:
        if self.bot.gateway is not None:
            await self.bot.gateway.change_presence(
                status=Status.ONLINE,
                activities=(Game("/help"),),
            )
            logger.info("Gateway ready; bot presence is online")

    @listener("on_connect")
    async def gateway_connected(self) -> None:
        logger.info("Community Assistant connected to VoiceRoute Gateway")

    @listener("on_stream_unavailable")
    async def stream_unavailable(self, *args: object) -> None:
        logger.warning(
            "Message stream is unavailable; enable the required privileged intents "
            "to use prefix commands"
        )

    @listener("on_member_join")
    async def member_joined(self, member: CachedEntity) -> None:
        logger.info(
            "member joined",
            extra={"community_id": member.community_id, "user_id": member.data.get("userId")},
        )

    @listener("on_role_update")
    async def role_updated(
        self,
        before: CachedEntity | None,
        after: CachedEntity,
    ) -> None:
        logger.info(
            "role updated",
            extra={
                "role_id": after.id,
                "before": before.data.get("name") if before is not None else None,
                "after": after.data.get("name"),
            },
        )

    @listener("on_unknown_event")
    async def unknown_event(self, event: PlatformEvent) -> None:
        logger.info("future Gateway event", extra={"event": event.name})


async def setup(bot: Bot) -> Extension:
    return GatewayFeatures(bot)
