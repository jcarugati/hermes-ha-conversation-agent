# Security policy

## Security posture

This project bridges spoken requests from Home Assistant Assist to an agent capable of using tools. That makes the bridge a security-sensitive boundary. The project prioritizes a small attack surface, explicit trust boundaries, and fail-closed behavior over broad automation capability.

## Supported security baseline for v0.1

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

## High-impact actions

A model instruction such as “ask for confirmation” does not reliably protect an action. Voice is also not identity proof.

Until Hermes provides a server-enforced confirmation API that binds a pending action ID, exact action parameters, origin conversation, and expiry, this project must block high-impact actions from the voice bridge. This includes locks, alarms, doors/garage, pet feeding, deletion/destructive commands, and Home Assistant configuration changes.

## Reporting a vulnerability

Please do **not** publish credentials, tokens, voice transcripts, network addresses, or proof-of-concept details in a public GitHub issue.

Open a private GitHub security advisory for this repository if available, or contact the repository owner privately with:

- A clear description of the issue and impact.
- Minimal reproduction steps with all secrets and personal data removed.
- Affected versions/commit.
- Suggested mitigations, if known.

The maintainers will acknowledge valid reports, coordinate a fix, and publish a disclosure after users have a reasonable update path.
