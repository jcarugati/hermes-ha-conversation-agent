# Architecture

```text
Voice device → Home Assistant Assist STT
  → Hermes ConversationEntity
  → authenticated private POST /v1/responses
  → existing Hermes API server or legacy no-tools gateway
  → final text → Home Assistant TTS → voice device
```

## Boundaries

Home Assistant retains voice, Assist, and Home Assistant credentials. The integration never forwards HA cookies, contexts, device/user identifiers, service tokens, or inbound ChatLog. It uses Home Assistant's connector with a cookie-free session.

The bridge accepts only the fixed health, capabilities, and Responses endpoints, disables redirects, validates bounded JSON, and emits only `{model, input, conversation, stream: false}`. It never exposes an HA service callback or tool schema.

## Capability contracts

A direct Hermes server advertises `responses_api` and `chat_completions` with bearer auth and no `security` key. It owns tool/MCP policy, so it can use the same configured abilities as the existing Hermes instance.

A legacy gateway has no `chat_completions` feature and must supply the exact server-enforced no-tools security object. Contracts are mutually exclusive and validated immediately before dispatch.

Direct operation is rolled out in parallel: conversational text first, then read-only HA access, then an explicitly authorized harmless action. Do not remove a functioning fallback before those checks.