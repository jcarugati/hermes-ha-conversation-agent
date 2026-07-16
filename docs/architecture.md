# Architecture

To configure the integration, start with [installation and usage](installation-and-usage.md). For model aliases, limits, and operational risks, see [advanced configuration](advanced-configuration.md).

```text
Voice device
  → Home Assistant Assist (STT, pipeline, and TTS)
  → Hermes config-entry conversation entity
  → authenticated POST /v1/responses to the private Hermes API
  → final Hermes text
  → Home Assistant TTS
  → voice device
```

## Responsibilities

Home Assistant retains wake word, STT, TTS, Assist, native automations, the device registry, and its own credentials. Hermes retains reasoning, model routes, and its tool and MCP policy.

Hermes Conversation Agent is only the adapter between them. It does not create Home Assistant tool schemas, execute HA callbacks, add another automation platform, or change capabilities configured in Hermes.

## Request flow

1. Assist delivers the current text to the conversation entity.
2. The entity creates a fresh opaque conversation key for that turn and chooses the default model stored when the entry was set up or the configured alias.
3. Before sending the request, the client revalidates Hermes's authenticated direct capabilities.
4. The client sends only `{model, input, conversation, stream: false}` to `POST /v1/responses`, with redirects disabled.
5. If the completed response includes non-empty final text, the entity returns it to Assist for Home Assistant to speak.

Hermes tool records can precede final text. A completed response containing only tool records is an error and is never converted into a successful spoken response.

## Trust and data boundaries

The operator must connect the adapter to a private Hermes server that uses bearer authentication and advertises `responses_api: true`, `chat_completions: true`, and the fixed `POST /v1/responses` endpoint, with no custom `security` contract. Configuration and every config-entry setup or reload check `GET /health` and authenticated capabilities. Every dispatch revalidates only authenticated capabilities before the `POST`; it does not repeat the health check.

The integration does not prove that an HTTPS host is private; that LAN, Tailnet, or private-proxy exposure is the operator's responsibility. Only unencrypted HTTP URLs are technically limited to local names or private addresses.

The request contains no `ChatLog` history, cookies, Home Assistant context, user or device identifiers, HA credentials, service tokens, tools, actions, instructions, or prompt overrides. The client uses a cookie-free session so that Home Assistant cookies do not cross the boundary.

The integration does not link turns: the opaque conversation key is never reused, and no `ChatLog` or cross-turn context is forwarded. However, Hermes may retain a turn's named conversation, response, and tool records under its own policy; the integration offers no remote retention or deletion guarantee. The bearer token is transmitted only in the authentication header, never in the URL or logs.

## Model and availability

Config-entry setup or reload stores the default model announced by capabilities. Without an alias, that stored value is used; if Hermes changes its default model, the entry must be reloaded or reconfigured. An alias replaces only the `model` value in the same four-field request body. The integration does not pre-validate it against model routes: Hermes must accept it and return it as `model`. The alias does not change the endpoint, select an isolated instance, profile, or agent, or modify tools or permissions. See [advanced configuration](advanced-configuration.md#model-alias) for details.

After a `POST` has been sent, a timeout or disconnect is treated as indeterminate and is not retried automatically. The Home Assistant operator must check the real state before repeating an action.
