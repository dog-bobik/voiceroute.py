from voiceroute.models import Message


def test_message_preserves_bigint_sequence_as_string() -> None:
    message = Message.from_dict(
        {
            "seq": "9007199254740993",
            "communityId": "community-id",
            "channelId": "channel-id",
            "body": "hello",
            "author": {
                "id": 42,
                "username": "bot_example",
                "displayName": "Example",
                "bot": True,
            },
        }
    )

    assert message.seq == "9007199254740993"
    assert message.author is not None and message.author.bot
