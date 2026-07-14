# AGENTS.md — Hermes Home Assistant Conversation Agent

## Repository mission

Build a thin Home Assistant Conversation Agent that sends an Assist utterance to the private, authenticated API server of a running Hermes instance and speaks its final response.

Home Assistant owns wake word, STT, TTS, Assist pipelines, device registry, and native automations. Hermes owns reasoning and tool execution. The component is an HTTP adapter only: it never exposes Home Assistant tool schemas or execution callbacks.

## Supported endpoint

The integration supports only the direct Hermes API server for the same running Hermes instance used by other channels. It must advertise `responses_api: true`, `chat_completions: true`, bearer auth, and the fixed `POST /v1/responses` endpoint, with no custom `security` member. Its tool/MCP policy is owned by that Hermes instance; it can execute the instance's configured capabilities.

Never substitute a restricted profile, HA-only allowlist, or alternate gateway contract for the direct Hermes instance.

## Bridge constraints

- Target only authenticated `POST /v1/responses`, `stream: false`, and opaque named conversations. Never use `/v1/chat/completions` from the bridge.
- Require authenticated `GET /v1/capabilities` before setup and each dispatch. Reject missing bearer auth, missing Responses endpoint, invalid `responses_api` or `chat_completions`, custom security contracts, and malformed capabilities.
- Create a fresh opaque conversation key per HA turn. Do not read or transmit inbound HA `ChatLog` history.
- Use only `{model, input, conversation, stream: false}`. A configured alias replaces only the `model` value. Never forward HA credentials, context objects, cookies, copied headers, device/user IDs, service tokens, tools, actions, instructions, or prompt overrides.
- Treat every timeout after request dispatch as indeterminate. Never automatically retry a dispatched request.
- TLS verification is on by default. Local/private HTTP requires explicit opt-in and an operator-visible warning.

## Safety rules

1. A voice utterance is not user authentication. Direct API-server mode intentionally inherits its full Hermes instance capability surface; explain this rather than claiming a prompt is protection.
2. The API server must remain private (LAN/Tailnet/reverse proxy), require bearer authentication, and have no unnecessary browser CORS.
3. Do not log transcripts or bearer tokens. Redact nested diagnostics and URL query values.
4. Do not add public listeners, arbitrary URL input, redirects, credential-bearing URLs, shell commands, or Home Assistant Core patches.
5. Preserve the working Voice path while testing a direct entry. Verify direct Assist text, a read-only HA request, and an explicitly authorized harmless action before normal control use.

## Development standards

- Use Home Assistant's current entity-based Conversation API and its shared async HTTP session.
- Validate URL scheme/host/path rules, TLS, redirects, JSON content type, response size, output length, model alias length, and timeouts.
- Implement config-entry lifecycle fully: unique ID/duplicate prevention, setup, unload/reload, options, reauth/token rotation, and unavailable-server behavior.
- Keep code small and dependency-light. Do not add STT, TTS, MQTT, a second automation system, or a webhook-first mode.

## Tests required before release

Cover exact default-model and alias request construction; DTO field exclusion; direct capability positive and negative cases; redirects; TLS and malformed URLs; oversized/non-JSON responses; timeouts; cancellation; entry isolation; config flow; reload/unload; duplicate entries; no automatic retry; and prompt/HA-context exclusion.

## Documentation requirements

Any behavior/configuration change must update `README.md`, `docs/installation-and-usage.md`, `docs/architecture.md`, and `SECURITY.md`. Never commit real URLs, tokens, device names, transcripts, screenshots containing secrets, or Home Assistant backups.
