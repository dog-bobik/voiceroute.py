"""Entrypoint for ``python -m examples.community_assistant.bot``."""

from __future__ import annotations

import hashlib
import logging

from dotenv import load_dotenv

from examples.community_assistant.config import CommunityAssistantConfig
from examples.community_assistant.extensions.native import register_native_commands
from voiceroute import (
    Bot,
    CachePolicy,
    Capabilities,
    FileGatewayCheckpointStore,
    SQLiteCursorStore,
)

EXTENSIONS = ("examples.community_assistant.extensions.gateway",)


class CommunityAssistantBot(Bot):
    async def setup_hook(self) -> None:
        for extension in EXTENSIONS:
            await self.load_extension(extension)
        register_native_commands(self)


def create_bot(config: CommunityAssistantConfig) -> CommunityAssistantBot:
    capabilities = Capabilities.from_values(config.gateway_capabilities)
    component_secret = config.component_secret or hashlib.sha256(
        b"voiceroute.py:community-assistant:components\0" + config.token.encode()
    ).digest()
    return CommunityAssistantBot(
        token=config.token,
        base_url=config.base_url,
        community_id=config.community_id,
        channel_id=config.channel_id,
        command_prefix=config.command_prefix,
        cursor_store=SQLiteCursorStore(config.cursor_path),
        gateway_store=FileGatewayCheckpointStore(config.gateway_path),
        capabilities=capabilities,
        cache_policy=CachePolicy(messages=True, max_messages=500),
        sync_application_commands=config.sync_application_commands,
        component_secret=component_secret,
    )


def main() -> None:
    load_dotenv()
    logging.basicConfig(level=logging.INFO, format="%(levelname)s %(name)s: %(message)s")
    logging.getLogger("httpx").setLevel(logging.WARNING)
    config = CommunityAssistantConfig.from_env()
    create_bot(config).run()


if __name__ == "__main__":
    main()
