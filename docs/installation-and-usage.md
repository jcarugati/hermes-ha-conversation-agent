# Installation and usage

> **Current status:** the Hermes HTTP contract verifier is implemented, but its strengthened checks await a fresh live run and the Home Assistant component is not published or installable yet.

> **Current status:** this repository contains a developer-only ConversationEntity
> compatibility spike plus the target workflow for a future implementation. It is not
> a Hermes bridge, is not published, and is not supported for installation or use.

## Compatibility evidence available now

The spike registers one inert conversation entity and returns a fixed reply. It has no
Hermes connection, token or endpoint configuration, tools, conversation state, or
config flow. It neither inspects nor forwards the utterance or Home Assistant
`ChatLog`.

The automated test is pinned to Home Assistant Core 2026.7.1 and Python 3.14.2. It uses
Home Assistant's own test harness, integration loader, entity registration, and
`async_converse` dispatcher:

```bash
uv python install 3.14.2
uv sync --python 3.14.2
uv run --python 3.14.2 pytest
```

Passing this test demonstrates only that the fixed-reply entity matches that release's
Conversation API. It does not test Assist/Voice, STT/TTS, installation lifecycle,
Hermes, or any production behavior.

## Proposed v0.1 operator workflow (not implemented)

The remaining sections record a possible operator workflow for the planned v0.1.
They are design notes, not instructions that work with this spike. The spike has no
configuration UI, network client, diagnostics, or production lifecycle.

### Proposed prerequisites

- A working Home Assistant installation with Assist and a configured voice pipeline.
- For a future bridge, Hermes Agent with a configured model and a verified
  read-only/status execution profile; arbitrary or action-bearing toolsets are outside
  the permitted v0.1 scope.
- Network reachability from the Home Assistant host to the Hermes API through a **private** path.
- A dedicated bearer token for Hermes API access.
- A Hermes Agent version that advertises and passes the committed contract verifier. No minimum version is pinned yet.
- A supported Home Assistant release, still to be pinned by the v0.1 compatibility matrix.

### 1. Enable a future Hermes API server

On the Hermes host, configure the API server with a new, long random key. Keep this outside Git and do not paste it into issues/chat:

```bash
# ~/.hermes/.env
API_SERVER_ENABLED=true
API_SERVER_KEY=<generate-a-long-random-secret>
```

Restart Hermes Gateway. Use the base URL configured for your deployment; this repository has not verified a default bind address or port.

Verify locally first:

```bash
curl "$HERMES_BASE_URL/health"
# Expected fields: status="ok", platform="hermes-agent", non-empty version

curl "$HERMES_BASE_URL/v1/capabilities" \
  -H "Authorization: Bearer $API_SERVER_KEY"
# Expected: auth.type="bearer", auth.required=true,
# features.responses_api=true, and a non-empty model
```

Contributors can run the deterministic and explicitly gated live contract checks described in [`hermes-responses-contract.md`](hermes-responses-contract.md). Do not put the real token or private URL in repository files or command output.

### 2. Provide private connectivity for a future bridge

Home Assistant must be able to reach Hermes, but the API must not be public.

Recommended patterns:

- A reverse proxy reachable only on the LAN, with HTTPS/TLS.
- A Tailscale path between Home Assistant and the Hermes host, preferably with HTTPS/TLS.
- A firewall rule allowing the HA host only.

Do **not** bind Hermes directly to a public interface or port-forward it to the Internet. Do not put the bearer token in a URL query string.

The proposed config flow would require explicit acknowledgement for a trusted local
HTTP-only network because both bearer tokens and speech text could be observed there.

### 3. Possible installation after a future release

### HACS

1. In HACS, add this GitHub repository as a custom integration repository.
2. Download **Hermes Home Assistant Conversation Agent**.
3. Restart Home Assistant.
4. Go to **Settings → Devices & services → Add integration**.
5. Select **Hermes Conversation Agent**.

### Manual installation

1. Copy `custom_components/hermes_conversation/` to your Home Assistant configuration directory:

   ```text
   /config/custom_components/hermes_conversation/
   ```

2. Restart Home Assistant.
3. Add the integration from **Settings → Devices & services**.

### 4. Proposed configuration

A future config flow is expected to request:

- Private Hermes base URL, such as `https://hermes.home.arpa`.
- Hermes API bearer token.
- Optional spoken response language/length preferences.
- Explicit acknowledgement when using plaintext HTTP.

The v0.1 design requires such a flow to validate the server capabilities before saving
and reject unsupported contracts. This behavior does not exist in the spike.

### 5. Possible Assist selection after a future release

1. Go to **Settings → Voice assistants**.
2. Create or edit an assistant.
3. Set **Conversation agent** to **Hermes Conversation Agent**.
4. Keep your preferred STT and TTS providers unchanged.
5. Assign the assistant to the Home Assistant Voice device.

### Proposed usage

Read-only/status examples for the currently permitted future scope:

- “¿Qué luces quedaron prendidas?”
- “¿Cuál es la temperatura en la oficina?”
- “¿Qué pasó hoy en casa?”

The proposed v0.1 would return answers brief enough for speech.

### Required safety limitations for v0.1

Until Hermes supports server-side, parameter-bound confirmation, this integration must not perform high-impact actions such as opening garages/doors, locks, alarms, pet feeding, destructive tasks, or Home Assistant configuration changes. A voice phrase such as “confirmo” is not proof of identity.

The committed HA-local prototype is a non-executing read-only/status declaration. Its
public API accepts no callable, operation, prompt, confirmation, or action parameters,
and it exposes no executable action route.

This is a local interface contract, not a usable Hermes feature or end-to-end safety
control. The current entity returns a fixed inert response and has no network client,
tool configuration, classifier, or Hermes execution sink. A real bridge additionally
requires a verified Hermes read-only/status execution profile, enforcement at every
future request and tool-execution sink, and startup plus request-time verification that
fails closed whenever the profile is absent, stale, or unverifiable.

### Proposed troubleshooting considerations

These checks apply only after a production bridge implements the relevant network,
configuration, and error-handling features; they cannot be performed against this
spike.

1. Check the Hermes API locally with `/health`.
2. Check `GET /v1/capabilities` with bearer auth and ensure `responses_api` is present.
3. From the Home Assistant host/network, verify DNS/routing/TLS to the private Hermes endpoint.
4. Confirm the API token is current and is not embedded in the URL.
5. If a future request times out after dispatch, do not repeat the action immediately.
   The action may have completed; inspect the relevant device state first.
