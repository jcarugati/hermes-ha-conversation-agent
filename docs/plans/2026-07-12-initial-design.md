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
  -> private authenticated Hermes API server (POST /v1/responses only)
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
opaque `conversation` key. The bridge never calls `/v1/chat/completions`. Hermes owns
any state inside the named-conversation API, while the bridge never reuses a key across
HA turns and omits inbound HA `ChatLog`.

The automated contract verifier defines the exact narrow `/v1/responses` request/response schema and tests named-conversation continuity with fresh run-scoped values. Its strengthened checks passed against the deployed private home gateway on 2026-07-12; the evidence is gateway-specific, so no generic Hermes compatibility or minimum version is pinned. Deterministic fixture tests run offline, while live verification requires an explicit flag, URL, and token. The integration must fail closed for an unsupported server/capability instead of silently falling back to another endpoint. Once a Responses POST is dispatched, a timeout or disconnect is indeterminate and the bridge never retries automatically, even though v0.1 exposes no action path.

### Conversation lifecycle

The integration uses Home Assistant’s current entity-based Conversation API (`ConversationEntity`, `ConversationInput`, and `ChatLog`) and advertises no control features. It creates a fresh random opaque Hermes key for each turn and does not forward raw Home Assistant conversation, device, user, assistant identifiers, or inbound `ChatLog`. Long-lived key mapping, per-conversation locking, idle expiry, reset, persistence, and replay behavior remain separate non-goals.

### Dangerous actions

A system prompt is not a security boundary. v0.1 accepts no tools, MCP, actions,
Home Assistant controls, executable callbacks, instructions, prompt override, or
confirmation unlock. The exact server-enforced no-tools/no-MCP policy therefore blocks
locks, alarms, garage/door actuators, pet feeding, destructive operations, Home
Assistant configuration changes, and all other actions. A spoken “confirmo” is never
treated as authentication.

### Network, privacy, and credential boundary

Only the allowlisted request DTO `{model, input, conversation, stream: false}` crosses
from HA to Hermes. It has no tool, MCP, action, instruction, or prompt-override field.
Never forward HA contexts, service credentials, cookies, copied headers, long-lived
access tokens, or inbound `ChatLog` contents. Validate normal TLS; local HTTP is an
explicit opt-in warning that transcripts and bearer tokens are exposed on that network.
Reject URL credentials, redirects, unexpected content type, oversized payloads, and
malformed JSON. Bound connect/total timeouts and output length. Redact tokens, URLs with
sensitive query strings, and sensitive nested diagnostic data; do not log transcripts
even at debug level.

## Remaining validation items

1. Keep the exercised Home Assistant development version distinct from any future
   published minimum-version declaration.
2. Preserve the 2026-07-12 strengthened live-verifier result as evidence for the
   deployed private home gateway only; do not infer generic compatibility or a minimum
   Hermes version. See `docs/hermes-responses-contract.md`.
3. Complete release validation and a real HA Voice end-to-end test before publishing.

### Tracker task: Restringir herramientas y acciones sensibles

- [x] Remove caller-controlled operation classification and the generic executable callback dispatcher.
- [x] Expose one HA-local, non-executing declaration for an explicit read-only/status capability.
- [x] Remove every executable route from the public policy API, including callable input.
- [x] Prove a high-impact callable cannot be passed through the public policy API or execute, and test only declaration/allowlist semantics.
- [x] Document that the inert spike has no Hermes execution sink and does not provide end-to-end enforcement.
- [x] Supersede the inert declaration with the exact gateway-enforced v0.1 policy:
  tools and MCP are both `none`, with no execution sink or prompt override.

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
- [x] Wire the validated client into ConversationEntity behavior with a fresh opaque
  key per HA turn and bounded local ChatLog completion.

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
3. Conversation bridge: async process implementation, fixed request/response contract,
   fresh per-turn opaque keys, timeouts, and fallback speech.
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
- Network failure, invalid auth, malformed API data, timeout, and invalid response output
  return short, safe spoken failures rather than throwing an unhandled exception.
- Docs include a command/request health check and a full setup walkthrough.
- No token exists in repository files, logs, diagnostics, test fixtures, or screenshots.
