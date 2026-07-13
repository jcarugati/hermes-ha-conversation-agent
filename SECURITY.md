# Security policy

## Security posture

The v0.1 integration bridges spoken requests only to authenticated
`POST /v1/responses` on the private Hermes home gateway in its server-enforced no-tools
mode. It never uses `/v1/chat/completions` and does not support a generic remote or
tool-capable Hermes server. This remains a security-sensitive boundary and prioritizes
a small attack surface, explicit trust boundaries, and fail-closed behavior over broad
automation.

The current integration stores a Hermes URL and bearer token through Home Assistant's
UI config-entry mechanism, validates health/authenticated capabilities in both the
flow and setup, and registers one official Conversation entity per validated entry.
The entity sends only a bounded utterance, validated model, and fresh opaque key and
returns bounded final text. It never reads or forwards inbound `ChatLog`, HA context,
device/user IDs, extra system prompts, or credentials. It adds only Hermes's bounded
assistant result to HA's local `ChatLog` to complete the official dispatcher lifecycle;
that local content is not added to the client DTO.
Diagnostics and diagnostics redaction are explicitly excluded from this tracker task.
The client and lifecycle never log requests, URLs, transcripts, or tokens.
HTTP 401/403 responses have a dedicated sanitized error path that starts Home
Assistant reauthentication during setup; rejected replacement credentials do not
overwrite the working entry or trigger a reload.

The entity and client have no arbitrary tool/action field, execution callback, or generic
request interface. In addition, every authenticated capabilities validation must receive
exactly `security: {"tool_policy":"none","mcp_policy":"none","server_enforced":true}`.
Missing, mismatched, or extended policy objects fail closed before configuration, setup,
or response dispatch. This is the gateway-enforced home boundary, not a prompt claim.

## Enforced security requirements for v0.1 home mode

On 2026-07-12 the strengthened verifier passed against the deployed private home gateway, including its exact no-tools/MCP policy and two-turn continuity. The evidence is specific to that gateway; no generic Hermes compatibility or minimum version is claimed or pinned.

- Hermes API access over a private LAN/Tailscale/reverse-proxy route; never public Internet exposure.
- Bearer token supplied in an HTTP Authorization header, never in a URL.
- Normal TLS certificate validation by default. Plaintext HTTP requires explicit
  acknowledgement in every configuration lifecycle flow and is accepted only for loopback, RFC 1918, IPv4/IPv6 link-local,
  IPv6 ULA, Tailscale `100.64.0.0/10`, or hostnames ending in `.local`, `.home.arpa`,
  or `.ts.net` (plus `localhost`). Public and unclassified HTTP hosts are rejected.
- Endpoint identity canonicalizes DNS case/trailing dots, IDN punycode, IPv6 text, and
  default ports before atomic duplicate checks; all non-root path variants are rejected.
- No redirects on authenticated outbound requests.
- Require the exact authenticated, server-enforced no-tools/MCP security policy during
  configuration, setup, reload, reauthentication, and immediately before every POST.
- Refuse an injected shared session that currently contains cookies, so Home
  Assistant cookies cannot accompany Hermes requests. The client never creates a
  private session.
- Strict endpoint/response validation, bounded request/response sizes, and bounded deadlines.
- Home Assistant credentials, cookies, contexts, service tokens, device/user identifiers, and `ChatLog` history never leave HA through this integration.
- Voice transcripts and bearer tokens never appear in logs, diagnostics, entities, issue templates, fixtures, or Git history.
- The current integration exposes no diagnostics platform; future diagnostics must use
  Home Assistant redaction utilities and cover nested sensitive fields before release.
- No automatic retry after a timeout or disconnect once a request could have reached Hermes.
- Every Responses API call revalidates authenticated capabilities before POST; a
  failed capability check sends no POST. Once POST is dispatched, HTTP errors,
  malformed/oversized/invalid responses, read timeouts, and disconnects are reported
  as indeterminate and are never retried automatically.

## v0.1 handling of actions and prompt override

A model instruction such as “ask for confirmation” does not reliably protect an action. Voice is also not identity proof.

v0.1 home mode exposes no tools, MCP, actions, Home Assistant controls, executable
callbacks, confirmation route, instructions, or prompt override. This blocks locks,
alarms, doors/garage actuators, pet feeding, destructive operations, and Home Assistant
configuration changes together with every lower-impact action rather than attempting
to classify an utterance.

The boundary is enforced twice: the public request interface contains no executable or
prompt fields, and configuration, setup, and every response request require the gateway
to advertise exactly `security: {"tool_policy":"none","mcp_policy":"none",
"server_enforced":true}`. Missing, different, or extended policy fails closed before
`POST /v1/responses`. The inert HA-local `safety.py` declaration is not an execution
sink and does not weaken this gateway-enforced boundary.

## Reporting a vulnerability

Please do **not** publish credentials, tokens, voice transcripts, network addresses, or proof-of-concept details in a public GitHub issue.

Open a private GitHub security advisory for this repository if available, or contact the repository owner privately with:

- A clear description of the issue and impact.
- Minimal reproduction steps with all secrets and personal data removed.
- Affected versions/commit.
- Suggested mitigations, if known.

The maintainers will acknowledge valid reports, coordinate a fix, and publish a disclosure after users have a reasonable update path.
