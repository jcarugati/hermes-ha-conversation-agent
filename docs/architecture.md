# Architecture

```text
Voice device → Home Assistant Assist STT
  → Hermes ConversationEntity
  → authenticated private POST /v1/responses
  → direct API server of the existing Hermes instance
  → final text → Home Assistant TTS → voice device
```

## Boundaries

Home Assistant retains voice, Assist, and Home Assistant credentials. The integration never forwards HA cookies, contexts, device/user identifiers, service tokens, or inbound ChatLog. It uses Home Assistant's connector with a cookie-free session.

The bridge accepts only the fixed health, capabilities, and Responses endpoints, disables redirects, validates bounded JSON, and emits only `{model, input, conversation, stream: false}`. It never exposes an HA service callback or tool schema.

## Direct capability contract

The server must identify as Hermes, require bearer authentication, advertise `responses_api: true` and `chat_completions: true`, publish the fixed Responses route, and omit custom `security`. This is checked during configuration, setup, and immediately before every Responses dispatch. A Responses-only or custom gateway contract is rejected before POST.

Hermes owns the tool/MCP policy and can use the same configured abilities as its other channels. The Conversation entity therefore advertises Home Assistant control support, but that UI capability is not an authorization boundary.

The response parser ignores validated Hermes tool records only when final non-empty assistant `output_text` is also present. A completed tool-only response is a protocol error and cannot enter the Conversation entity's success path.

Once a POST has been dispatched, the bridge never retries it. A timeout, disconnect, malformed response, or response without final assistant text becomes an indeterminate result; the retained internal cause is sanitized while the Conversation entity returns only its fixed confirmation-failure message.

## Request timeout data flow

When a new entry is created, it saves a 90-second total timeout option. The options UI accepts 1 to 120 seconds. Existing stored options are not migrated or overwritten; an operator who wants the new value opens **Settings → Devices & services → Hermes Conversation Agent → Configure**, sets **Total timeout** to `90`, and saves the options.

## Model data flow

Setup retains the capabilities-advertised model as the entry's validated default and separately stores an optional model alias. On each turn, the client revalidates that the same default is still advertised. It then sends either the default model (blank alias) or the configured alias (nonblank alias) as the value of the existing `model` field and validates the response against that selected value.

The alias never appears as a separate HTTP field. The remaining DTO is the bounded utterance as `input`, an opaque entry-local Hermes named-conversation key as `conversation`, and `stream: false`.

## Conversation continuity data flow

On a first turn without a Home Assistant `conversation_id`, the entity generates an opaque ID and returns it in `ConversationResult`. The entity keeps an entry-local mapping from each HA conversation ID to a separate opaque Hermes conversation key. Follow-up turns with the same HA ID reuse that Hermes key; distinct HA IDs receive distinct keys, so their Hermes contexts cannot mix. The mapping is a 256-item least-recently-used cache: touching an ID refreshes it, and an evicted ID receives a new Hermes key if it returns. The HA ID and inbound ChatLog never cross the HTTP boundary. Unloading or reloading the entry discards the in-memory mapping rather than sharing conversation state with another entity or config entry.
