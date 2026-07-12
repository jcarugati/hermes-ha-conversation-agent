# AGENTS.md — Hermes Home Assistant Conversation Agent

## Repository mission

Build a **secure, thin Home Assistant custom Conversation Agent** that lets Home Assistant Assist / Home Assistant Voice send an utterance to Hermes Agent synchronously and speak Hermes’s concise final response.

Home Assistant owns wake word, STT, TTS, Assist pipelines, device registry, and native automations. Hermes owns reasoning and its own configured tools. This component only adapts the official Home Assistant Conversation entity API to Hermes’s documented API.

## v0.1 design boundary

- Target one verified Hermes contract: `POST /v1/responses`, bearer authentication, `stream: false`, and opaque named conversations.
- Require `GET /v1/capabilities` to advertise `responses_api`; fail closed if it does not.
- Hermes, not Home Assistant `ChatLog`, owns cross-turn history. Do not transmit HA `ChatLog` history.
- Use an allowlisted request DTO only: bounded utterance text, opaque conversation key, and explicit supported options. Never transmit HA credentials, context objects, cookies, headers, device/user IDs, or service tokens.
- Treat every timeout after request dispatch as **indeterminate**. Never automatically retry an action-bearing request.
- Serialize requests per conversation, bound the cache, define idle expiry/reset, and never cross-contaminate conversations.
- TLS verification is on by default. Local HTTP requires explicit opt-in and an operator-visible warning.

## Non-negotiable safety rules

1. **A prompt is not a security boundary.** Do not claim that “ask for confirmation” is enough to protect dangerous actions.
2. Until Hermes supports an enforceable server-side pending-action protocol that binds action ID, exact parameters, source conversation, and expiry, block high-impact actions in this integration: locks, alarms, garage/door actuators, pet feeders, destructive tasks, and Home Assistant configuration changes.
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
- Pin minimum supported Home Assistant and Hermes versions only after a contract test proves compatibility.

## Tests required before release

Cover: request construction; auth; redirects; TLS and malformed URLs; oversized/non-JSON responses; connect/total timeout; cancellation; same-conversation serialization; conversation expiry/reset; missing/reused IDs; config flow; reload/unload; diagnostics redaction; duplicate config entries; no automatic retry; prompt injection; stale/replayed confirmation; and proof that high-impact actions cannot execute through v0.1.

CI should run unit tests, lint/type checks, Home Assistant validation/hassfest as applicable, HACS validation, package-layout checks, and secret/dependency scans.

## Documentation requirements

Any behavior/configuration change must update:

- `README.md` for the user-level capability/status statement.
- `docs/installation-and-usage.md` for setup and verification.
- `docs/architecture.md` for trust boundaries and data flow.
- `SECURITY.md` when safety or threat assumptions change.
- The implementation plan when it changes v0.1 scope or an acceptance criterion.

Never commit real URLs, tokens, user names, device names, transcripts, screenshots containing secrets, or Home Assistant backups.
