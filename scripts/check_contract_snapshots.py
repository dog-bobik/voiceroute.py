#!/usr/bin/env python3
"""Verify checked-in VoiceRoute contract snapshots against their pinned hashes."""

from __future__ import annotations

import hashlib
import json
import subprocess
import sys
import tempfile
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
    checked_manifest = ROOT / "sdk-coverage.json"
    with tempfile.TemporaryDirectory() as temporary:
        generated = Path(temporary) / "sdk-coverage.json"
        result = subprocess.run(
            [
                sys.executable,
                str(ROOT.parents[1] / "scripts" / "check_api_coverage.py"),
                "--write-manifest",
                str(generated),
            ],
            check=False,
            capture_output=True,
            text=True,
        )
        if result.returncode != 0:
            print(result.stderr or result.stdout)
            return 1
        if (
            not checked_manifest.is_file()
            or checked_manifest.read_bytes() != generated.read_bytes()
        ):
            failures.append("SDK operation/event coverage inventory is stale; regenerate it")
    if failures:
        print("\n".join(failures))
        return 1
    print(
        f"Verified {len(manifest['files'])} contract snapshots from {manifest['source_revision']}."
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
