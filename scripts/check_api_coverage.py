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
    "listApplicationDmMessages": ("OAuthPrivateMessagesAPI.history", None, "dict[]"),
    "createApplicationDmMessage": ("OAuthPrivateMessagesAPI.send", None, "dict"),
    "deleteApplicationDmMessage": ("OAuthPrivateMessagesAPI.delete", None, None),
    "editApplicationDmMessage": ("OAuthPrivateMessagesAPI.edit", None, "dict"),
    "getApplicationDmMessage": ("OAuthPrivateMessagesAPI.get_message", None, "dict"),
    "getApplicationDm": ("OAuthPrivateMessagesAPI.get", None, "dict"),
    "openApplicationDm": ("OAuthPrivateMessagesAPI.open", None, "dict"),
    "listGlobalCommands": ("ApplicationCommandsAPI.list", None, "ApplicationCommand[]"),
    "createGlobalCommand": ("ApplicationCommandsAPI.create", None, "ApplicationCommand"),
    "syncGlobalCommands": ("ApplicationCommandsAPI.sync", None, "CommandSyncDiff"),
    "deleteGlobalCommand": ("ApplicationCommandsAPI.delete", None, None),
    "getGlobalCommand": ("ApplicationCommandsAPI.get", None, "ApplicationCommand"),
    "updateGlobalCommand": ("ApplicationCommandsAPI.update", None, "ApplicationCommand"),
    "listCommunityCommands": ("ApplicationCommandsAPI.list", None, "ApplicationCommand[]"),
    "createCommunityCommand": ("ApplicationCommandsAPI.create", None, "ApplicationCommand"),
    "syncCommunityCommands": ("ApplicationCommandsAPI.sync", None, "CommandSyncDiff"),
    "deleteCommunityCommand": ("ApplicationCommandsAPI.delete", None, None),
    "getCommunityCommand": ("ApplicationCommandsAPI.get", None, "ApplicationCommand"),
    "updateCommunityCommand": ("ApplicationCommandsAPI.update", None, "ApplicationCommand"),
    "listEventSubscriptions": ("SubscriptionsAPI.list", None, "EventSubscription[]"),
    "createEventSubscription": ("SubscriptionsAPI.create", None, "EventSubscription"),
    "deleteEventSubscription": ("SubscriptionsAPI.delete", None, None),
    "getEventSubscription": ("SubscriptionsAPI.get", None, "EventSubscription"),
    "updateEventSubscription": ("SubscriptionsAPI.update", None, "EventSubscription"),
    "listSubscriptionDeliveries": ("SubscriptionsAPI.deliveries", None, "DeliveryLogPage"),
    "getSubscriptionDelivery": ("SubscriptionsAPI.get_delivery", None, "DeliveryDetails"),
    "acknowledgeSubscriptionDelivery": ("SubscriptionsAPI.acknowledge", None, None),
    "replaySubscriptionDelivery": ("SubscriptionsAPI.replay", None, None),
    "pullSubscriptionDeliveries": ("SubscriptionsAPI.pull", None, "DeliveryLease[]"),
    "getApplicationDeliveryStatus": ("SubscriptionsAPI.delivery_status", None, "dict"),
    "getCurrentBotApplication": ("PlatformAPI.current_application", None, "CurrentApplication"),
    "getApplicationProfile": ("PlatformAPI.application_profile", None, "ApplicationProfile"),
    "getApplicationBrandingAsset": (
        "PlatformAPI.branding_asset",
        None,
        "AsyncIterator[bytes]",
    ),
    "getGateway": ("PlatformAPI.gateway", None, "GatewayDiscovery"),
    "getEmbedImage": ("PlatformAPI.embed_image", None, "AsyncIterator[bytes]"),
    "acknowledgeMiniAppAction": ("MiniAppsAPI.acknowledge_action", None, None),
    "completeMiniAppAction": ("MiniAppsAPI.complete_action", None, None),
    "rejectMiniAppAction": ("MiniAppsAPI.reject_action", None, None),
    "getApplicationMiniAppState": ("MiniAppsAPI.get_state", None, "MiniAppState"),
    "publishMiniAppState": ("MiniAppsAPI.publish_state", None, "MiniAppState"),
    "resolveApplicationMiniAppInstance": ("MiniAppsAPI.resolve_instance", None, "str"),
    "listAutoModActions": ("AutoModAPI.actions", None, "dict[]"),
    "listAutoModRules": ("AutoModAPI.list_rules", None, "AutoModRule[]"),
    "createAutoModRule": ("AutoModAPI.create_rule", None, "AutoModRule"),
    "deleteAutoModRule": ("AutoModAPI.delete_rule", None, None),
    "getAutoModRule": ("AutoModAPI.get_rule", None, "AutoModRule"),
    "updateAutoModRule": ("AutoModAPI.update_rule", None, "AutoModRule"),
    "listCommunityCategories": ("CategoriesAPI.list", None, "Category[]"),
    "createCommunityCategory": ("CategoriesAPI.create", None, "Category"),
    "reorderCommunityCategories": ("CategoriesAPI.reorder", None, "Category[]"),
    "deleteCommunityCategory": ("CategoriesAPI.delete", None, None),
    "getCommunityCategory": ("CategoriesAPI.get", None, "Category"),
    "updateCommunityCategory": ("CategoriesAPI.update", None, "Category"),
    "listCommunityChannels": ("ChannelsAPI.list", None, "Channel[]"),
    "createCommunityChannel": ("ChannelsAPI.create", None, "Channel"),
    "reorderCommunityChannels": ("ChannelsAPI.reorder", None, "Channel[]"),
    "deleteCommunityChannel": ("ChannelsAPI.delete", None, None),
    "getCommunityChannel": ("ChannelsAPI.get", None, "Channel"),
    "updateCommunityChannel": ("ChannelsAPI.update", None, "Channel"),
    "startTyping": ("ChannelsAPI.start_typing", None, None),
    "listTyping": ("ChannelsAPI.typing", None, "TypingIndicator[]"),
    "cloneCommunityChannel": ("ChannelsAPI.clone", None, "Channel"),
    "listMessages": ("MessagesAPI.history_v1", None, "RichMessagePage"),
    "createMessage": ("MessagesAPI.send_rich", None, "RichMessage"),
    "deleteMessage": ("MessagesAPI.delete_v1", None, None),
    "getMessage": ("MessagesAPI.get_v1", None, "RichMessage"),
    "updateMessage": ("MessagesAPI.edit_rich", None, "RichMessage"),
    "clearMessageReactions": ("MessagesAPI.clear_reactions_v1", None, None),
    "bulkDeleteMessages": ("MessagesAPI.bulk_delete_v1", None, None),
    "createPoll": ("PollsAPI.create", None, "PollCreation"),
    "getPoll": ("PollsAPI.get", None, "Poll"),
    "closePoll": ("PollsAPI.close", None, "Poll"),
    "listPollVoters": ("PollsAPI.voters", None, "PollVoterPage"),
    "listChannelThreads": ("ThreadsAPI.list", None, "ThreadPage"),
    "createChannelThread": ("ThreadsAPI.create", None, "Thread"),
    "getChannelAutoModAlerts": ("AutoModAPI.alerts", None, "dict[]"),
    "listCommunityEmojis": ("ExpressionsAPI.list", None, "Expression[]"),
    "createCommunityEmoji": ("ExpressionsAPI.create", None, "Expression"),
    "deleteCommunityEmoji": ("ExpressionsAPI.delete", None, None),
    "getCommunityEmoji": ("ExpressionsAPI.get", None, "Expression"),
    "updateCommunityEmoji": ("ExpressionsAPI.update", None, "Expression"),
    "simulateCommunityPermissions": ("RolesAPI.simulate_permissions", None, "PermissionSimulation"),
    "listCommunityRoles": ("RolesAPI.list_page_v1", None, "RolePage"),
    "createCommunityRole": ("RolesAPI.create_v1", None, "Role"),
    "reorderCommunityRoles": ("RolesAPI.reorder_v1", None, "Role[]"),
    "deleteCommunityRole": ("RolesAPI.delete_v1", None, None),
    "getCommunityRole": ("RolesAPI.get_v1", None, "Role"),
    "updateCommunityRole": ("RolesAPI.update_v1", None, "Role"),
    "listCommunityStickers": ("StickersAPI.list", None, "Sticker[]"),
    "createCommunitySticker": ("StickersAPI.create", None, "Sticker"),
    "deleteCommunitySticker": ("StickersAPI.delete", None, None),
    "getCommunitySticker": ("StickersAPI.get", None, "Sticker"),
    "updateCommunitySticker": ("StickersAPI.update", None, "Sticker"),
    "deleteCommunityThread": ("ThreadsAPI.delete", None, None),
    "getCommunityThread": ("ThreadsAPI.get", None, "Thread"),
    "updateCommunityThread": ("ThreadsAPI.update", None, "Thread"),
    "listThreadMembers": ("ThreadsAPI.members", None, "ThreadMemberPage"),
    "leaveThread": ("ThreadsAPI.leave", None, None),
    "getOwnThreadMembership": ("ThreadsAPI.own_membership", None, "OwnThreadMembership"),
    "joinThread": ("ThreadsAPI.join", None, None),
    "removeThreadMember": ("ThreadsAPI.remove_member", None, None),
    "addThreadMember": ("ThreadsAPI.add_member", None, None),
    "listMessagesInThread": ("ThreadsAPI.history", None, "RichMessagePage"),
    "createMessageInThread": ("ThreadsAPI.send", None, "RichMessage"),
    "bulkDeleteMessagesInThread": ("ThreadsAPI.bulk_delete_messages", None, None),
    "deleteMessageInThread": ("ThreadsAPI.delete_message", None, None),
    "getMessageInThread": ("ThreadsAPI.get_message", None, "RichMessage"),
    "updateMessageInThread": ("ThreadsAPI.edit_message", None, "RichMessage"),
    "listCommunityVoiceStates": ("VoiceAPI.list_states", None, "VoiceStatePage"),
    "getCommunityUserVoiceState": ("VoiceAPI.get_state", None, "VoiceState"),
    "createCommunityVoiceConnection": ("VoiceAPI.connect", None, "VoiceConnection"),
    "deleteCommunityVoiceConnection": ("VoiceAPI.disconnect", None, None),
    "getCommunityVoicePolicy": ("VoiceAPI.policy", None, "VoicePolicy"),
    "listMessageWebhooks": ("WebhooksAPI.list", None, "Webhook[]"),
    "createMessageWebhook": ("WebhooksAPI.create", None, "Webhook"),
    "deleteMessageWebhook": ("WebhooksAPI.delete", None, None),
    "getMessageWebhook": ("WebhooksAPI.get", None, "Webhook"),
    "updateMessageWebhook": ("WebhooksAPI.update", None, "Webhook"),
    "rotateMessageWebhookSecret": ("WebhooksAPI.rotate", None, None),
    "getFile": ("FilesAPI.get", None, "FileResource"),
    "downloadFile": ("FilesAPI.download", None, "AsyncIterator[bytes]"),
    "createUpload": ("UploadsAPI.create", None, "Upload"),
    "cancelUpload": ("UploadsAPI.cancel", None, None),
    "getUpload": ("UploadsAPI.get", None, "Upload"),
    "completeUpload": ("UploadsAPI.complete", None, "Upload"),
    "putUploadPart": ("UploadsAPI.put_part", None, None),
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
    "getCategoryOverrides": ("RolesAPI.category_permissions_v1", None, "PermissionOverride[]"),
    "replaceCategoryOverrides": (
        "RolesAPI.replace_category_overrides_v1",
        None,
        "PermissionOverride[]",
    ),
    "getChannelOverrides": ("RolesAPI.channel_permissions_v1", None, "ChannelPermissionSnapshot"),
    "replaceChannelOverrides": (
        "RolesAPI.replace_channel_overrides_v1",
        None,
        "ChannelPermissionSnapshot",
    ),
    "syncChannelOverrides": (
        "RolesAPI.sync_channel_overrides_v1",
        None,
        "ChannelPermissionSnapshot",
    ),
}


def candidate_module(path: str) -> str | None:
    """Map contract paths to their most specific SDK resource module candidate."""
    if (
        path == "/applications/@me"
        or path == "/gateway"
        or ("/applications/" in path and ("/assets/" in path or path.endswith("/profile")))
        or path.startswith("/media/images/")
    ):
        return "voiceroute.api.platform"
    if path.startswith("/files/"):
        return "voiceroute.api.files"
    if "/polls" in path:
        return "voiceroute.api.polls"
    if "/threads" in path:
        return "voiceroute.api.threads"
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
    if "/commands" not in path and "/permissions" in path:
        return "voiceroute.api.roles"
    if "/commands" in path or "/application-commands" in path:
        return "voiceroute.api.application_commands"
    for segment, module in RESOURCE_MODULES.items():
        if f"/{segment}/" in f"{path}/" or path.endswith(f"/{segment}"):
            return f"voiceroute.api.{module}"
    if path in {"/capabilities", "/status", "/openapi.json", "/asyncapi.json"}:
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
            "partial_mapping": sum(item["status"] == "partial" for item in ops),
            "missing_mapping": sum(item["status"] == "missing" for item in ops),
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
    print("\nBot candidate operations without full contract coverage:")
    for item in ops:
        if item["status"] != "excluded":
            binding = f" -> {item['sdk_method']}" if item["sdk_method"] else ""
            print(
                f"{item['status']:7} {item['method']:6} {item['path']:75} "
                f"{item['operationId']}{binding}"
            )
    print("\nEvents:")
    events_report = report["events"]
    assert isinstance(events_report, list)
    print(", ".join(item["event"] for item in events_report))
    print("\nThis report is an inventory, not a coverage percentage.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
