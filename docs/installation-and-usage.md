# Installation and usage

> **Current status:** configuration lifecycle and endpoint validation are implemented,
> but no Conversation entity or Assist/Hermes request bridge exists yet.

## Install the development integration

The repository has the standard `custom_components/hermes_conversation` package and
HACS custom-repository metadata. It is not published as a release or default HACS
listing.

For manual installation, copy `custom_components/hermes_conversation/` into
`/config/custom_components/` and restart Home Assistant. Do not add YAML;
configuration is UI-only.

Go to **Settings → Devices & services → Add integration** and select **Hermes
Conversation Agent**.

## Configure Hermes

Enter a private Hermes base URL with no credentials, path, query, or fragment, plus a
dedicated bearer token. The flow canonicalizes DNS case and trailing dots, Unicode IDNs
to punycode, IPv6 text, and default ports, then uses that identity as the entry's unique
ID. Home Assistant's in-progress reservation prevents equivalent concurrent flows from
creating duplicates. Non-root paths, including encoded variants, are rejected.

Before saving, the flow validates `GET /health` and authenticated
`GET /v1/capabilities`, including `responses_api`, bearer-required authentication, and
the fixed Responses endpoint advertisement. Setup repeats the same validation. If
Hermes is unavailable, Home Assistant keeps the entry retryable instead of loading
unvalidated runtime state.

HTTPS is accepted by default. Plaintext HTTP is restricted to the documented
local/private/Tailscale host allowlist and opens a separate acknowledgement step. User,
import, reauthentication, and options flows each require acknowledgement before making
an HTTP validation request or accepting changes. The warning explains that the bearer
token and future request data would be visible on the network. Acknowledgement does not
weaken the host allowlist.

## Maintain an entry

- Reauthentication accepts only a replacement token, validates it against the fixed
  endpoint, updates the entry, and reloads it. An HTTP 401 or 403 during setup starts
  Home Assistant reauthentication. A failed replacement leaves stored data unchanged
  and does not reload the entry.
- **Configure** changes connect timeout, total timeout, and maximum output characters.
  Options never expose the URL or token and automatically reload the entry when saved.
- Reload reconstructs and revalidates a fresh client. Unload releases entry-owned
  runtime state without closing Home Assistant's shared HTTP session.

## Verify configuration

A loaded entry proves only that the endpoint was healthy and advertised the required
authenticated capability at setup time. It does not prove Voice, conversation, tool,
or action behavior. There is currently no Hermes agent to select under **Settings →
Voice assistants**.

If setup is retrying:

1. Verify private DNS/routing and TLS trust from the Home Assistant host.
2. Verify the token against `GET /v1/capabilities` without placing it in the URL or logs.
3. Confirm `features.responses_api` is `true` and the advertised auth/endpoint contract matches the verifier.
4. For HTTP, confirm the host belongs to an allowed private class.

Contract checks are documented in
[`hermes-responses-contract.md`](hermes-responses-contract.md).

## Deliberately excluded

This implementation has no diagnostics endpoint or diagnostics redaction,
coordinator, periodic polling, Conversation entity, utterance forwarding,
conversation state, tool declarations, or action execution path. These require
separate reviewed tracker tasks. No high-impact action can execute through this
configuration-only lifecycle.
