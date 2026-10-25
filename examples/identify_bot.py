"""Print the identity associated with VOICEROUTE_BOT_TOKEN."""

import asyncio
import os

from voiceroute import VoiceRouteClient


async def main() -> None:
    token = os.environ["VOICEROUTE_BOT_TOKEN"]
    base_url = os.getenv("VOICEROUTE_URL", "https://dev.voiceroute.cc")

    async with VoiceRouteClient(token=token, base_url=base_url) as client:
        identity = await client.bots.get_current()
        print(f"{identity.user.display_name} ({identity.user.username})")


if __name__ == "__main__":
    asyncio.run(main())
