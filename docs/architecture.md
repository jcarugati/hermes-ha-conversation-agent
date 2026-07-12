# Architecture

## Purpose

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

### Bridge component

The component is an asynchronous HTTP client and Conversation entity—not a general proxy. It accepts only an operator-configured Hermes endpoint. It validates the endpoint, uses bearer authentication from its config entry, disables redirects, enforces normal TLS, bounds payloads/deadlines, and sanitizes final speech.

### Hermes

Hermes holds its own model/tool configuration and, if smart-home control is enabled, a separate Home Assistant credential. Hermes owns stateful named conversation history. The bridge must use an opaque conversation key, not a raw HA identifier.

The committed verifier obtains the request `model` from authenticated `/v1/capabilities`, requires `features.responses_api: true`, and tests state across two requests carrying the same fresh opaque `conversation`. Its strengthened checks await a fresh live run; the exact requirements and evidence limitations are in [`hermes-responses-contract.md`](hermes-responses-contract.md).

## Conversation state

The component maps each incoming HA conversation to a locally held opaque key. Requests for the same key run serially. Entries have an idle TTL and a maximum cache size. Reset/unload removes mappings locally; the exact Hermes-side deletion contract must be tested and documented before claiming hard deletion.

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

## Network deployment

A user should make Hermes reachable to Home Assistant only over a private path—such as a LAN reverse proxy or Tailscale—with TLS where possible. The verifier does not establish a default Hermes bind address. The API must not be directly Internet-accessible.

HTTP can be necessary on a trusted isolated LAN, but is an explicit opt-in because it exposes bearer tokens and voice text to the network.
