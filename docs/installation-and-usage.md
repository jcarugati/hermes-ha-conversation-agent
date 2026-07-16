# Installation and usage

This guide configures Hermes Conversation Agent as the conversation agent for an Assist pipeline. For the data model, aliases, and limits, see [advanced configuration](advanced-configuration.md).

## Before you begin

You need the following:

- A Home Assistant installation that supports custom integrations and administrator access to its UI. If you use the HACS method, install HACS first.
- An already-running Hermes instance that is private and reachable from Home Assistant.
- The Hermes API root URL, with no path, query parameters, or credentials in the URL. Use HTTPS whenever possible.
- A valid bearer token for that API. Enter it only in the configuration flow: Home Assistant stores it securely in its config entry. Do not manually copy it into documentation, screenshots, logs, URLs, or ordinary files.

The server must be the direct API of the same Hermes instance you use for other channels. During configuration and every config-entry setup or reload, the integration checks `GET /health`, authenticated `GET /v1/capabilities`, and the `POST /v1/responses` contract. The server must advertise required bearer authentication, `responses_api: true`, `chat_completions: true`, and the fixed Responses endpoint, with no custom `security` contract. Before each Assist request, it rechecks only authenticated capabilities and then sends the `POST`; it does not repeat `GET /health` at that time.

## Install the integration

### Through HACS as a custom repository

This method requires HACS to be installed already and adds the project as a custom repository; it does not depend on the integration appearing in the public HACS listing.

1. In HACS, open **Integrations**.
2. Open the three-dot menu and select **Custom repositories**.
3. Enter `https://github.com/jcarugati/hermes-ha-conversation-agent` as the repository URL and select the **Integration** type.
4. Open the **Hermes Conversation Agent** custom repository and install the integration.
5. Restart Home Assistant when HACS finishes.

### Manual installation

1. Copy this repository's `custom_components/hermes_conversation` directory to `<home-assistant-configuration>/custom_components/hermes_conversation`.
2. Keep all of its files and subdirectories; do not copy only Python files.
3. Restart Home Assistant.

## Configure the connection in Home Assistant

1. Go to **Settings → Devices & services → Add integration**.
2. Search for and select **Hermes Conversation Agent**.
3. Complete the two fields shown by the configuration flow:

   - **Hermes base URL**: the root URL of the Hermes API you keep private, for example using the `https://` scheme. Do not add `/v1/responses` or a subdirectory.
   - **Bearer token**: the Hermes API token.

4. If you use `http://`, Home Assistant displays an additional screen. Select exactly **I understand that HTTP exposes the token and request data on the network** only when the host is local or private and you accept the risk. HTTPS is the recommended choice.
5. Wait for validation to finish. If the URL, token, or server contract is invalid, the entry is not saved.

Keeping Hermes on a LAN, Tailnet, or behind a private proxy is an operator requirement. Validation limits hosts only when the URL uses unencrypted HTTP; an HTTPS URL can pass validation even when it points to a public host. Do not expose Hermes to the Internet or use an alternative gateway; redirects and credentials in the URL are not supported.

## Select Hermes in an Assist pipeline

1. Open the Assist-pipeline editor you want to use in **Settings → Voice assistants**.
2. In the conversation-agent field, select the entry associated with your Hermes URL. Because the entity has no fixed display name, the selector can show the endpoint hostname instead of **Hermes Conversation Agent**.
3. Save the pipeline and assign it to the voice assistant or device that you will test.

The integration returns Hermes's final text to Assist. Home Assistant retains voice input, voice output, and devices; Hermes retains its configured tools.

## Quick start

Keep your working voice pipeline in place while you verify the new entry.

1. In Assist's text UI, send a simple request that does not control a device, for example: “Reply with a short sentence to confirm the connection.” Confirm that Hermes's written response appears.
2. Through the voice device or voice pipeline, repeat a harmless request and separately confirm that STT receives the utterance and TTS speaks the response.
3. Make a read-only request that Hermes is authorized to resolve in your installation.
4. Try a harmless action you have explicitly authorized, preferably against a test entity.
5. Only after those checks, use the pipeline for normal control.

A response that contains tool calls and valid final text can be spoken. If Hermes finishes without final text, the integration fails closed rather than announcing success.

## Change options, rotate the token, or remove the entry

In **Settings → Devices & services**, open the entry associated with your Hermes URL and choose **Configure** to change its options. The entry can appear under the endpoint hostname. Home Assistant reloads it when you save.

The current option fields are:

- **Connect timeout (seconds)**: 0.1 to 30; default 5.
- **Total timeout (seconds)**: 1 to 120; default 30.
- **Maximum response characters**: 256 to 32768; default 8192.
- **Model alias (optional)**: up to 512 characters. Leave it blank to use the model announced by Hermes and stored when the entry was set up or reloaded. See [advanced configuration](advanced-configuration.md#model-alias).

For an HTTP entry, Home Assistant asks for the risk acknowledgement again before opening options.

If Hermes rejects the token during a request, Home Assistant starts the **Update authentication** flow. Enter the new value in **Bearer token** and complete the HTTP acknowledgement again if applicable. This process does not change the URL.

To stop using the integration, open the entry menu and choose **Delete**. This removes Home Assistant's local configuration; it does not stop Hermes or modify its models, tools, or data.

## Troubleshooting

| Symptom | What to check |
| --- | --- |
| **Could not validate the Hermes endpoint, credentials, and Responses API capability** | Confirm that the URL is the private API root, that Home Assistant can reach it, and that the server advertises the required direct contract. Also check the HTTPS certificate. |
| **Hermes rejected the bearer token** | Replace the token through **Update authentication**. Do not add the token to the URL. |
| The HTTP acknowledgement does not allow you to continue | HTTP is accepted only for `localhost`, allowed local suffixes, or private addresses. Use HTTPS unless you need local HTTP. |
| Hermes does not appear as a conversation agent | Verify that the entry was created without errors and that Home Assistant was restarted after installation. In the selector, look for the entry associated with your Hermes URL; it can appear as the endpoint hostname because the entity has no fixed display name. |
| Assist says Hermes is unavailable | Check private connectivity, Hermes health, token validity, and the capabilities contract. |
| The result could not be confirmed | A request that was already sent may have reached Hermes even if it timed out or the connection dropped. Check the real state before repeating an action. The integration does not retry it automatically. |
| Hermes's default model changed | Reload or reconfigure the entry to store the new model announced by capabilities. A loaded entry retains the model that was announced when it loaded. |
| The model alias fails | The integration forwards the alias without checking whether it exists in model routes. Verify that Hermes accepts it and returns it as `model`, or leave it blank to use the model stored when the entry loaded. |

No `ChatLog` or cross-turn context is forwarded: each Assist turn uses a new opaque conversation. The integration provides no controls to retrieve, delete, or reuse remote data, but it also does not guarantee that Hermes deletes it; Hermes may retain the one-turn conversation, response, and tool records under its own policy. Read [advanced configuration](advanced-configuration.md#conversations-and-privacy) before relying on a conversational workflow.
