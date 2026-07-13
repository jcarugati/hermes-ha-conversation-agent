# Hermes Home Assistant Conversation Agent

A thin Home Assistant Conversation entity that sends final-response requests to a validated private Hermes endpoint and speaks the returned text through Assist.

## What it supports

- **Direct Hermes API server:** connects Assist to the same running Hermes instance used by other channels. This is the intended mode when that instance already controls Home Assistant. The direct server owns its own tool and MCP policy; the integration does not artificially restrict it.
- **Legacy no-tools gateway:** remains supported as a private fallback while a direct deployment is verified.

Both modes use authenticated `POST /v1/responses`; the bridge never uses chat completions itself, forwards HA ChatLog/cookies/context, or exposes an HA tool callback.

## Capability validation

Before configuration, setup, and every request, the component validates health and authenticated capabilities.

A direct server must advertise bearer authentication, `responses_api: true`, `chat_completions: true`, the fixed Responses endpoint, and no custom `security` object. A legacy gateway must advertise the exact no-tools policy. The two contracts are mutually exclusive and any other endpoint fails closed.

## Security and rollout

Keep endpoints private (Tailnet/LAN/private reverse proxy) and use bearer auth; this privacy is an operator deployment requirement for HTTPS endpoints. Disable unnecessary browser CORS. HTTPS is preferred; private HTTP needs explicit acknowledgement. Requests use a cookie-free Home Assistant session and contain only `{model, input, conversation, stream: false}`. Dispatched requests revalidate capabilities (not health) and are never retried automatically.

For safe migration, keep the working Voice pipeline enabled, add a separate direct entry/pipeline, verify simple text conversation, then a read-only HA query, then an explicitly authorized harmless action. Only after those checks should the fallback be retired or control advertised in Assist.

## Development

```bash
uv sync --all-groups
uv run pytest
uv run ruff check .
uv run mypy
```

See [installation](docs/installation-and-usage.md), [architecture](docs/architecture.md), and [security policy](SECURITY.md).
