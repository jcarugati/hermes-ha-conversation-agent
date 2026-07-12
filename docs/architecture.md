# Architecture

## Current config-entry foundation

The current code is not the bridge described below. It implements a UI-only config
flow and complete entry lifecycle around the narrow Hermes client. The user step
normalizes a base URL, prevents duplicates by normalized URL, stores the bearer token
in config-entry data, and validates health plus the authenticated Responses API
capability before saving. Permitted HTTP requires a distinct acknowledgement step.

Every setup independently reconstructs a client from entry data and bounded
non-secret options, injects Home Assistant's shared asynchronous HTTP session, and
repeats health/capability validation. Unavailable endpoints raise
`ConfigEntryNotReady`; reload repeats setup and unload releases runtime state without
closing the shared session. Reauthentication rotates only the token and reloads after
validation. Options contain only connect timeout, total timeout, and maximum output
length and reload on change.

There is no coordinator, periodic polling, diagnostics, Conversation entity, request
bridge, conversation state/cache, tool interface, or action path. Setup validation
performs no Responses POST.

The implemented `safety` module is an HA-local prototype declaration, not a production
boundary. It contains one immutable read-only/status request type and exposes no
executable action route. Its public API accepts no callable, utterance, operation,
prompt, spoken confirmation, action parameters, or generic tool list.

Everything below remains the planned v0.1 bridge architecture and is not implemented
by the config-entry foundation.

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

The implemented asynchronous client is not a general proxy. It accepts only a base
URL, bearer token, and explicit limits from a future caller; calls only `/health`,
`/v1/capabilities`, and `/v1/responses`; disables redirects; uses HTTPS by default;
and bounds payloads, output, connect time, and total time. It exposes no arbitrary
path, header, tool, or action parameters. Configuration and setup-time validation now
exist; conversation/request wiring does not. The client uses only the injected shared
async session and refuses to dispatch if that session currently contains cookies.

Each `async_respond` validates bounded request data, then performs authenticated
`GET /v1/capabilities`. It sends exactly one `POST /v1/responses` only when the
capabilities object advertises bearer-required `responses_api`, the fixed endpoint,
and the requested model. There is no capability cache and no retry.

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
| Capability HTTP/schema/auth/model failure | Fail closed before POST. |
| Invalid JSON/content type/oversized response before POST | Return brief safe failure; log only redacted diagnostics. |
| POST HTTP error or malformed/oversized/invalid response | Say outcome may be unknown; do not retry automatically. |
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

HTTP can be necessary on a trusted isolated LAN, but is an explicit opt-in because it
exposes bearer tokens and voice text to the network. Opt-in alone is insufficient:
the client accepts plaintext only for loopback, RFC 1918, link-local, IPv6 ULA,
Tailscale CGNAT (`100.64.0.0/10`), `localhost`, or `.local`, `.home.arpa`, and
`.ts.net` hostnames. It rejects public and unclassified HTTP hosts. Hostname suffixes
are an operator trust assertion; HTTPS remains preferred because DNS and the LAN are
otherwise part of the trust boundary.
