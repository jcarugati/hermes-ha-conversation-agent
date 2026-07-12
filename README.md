# Hermes Home Assistant Conversation Agent

> A secure config-entry and HTTP-client foundation. It validates Hermes configuration,
> but does not yet connect Assist, Home Assistant Voice, or conversation requests.

## Mission

The planned v0.1 integration will let Home Assistant Assist pass a transcribed request
to Hermes and speak Hermes's final response. Home Assistant owns wake word, STT, TTS,
pipelines, devices, and native automations; Hermes owns reasoning and its configured
tools. This integration remains a thin adapter to the verified Responses API.

## Current status

**UI-configurable foundation, not a usable Hermes conversation agent.** Home Assistant
can create one config entry per canonical Hermes endpoint identity, validate `/health` and the
authenticated `responses_api` capability before saving, rotate the bearer token by
reauthentication, change bounded non-secret request limits, reload entries, and retry
setup when Hermes is unavailable. Every setup repeats validation and stores a client
using Home Assistant's shared asynchronous HTTP session.
Because `/health` is unauthenticated, any health failure remains retryable; only a
401/403 from authenticated capabilities starts token reauthentication.

Configuration is UI-only. HTTPS is the default; every user, import, reauthentication,
and options flow involving permitted local/private HTTP requires a separate operator
acknowledgement. Credentials stay in config-entry data, while the
options flow contains only connect timeout, total timeout, and maximum output length.

This task deliberately adds no `ConversationEntity`, request bridge, conversation
cache, coordinator, periodic check, tool/action path, or diagnostics. Installing it
exposes configuration only; there is no selectable Hermes agent yet. Diagnostics and
redaction are a separate tracker task.

The deterministic Hermes contract verifier and defensive async client cover the fixed
`/health`, `/v1/capabilities`, and `/v1/responses` surface. The strengthened verifier
still needs a fresh live run before a minimum Hermes version can be pinned.

## Safety boundary

- Hermes must remain on a private LAN/Tailscale/reverse-proxy path, never the public Internet.
- TLS verification is enabled by default. HTTP opt-in remains limited to explicit local/private host classes.
- Home Assistant credentials, cookies, contexts, identifiers, and `ChatLog` history are never accepted by the client request interface.
- Transcripts and bearer tokens must never be logged.
- A voice utterance or spoken confirmation is not authentication.
- High-impact actions remain blocked until Hermes has an enforceable server-side pending-action protocol binding exact parameters, source conversation, and expiry.
- Dispatched requests are never automatically retried when their outcome may be unknown.

The repository also contains an inert HA-local declaration for a read-only/status
capability. It has no execution sink and is not end-to-end enforcement. A future
bridge requires a verified Hermes read-only/status profile at startup and every
request/tool sink.

## Implemented lifecycle

- UI-only URL/token config flow with canonical URL unique ID and atomic duplicate prevention.
- Canonical DNS/IDN/IP endpoint identity across case, trailing dots, default ports, and IPv6 spelling.
- Separate warning and affirmative acknowledgement in every permitted plaintext HTTP flow.
- Flow-time and setup-time health, authentication, endpoint, and capability validation.
- Token-only reauthentication with validation and reload; setup-time 401/403 starts reauth.
- Non-secret bounded options with automatic reload.
- Retryable unavailable-server setup, fresh validation on reload, and clean unload.
- No coordinator, periodic polling, diagnostics, conversation behavior, tools, or actions.

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
3. Implement the entity-based conversation bridge, opaque conversation lifecycle, and execution-profile enforcement in separately reviewed tasks.
4. Run HACS/Home Assistant validation, release checks, and a real Voice end-to-end test before publishing v0.1.

## License

License selection is intentionally pending before the first code release.
