from voiceroute.models import Channel, Community


def test_community_preserves_unknown_fields() -> None:
    community = Community.from_dict(
        {
            "id": "community-id",
            "name": "Example",
            "permissions": ["viewChannel", "sendMessages"],
            "ownerId": 42,
        }
    )

    assert community.permissions == ("viewChannel", "sendMessages")
    assert community.extra["ownerId"] == 42


def test_channel_accepts_parent_community_context() -> None:
    channel = Channel.from_dict(
        {
            "id": "channel-id",
            "name": "general",
            "type": "text",
            "categoryId": None,
            "position": 3,
        },
        community_id="community-id",
    )

    assert channel.community_id == "community-id"
    assert channel.position == 3


def test_channel_uses_production_kind_field() -> None:
    channel = Channel.from_dict(
        {
            "id": "channel-id",
            "communityId": "community-id",
            "name": "general",
            "kind": "text",
            "presentation": "chat",
        }
    )

    assert channel.kind == "text"
    assert channel.type == "text"
    assert channel.extra["presentation"] == "chat"
