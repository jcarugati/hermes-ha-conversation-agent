# Hermes Home Assistant Conversation Agent

> A secure, thin Home Assistant Conversation entity that sends final-response requests
> to one validated Hermes endpoint per config entry.

## Mission

The planned v0.1 integration will let Home Assistant Assist pass a transcribed request
to Hermes and speak Hermes's final response. Home Assistant owns wake word, STT, TTS,
pipelines, devices, and native automations; Hermes owns reasoning and its configured
tools. This integration remains a thin adapter to the verified Responses API.

## Current status

**UI-configurable Hermes home-gateway conversation agent.** Home Assistant
can create one config entry per canonical Hermes endpoint identity, validate `/health` and the
authenticated `responses_api` capability plus the exact gateway-enforced no-tools security
policy before saving, rotate the bearer token by
reauthentication, change bounded non-secret request limits, reload entries, and retry
setup when Hermes is unavailable. Every setup repeats validation, stores the client
and validated model, and registers exactly one official Conversation entity using
Home Assistant's shared asynchronous HTTP session.
Because `/health` is unauthenticated, any health failure remains retryable; only a
401/403 from authenticated capabilities starts token reauthentication.

Configuration is UI-only. HTTPS is the default; every user, import, reauthentication,
and options flow involving permitted local/private HTTP requires a separate operator
acknowledgement. Credentials stay in config-entry data, while the
options flow contains only connect timeout, total timeout, and maximum output length.

For each dispatcher turn, the entity sends only the bounded utterance, setup-validated
model, and a fresh opaque conversation key to the client's fixed non-streaming
Responses API. It does not read or forward inbound HA `ChatLog` history or any context,
device, user, system-prompt, or credential fields. After Hermes returns, it adds only
the bounded assistant text to HA's local `ChatLog` through the official no-tools API
and returns that same text for speech.
This mode is intentionally incompatible with a generic remote Hermes server: authenticated
`GET /v1/capabilities` must contain exactly `security: {"tool_policy":"none",
"mcp_policy":"none","server_enforced":true}`. Missing, mismatched, or extended policy
objects fail closed during configuration, setup, and every pre-send capability check.

The deterministic Hermes contract verifier requires the same exact security object
before its first POST, and its successful evidence contains only sanitized validated
policy values. Together with the defensive async client, it covers the fixed
`/health`, `/v1/capabilities`, and `/v1/responses` surface. It passed against the
private home gateway on 2026-07-12; that gateway-specific evidence does not pin a
minimum version or certify generic Hermes servers.

## Safety boundary

- Hermes must remain on a private LAN/Tailscale/reverse-proxy path, never the public Internet.
- TLS verification is enabled by default. HTTP opt-in remains limited to explicit local/private host classes.
- Home Assistant credentials, cookies, contexts, identifiers, and `ChatLog` history are never accepted by the client request interface.
- Transcripts and bearer tokens must never be logged.
- A voice utterance or spoken confirmation is not authentication.
- The accepted home gateway server-enforces no tools or MCP; the bridge exposes no actions.
- Dispatched requests are never automatically retried when their outcome may be unknown.

The bridge exposes no tool/action request fields or execution callbacks. The inert,
data-only `safety.py` declaration remains unchanged; it is not an execution sink or an
end-to-end attestation of independently configured Hermes tools.

## Implemented lifecycle

- UI-only URL/token config flow with canonical URL unique ID and atomic duplicate prevention.
- Canonical DNS/IDN/IP endpoint identity across case, trailing dots, default ports, and IPv6 spelling.
- Separate warning and affirmative acknowledgement in every permitted plaintext HTTP flow.
- Flow-time and setup-time health, authentication, endpoint, and capability validation.
- Token-only reauthentication with validation and reload; setup-time 401/403 starts reauth.
- Non-secret bounded options with automatic reload.
- Retryable unavailable-server setup, fresh validation on reload, and clean unload.
- One official Conversation entity per loaded entry, with clean unload/reload behavior.
- Sanitized availability, authentication, invalid-request, and indeterminate-result errors.
- No coordinator, periodic polling, diagnostics, tools, actions, or confirmation unlock.

## Development

The development environment is pinned in `uv.lock` and currently exercises Home
Assistant Core 2026.7.1.

```bash
uv sync --all-groups
uv run pytest
uv run ruff check .
uv run mypy
```

See the [installation guide](docs/installation-and-usage.md),
[architecture](docs/architecture.md), [security policy](SECURITY.md), and
[Hermes contract evidence](docs/hermes-responses-contract.md).

## Remaining v0.1 work

1. Run the strengthened contract verifier against a candidate Hermes release and pin compatibility from evidence.
2. Implement diagnostics/redaction in its separate tracker task.
3. Implement conversation locking/cache/TTL/reset/persistence and execution-profile enforcement in separately reviewed tasks.
4. Run HACS/Home Assistant validation, release checks, and a real Voice end-to-end test before publishing v0.1.

## License

License selection is intentionally pending before the first code release.
