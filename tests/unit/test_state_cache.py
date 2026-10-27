from voiceroute import (
    Bot,
    CachedEntity,
    CachedResource,
    CachedRole,
    CachePolicy,
    PlatformEvent,
    StateCache,
)


def platform_event(
    name: str,
    sequence: str,
    data: dict[str, object],
) -> PlatformEvent:
    return PlatformEvent.from_gateway_frame(
        {
            "op": 0,
            "event": name,
            "sequence": sequence,
            "deliveryId": f"00000000-0000-4000-8000-{int(sequence):012d}",
            "data": data,
        }
    )


async def test_cache_exposes_before_and_after_snapshots() -> None:
    cache = StateCache()
    created = platform_event(
        "ROLE_CREATED",
        "1",
        {"id": "role", "communityId": "community", "name": "First", "position": 1},
    )
    updated = platform_event(
        "ROLE_UPDATED",
        "2",
        {"id": "role", "communityId": "community", "name": "Second", "position": 2},
    )

    await cache.apply(created)
    await cache.apply(updated)

    change = cache.change_for(updated)
    assert change is not None
    assert change.before is not None and change.before.name == "First"
    assert change.after is not None and change.after.name == "Second"
    assert cache.get_role("role") == change.after
    assert change.after.partial is True


async def test_cache_removes_member_after_left_event() -> None:
    cache = StateCache()
    joined = platform_event(
        "MEMBER_JOINED", "1", {"communityId": "community", "userId": "42", "role": "member"}
    )
    left = platform_event(
        "MEMBER_LEFT", "2", {"communityId": "community", "userId": "42", "role": "member"}
    )

    await cache.apply(joined)
    assert cache.get_member("community", "42") is not None
    await cache.apply(left)

    assert cache.get_member("community", "42") is None
    change = cache.change_for(left)
    assert change is not None and change.before is not None and change.after is None


async def test_message_cache_is_optional_and_bounded() -> None:
    disabled = StateCache()
    first = platform_event(
        "MESSAGE_CREATED",
        "1",
        {"communityId": "c", "channelId": "ch", "messageSeq": "1"},
    )
    await disabled.apply(first)
    assert disabled.get_message("c", "ch", "1") is None

    cache = StateCache(CachePolicy(messages=True, max_messages=1))
    second = platform_event(
        "MESSAGE_CREATED",
        "2",
        {"communityId": "c", "channelId": "ch", "messageSeq": "2"},
    )
    await cache.apply(first)
    await cache.apply(second)

    assert cache.get_message("c", "ch", "1") is None
    assert cache.get_message("c", "ch", "2") is not None


async def test_cache_uses_typed_entities_and_per_domain_lru() -> None:
    cache = StateCache(CachePolicy(max_per_domain=1))
    await cache.apply(
        platform_event(
            "ROLE_CREATED",
            "1",
            {"id": "first", "communityId": "c", "name": "First", "position": 1},
        )
    )
    await cache.apply(
        platform_event(
            "ROLE_CREATED",
            "2",
            {"id": "second", "communityId": "c", "name": "Second", "position": 2},
        )
    )
    assert cache.get_role("first") is None
    second = cache.get_role("second")
    assert isinstance(second, CachedRole)

    await cache.apply(platform_event("POLL_CREATED", "3", {"id": "poll", "channelId": "ch"}))
    assert isinstance(cache.get_cached("poll", "poll"), CachedResource)


async def test_bot_dispatches_semantic_cache_events() -> None:
    bot = Bot(token="vrb_test", event_transport="gateway")
    changes: list[tuple[CachedEntity | None, CachedEntity]] = []

    @bot.event
    async def on_role_update(
        before: CachedEntity | None,
        after: CachedEntity,
    ) -> None:
        changes.append((before, after))

    await bot.dispatcher.dispatch(
        platform_event(
            "ROLE_CREATED",
            "1",
            {"id": "role", "communityId": "community", "name": "First"},
        )
    )
    await bot.dispatcher.dispatch(
        platform_event(
            "ROLE_UPDATED",
            "2",
            {"id": "role", "communityId": "community", "name": "Second"},
        )
    )
    await bot.client.close()

    assert len(changes) == 1
    assert changes[0][0] is not None and changes[0][0].name == "First"
    assert changes[0][1].name == "Second"


async def test_failed_listener_rolls_cache_back_for_replay() -> None:
    bot = Bot(token="vrb_test", event_transport="gateway")

    @bot.event
    async def on_role_created(item: PlatformEvent) -> None:
        raise RuntimeError("storage failed")

    created = platform_event(
        "ROLE_CREATED",
        "1",
        {"id": "role", "communityId": "community", "name": "First"},
    )
    try:
        await bot.dispatcher.dispatch(created)
    except RuntimeError:
        pass
    await bot.client.close()

    assert bot.get_role("role") is None
