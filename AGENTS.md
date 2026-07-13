# AGENTS.md — Hermes Home Assistant Conversation Agent

## Repository mission

Build a **secure, thin Home Assistant custom Conversation Agent** that lets Home Assistant Assist / Home Assistant Voice send an utterance to Hermes Agent synchronously and speak Hermes’s concise final response.

Home Assistant owns wake word, STT, TTS, Assist pipelines, device registry, and native automations. Hermes owns reasoning behind a private gateway that server-enforces no tools or MCP. This component only adapts the official Home Assistant Conversation entity API to Hermes’s documented Responses API.

## v0.1 design boundary

- Target one verified Hermes contract: authenticated `POST /v1/responses` only, `stream: false`, and opaque named conversations. Never use `/v1/chat/completions`.
- Require authenticated `GET /v1/capabilities` to advertise `responses_api` and exactly `security: {"tool_policy":"none","mcp_policy":"none","server_enforced":true}`; fail closed otherwise.
- Create a fresh opaque conversation key for every HA turn. Hermes owns any state inside that named turn, but the bridge does not provide cross-turn history.
- Do not read or transmit inbound HA `ChatLog`; append only bounded Hermes assistant output to the local ChatLog through Home Assistant’s no-tools completion method.
- Use only the allowlisted request DTO `{model, input, conversation, stream: false}`. Never transmit HA credentials, context objects, cookies, copied headers, device/user IDs, service tokens, tools, MCP, actions, instructions, or prompt overrides.
- Treat every timeout after request dispatch as **indeterminate**. Never automatically retry a dispatched Responses request.
- Do not add conversation-key reuse, serialization, caching, idle expiry, reset, persistence, or replay to v0.1 home mode.
- TLS verification is on by default. Local HTTP requires explicit opt-in and an operator-visible warning.

## Non-negotiable safety rules

1. **A prompt is not a security boundary.** Do not claim that “ask for confirmation” is enough to protect dangerous actions.
2. v0.1 accepts no tools, MCP, actions, Home Assistant controls, executable callbacks, confirmation unlock, instructions, or prompt override. The exact server-enforced policy blocks all actions, including locks, alarms, garage/door actuators, pet feeders, destructive tasks, and Home Assistant configuration changes.
3. A voice utterance or spoken “confirmo” is not user authentication.
4. Do not log transcripts or bearer tokens. Redact nested diagnostics and URL query values.
5. Do not add a public listener, arbitrary URL input, redirects, credential-bearing URLs, shell commands, or Home Assistant Core patches.
6. No automatic retry on uncertain requests. Explain that the outcome may be unknown and provide a safe way to inspect state.

## Development standards

- Use Home Assistant’s current entity-based Conversation API; do not use obsolete `AbstractConversationAgent` registration patterns.
- Use Home Assistant’s shared async HTTP session; never block the event loop.
- Validate URL scheme/host/path rules, TLS, redirects, JSON content type, response size, output length, and timeouts.
- Implement config-entry lifecycle fully: unique ID/duplicate prevention, setup, unload/reload, options, reauth/token rotation, diagnostics, and unavailable-server behavior.
- Keep code small and dependency-light. Do not add STT, TTS, MQTT, a second automation system, or a webhook-first mode to v0.1.
- Do not infer generic Hermes compatibility or a minimum Hermes version from the successful 2026-07-12 live verifier run; its evidence applies only to the deployed private home gateway.

## Tests required before release

Cover: request construction; auth; exact security-policy enforcement; redirects; TLS and malformed URLs; oversized/non-JSON responses; connect/total timeout; cancellation; fresh per-turn conversation keys and entry isolation; config flow; reload/unload; duplicate config entries; no automatic retry; prompt-field exclusion; and proof that no tools, MCP, or actions can execute through v0.1.

CI should run unit tests, lint/type checks, Home Assistant validation/hassfest as applicable, HACS validation, package-layout checks, and secret/dependency scans.

## Documentation requirements

Any behavior/configuration change must update:

- `README.md` for the user-level capability/status statement.
- `docs/installation-and-usage.md` for setup and verification.
- `docs/architecture.md` for trust boundaries and data flow.
- `SECURITY.md` when safety or threat assumptions change.
- The implementation plan when it changes v0.1 scope or an acceptance criterion.

Never commit real URLs, tokens, user names, device names, transcripts, screenshots containing secrets, or Home Assistant backups.
