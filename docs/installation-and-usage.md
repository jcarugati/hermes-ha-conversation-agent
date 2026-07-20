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

### Isolated Voice reasoning route

Install a Hermes runtime version/change that supports per-route `reasoning_effort`, then add an API-server route using the same provider and model as the default profile:

```yaml
platforms:
  api_server:
    extra:
      model_routes:
        hermes-voice:
          provider: "<same-provider-as-default>"
          model: "<same-model-as-default>"
          reasoning_effort: none
```

Replace both placeholders with the exact provider and model used by the default profile, restart Hermes as required, and set this integration's **Model alias** to `hermes-voice`. The integration then sends `hermes-voice` only as the existing `model` value.

This override applies only to API requests that send the `hermes-voice` alias. Discord, Telegram, CLI, and API requests that use the default model or another alias retain the global `agent.reasoning_effort`. Do not assume this isolation is active before the matching Hermes runtime support is installed.

## Request timeout

New entries save a 90-second total timeout. The supported range remains 1 to 120 seconds, while connect timeout and the other limits remain separately configurable. Existing entries retain their saved value. To set an existing entry to 90 seconds, open **Settings → Devices & services → Hermes Conversation Agent → Configure**, enter `90` for **Total timeout**, and submit the form; Home Assistant reloads the entry.

## Verify safely

1. Keep the existing Voice pipeline unchanged while adding the direct entry.
2. Test a simple spoken text request.
3. Test a read-only Home Assistant question.
4. Test an explicitly authorized harmless action.
5. Only then route normal control traffic to the direct agent.

Every turn sends only a bounded utterance, selected model value, and opaque Hermes conversation key. If Home Assistant supplies no `conversation_id` on the first turn, the integration creates an opaque ID and returns it in the result. Follow-up turns carrying that ID reuse the same entry-local Hermes named conversation, while distinct IDs receive distinct keys. Each entry retains its 256 most recently used mappings; an inactive ID that returns after eviction starts a new Hermes context. The HA ID and ChatLog remain local. Requests are not automatically retried after dispatch. A timeout, disconnect, malformed response, or tool-only completed response after dispatch has an indeterminate result, so Assist reports that confirmation failed rather than claiming an action succeeded.

Hermes tool records may precede the final assistant message in a valid response. If a completed response contains only tool records and no assistant text, the integration fails closed instead of speaking success.
