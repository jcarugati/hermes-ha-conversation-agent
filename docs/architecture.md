# Architecture

## Current conversation bridge

The current code implements a UI config flow, complete entry lifecycle, and one
official Conversation entity per validated entry around the narrow Hermes client. Credential flows
canonicalize a base URL, atomically prevent duplicates by canonical identity, store the bearer token
in config-entry data, and validate health plus the authenticated Responses API
capability before saving. Permitted HTTP requires a distinct acknowledgement in user,
import, reauthentication, and options flows.

Every setup independently reconstructs a client from entry data and bounded
non-secret options, injects Home Assistant's shared asynchronous HTTP session, and
repeats health/capability validation. Unavailable endpoints raise
`ConfigEntryNotReady`; this includes HTTP 401/403 from unauthenticated health.
HTTP 401/403 from authenticated capabilities raises `ConfigEntryAuthFailed` so Home
Assistant starts reauthentication. Reload repeats setup and unload releases runtime
state without closing the shared session. Reauthentication rotates only the token and
reloads after validation; failure preserves the old token and performs no reload.
Options contain only connect timeout, total timeout, and maximum output length and
reload on change.

Setup validation performs no Responses POST. After validation, runtime data retains
only the client and advertised model and forwards the entry to the Conversation
platform. Unload removes the platform instance; reload validates and creates one fresh
instance without doubling entities.

The implemented `safety` module is an HA-local prototype declaration, not a production
boundary. It contains one immutable read-only/status request type and exposes no
executable action route. Its public API accepts no callable, utterance, operation,
prompt, spoken confirmation, action parameters, or generic tool list.

There is no coordinator, periodic polling, diagnostics, reused conversation-key
lock/cache/TTL, persistence/replay, tool interface, action path, prompt override, or
Voice end-to-end implementation. Fresh per-turn keys are the v0.1 design, not an
unfinished cache feature.

## Implemented bridge purpose

`hermes_conversation` is a Home Assistant custom component that implements a
Conversation entity. It receives `ConversationInput` from Assist, sends a restricted
request to the private Hermes Responses API, and returns a final speech response that
Home Assistant can send to TTS. It never calls `/v1/chat/completions`.

## Data flow

```text
Voice device → Home Assistant Assist STT
  → ConversationEntity.async_process(input, chat_log)
  → request DTO { model, input, conversation, stream: false }
  → private authenticated HTTPS connection to the no-tools home gateway
  → gateway-enforced Hermes POST /v1/responses
  → final text only
  → HA conversation response
  → HA TTS → voice device
```

## Trust boundaries

### Home Assistant

Home Assistant holds voice-device, Assist, and Home Assistant credentials. Those values remain inside Home Assistant. The component must not forward HA `Context`, long-lived tokens, cookies, headers, service-call data, or `ChatLog` content.

### Bridge component

The implemented asynchronous client is not a general proxy. It accepts only a base
URL, bearer token, and explicit limits from the entity caller; calls only `/health`,
`/v1/capabilities`, and `/v1/responses`; disables redirects; uses HTTPS by default;
and bounds payloads, output, connect time, and total time. It exposes no arbitrary
path, header, tool, or action parameters. Configuration, setup-time validation, and the
ConversationEntity request/response wiring now exist. The client uses only the injected shared
async session and refuses to dispatch if that session currently contains cookies.

Each `async_respond` validates bounded request data, then performs authenticated
`GET /v1/capabilities`. It sends exactly one `POST /v1/responses` only when the
capabilities object advertises bearer-required `responses_api`, the fixed endpoint,
the requested model, and exactly `security: {"tool_policy":"none","mcp_policy":"none",
"server_enforced":true}`. There is no capability cache and no retry. A generic remote
Hermes server, even one advertising `responses_api`, is outside this bridge contract.

### Hermes home gateway

The accepted gateway server-enforces that neither tools nor MCP are available. Hermes
owns any state within its named-conversation API, but the bridge generates a fresh
opaque key for every HA turn and never reuses a key for cross-turn HA history. The key
is not derived from a raw HA identifier. The integration does not accept a generic or
tool-capable Hermes server.

The committed verifier obtains the request `model` from authenticated `/v1/capabilities`, requires `features.responses_api: true`, the exact no-tools/MCP policy, and tests state across two requests carrying the same fresh opaque `conversation`. It passed against the deployed private home gateway on 2026-07-12; that evidence is gateway-specific. Exact requirements and limitations are in [`hermes-responses-contract.md`](hermes-responses-contract.md).

## Conversation state

This tracker deliberately creates a fresh cryptographically opaque key for each turn;
it never derives a Hermes key from the incoming HA conversation, user, device, or
entry identifier. Mapping, same-key serialization, idle expiry, bounded caching,
reset, persistence, and replay are deliberately absent from v0.1 home mode.

Only Hermes constructs model input within each fresh named turn. The entity neither
reads nor sends inbound HA `ChatLog` content and does not reuse the key, so v0.1 supplies
no cross-turn history and avoids duplicated turns and excess transcript exposure.
To complete Home Assistant's official dispatcher lifecycle, it adds only Hermes's
already-bounded returned assistant text to the local `ChatLog` through Home Assistant's
official no-tools completion method; that local completion is never copied into the
Hermes request DTO.

The verifier does not establish Hermes retention capacity or durability. Continuity is useful state, not assumed durable storage. A missing/forgotten conversation must fail safely or begin fresh without mixing keys.

## Failure behavior

| Condition | Required behavior |
| --- | --- |
| Endpoint unavailable before dispatch | Return brief spoken availability failure; no action occurred. |
| Auth/capability failure | Return setup-oriented failure; do not save unsupported config. |
| Capability HTTP/schema/auth/model/security-policy failure | Fail closed before POST. |
| Invalid JSON/content type/oversized response before POST | Return brief safe failure; log only redacted diagnostics. |
| POST HTTP error or malformed/oversized/invalid response | Say outcome may be unknown; do not retry automatically. |
| Timeout/disconnect after dispatch | Say outcome may be unknown; do not retry automatically. |
| Invalid completed-response schema or output | Return a concise sanitized failure; execute nothing. |

## High-impact actions

v0.1 exposes no tools, MCP, actions, executable callbacks, confirmation route, or prompt
override. Its accepted home gateway must advertise exactly `security:
{"tool_policy":"none","mcp_policy":"none","server_enforced":true}` during
configuration, setup, and immediately before each POST. Any other policy fails closed
before response dispatch.

This is a gateway-specific enforced home mode, not a claim about an independently
configured or generic Hermes server. The HA-local `safety.py` declaration is inert and
has no request or tool-execution sink. Model instructions and spoken confirmation do
not substitute for the exact server-enforced policy.

## Network deployment

A user should make Hermes reachable to Home Assistant only over a private path—such as a LAN reverse proxy or Tailscale—with TLS where possible. The verifier does not establish a default Hermes bind address. The API must not be directly Internet-accessible.

HTTP can be necessary on a trusted isolated LAN, but is an explicit opt-in because it
exposes bearer tokens and voice text to the network. Opt-in alone is insufficient:
the client accepts plaintext only for loopback, RFC 1918, link-local, IPv6 ULA,
Tailscale CGNAT (`100.64.0.0/10`), `localhost`, or `.local`, `.home.arpa`, and
`.ts.net` hostnames. It rejects public and unclassified HTTP hosts. Hostname suffixes
are an operator trust assertion; HTTPS remains preferred because DNS and the LAN are
otherwise part of the trust boundary.
