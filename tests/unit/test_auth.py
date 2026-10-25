import pytest

from voiceroute.transport.auth import BotAuth


def test_bot_auth_builds_expected_header() -> None:
    auth = BotAuth("vrb_secret")

    assert auth.headers() == {"Authorization": "Bot vrb_secret"}
    assert "secret" not in repr(auth)


def test_bot_auth_rejects_non_bot_token() -> None:
    with pytest.raises(ValueError, match="vrb_"):
        BotAuth("not-a-bot-token")
