# Migration guide

## 0.1 development API additions

- Bot can use an injected `VoiceRouteClient`; ownership controls whether closing the Bot closes that client.
- `MembersAPI.get()` and cursor-based `search()` provide direct server lookup instead of fetching the full community member snapshot.
- Rich v1 messages, uploads, channels/categories, threads, polls, webhooks, and durable subscriptions are explicit resource APIs. Existing legacy methods remain available; `api_version` only selects adapters that implement both route families.
- Gateway message dispatch can handle prefix commands when the required content capability is granted. SSE remains the compatibility path for deployments that do not provide sufficient Gateway payloads.
- `Router`, dependency providers, command enum conversion, hybrid command registration, `View`, FSM storage, and supervised extension loops extend the existing Bot pipeline.
- Router filters, middleware, and providers can be scoped to a command subtree. Entity converters perform explicit fetches for member, channel, and role parameters.
- `RolesAPI` preserves legacy methods and adds v1 CRUD/order, collection ETags, permission registry, effective permissions, simulation, and conditional overrides via `*_v1` methods.
- Signed durable callbacks can be verified against public keys fetched from the configured origin; use an atomic replay store and preserve the raw request body.
- OAuth credentials are separate from Bot tokens. Use PKCE and persist rotating refresh tokens using a secure `OAuthTokenStore`.

## Before upgrading

Review constructor changes and exports in the current reference, confirm the server contract revision and grants, and retain legacy API calls until the corresponding v1 capability is available in the target deployment. Do not treat a successful mock/contract check as live-server conformance.
