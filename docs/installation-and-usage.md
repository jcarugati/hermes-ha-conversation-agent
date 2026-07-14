# Installation and usage

Install through HACS or copy `custom_components/hermes_conversation/` into Home Assistant and restart Home Assistant. Configure it from **Settings → Devices & services → Add integration → Hermes Conversation Agent**.

## Direct Hermes endpoint

Enter the private root URL and bearer token for the API server of the same running Hermes instance used by other channels. The integration validates `/health`, authenticated `/v1/capabilities`, and the fixed `/v1/responses` endpoint before saving.

The server must advertise `responses_api: true`, `chat_completions: true`, bearer-required authentication, the fixed `POST /v1/responses` route, and no custom `security` object. No alternate gateway contract is supported. The integration inherits the configured Hermes capability surface; it is not a home-only sandbox, and voice is not user authentication.

Keep the endpoint private and disable unnecessary browser CORS. HTTPS is preferred; private HTTP requires explicit acknowledgement. Do not place credentials in URLs.

## Optional model alias

Open the config entry's options to set **Model alias**.

- Leave it blank to use the model advertised by `/v1/capabilities`, preserving the direct-server default behavior.
- Enter a non-empty Hermes model/routing alias to send that alias as the `model` value to the same API server.

The alias is bounded to 512 characters, is stored as a non-secret config-entry option, and does not change the endpoint. Both paths send the same four-field request DTO.

## Verify safely

1. Keep the existing Voice pipeline unchanged while adding the direct entry.
2. Test a simple spoken text request.
3. Test a read-only Home Assistant question.
4. Test an explicitly authorized harmless action.
5. Only then route normal control traffic to the direct agent.

Every turn sends only a bounded utterance, selected model value, and fresh opaque conversation key. HA ChatLog remains local and requests are not automatically retried after dispatch.

Hermes tool records may precede the final assistant message in a valid response. If a completed response contains only tool records and no assistant text, the integration fails closed instead of speaking success.
