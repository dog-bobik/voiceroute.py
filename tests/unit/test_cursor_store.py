import json
import stat

import pytest

from voiceroute import (
    FileCursorStore,
    MemoryCursorStore,
    RedisCursorStore,
    SQLiteCursorStore,
    StreamCheckpoint,
)
from voiceroute.errors import CursorStoreError


@pytest.mark.parametrize("store_factory", [MemoryCursorStore, lambda: FileCursorStore("")])
async def test_cursor_store_round_trip(store_factory, tmp_path) -> None:
    store = store_factory()
    if isinstance(store, FileCursorStore):
        store = FileCursorStore(tmp_path / "cursors.json")
    checkpoint = StreamCheckpoint(change_cursor="83", message_seq="17")

    await store.save("stream", checkpoint)

    assert await store.load("stream") == checkpoint


async def test_file_cursor_store_is_atomic_and_private(tmp_path) -> None:
    path = tmp_path / "state" / "cursors.json"
    store = FileCursorStore(path)

    await store.save("stream", StreamCheckpoint(change_cursor="83", message_seq="17"))

    assert stat.S_IMODE(path.stat().st_mode) == 0o600
    assert not list(path.parent.glob(f".{path.name}.*"))


async def test_file_cursor_store_rejects_corrupt_json(tmp_path) -> None:
    path = tmp_path / "cursors.json"
    path.write_text("not-json", encoding="utf-8")
    store = FileCursorStore(path)

    with pytest.raises(CursorStoreError, match="cannot read"):
        await store.load("stream")


async def test_file_cursor_store_preserves_other_streams(tmp_path) -> None:
    path = tmp_path / "cursors.json"
    path.write_text(json.dumps({"first": {"change_cursor": "1", "message_seq": "2"}}))
    store = FileCursorStore(path)

    await store.save("second", StreamCheckpoint(change_cursor="3", message_seq="4"))

    assert await store.load("first") == StreamCheckpoint("1", "2")
    assert await store.load("second") == StreamCheckpoint("3", "4")


async def test_sqlite_cursor_store_is_durable_and_updates_atomically(tmp_path) -> None:
    path = tmp_path / "state" / "cursors.sqlite3"
    first = SQLiteCursorStore(path)
    await first.save("stream", StreamCheckpoint("1", "2"))
    await first.save("stream", StreamCheckpoint("3", "4"))

    second = SQLiteCursorStore(path)

    assert await second.load("stream") == StreamCheckpoint("3", "4")
    assert await second.load("missing") is None


class FakeRedis:
    def __init__(self) -> None:
        self.values: dict[str, str] = {}
        self.closed = False

    async def get(self, key: str) -> str | None:
        return self.values.get(key)

    async def set(self, key: str, value: str) -> None:
        self.values[key] = value

    async def aclose(self) -> None:
        self.closed = True


async def test_redis_cursor_store_uses_namespaced_keys() -> None:
    client = FakeRedis()
    store = RedisCursorStore(client, key_prefix="test:")

    await store.save("stream", StreamCheckpoint("5", "6"))

    assert await store.load("stream") == StreamCheckpoint("5", "6")
    assert "test:stream" in client.values
    await store.close()
    assert client.closed


async def test_redis_cursor_store_wraps_corrupt_data() -> None:
    client = FakeRedis()
    client.values["test:stream"] = "not-json"
    store = RedisCursorStore(client, key_prefix="test:")

    with pytest.raises(CursorStoreError, match="cannot read Redis"):
        await store.load("stream")
