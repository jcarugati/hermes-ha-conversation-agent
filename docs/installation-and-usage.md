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

The alias is bounded to 512 characters, is stored as a non-secret config-entry option, and does not change the endpoint. Both paths send the same four-field request DTO. Without an alias, each request also checks that `/v1/capabilities` still advertises the model seen at setup; with an alias this one check is skipped, because the alias route does not use the default model. If the default model changes while no alias is set, reload the entry.

### Reasoning effort for the voice model

Current Hermes does **not** honor `reasoning_effort` in `platforms.api_server.extra.model_routes`. The route parser keeps only `model`, `provider`, `api_key`, and `base_url` and drops other keys without an error. A route such as `hermes-voice` can still select which model Voice uses, but its `reasoning_effort` has no effect.

Set reasoning for the model that actually runs with `agent.reasoning_overrides` in the Hermes `config.yaml`:

```yaml
agent:
  reasoning_overrides:
    "<voice-model-id>": none
```

Restart Hermes after the change. The override applies to every Hermes channel that runs that model, including Discord, Telegram, CLI, and default API requests. To keep it voice-only, point the voice route at a model ID that no other channel uses and put the override on that ID.

## Request timeout

The Responses POST uses a 90-second total timeout by default. The supported range is 1 to 120 seconds, while connect timeout and the other limits remain separately configurable. Entries that have no saved value, including entries created before the value was saved, use the same 90-second default as new entries. An explicitly saved value is kept. To change it, open **Settings → Devices & services → Hermes Conversation Agent → Configure**, enter a new **Total timeout**, and submit the form; Home Assistant reloads the entry.

`/health` and `/v1/capabilities` (setup, reauth, and the check before every request) use a separate 5-second total timeout, or the total timeout if that is shorter. A stalled check therefore fails before anything is dispatched instead of holding the voice turn.

## Voice setup recommendations

### Prefer handling commands locally

Open **Settings → Voice assistants**, select the pipeline that uses this agent, and enable **Prefer handling commands locally**. Home Assistant then tries its built-in intents first and answers commands it understands, such as turning exposed lights on or off, without calling Hermes. Everything it does not match is sent to Hermes as before.

Tradeoffs:

- Locally handled turns never reach Hermes. Hermes has no record of them, so a follow-up such as "and dim it to 30%" that Home Assistant does not match reaches Hermes without the earlier command as context.
- Local handling uses Home Assistant's exposed entities, names, aliases, and the satellite's area. Expose the entities you control by voice and give them the names you actually say.
- Because this entity advertises control support, Home Assistant still sends state questions and media search/play to Hermes rather than answering them locally.

### Voice hint for Hermes

The integration never sends instructions or prompts. Configure voice behavior on the Hermes side with `platform_hints` in its `config.yaml`:

```yaml
platform_hints:
  api_server:
    append: >-
      Input is a speech-to-text transcript from Home Assistant Assist and may
      contain recognition errors; infer the most likely intent. Answer in one
      or two short plain-text sentences without Markdown, lists, emoji, or URLs.
      If something essential is missing, ask one short question ending in "?".
```

`append` keeps Hermes' built-in API-server hint; `replace` substitutes it. The hint applies to every client of the Hermes API server, not only Voice. Write it in the language you speak to Assist. Ending clarifying questions with a question mark matters: see the follow-up behavior below.

### What Assist speaks

- Assist speaks a cleaned copy of the reply. Markdown emphasis and code markers, heading and bullet markers, link targets, bare URLs, and emoji are removed; list lines become sentences. Numbers, units, and negations are kept. The full reply stays in Home Assistant's ChatLog.
- When the reply ends with a question mark, the result asks the satellite to keep listening (Home Assistant's `ChatLog.continue_conversation` rule), so you can answer without the wake word. The rule reads the original reply, so a question followed by an emoji or Markdown does not reopen the mic.

### Debug timings

To see where a slow turn spends its time, enable debug logging for the integration in Home Assistant's `configuration.yaml`:

```yaml
logger:
  logs:
    custom_components.hermes_conversation: debug
```

Each turn then logs one line with the preflight and POST durations, the outcome class name (for example `HermesResponse` or `HermesIndeterminateError`), and the reply length in characters. The line never contains the transcript, reply text, token, URL, or conversation key.

## Verify safely

1. Keep the existing Voice pipeline unchanged while adding the direct entry.
2. Test a simple spoken text request.
3. Test a read-only Home Assistant question.
4. Test an explicitly authorized harmless action.
5. Only then route normal control traffic to the direct agent.

Every turn sends only a bounded utterance, selected model value, and opaque Hermes conversation key. If Home Assistant supplies no `conversation_id` on the first turn, the integration creates an opaque ID and returns it in the result. Follow-up turns carrying that ID reuse the same entry-local Hermes named conversation, while distinct IDs receive distinct keys. Each entry retains its 256 most recently used mappings; an inactive ID that returns after eviction starts a new Hermes context. The HA ID and ChatLog remain local. Requests are not automatically retried after dispatch. A timeout, disconnect, malformed response, or tool-only completed response after dispatch has an indeterminate result, so Assist reports that confirmation failed rather than claiming an action succeeded. If the POST is rejected with HTTP 401 or 403, Assist reports that authentication is required and Home Assistant starts reauthentication; rotate the token there.

Hermes tool records and `reasoning` records may precede the final assistant message in a valid response. They are skipped, and reasoning is never spoken. If a completed response contains no final assistant text, the integration fails closed instead of speaking success.
