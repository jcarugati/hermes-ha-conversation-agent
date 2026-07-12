# Hermes Home Assistant Conversation Agent — Initial Design Plan

> **Historical plan, updated with current v0.1 decisions.** The implemented home mode is
> a private, server-enforced **no-tools/no-MCP** gateway. It is not a general Hermes
> tool/control bridge; the authoritative current behavior is documented in `README.md`,
> `SECURITY.md`, and `docs/architecture.md`.

**Goal:** Make the private no-tools Hermes home gateway available as an Assist conversation agent: spoken requests receive concise text replies, with no Home Assistant control actions.

## Product outcome

A user selects **Hermes** under Home Assistant’s Voice Assistant settings. The integration sends only a bounded utterance and fresh opaque conversation key to the trusted home gateway, receives final text, appends that result only to HA’s local ChatLog, and returns it for TTS. It never forwards HA conversation/device identity or inbound ChatLog.

## Scope for v0.1

- HACS/manual custom component, UI config flow, private endpoint and bearer validation.
- `conversation` platform that supports only the authenticated Responses API and the exact server-enforced no-tools/MCP capability policy.
- Fresh opaque key per HA turn; Hermes owns only its ephemeral named-conversation state.
- No tools, actions, prompts/instructions, Home Assistant controls, context forwarding, or confirmation-based unlocks.
- Timeouts, bounded safe spoken failures, and no secrets/transcripts in logs.
- Unit, dispatcher, and live private-gateway contract coverage.

## Explicit non-goals for v0.1

- Do not expose Hermes directly to the public Internet.
- Do not implement STT, TTS, wake-word, or hardware support; Home Assistant owns that pipeline.
- Do not enable device controls, tools, MCPs, callbacks, or high-impact actions.
- Do not treat a prompt or spoken confirmation as a safety boundary.
- Do not persist raw voice transcripts in the integration.

## Architecture

```text
Home Assistant Voice / Assist
  -> HA STT
  -> hermes_conversation custom integration (Conversation Agent)
  -> authenticated private HTTP connection
  -> Hermes API server (/v1/chat/completions or /v1/responses)
  -> Hermes Agent (no tools or MCP)
  -> final text response
  -> HA Conversation response
  -> HA TTS -> voice device
```

The custom component should be a thin asynchronous adapter using Home Assistant’s official Conversation platform API and its shared `aiohttp` client session. It should avoid shelling out, avoid accepting arbitrary callback URLs, and make only HTTPS requests by default. Local HTTP should require an explicit user acknowledgement because many homelabs use a trusted LAN/Tailscale path.

An operator should expose Hermes to Home Assistant only through a private reverse proxy or Tailscale/LAN route with TLS where feasible. The contract verifier does not establish a default Hermes bind address. Home Assistant stores the API token through the config-entry mechanism; it must never appear in logs, diagnostics, entity attributes, or Git history.

## Closed v0.1 contract and safety decisions

### Hermes API contract

v0.1 targets **`POST /v1/responses`** only on the simple Hermes home gateway. In addition
to `responses_api: true`, authenticated `GET /v1/capabilities` must advertise exactly
`security: {"tool_policy":"none","mcp_policy":"none","server_enforced":true}`. Generic
remote Hermes servers are outside scope. The bridge sends a bearer token in
`Authorization`, JSON content only, `stream: false`, a bounded plain-text `input`, and an
opaque `conversation` key. Hermes is the only history owner, so HA `ChatLog` is omitted.

The automated contract verifier defines the exact narrow `/v1/responses` request/response schema and tests named-conversation continuity with fresh run-scoped values. Its strengthened checks passed against the deployed private home gateway on 2026-07-12; the evidence is gateway-specific, so no generic Hermes compatibility or minimum version is pinned. Deterministic fixture tests run offline, while live verification requires an explicit flag, URL, and token. The integration must fail closed for an unsupported server/capability instead of silently falling back to another endpoint. It must never automatically retry a request that may have initiated an action: a network timeout is an indeterminate result.

### Conversation lifecycle

The integration uses Home Assistant’s current entity-based Conversation API (`ConversationEntity`, `ConversationInput`, and `ChatLog`) and advertises only the intended `CONTROL` capability. It creates a fresh random opaque Hermes key for each turn and does not forward raw Home Assistant conversation, device, user, assistant identifiers, or inbound `ChatLog`. Long-lived key mapping, per-conversation locking, idle expiry, reset, persistence, and replay behavior remain separate non-goals.

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

### Tracker task: Construir cliente HTTP seguro para Hermes

- [x] Add an injected-session asynchronous client for only `/health`,
  `/v1/capabilities`, and `/v1/responses`.
- [x] Enforce HTTPS by default, explicit HTTP opt-in, safe base URLs, bearer headers,
  disabled redirects, strict JSON/schema checks, and bounded payloads/deadlines.
- [x] Propagate cancellation and make dispatched response timeouts indeterminate with
  no automatic retry.
- [x] Keep the request interface data-only with no generic paths, headers, tools, or
  action fields.
- [x] Wire the client into config-entry validation and lifecycle.
- [ ] Wire the validated client into ConversationEntity behavior (separate tracker task).

### Tracker task: Implementar ciclo de vida del flujo de configuración

- [x] Add a UI-only config flow with normalized URL unique IDs and duplicate prevention.
- [x] Validate health, bearer authentication, and `responses_api` in both the flow and config-entry setup.
- [x] Require a separate acknowledgement for allowlisted local/private plaintext HTTP.
- [x] Add token-only reauthentication, bounded non-secret options, automatic reload, setup retry, and unload.
- [x] Use Home Assistant's shared asynchronous HTTP session without a coordinator or periodic checks.
- [x] Keep diagnostics/redaction, Conversation entities, request/bridge behavior, conversation state, tools, and actions outside this task.

## Implementation phases

1. Repository and contributor documentation: README, AGENTS.md, security policy, architecture diagram, installation/use guide, development setup, and a detailed implementation plan.
2. Skeleton custom component: manifest, config flow, and client lifecycle. Diagnostics
   and redaction are a separate tracker task; no coordinator is required for setup-only
   validation.
3. Conversation bridge: async process implementation, request/response contract, context key mapping, timeouts, and fallback speech.
4. Tests and CI: pytest test matrix against supported HA versions, lint/type checks, secret scan.
5. Packaging/release: HACS metadata, release checklist, example reverse-proxy guidance, and a v0.1 tagged release after a real HA Voice end-to-end test.

## Acceptance criteria for v0.1

- Installation does not require editing Home Assistant Core.
- HA can validate a configured Hermes endpoint before saving the entry.
- The standalone client revalidates authenticated `responses_api` capabilities before
  every Responses POST, requires the exact server-enforced no-tools/MCP policy, and proves
  that missing or mismatched policy dispatches no POST.
- Plaintext opt-in is constrained to the documented local/private/Tailscale address
  policy; public and unclassified HTTP hosts are rejected.
- Numeric deadlines and limits reject booleans, non-finite/non-positive values, and
  wrong types; client error representations never include the configured URL/token.
- Real loopback aiohttp tests cover redirect refusal (including bearer presence only on
  the refused initial request), cookie non-forwarding/refusal, rejection of an ephemeral
  self-signed certificate under aiohttp's normal trust validation, TLS non-downgrade,
  body-read timeout, cancellation, and exactly-one POST dispatch. Connect-timeout
  classification is exercised through a real `ClientSession` and asynchronous connector
  lifecycle whose connection establishment is deliberately stalled; this deterministic
  boundary proves aiohttp's connect deadline and the client's pre-dispatch classification
  without relying on environment-specific routing behavior for an unroutable address.
- A selected Assist pipeline successfully receives and speaks a Hermes response.
- Two different Assist conversation IDs do not share context.
- Network failure, invalid auth, malformed API data, timeout, and Hermes tool failure return short, safe spoken failures rather than throwing an unhandled exception.
- Docs include a command/request health check and a full setup walkthrough.
- No token exists in repository files, logs, diagnostics, test fixtures, or screenshots.
