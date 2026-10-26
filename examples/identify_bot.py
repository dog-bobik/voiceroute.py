"""Print the identity associated with VOICEROUTE_BOT_TOKEN."""

import asyncio
import os
from pathlib import Path

from dotenv import load_dotenv

from voiceroute import VoiceRouteClient

load_dotenv(Path(__file__).resolve().parents[1] / ".env")


async def main() -> None:
    token = os.environ["VOICEROUTE_BOT_TOKEN"]
    base_url = os.getenv(
        "VOICEROUTE_BASE_URL",
        os.getenv("VOICEROUTE_URL", "https://voiceroute.cc"),
    )

    async with VoiceRouteClient(token=token, base_url=base_url) as client:
        identity = await client.bots.get_current()
        print(f"{identity.user.display_name} ({identity.user.username})")
        capabilities = await client.platform.capabilities()
        application = await client.platform.current_application()
        selected_version = await client.resolve_api_version()
        print(
            f"application={application.name} api={selected_version.value} "
            f"gateway={capabilities.supports('gateway')} "
            f"events={len(capabilities.events)}"
        )


if __name__ == "__main__":
    asyncio.run(main())
