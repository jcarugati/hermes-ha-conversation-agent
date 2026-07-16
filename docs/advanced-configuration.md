# Advanced configuration

This integration connects only to the direct API of an already-running Hermes instance. The introductory guide is [installation and usage](installation-and-usage.md); the internal flow is described in [architecture](architecture.md).

## Model alias

The **Model alias (optional)** option does not add agent selection. It determines only the `model` value that the integration sends to the same Hermes API.

- During config-entry setup or reload, the integration stores the default model announced by `/v1/capabilities`. When the alias is blank, each request uses that stored default model.
- If Hermes changes its default model, reload or reconfigure the entry to store the newly announced value.
- When set, the integration forwards the alias as the sole `model` value; it does not pre-validate that it exists in model routes. Hermes must accept the alias and return it as `model` in the response.
- The alias does not select an isolated profile, agent, or environment. It also does not change the endpoint, available tools, MCP servers, or permissions in Hermes.

The field accepts at most 512 characters. If you do not want an alias, leave it blank to retain the model stored during the most recent config-entry setup or reload.

## Direct endpoint and contract

The configured URL is the API root, not a chat or gateway URL. During configuration and every config-entry setup or reload, the integration performs these checks:

1. `GET /health` must identify a healthy Hermes server.
2. Authenticated `GET /v1/capabilities` must advertise `responses_api: true`, `chat_completions: true`, required bearer authentication, and `POST /v1/responses`, with no custom `security` member.

Before every Assist request, it runs only authenticated `GET /v1/capabilities` again, verifies that the default model still matches the stored value, and then sends authenticated `POST /v1/responses`, with redirects disabled and `stream: false`. It does not run `GET /health` before every dispatch.

The request body contains exactly these four fields:

```json
{
  "model": "<stored default model or alias>",
  "input": "<Assist utterance>",
  "conversation": "<fresh opaque key>",
  "stream": false
}
```

It does not use `/v1/chat/completions`. A compatibility server, restricted gateway, or different security contract is not supported by this integration.

## Conversations and privacy

For each Assist turn, the integration generates a new opaque conversation key. It does not read or send Home Assistant's inbound `ChatLog`, and it does not retain or forward context between turns. By design, there are no controls to reset, select, retrieve, or reuse remote data.

The new key prevents the integration from chaining turns, but it does not impose a retention policy on Hermes. Hermes may retain that turn's named conversation, response, and tool records under its own policy. The integration does not guarantee remote deletion of that data.

In addition to the four request-body fields, the authenticated request carries the bearer token in its header. It does not send Home Assistant cookies, user or device identifiers, context, HA credentials, service tokens, tools, actions, instructions, or prompt overrides. Treat the token and conversation text as sensitive in logs and diagnostics.

As an operator requirement, keep the server on a LAN, Tailnet, or behind a private proxy, without unnecessary browser CORS. HTTPS verifies the certificate by default, but the integration does not validate that its host is private. Only unencrypted HTTP is technically limited to local or private hosts; it must be explicitly enabled and exposes the token and request data to the network.

## Limits and timeouts

The limits contain requests and responses; they do not add permissions:

- Assist input accepts up to 8192 characters; the request body is limited to 32768 bytes.
- **Connect timeout (seconds)** accepts 0.1 to 30 seconds; its default is 5.
- **Total timeout (seconds)** accepts 1 to 120 seconds; its default is 30.
- **Maximum response characters** accepts 256 to 32768; its default is 8192. HTTP responses are also limited to 1 MiB.
- Responses must be JSON and contain non-empty final Hermes text; a response containing only tool records is rejected.

Once the `POST` has been sent, a timeout or disconnection is indeterminate: Hermes may have executed the request. The integration makes no automatic retry. Before repeating an action, especially one that changes something, check its real state.

## Operational risk

Hermes retains the full tool and MCP surface configured for that instance. The control capability that Assist sees is not an additional authorization limit, and a voice utterance does not prove the identity of the speaker. A prompt does not replace Hermes permissions or network controls.

Keep the working voice path in place while you perform the initial checks. First verify a written response in Assist's text UI; then separately verify voice input and TTS output. Continue with a read-only request and finally an authorized harmless action. Also see the [security policy](../SECURITY.md).
