# VoiceRoute Python SDK reference

This reference describes the public surface in the current development build. Server capabilities and grants still determine which operations are available at runtime.

## Client and transport

`VoiceRouteClient(token, api_version=...)` is the top-level REST resource collection. Pass a `Transport` implementation to inject HTTP behavior; set `owns_transport=True` only when the client should close that transport. Use it as an async context manager. `api_version` selects the supported adapter where an API exposes both legacy and v1 routes; it does not imply every resource has a v1 adapter.

```python
async with VoiceRouteClient(token="vrb_…") as client:
    member = await client.members.get(community_id, user_id)
    page = await client.members.search(community_id, query="alex")
```

## Bot runtime

`Bot` composes Gateway, command pipeline, cache, extensions, and API client. Register handlers before `run()`. A `Router` can be included into another router or the Bot. Request-scoped values are available through `Context.data` and registered dependency providers. Extensions can own `@loop` background tasks; unloading an extension cancels its loops.

```python
router = Router()

@router.command("ping")
async def ping(ctx: Context) -> None:
    await ctx.send("pong")

bot.include_router(router)
```

## REST resources

The SDK exposes resources through `VoiceRouteClient` and the `voiceroute.api` namespace. The current additions include v1 channels/categories, roles and permission simulation, stickers and emoji expressions, rich messages, file upload and streamed download, thread and thread-message lifecycle, polls, AutoMod rules, webhooks, durable event subscriptions, and application private messages. `client.members.iter_members()` and `client.members.iter_search()` consume cursor pages lazily; `client.channels.start_typing()` starts an ephemeral typing lease. `client.voice.connect()` creates a single-use bot media credential and `client.voice.disconnect()` revokes that connection. Mutations that support optimistic concurrency accept `if_match`; retryable writes accept an idempotency key. Opaque cursors and version values remain strings.

Private application messages require a separately consented OAuth bearer client. They do not use or inherit the Bot token:

```python
async with oauth.private_messages(access_token) as dms:
    channel = await dms.open("@me", idempotency_key="open-request-1")
    await dms.send(channel["id"], content="Hello")
```

## OAuth

`OAuthClient` creates Authorization Code + PKCE requests, exchanges authorization codes, refreshes rotated refresh tokens through an `OAuthTokenStore`, and performs bearer-authenticated identity lookups. Persist refresh credentials in an encrypted secret store. Check `AuthorizationRequest.matches_state()` before exchanging a callback code.

## Events and state

Use Gateway for live bot events and `SubscriptionsAPI` for durable pull delivery with explicit acknowledgements. These cursors are independent. FSM storage is opt-in; `MemoryStorage` is process-local and `RedisStorage` requires the `redis` extra.

For HTTPS event callbacks, fetch application keys using `client.platform.verification_keys()` from the configured VoiceRoute origin. Pass the trusted key ID to `verify_signed_delivery()` with the original request bytes and an atomic replay store. Ed25519 verification requires the `webhooks` extra; unknown keys fail closed and should trigger a key refresh from the configured origin.

## Testing and optional dependencies

`FakeTransport` checks request order, payloads, headers, and idempotency keys. `FakeGatewaySocket` supplies deterministic Gateway frames. Install `voiceroute.py[redis]` for Redis-backed state or `voiceroute.py[voice]` for LiveKit media. Examples are in `examples/`.

## Compatibility note

The SDK remains pre-1.0. Legacy resource methods remain available where documented. Prefer v1 APIs when the application capability snapshot advertises them. Check the contract snapshot revision in `contracts/voiceroute/manifest.json` when validating a deployment.
