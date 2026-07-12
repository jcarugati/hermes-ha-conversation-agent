# Home Assistant ConversationEntity compatibility spike

> A fixed-response developer spike that verifies one Home Assistant Conversation entity
> API shape. It does not connect Assist, Home Assistant Voice, or Hermes Agent.

## Mission

The proposed project would make Hermes a **Home Assistant Conversation Agent**: Assist
would pass a transcribed request to Hermes, and Home Assistant would speak Hermes's
final answer. That bridge is a future goal, not functionality in this spike.

The proposed bridge is deliberately a **thin, secure adapter**. It would not replace
Home Assistant's STT, TTS, wake-word detection, dashboards, entity registry, or
automation engine. Home Assistant would own the voice pipeline; Hermes would own
reasoning and tool selection.

## Status

**Contract validation / developer-only compatibility spike.** This repository is **not installable yet**. The narrow Hermes Responses API has a deterministic verifier and an explicitly opt-in live test, but the strengthened verifier still needs a fresh live run before a minimum Hermes version can be pinned. The inert Home Assistant compatibility spike is implemented; the production Hermes bridge is not.

**ConversationEntity compatibility spike, not an installable bridge.** The repository
contains one deliberately inert custom component used only to test Home Assistant's
current entity-based Conversation API. It registers a single entity and always returns
the same non-action-bearing reply.

The spike is tested against **Home Assistant Core 2026.7.1** on Python 3.14.2. The test
starts Home Assistant, loads the custom integration through HA's integration loader,
verifies entity registration, and sends input through HA's `async_converse` dispatcher.
This is narrow API compatibility evidence only; it does not establish installability,
Voice pipeline behavior, Hermes compatibility, or production readiness.

The initial plan was independently reviewed with **Codex GPT-5.6 Sol, medium reasoning**. The review identified three blockers that are now explicit design requirements:

1. Dangerous actions must be blocked until Hermes exposes an enforceable, server-side confirmation contract—not just a prompt.
2. v0.1 uses Hermes’s stateful `POST /v1/responses` contract with named conversations, after an automated compatibility test pins the supported Hermes version.
3. Conversation identity, serialization, expiry, reset, and privacy boundaries must be implemented and tested before release.

Read the complete reviewed plan in [`docs/plans/2026-07-12-initial-design.md`](docs/plans/2026-07-12-initial-design.md).

The required request/response schema, current evidence limitations, and test commands are documented in [`docs/hermes-responses-contract.md`](docs/hermes-responses-contract.md).

## Compatibility spike boundary

The spike has no Hermes HTTP client, endpoint or token configuration, capability
validation, conversation storage, cache, TTL, locks, diagnostics, config flow, tools,
or general bridge behavior. It does not inspect, log, persist, or forward the incoming
utterance or HA `ChatLog`. Home Assistant constructs those objects as part of the
current API call; the entity uses only the language and conversation ID needed to form
the fixed HA response.

Do not copy this component into a Home Assistant installation expecting a usable
conversation agent. The planned v0.1 below remains unimplemented.

## Proposed v0.1 design

```text
Home Assistant Voice
  → Assist STT
  → hermes_conversation custom integration
  → authenticated private connection
  → Hermes API server
  → Hermes Agent + its existing tools
  → concise final answer
  → Assist TTS
  → Home Assistant Voice
```

For example:

> **You:** “¿Qué luces quedaron prendidas?”  
> **Hermes:** “Quedaron encendidas la cocina y el pasillo.”

A conversation remains scoped to its originating Assist conversation using an opaque identifier. It must never be shared across rooms/users merely because they use the same Hermes instance.

## Safety model

- The Hermes API is never exposed directly to the public Internet.
- The integration uses a private LAN/Tailscale/reverse-proxy path with bearer authentication and TLS by default.
- Home Assistant credentials, cookies, contexts, and raw chat history are **not** forwarded to Hermes.
- Voice text and API tokens are not logged by this integration.
- A spoken confirmation is not authentication.
- Until Hermes offers an auditable execution-time confirmation gate, v0.1 must not expose high-impact actions through this agent: locks, alarms, garage/doors, pet feeding, destructive tasks, or Home Assistant configuration changes.
- An uncertain timeout never triggers an automatic retry, because an action might already have executed.

See [`SECURITY.md`](SECURITY.md) for the threat model and responsible disclosure policy.

## Planned capabilities for v0.1

- Home Assistant custom component in `custom_components/hermes_conversation`.
- Config flow for Hermes URL and bearer token.
- Connection/capability validation before saving configuration.
- A current Home Assistant `ConversationEntity` implementation.
- Hermes Responses API with opaque named conversations.
- Spanish-first, short spoken answers.
- Safe failures for timeout, bad auth, malformed response, unavailable endpoint, and tool errors.
- Diagnostics redaction, test coverage, CI, HACS metadata, manual install docs, and a real Voice end-to-end test.

## Documentation

- [Installation and usage guide](docs/installation-and-usage.md)
- [Architecture](docs/architecture.md)
- [Hermes Responses API contract verifier](docs/hermes-responses-contract.md)
- [Reviewed v0.1 design plan](docs/plans/2026-07-12-initial-design.md)
- [Contributor and agent instructions](AGENTS.md)
- [Security model](SECURITY.md)

## Roadmap

1. Validate the supported Home Assistant Conversation API and Hermes Responses API contract.
2. Implement the component skeleton, configuration flow, secure client, and diagnostics redaction.
3. Implement conversation processing, lifecycle controls, and safe error speech.
4. Add contract/unit/adversarial tests plus CI and HACS validation.
5. Perform fresh install, upgrade, rollback, and physical Home Assistant Voice end-to-end validation.
6. Release v0.1 only after the safety and compatibility acceptance criteria pass.

## License

License selection is intentionally pending before the first code release.
