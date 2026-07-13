# Installation and usage

> **Current status:** each loaded, validated entry registers one selectable Conversation
> entity and forwards one bounded final-response request per Home Assistant turn.

## Install the development integration

The repository has the standard `custom_components/hermes_conversation` package and
HACS custom-repository metadata. It is not published as a release or default HACS
listing.

For manual installation, copy `custom_components/hermes_conversation/` into
`/config/custom_components/` and restart Home Assistant. Do not add YAML;
configuration is UI-only.

Go to **Settings → Devices & services → Add integration** and select **Hermes
Conversation Agent**.

## Configure the Hermes home gateway

Enter a private Hermes base URL with no credentials, path, query, or fragment, plus a
dedicated bearer token. The flow canonicalizes DNS case and trailing dots, Unicode IDNs
to punycode, IPv6 text, and default ports, then uses that identity as the entry's unique
ID. Home Assistant's in-progress reservation prevents equivalent concurrent flows from
creating duplicates. Non-root paths, including encoded variants, are rejected.

Before saving, the flow validates `GET /health` and authenticated
`GET /v1/capabilities`, including `responses_api`, bearer-required authentication, and
the fixed Responses endpoint advertisement. It also requires the authenticated response
to advertise exactly `security: {"tool_policy":"none","mcp_policy":"none",
"server_enforced":true}`. This gateway-enforced home mode is not a generic remote Hermes
server configuration; missing keys, different values, or extra policy keys are rejected.
Setup repeats the same validation. If
Hermes is unavailable, Home Assistant keeps the entry retryable instead of loading
unvalidated runtime state. This includes HTTP 401/403 from the unauthenticated health
endpoint. Only HTTP 401/403 from authenticated capabilities starts reauthentication.

HTTPS is accepted by default. Plaintext HTTP is restricted to the documented
local/private/Tailscale host allowlist and opens a separate acknowledgement step. User,
import, reauthentication, and options flows each require acknowledgement before making
an HTTP validation request or accepting changes. The warning explains that the bearer
token and future request data would be visible on the network. Acknowledgement does not
weaken the host allowlist.

## Maintain an entry

- Reauthentication accepts only a replacement token, validates it against the fixed
  endpoint, updates the entry, and reloads it. An HTTP 401 or 403 from authenticated
  capabilities during setup starts Home Assistant reauthentication. A failed
  replacement leaves stored data unchanged and does not reload the entry.
- **Configure** changes connect timeout, total timeout, and maximum output characters.
  Options never expose the URL or token and automatically reload the entry when saved.
- Reload reconstructs and revalidates a fresh client. Unload releases entry-owned
  runtime state without closing Home Assistant's shared HTTP session.

## Verify configuration

A loaded entry exposes one Hermes agent under **Settings → Voice assistants**. Select
it in an Assist pipeline, submit a short test utterance, and verify that Hermes's
concise final text is spoken. This validates the Conversation dispatcher path, not a
full wake-word/STT/TTS Voice end-to-end test.

Each turn sends only the utterance, setup-validated model, and a fresh opaque
conversation key. The bridge does not read or send inbound `ChatLog`, HA context,
device/user IDs, extra system prompts, credentials, tools, or actions. Once Hermes
returns, the bridge records only its bounded assistant text in HA's local `ChatLog`
using the official no-tools completion API. A request-time authentication
failure starts reauthentication. Other failures return fixed sanitized conversation
errors; an indeterminate dispatched POST is never retried and instructs the operator
to inspect state before trying again.

If setup is retrying:

1. Verify private DNS/routing and TLS trust from the Home Assistant host.
2. Verify the token against `GET /v1/capabilities` without placing it in the URL or logs.
3. Confirm `features.responses_api` is `true`, the auth/endpoint contract matches, and
   `security` is exactly the server-enforced no-tools policy above.
4. For HTTP, confirm the host belongs to an allowed private class.

Contract checks are documented in
[`hermes-responses-contract.md`](hermes-responses-contract.md).

## Deliberately excluded

This implementation has no diagnostics, coordinator, periodic polling, reused-key
locks/cache/TTL/persistence/replay, voice end-to-end support, tool declarations,
action execution path, prompt override, or confirmation unlock. Fresh opaque keys per
HA turn are intentional v0.1 behavior; the omitted lifecycle features are outside v0.1
rather than incomplete home-mode requirements.
