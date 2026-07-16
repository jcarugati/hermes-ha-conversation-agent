# Hermes Conversation Agent for Home Assistant

<img src="custom_components/hermes_conversation/assets/logo.png" alt="Hermes Conversation Agent project logo" width="160">

Hermes Conversation Agent connects a Home Assistant Assist pipeline to the API of an already-running Hermes instance that the operator keeps private. Home Assistant retains wake word, speech-to-text, text-to-speech, Assist, and the device registry; Hermes handles reasoning and its configured tools.

**Quick start:** follow the [installation and usage guide](docs/installation-and-usage.md#quick-start).

## What it does—and does not do

The integration is a thin HTTP adapter. It sends each Assist utterance to the authenticated direct endpoint of the same Hermes instance and returns the final text for Assist to speak.

It works only with the direct Hermes contract: `POST /v1/responses`, bearer authentication, and non-streaming responses (`stream: false`). It does not use `/v1/chat/completions`, install a second automation platform, or forward tools, Home Assistant schemas, HA credentials, or ChatLog history.

Hermes retains its own tool and MCP policy. Choosing this integration therefore does not create an isolated profile or a Home Assistant-only permission list.

## Privacy and security

- Keeping the Hermes API on a LAN, Tailnet, or behind a private proxy and protecting it with a bearer token is an operator requirement. The integration does not verify that an HTTPS host is private.
- HTTPS is verified by default. Only unencrypted HTTP hosts are technically limited to local names or private addresses; they require explicit opt-in and display a warning.
- Each turn sends only `model`, `input`, `conversation`, and `stream: false`. The conversation key is opaque and new for every turn; no Assist `ChatLog` or cross-turn context is forwarded. Hermes may retain that one-turn conversation, the response, and tool records under its own policy, and the integration does not guarantee remote deletion.
- A voice utterance does not authenticate the speaker. Start with read-only requests and harmless actions you have explicitly authorized.

See [advanced configuration](docs/advanced-configuration.md) and the [security policy](SECURITY.md) for operational and risk details.

## Current status

The integration provides Home Assistant UI configuration, token rotation when Hermes rejects authentication, and options for request limits and model aliases. It supports one direct connection per config entry; it does not provide history controls or an alternative gateway.

## Logo

The repository-local project logo is packaged at [`custom_components/hermes_conversation/assets/logo.png`](custom_components/hermes_conversation/assets/logo.png). It is **not published through Home Assistant Brands**, so Home Assistant or HACS may show a generic icon.

## Documentation

- [Installation and usage](docs/installation-and-usage.md): getting started, Assist-pipeline setup, and troubleshooting.
- [Advanced configuration](docs/advanced-configuration.md): model aliases, privacy, limits, and risks.
- [Architecture](docs/architecture.md): data flow and adapter boundaries.
- [Responses API contract](docs/hermes-responses-contract.md): the technical contract the Hermes server must advertise.
- [Security policy](SECURITY.md): trust model and responsible disclosure.
