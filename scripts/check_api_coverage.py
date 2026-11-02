#!/usr/bin/env python3
"""Report bot-compatible VoiceRoute operations against SDK public resources.

This first baseline intentionally classifies by operation/path and exposed API
module. It is a review aid, not a claim that every listed operation is fully
implemented. Full coverage requires typed models and request/response tests.
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any, cast

ROOT = Path(__file__).resolve().parents[1]
DEFAULT_OPENAPI = ROOT.parent / "VoiceRoute" / "docs/bot-platform/openapi.json"
DEFAULT_ASYNCAPI = ROOT.parent / "VoiceRoute" / "docs/bot-platform/asyncapi.json"
DEFAULT_CAPABILITIES = ROOT.parent / "VoiceRoute" / "docs/bot-platform/capabilities.json"

RESOURCE_MODULES = {
    "application_commands": "application_commands",
    "audit": "audit",
    "automod": "automod",
    "bots": "bots",
    "communities": "communities",
    "events": "events",
    "interactions": "interactions",
    "members": "members",
    "messages": "messages",
    "mini_apps": "mini_apps",
    "moderation": "moderation",
    "platform": "platform",
    "roles": "roles",
    "voice": "voice",
}


def load(path: Path) -> dict[str, Any]:
    return cast(dict[str, Any], json.loads(path.read_text(encoding="utf-8")))


def operations(document: dict[str, Any]) -> list[dict[str, str]]:
    result = []
    for path, methods in document.get("paths", {}).items():
        if not isinstance(methods, dict):
            continue
        for method, operation in methods.items():
            if method.lower() not in {"get", "post", "put", "patch", "delete"}:
                continue
            if not isinstance(operation, dict) or not operation.get("operationId"):
                continue
            security = operation.get("security", document.get("security", []))
            schemes = {name for clause in security for name in clause}
            if schemes and "botToken" not in schemes:
                status = "excluded-auth"
            else:
                status = "review-required"
            result.append(
                {
                    "operationId": str(operation["operationId"]),
                    "method": method.upper(),
                    "path": path,
                    "auth": ",".join(sorted(schemes)) or "public",
                    "status": status,
                }
            )
    return sorted(result, key=lambda item: (item["path"], item["method"]))


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--openapi", type=Path, default=DEFAULT_OPENAPI)
    parser.add_argument("--asyncapi", type=Path, default=DEFAULT_ASYNCAPI)
    parser.add_argument("--capabilities", type=Path, default=DEFAULT_CAPABILITIES)
    parser.add_argument("--json", action="store_true", help="print machine-readable report")
    args = parser.parse_args()
    missing = [p for p in (args.openapi, args.asyncapi, args.capabilities) if not p.is_file()]
    if missing:
        parser.error("contract file not found: " + ", ".join(map(str, missing)))

    api = load(args.openapi)
    asyncapi = load(args.asyncapi)
    capabilities = load(args.capabilities)
    ops = operations(api)
    events = capabilities.get("events", [])
    report = {
        "source": {
            "openapi": str(args.openapi),
            "asyncapi": str(args.asyncapi),
            "capabilities": str(args.capabilities),
        },
        "counts": {
            "operations": len(ops),
            "bot_candidate": sum(item["status"] != "excluded-auth" for item in ops),
            "excluded_auth": sum(item["status"] == "excluded-auth" for item in ops),
            "events": len(events),
            "public_resource_modules": len(RESOURCE_MODULES),
        },
        "operations": ops,
        "events": sorted(map(str, events)),
        "asyncapi_channels": sorted(asyncapi.get("channels", {})),
        "classification_note": (
            "review-required means auth permits botToken; "
            "it does not assert SDK coverage"
        ),
    }
    if args.json:
        print(json.dumps(report, indent=2, sort_keys=True))
        return 0
    print("VoiceRoute contract coverage baseline")
    counts = report["counts"]
    assert isinstance(counts, dict)
    for name, value in counts.items():
        print(f"{name}: {value}")
    print("\nBot candidate operations requiring manual method/model/test mapping:")
    for item in ops:
        if item["status"] != "excluded-auth":
            print(f"{item['method']:6} {item['path']:75} {item['operationId']}")
    print("\nEvents:")
    events_report = report["events"]
    assert isinstance(events_report, list)
    print(", ".join(events_report))
    print("\nThis report is an inventory, not a coverage percentage.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
