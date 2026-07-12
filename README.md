# Hermes Home Assistant Conversation Agent

> A Home Assistant custom integration that connects **Assist / Home Assistant Voice** to **Hermes Agent** for private, spoken, tool-using home conversations.

## Mission

Make Hermes a first-class **Home Assistant Conversation Agent**: a person speaks to Home Assistant Voice, Assist transcribes the request, Hermes reasons and uses its configured tools, and Home Assistant speaks Hermes’s final answer.

The project is deliberately a **thin, secure adapter**. It does not replace Home Assistant’s STT, TTS, wake-word detection, dashboards, entity registry, or automation engine. It does not reimplement smart-home commands. Home Assistant owns the voice pipeline; Hermes owns reasoning and tool selection.

## Status

**Contract validation / pre-component implementation.** This repository is **not installable yet**. The narrow Hermes Responses API contract is now live-verified against Hermes Agent 0.18.2 and covered by deterministic plus explicitly opt-in live tests; Home Assistant component code has not been implemented.

The initial plan was independently reviewed with **Codex GPT-5.6 Sol, medium reasoning**. The review identified three blockers that are now explicit design requirements:

1. Dangerous actions must be blocked until Hermes exposes an enforceable, server-side confirmation contract—not just a prompt.
2. v0.1 uses Hermes’s stateful `POST /v1/responses` contract with named conversations, after an automated compatibility test pins the supported Hermes version.
3. Conversation identity, serialization, expiry, reset, and privacy boundaries must be implemented and tested before release.

Read the complete reviewed plan in [`docs/plans/2026-07-12-initial-design.md`](docs/plans/2026-07-12-initial-design.md).

The verified request/response schema, errors, limits, evidence boundary, and test commands are documented in [`docs/hermes-responses-contract.md`](docs/hermes-responses-contract.md).

## Superficial design

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
- [Verified Hermes Responses API contract](docs/hermes-responses-contract.md)
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
