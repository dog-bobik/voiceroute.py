#!/usr/bin/env python3
"""Report bot-compatible VoiceRoute operations against SDK public resources.

This first baseline intentionally classifies by operation/path and exposed API
module. It is a review aid, not a claim that every listed operation is fully
implemented. Full coverage requires typed models and request/response tests.
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any, cast

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
CONTRACTS = ROOT / "contracts/voiceroute"
DEFAULT_OPENAPI = CONTRACTS / "openapi.json"
DEFAULT_ASYNCAPI = CONTRACTS / "asyncapi.json"
DEFAULT_CAPABILITIES = CONTRACTS / "capabilities.json"

RESOURCE_MODULES = {
    "application_commands": "application_commands",
    "audit": "audit",
    "automod": "automod",
    "bots": "bots",
    "events": "events",
    "interactions": "interactions",
    "members": "members",
    "messages": "messages",
    "mini_apps": "mini_apps",
    "moderation": "moderation",
    "platform": "platform",
    "roles": "roles",
    "permissions": "roles",
    "channels": "channels",
    "categories": "channels",
    "threads": "threads",
    "polls": "polls",
    "uploads": "uploads",
    "stickers": "stickers",
    "emojis": "expressions",
    "webhooks": "webhooks",
    "application-dms": "private_messages",
    "subscriptions": "subscriptions",
    "voice": "voice",
}

# Hand-verified operation bindings. Unlisted operations remain missing instead of
# being guessed from their URL or operationId. Contract tests are tracked separately.
OPERATION_BINDINGS: dict[str, tuple[str, str | None, str | None]] = {
    "listCommunityMembers": ("MembersAPI.list_page", None, "MemberPage"),
    "getCommunityMember": ("MembersAPI.get", None, "Member"),
    "searchCommunityMembers": ("MembersAPI.search", None, "MemberPage"),
    "updateCommunityMember": ("MembersAPI.update_v1", None, "Member"),
    "getEffectiveMemberPermissions": (
        "RolesAPI.effective_permissions",
        None,
        "EffectivePermissions",
    ),
    "addCommunityMemberRole": ("RolesAPI.add_member_role_v1", None, None),
    "removeCommunityMemberRole": ("RolesAPI.remove_member_role_v1", None, None),
}


def candidate_module(path: str) -> str | None:
    """Map contract paths to their most specific SDK resource module candidate."""
    if "/event-subscriptions" in path or "/event-delivery-status" in path:
        return "voiceroute.api.subscriptions"
    if "/application-dms/" in path or path.endswith("/dm"):
        return "voiceroute.api.private_messages"
    if path.startswith("/webhooks/"):
        return "voiceroute.api.interactions"
    if path.startswith("/message-webhooks/") or "/webhooks" in path:
        return "voiceroute.api.webhooks"
    if "/mini-app" in path:
        return "voiceroute.api.mini_apps"
    if "/voice-" in path or path.endswith("/voice-policy"):
        return "voiceroute.api.voice"
    if "/commands" not in path and (
        "/permissions" in path or ("/members/" in path and "/roles" in path)
    ):
        return "voiceroute.api.roles"
    if "/commands" in path or "/application-commands" in path:
        return "voiceroute.api.application_commands"
    for segment, module in RESOURCE_MODULES.items():
        if f"/{segment}/" in f"{path}/" or path.endswith(f"/{segment}"):
            return f"voiceroute.api.{module}"
    if path in {"/gateway", "/capabilities", "/status", "/openapi.json", "/asyncapi.json"}:
        return "voiceroute.api.platform"
    return None


def load(path: Path) -> dict[str, Any]:
    return cast(dict[str, Any], json.loads(path.read_text(encoding="utf-8")))


def event_inventory(names: list[Any]) -> list[dict[str, Any]]:
    from voiceroute.events.catalog import event_definition

    inventory = []
    for raw_name in sorted(map(str, names)):
        definition = event_definition(raw_name)
        inventory.append(
            {
                "event": raw_name,
                "payload_model": "voiceroute.models.PlatformEvent" if definition else None,
                "handler_aliases": list(definition.handlers) if definition else [],
                "resource_ordering_fields": (
                    list(definition.ordering_fields) if definition else []
                ),
                "status": "partial" if definition else "missing",
            }
        )
    return inventory


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
            clauses = [sorted(map(str, clause)) for clause in security]
            if not any("botToken" in clause for clause in clauses):
                status = "excluded"
            else:
                status = "missing"
            binding = OPERATION_BINDINGS.get(str(operation["operationId"]))
            if status != "excluded" and binding is not None:
                status = "partial"
            resource = candidate_module(path)
            result.append(
                {
                    "operationId": str(operation["operationId"]),
                    "method": method.upper(),
                    "path": path,
                    "auth_surfaces": clauses or [["public"]],
                    "candidate_module": resource,
                    "sdk_method": binding[0] if binding else None,
                    "request_dto": binding[1] if binding else None,
                    "response_dto": binding[2] if binding else None,
                    "contract_test": None,
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
    parser.add_argument(
        "--write-manifest", type=Path, help="write operation-level mapping JSON to this path"
    )
    args = parser.parse_args()
    missing = [p for p in (args.openapi, args.asyncapi, args.capabilities) if not p.is_file()]
    if missing:
        parser.error("contract file not found: " + ", ".join(map(str, missing)))

    api = load(args.openapi)
    asyncapi = load(args.asyncapi)
    capabilities = load(args.capabilities)
    ops = operations(api)
    events = capabilities.get("events", [])
    event_map = event_inventory(events)
    report = {
        "source_revision": load(CONTRACTS / "manifest.json").get("source_revision"),
        "source": {
            "openapi": args.openapi.name,
            "asyncapi": args.asyncapi.name,
            "capabilities": args.capabilities.name,
        },
        "counts": {
            "operations": len(ops),
            "bot_candidate": sum(item["status"] != "excluded" for item in ops),
            "excluded_auth": sum(item["status"] == "excluded" for item in ops),
            "events": len(events),
            "public_resource_modules": len(RESOURCE_MODULES),
        },
        "operations": ops,
        "events": event_map,
        "asyncapi_channels": sorted(asyncapi.get("channels", {})),
        "classification_note": (
            "partial means a hand-verified SDK method binding exists, but full DTO and "
            "contract-test coverage is not established; missing means no verified "
            "method mapping exists"
        ),
    }
    if args.json:
        print(json.dumps(report, indent=2, sort_keys=True))
        return 0
    if args.write_manifest:
        args.write_manifest.parent.mkdir(parents=True, exist_ok=True)
        args.write_manifest.write_text(
            json.dumps(report, indent=2, sort_keys=True) + "\n", encoding="utf-8"
        )
        print(f"Wrote operation inventory to {args.write_manifest}")
        return 0
    print("VoiceRoute contract coverage baseline")
    counts = report["counts"]
    assert isinstance(counts, dict)
    for name, value in counts.items():
        print(f"{name}: {value}")
    print("\nBot candidate operations requiring manual method/model/test mapping:")
    for item in ops:
        if item["status"] != "excluded":
            print(f"{item['method']:6} {item['path']:75} {item['operationId']}")
    print("\nEvents:")
    events_report = report["events"]
    assert isinstance(events_report, list)
    print(", ".join(item["event"] for item in events_report))
    print("\nThis report is an inventory, not a coverage percentage.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
