from voiceroute.models import BotIdentity, User


def test_bot_identity_uses_wire_field_names() -> None:
    identity = BotIdentity.from_dict(
        {
            "user": {
                "id": 42,
                "username": "bot_example",
                "displayName": "Example",
                "bot": True,
            },
            "applicationId": "00000000-0000-4000-8000-000000000001",
        }
    )

    assert identity.user == User(42, "bot_example", "Example", bot=True)
    assert identity.application_id.endswith("1")
