#!/usr/bin/env python3
"""Verify checked-in VoiceRoute contract snapshots against their pinned hashes."""

from __future__ import annotations

import hashlib
import json
from pathlib import Path
from typing import Any, cast

ROOT = Path(__file__).resolve().parents[1] / "contracts" / "voiceroute"


def main() -> int:
    manifest_path = ROOT / "manifest.json"
    manifest = cast(dict[str, Any], json.loads(manifest_path.read_text(encoding="utf-8")))
    failures: list[str] = []
    for name, metadata in manifest.get("files", {}).items():
        path = ROOT / name
        if not path.is_file():
            failures.append(f"missing snapshot: {name}")
            continue
        digest = hashlib.sha256(path.read_bytes()).hexdigest()
        expected = metadata.get("sha256") if isinstance(metadata, dict) else None
        if digest != expected:
            failures.append(f"hash mismatch: {name} (expected {expected}, got {digest})")
    if failures:
        print("\n".join(failures))
        return 1
    print(
        f"Verified {len(manifest['files'])} contract snapshots from {manifest['source_revision']}."
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
