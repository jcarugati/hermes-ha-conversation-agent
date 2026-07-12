# Security policy

## Security posture

The proposed v0.1 production integration will bridge spoken requests from Home Assistant Assist to an agent capable of using tools. That production bridge will be a security-sensitive boundary and must prioritize a small attack surface, explicit trust boundaries, and fail-closed behavior over broad automation capability.

The current compatibility spike only registers a Conversation entity and returns a
fixed response. It does not connect to Hermes, send transcripts or tokens, expose
diagnostics, or implement the production network bridge described below. An unwired
client module implements the fixed outbound HTTP contract for future callers; it
stores configuration only in memory and never logs requests, URLs, transcripts, or
tokens.

The client has no arbitrary tool/action field or generic request interface. This
data-only shape prevents callers from adding tool definitions through the client, but
does not attest or constrain tools configured independently on Hermes. Production
wiring therefore remains blocked on the documented read-only/status execution-profile
control.

## Proposed security requirements for the v0.1 production bridge

The strengthened Hermes contract verifier has deterministic coverage but still awaits a fresh live run; no minimum Hermes version is currently claimed or pinned.

- Hermes API access over a private LAN/Tailscale/reverse-proxy route; never public Internet exposure.
- Bearer token supplied in an HTTP Authorization header, never in a URL.
- Normal TLS certificate validation by default; plaintext HTTP only with explicit acknowledgement.
- No redirects on authenticated outbound requests.
- Strict endpoint/response validation, bounded request/response sizes, and bounded deadlines.
- Home Assistant credentials, cookies, contexts, service tokens, device/user identifiers, and `ChatLog` history never leave HA through this integration.
- Voice transcripts and bearer tokens never appear in logs, diagnostics, entities, issue templates, fixtures, or Git history.
- Diagnostics use Home Assistant redaction utilities and are tested against nested sensitive fields.
- No automatic retry after a timeout or disconnect once a request could have reached Hermes.

## Proposed v0.1 handling of high-impact actions

A model instruction such as “ask for confirmation” does not reliably protect an action. Voice is also not identity proof.

Until Hermes provides a server-enforced confirmation API that binds a pending action ID, exact action parameters, origin conversation, and expiry, the proposed v0.1 production bridge must block high-impact actions. This includes locks, alarms, doors/garage, pet feeding, deletion/destructive commands, and Home Assistant configuration changes.

The committed HA-local prototype is a non-executing read-only/status declaration. Its
public API accepts no callable, operation, prompt, confirmation, or action parameters,
and it exposes no executable action route.

This is a prototype/interface property only, not end-to-end enforcement. Hermes tool
profiles are external server configuration, and the current inert component sends
nothing to Hermes and has no tool-execution sink. A future network bridge requires a
verified Hermes read-only/status execution profile and enforcement at every future
request and tool sink. It must verify the profile at startup and request time and fail
closed when the profile is absent, stale, or unverifiable. No such attestation or sink
integration exists in this repository today.

## Reporting a vulnerability

Please do **not** publish credentials, tokens, voice transcripts, network addresses, or proof-of-concept details in a public GitHub issue.

Open a private GitHub security advisory for this repository if available, or contact the repository owner privately with:

- A clear description of the issue and impact.
- Minimal reproduction steps with all secrets and personal data removed.
- Affected versions/commit.
- Suggested mitigations, if known.

The maintainers will acknowledge valid reports, coordinate a fix, and publish a disclosure after users have a reasonable update path.
