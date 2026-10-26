"""Coordinated Gateway shards, including process-local subsets."""

from __future__ import annotations

import asyncio
from collections.abc import Sequence

from voiceroute.gateway.client import GatewayClient, GatewayHandler


class ShardManager:
    """Run selected shards while spacing Identify frames deterministically."""

    def __init__(
        self,
        clients: Sequence[GatewayClient],
        *,
        identify_interval: float = 5.0,
    ) -> None:
        if identify_interval < 0:
            raise ValueError("identify_interval cannot be negative")
        if not clients:
            raise ValueError("at least one Gateway shard is required")
        shards = [client.shard for client in clients]
        if len(shards) != len(set(shards)):
            raise ValueError("Gateway shards must be unique")
        shard_counts = {shard_count for _, shard_count in shards}
        if len(shard_counts) != 1:
            raise ValueError("all Gateway clients must use the same shard count")
        self.clients = tuple(sorted(clients, key=lambda client: client.shard))
        self.identify_interval = identify_interval
        self._tasks: set[asyncio.Task[None]] = set()

    @property
    def shard_ids(self) -> tuple[int, ...]:
        return tuple(client.shard[0] for client in self.clients)

    async def run(self, handler: GatewayHandler) -> None:
        try:
            for index, client in enumerate(self.clients):
                task = asyncio.create_task(
                    client.run(handler), name=f"voiceroute:shard:{client.shard[0]}"
                )
                self._tasks.add(task)
                identified = asyncio.create_task(client.wait_until_identified())
                done, _ = await asyncio.wait(
                    {task, identified}, return_when=asyncio.FIRST_COMPLETED
                )
                if task in done:
                    identified.cancel()
                    await task
                await identified
                if index + 1 < len(self.clients) and self.identify_interval:
                    await asyncio.sleep(self.identify_interval)
            await asyncio.gather(*self._tasks)
        finally:
            await self.close()

    async def close(self) -> None:
        await asyncio.gather(*(client.close() for client in self.clients))
        tasks = tuple(self._tasks)
        for task in tasks:
            task.cancel()
        if tasks:
            await asyncio.gather(*tasks, return_exceptions=True)
        self._tasks.clear()
