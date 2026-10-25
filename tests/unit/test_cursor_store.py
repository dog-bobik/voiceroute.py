import json
import stat

import pytest

from voiceroute import FileCursorStore, MemoryCursorStore, StreamCheckpoint
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
