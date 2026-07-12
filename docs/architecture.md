# Architecture

## Current installable compatibility spike

The code currently present is not the bridge described in the remaining sections. It
is a deliberately minimal, YAML-loadable compatibility spike for Home Assistant Core
2026.7.1. The versioned manifest makes the copied custom-component package
recognizable to Home Assistant; root `hacs.json` metadata makes the repository
recognizable as a HACS custom integration repository. Neither mechanism publishes a
release or adds configuration behavior. During setup it adds one `ConversationEntity`
to Home Assistant's conversation entity component. Home Assistant passes
`ConversationInput` and creates the required `ChatLog`; the spike does not inspect,
log, persist, or forward their transcript content. It returns a fixed `query_answer`
with no successful or failed action targets.

The spike contains no network client, Hermes configuration, capability validation,
conversation state, cache, TTL, serialization, diagnostics, config flow, or tools.
Its HA-backed registration and `async_converse` test is evidence for this narrow API
shape and minimal package layout only, not for production installation lifecycle,
Assist/Voice pipelines, Hermes interoperability, or production readiness.

The implemented `safety` module is an HA-local prototype declaration, not a production
boundary. It contains one immutable read-only/status request type and exposes no
executable action route. Its public API accepts no callable, utterance, operation,
prompt, spoken confirmation, action parameters, or generic tool list.

Everything below remains the planned v0.1 architecture and is not implemented by the
spike.

## Planned v0.1 purpose

`hermes_conversation` will be a Home Assistant custom component that implements a Conversation entity. It receives `ConversationInput` from Assist, sends a restricted request to the Hermes API, and returns a final speech response that Home Assistant can send to TTS.

## Data flow

```text
Voice device → Home Assistant Assist STT
  → ConversationEntity.async_process(input, chat_log)
  → request DTO { model, input, conversation, stream: false }
  → private authenticated HTTPS connection
  → Hermes POST /v1/responses
  → Hermes runs its own configured tools
  → final text only
  → HA conversation response
  → HA TTS → voice device
```

## Trust boundaries

### Home Assistant

Home Assistant holds voice-device, Assist, and Home Assistant credentials. Those values remain inside Home Assistant. The component must not forward HA `Context`, long-lived tokens, cookies, headers, service-call data, or `ChatLog` content.

### Proposed bridge component

The planned component would be an asynchronous HTTP client and Conversation entity,
not a general proxy. The v0.1 design requires it to accept only an operator-configured
Hermes endpoint, validate that endpoint, use bearer authentication, disable redirects,
enforce normal TLS, bound payloads and deadlines, and sanitize final speech. None of
these production features exist in the spike.

### Hermes

Hermes holds its own model/tool configuration and, if smart-home control is enabled, a separate Home Assistant credential. Hermes owns stateful named conversation history. The bridge must use an opaque conversation key, not a raw HA identifier.

The committed verifier obtains the request `model` from authenticated `/v1/capabilities`, requires `features.responses_api: true`, and tests state across two requests carrying the same fresh opaque `conversation`. Its strengthened checks await a fresh live run; the exact requirements and evidence limitations are in [`hermes-responses-contract.md`](hermes-responses-contract.md).

## Conversation state

The planned component would map each incoming HA conversation to a locally held opaque
key. The v0.1 design requires same-key serialization, idle expiry, a bounded cache, and
local reset/unload behavior. The exact Hermes-side deletion contract must be tested
and documented before claiming hard deletion.

Only Hermes holds dialogue history. The HA `ChatLog` is not sent to avoid duplicating turns and leaking more transcript context than necessary.

The verifier does not establish Hermes retention capacity or durability. Continuity is useful state, not assumed durable storage. A missing/forgotten conversation must fail safely or begin fresh without mixing keys.

## Failure behavior

| Condition | Required behavior |
| --- | --- |
| Endpoint unavailable before dispatch | Return brief spoken availability failure; no action occurred. |
| Auth/capability failure | Return setup-oriented failure; do not save unsupported config. |
| Invalid JSON/content type/oversized response | Return brief safe failure; log only redacted diagnostics. |
| Timeout/disconnect after dispatch | Say outcome may be unknown; do not retry automatically. |
| Hermes tool failure | Return Hermes’s safe final text if available; otherwise concise failure. |

## High-impact actions

v0.1 does not expose high-impact actions through this component until Hermes has an auditable execution-time confirmation mechanism. A model prompt or a spoken confirmation alone is insufficient. High-impact includes locks, alarms, doors/garage, feeders, destructive operations, and HA configuration changes.

This repository cannot enforce which tools an independently configured Hermes server
loads, and the inert spike has no Hermes request or tool-execution sink. The HA-local
prototype therefore does not establish end-to-end enforcement or production
readiness.

A real bridge requires Hermes to advertise a verifiable read-only/status execution
profile. The integration must enforce that restriction at every future request and
tool-execution sink, verify it both at startup and for each request, and fail closed
when the profile is absent, stale, or unverifiable. Until that sink integration exists,
the local declaration alone does not enforce Hermes behavior. Prompt instructions and
spoken confirmation cannot substitute for these controls.

## Network deployment

A user should make Hermes reachable to Home Assistant only over a private path—such as a LAN reverse proxy or Tailscale—with TLS where possible. The verifier does not establish a default Hermes bind address. The API must not be directly Internet-accessible.

HTTP can be necessary on a trusted isolated LAN, but is an explicit opt-in because it exposes bearer tokens and voice text to the network.
