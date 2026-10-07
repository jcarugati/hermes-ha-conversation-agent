# Hermes Home Assistant Conversation Agent

<img src="custom_components/hermes_conversation/assets/logo.png" alt="Hermes Conversation Agent project logo" width="160">

A thin Home Assistant Conversation entity that sends final-response requests to the private API server of a running Hermes instance and speaks the returned text through Assist.

## What it supports

The integration supports one architecture: an authenticated direct Hermes API server. It connects Assist to the same Hermes instance used by other channels, so the Hermes instance owns its tool and MCP policy and may execute any capability configured there. The bridge itself never supplies tools or Home Assistant execution callbacks.

It uses authenticated `POST /v1/responses`; it never uses chat completions itself, forwards HA ChatLog/cookies/context, or exposes an HA tool callback.

Conversation continuity follows Home Assistant's `conversation_id`. A first turn without one receives a new opaque ID in the result. The entry maps that ID to a separate opaque Hermes named-conversation key and reuses the key for follow-up turns; distinct HA IDs stay isolated and the HA ID itself is never sent to Hermes. The entry retains the 256 most recently used mappings, so an evicted inactive ID starts a new Hermes context if it returns rather than sharing another conversation's context.

Responses may contain Hermes tool records and `reasoning` records before the final assistant message. Both are skipped; reasoning is never spoken. A completed response with no final assistant text is rejected and is never treated as speakable success.

The Responses POST uses a 90-second total timeout by default (adjustable from 1 to 120 seconds). Entries without a saved value use the same 90-second default as new entries; an explicitly saved value is kept. To change it, open **Settings → Devices & services → Hermes Conversation Agent → Configure**, set **Total timeout**, and submit the options form. The `/health` and `/v1/capabilities` checks have their own 5-second timeout (never longer than the total timeout), so a stalled check fails quickly instead of holding the voice turn.

## Capability validation

Before configuration, setup, and every request, the component validates authenticated capabilities. The server must advertise bearer authentication, `responses_api: true`, `chat_completions: true`, the fixed Responses endpoint, and no custom `security` object. Other contracts fail closed before dispatch.

## Model selection

By default, each request uses the model advertised by `/v1/capabilities`, and every request checks that the same default is still advertised. The entry options include an optional **Model alias**: leave it blank to preserve that default, or enter a Hermes model/routing alias to send that value as `model` to the same server. With an alias, the advertised-default check is skipped because the alias route does not use the default model; all other capability checks still run. The alias neither changes the endpoint nor adds a request field.

**Reasoning effort for voice.** Current Hermes does **not** honor `reasoning_effort` inside `platforms.api_server.extra.model_routes`: the route parser keeps only `model`, `provider`, `api_key`, and `base_url` and silently drops other keys. A `model_routes` entry can select the voice model, but it cannot change its reasoning. Set the effort per model with `agent.reasoning_overrides` instead:

```yaml
agent:
  reasoning_overrides:
    "<voice-model-id>": none
```

This applies to every Hermes channel that runs that model, not only Voice. To keep it voice-only, the voice route must use a model ID that no other channel uses.

## Voice behavior

- **Spoken text is cleaned.** Assist speaks a copy without paired Markdown emphasis/code delimiters, heading markers, bullet markers at the start of a line, link targets (`[text](url)` becomes `text`), bare URLs, or emoji. Numbers, signs, arithmetic, units, and negations are kept: a `-` or `+` before a number is a sign, not a bullet, and an unpaired or spaced `*` stays, so `- 5 °C`, `-5 °C`, and `2*3 W` are spoken as written. Wrapped lines are joined with a space; only headings and list items start a new sentence, so a reply wrapped as `No` / `hay alarmas` is spoken as one sentence. If nothing speakable remains (for example a URL-only or emoji-only reply), Assist answers with a fixed error saying the reply cannot be read aloud: it never speaks the raw reply, never claims success, and does not reopen the mic. Home Assistant's ChatLog keeps Hermes' full original reply.
- **Follow-up questions keep the mic open.** The result carries Home Assistant's own `ChatLog.continue_conversation`: when Hermes' final reply ends with a question mark, a Voice PE or other satellite listens for the answer without a new wake word. The rule reads the original reply, so a question followed by an emoji or Markdown does not reopen the mic.
- **Prefer handling commands locally (recommended).** In the Assist pipeline that uses this agent, enable **Prefer handling commands locally**. Home Assistant then handles commands its built-in intents understand (for example turning exposed lights on or off) itself, without calling Hermes, and sends everything else to Hermes. Tradeoff: locally handled turns never reach Hermes, so Hermes has no record of them, and a follow-up that Home Assistant does not match reaches Hermes without that context. Because this entity advertises control support, Home Assistant still sends state questions and media search/play to Hermes.
- **Voice instructions belong to Hermes.** The bridge never sends instructions. To make Hermes answer briefly in plain text, add a server-side hint for the API-server platform:

  ```yaml
  platform_hints:
    api_server:
      append: >-
        Input is a speech-to-text transcript from Home Assistant Assist and may
        contain recognition errors; infer the most likely intent. Answer in one
        or two short plain-text sentences without Markdown, lists, emoji, or URLs.
        If something essential is missing, ask one short question ending in "?".
  ```

  This hint applies to every client of the Hermes API server, not only Voice. Write it in the language you speak to Assist.
- **Debug timings.** With debug logging enabled for `custom_components.hermes_conversation`, each turn logs one line with the preflight and POST durations, the outcome class name, and the reply length in characters. It never logs the transcript, reply text, token, URL, or conversation key.

## Security and rollout

Keep the endpoint private (Tailnet/LAN/private reverse proxy) and use bearer auth. Disable unnecessary browser CORS. HTTPS is preferred; private HTTP needs explicit acknowledgement. Requests use a cookie-free Home Assistant session and contain only `{model, input, conversation, stream: false}`. Dispatched requests revalidate capabilities and are never retried automatically. A timeout, disconnect, malformed result, or tool-only completed result after dispatch is indeterminate; Assist receives a fixed confirmation-failure response rather than a claimed action success. A POST rejected with HTTP 401/403 is an authentication failure, not an indeterminate result: Assist reports that authentication is required and Home Assistant starts the reauthentication flow.

A voice utterance is not identity proof. Verify simple text conversation, a read-only Home Assistant request, and an explicitly authorized harmless action before treating the pipeline as ready for control.

## Logo

The repository-local project logo is packaged at `custom_components/hermes_conversation/assets/logo.png` and used in this documentation. It is not published through Home Assistant Brands, so Home Assistant or HACS may still show a generic icon.

## Development

```bash
uv sync --all-groups
uv run pytest -q
uv run ruff check .
uv run ruff format --check .
uv run mypy
git diff --check
```

See [installation](docs/installation-and-usage.md), [architecture](docs/architecture.md), [contract verification](docs/hermes-responses-contract.md), and [security policy](SECURITY.md).
