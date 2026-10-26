"""Entrypoint for ``python -m examples.community_assistant.bot``."""

from __future__ import annotations

import logging

from dotenv import load_dotenv

from examples.community_assistant.config import CommunityAssistantConfig
from examples.community_assistant.extensions.native import register_native_commands
from voiceroute import (
    Bot,
    CachePolicy,
    FileGatewayCheckpointStore,
    Intents,
    SQLiteCursorStore,
)

EXTENSIONS = (
    "examples.community_assistant.extensions.general",
    "examples.community_assistant.extensions.knowledge",
    "examples.community_assistant.extensions.messages",
    "examples.community_assistant.extensions.diagnostics",
    "examples.community_assistant.extensions.gateway",
)


class CommunityAssistantBot(Bot):
    async def setup_hook(self) -> None:
        for extension in EXTENSIONS:
            await self.load_extension(extension)
        register_native_commands(self)


def create_bot(config: CommunityAssistantConfig) -> CommunityAssistantBot:
    intents = (
        Intents(
            communities=True,
            messages=True,
            interactions=True,
            members=True,
            message_content=True,
            presence=True,
        )
        if config.privileged_intents
        else Intents.default()
    )
    return CommunityAssistantBot(
        token=config.token,
        base_url=config.base_url,
        community_id=config.community_id,
        channel_id=config.channel_id,
        command_prefix=config.command_prefix,
        cursor_store=SQLiteCursorStore(config.cursor_path),
        gateway_store=FileGatewayCheckpointStore(config.gateway_path),
        intents=intents,
        cache_policy=CachePolicy(messages=True, max_messages=500),
        sync_application_commands=config.sync_application_commands,
    )


def main() -> None:
    load_dotenv()
    logging.basicConfig(level=logging.INFO, format="%(levelname)s %(name)s: %(message)s")
    config = CommunityAssistantConfig.from_env()
    create_bot(config).run()


if __name__ == "__main__":
    main()
