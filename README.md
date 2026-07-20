# Hermes Home Assistant Conversation Agent

<img src="custom_components/hermes_conversation/assets/logo.png" alt="Hermes Conversation Agent project logo" width="160">

A thin Home Assistant Conversation entity that sends final-response requests to the private API server of a running Hermes instance and speaks the returned text through Assist.

## What it supports

The integration supports one architecture: an authenticated direct Hermes API server. It connects Assist to the same Hermes instance used by other channels, so the Hermes instance owns its tool and MCP policy and may execute any capability configured there. The bridge itself never supplies tools or Home Assistant execution callbacks.

It uses authenticated `POST /v1/responses`; it never uses chat completions itself, forwards HA ChatLog/cookies/context, or exposes an HA tool callback.

Conversation continuity follows Home Assistant's `conversation_id`. A first turn without one receives a new opaque ID in the result. The entry maps that ID to a separate opaque Hermes named-conversation key and reuses the key for follow-up turns; distinct HA IDs stay isolated and the HA ID itself is never sent to Hermes. The entry retains the 256 most recently used mappings, so an evicted inactive ID starts a new Hermes context if it returns rather than sharing another conversation's context.

Responses may contain Hermes tool records before the final assistant message. A completed response containing only tool records is rejected and is never treated as speakable success.

New config entries use a 90-second total request timeout (adjustable from 1 to 120 seconds). Existing entries keep their saved timeout. To move an existing entry to 90 seconds, open **Settings → Devices & services → Hermes Conversation Agent → Configure**, set **Total timeout** to `90`, and submit the options form.

## Capability validation

Before configuration, setup, and every request, the component validates authenticated capabilities. The server must advertise bearer authentication, `responses_api: true`, `chat_completions: true`, the fixed Responses endpoint, and no custom `security` object. Other contracts fail closed before dispatch.

## Model selection

By default, each request uses the model advertised by `/v1/capabilities`. The entry options include an optional **Model alias**: leave it blank to preserve that default, or enter a Hermes model/routing alias to send that value as `model` to the same server. The alias neither changes the endpoint nor adds a request field.

## Security and rollout

Keep the endpoint private (Tailnet/LAN/private reverse proxy) and use bearer auth. Disable unnecessary browser CORS. HTTPS is preferred; private HTTP needs explicit acknowledgement. Requests use a cookie-free Home Assistant session and contain only `{model, input, conversation, stream: false}`. Dispatched requests revalidate capabilities and are never retried automatically. A timeout, disconnect, malformed result, or tool-only completed result after dispatch is indeterminate; Assist receives a fixed confirmation-failure response rather than a claimed action success.

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
