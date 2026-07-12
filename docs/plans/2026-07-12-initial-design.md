# Hermes Home Assistant Conversation Agent — Initial Design Plan

**Goal:** Build a Home Assistant custom integration that makes Hermes Agent available as an Assist conversation agent: spoken HA Voice requests go to Hermes, Hermes can use its existing tools (including Home Assistant controls), and Assist speaks Hermes’s concise final answer.

## Product outcome

A user selects **Hermes** under Home Assistant’s Voice Assistant settings and can say natural Spanish commands or questions. The custom integration forwards the utterance synchronously to the Hermes API, receives a final text answer, and returns it to Assist for TTS. A unique Home Assistant conversation/device maps to an isolated Hermes conversation so follow-up requests retain useful context without mixing users or rooms.

## Scope for v0.1

- A Home Assistant custom component, installable through HACS and manually.
- UI config flow for a reachable Hermes base URL and authentication token.
- Connectivity validation using Hermes’s authenticated health endpoint.
- A `conversation` platform implementation that forwards Assist text to Hermes’s OpenAI-compatible API.
- Per-conversation context continuity using a deterministic, privacy-preserving Hermes conversation key.
- Spanish-first, concise response instructions sent to Hermes.
- Explicit safety policy: normal home controls are allowed when unambiguous, but the proposed v0.1 production bridge must block locks, alarms, garage/door actuators, pet feeding, deletions, configuration changes, and other high-impact actions until Hermes provides a server-enforced pending-action protocol binding the action ID, exact parameters, source conversation, and expiry.
- Timeouts, useful spoken error responses, structured logging without secrets or raw authorization values.
- Unit tests for config validation, request construction, error handling, response parsing, and conversation-key isolation.
- Documentation: prerequisites, network topology, secure setup, HACS/manual installation, configuration, selecting Hermes as a conversation agent, troubleshooting, and threat model.

## Explicit non-goals for v0.1

- Do not expose Hermes directly to the public Internet.
- Do not implement STT, TTS, wake-word, or hardware support; Home Assistant owns that pipeline.
- Do not duplicate Home Assistant device-control logic in the integration; Hermes owns reasoning/tool selection.
- Do not add a webhook-only async mode as the primary interaction path; the goal is synchronous spoken replies.
- Do not treat a prompt or spoken confirmation as a safety boundary; high-impact actions remain blocked until the required server-enforced, parameter-bound pending-action protocol exists.
- Do not persist raw voice transcripts in the integration.

## Architecture

```text
Home Assistant Voice / Assist
  -> HA STT
  -> hermes_conversation custom integration (Conversation Agent)
  -> authenticated private HTTP connection
  -> Hermes API server (/v1/chat/completions or /v1/responses)
  -> Hermes Agent + existing Home Assistant tools
  -> final text response
  -> HA Conversation response
  -> HA TTS -> voice device
```

The custom component should be a thin asynchronous adapter using Home Assistant’s official Conversation platform API and its shared `aiohttp` client session. It should avoid shelling out, avoid accepting arbitrary callback URLs, and make only HTTPS requests by default. Local HTTP should require an explicit user acknowledgement because many homelabs use a trusted LAN/Tailscale path.

An operator should expose Hermes to Home Assistant only through a private reverse proxy or Tailscale/LAN route with TLS where feasible. The contract verifier does not establish a default Hermes bind address. Home Assistant stores the API token through the config-entry mechanism; it must never appear in logs, diagnostics, entity attributes, or Git history.

## Closed v0.1 contract and safety decisions

### Hermes API contract

v0.1 targets **`POST /v1/responses`** on a Hermes API server that advertises `responses_api: true` from `GET /v1/capabilities`. It sends a bearer token in `Authorization`, JSON content only, `stream: false`, a bounded plain-text `input`, and an opaque `conversation` key. Hermes’s current API documentation describes named conversations as the stateful mechanism; **Hermes is the only history owner**, so the HA integration does **not** include Home Assistant `ChatLog` history in requests.

The automated contract verifier defines the exact narrow `/v1/responses` request/response schema and tests named-conversation continuity with fresh run-scoped values. Its strengthened checks have not yet run against a live server, so no minimum Hermes version is pinned. Deterministic fixture tests run offline, while live verification requires an explicit flag, URL, and token. The integration must fail closed for an unsupported server/capability instead of silently falling back to another endpoint. It must never automatically retry a request that may have initiated an action: a network timeout is an indeterminate result.

### Conversation lifecycle

The integration uses Home Assistant’s current entity-based Conversation API (`ConversationEntity`, `ConversationInput`, and `ChatLog`) and advertises only the intended `CONTROL` capability. It maps HA conversation identity to a random opaque Hermes conversation key stored locally; it does not forward raw Home Assistant conversation, device, user, or assistant identifiers. The implementation must define and test identity fallback, one in-flight request per conversation, idle expiry, a bounded active-conversation cache, restart behavior, and reset/deletion behavior.

### Dangerous actions

A system prompt is not a security boundary. Until Hermes offers a verified tool-execution confirmation contract that binds a pending action ID, exact parameters, expiry, and the originating conversation, v0.1 must prevent high-impact categories from being available through this integration. Those categories include locks, alarms, garage/door actuators, pet feeding, destructive operations, and Home Assistant configuration changes. A spoken “confirmo” is never treated as authentication.

### Network, privacy, and credential boundary

Only an allowlisted request DTO (`input`, opaque `conversation`, declared model/options) crosses from HA to Hermes. Never forward HA contexts, service credentials, cookies, headers, long-lived access tokens, or `ChatLog` contents. Validate normal TLS; local HTTP is an explicit opt-in warning that transcripts and bearer tokens are exposed on that network. Reject URL credentials, redirects, unexpected content type, oversized payloads, and malformed JSON. Bound connect/total timeouts and output length. Redact tokens, URLs with sensitive query strings, and sensitive nested diagnostic data; do not log transcripts even at debug level.

## Remaining validation items

1. Pin the minimum Home Assistant version after compiling/running against its current Conversation entity API and testing setup/unload/reload registration.
2. Confirm Hermes’s `/v1/responses` schema and model identifier by running the strengthened automated contract verifier against the candidate minimum Hermes version; see `docs/hermes-responses-contract.md`.
3. Implement config-entry duplicate prevention, reauthentication/token rotation, options updates, TLS failures, and endpoint-unavailable behavior.
4. Define a future server-side confirmation capability before enabling high-impact actions.

### Tracker task: Restringir herramientas y acciones sensibles

- [x] Remove caller-controlled operation classification and the generic executable callback dispatcher.
- [x] Expose one HA-local, non-executing declaration for an explicit read-only/status capability.
- [x] Remove every executable route from the public policy API, including callable input.
- [x] Prove a high-impact callable cannot be passed through the public policy API or execute, and test only declaration/allowlist semantics.
- [x] Document that the inert spike has no Hermes execution sink and does not provide end-to-end enforcement.
- [ ] Require a verified Hermes read-only/status execution profile at every future request/tool sink, with startup and request-time fail-closed verification.

## Implementation phases

1. Repository and contributor documentation: README, AGENTS.md, security policy, architecture diagram, installation/use guide, development setup, and a detailed implementation plan.
2. Skeleton custom component: manifest, config flow, coordinator/client, and diagnostics redaction.
3. Conversation bridge: async process implementation, request/response contract, context key mapping, timeouts, and fallback speech.
4. Tests and CI: pytest test matrix against supported HA versions, lint/type checks, secret scan.
5. Packaging/release: HACS metadata, release checklist, example reverse-proxy guidance, and a v0.1 tagged release after a real HA Voice end-to-end test.

## Acceptance criteria for v0.1

- Installation does not require editing Home Assistant Core.
- HA can validate a configured Hermes endpoint before saving the entry.
- A selected Assist pipeline successfully receives and speaks a Hermes response.
- Two different Assist conversation IDs do not share context.
- Network failure, invalid auth, malformed API data, timeout, and Hermes tool failure return short, safe spoken failures rather than throwing an unhandled exception.
- Docs include a command/request health check and a full setup walkthrough.
- No token exists in repository files, logs, diagnostics, test fixtures, or screenshots.
