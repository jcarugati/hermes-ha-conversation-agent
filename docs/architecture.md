# Architecture

```text
Voice device → Home Assistant Assist STT
  → (optional) Home Assistant local intents, when "Prefer handling commands locally" is on
  → Hermes ConversationEntity
  → authenticated private POST /v1/responses
  → direct API server of the existing Hermes instance
  → final text → ChatLog (full) + cleaned speech copy → Home Assistant TTS → voice device
```

With **Prefer handling commands locally** enabled, the Assist pipeline tries Home Assistant's built-in intents before this entity. A matched command is executed and answered by Home Assistant and never reaches Hermes; anything unmatched reaches the entity exactly as before. Because the entity advertises control support, Home Assistant's local-first pass excludes state questions and media search/play, which therefore still reach Hermes.

## Boundaries

Home Assistant retains voice, Assist, and Home Assistant credentials. The integration never forwards HA cookies, contexts, device/user identifiers, service tokens, or inbound ChatLog. It uses Home Assistant's connector with a cookie-free session.

The bridge accepts only the fixed health, capabilities, and Responses endpoints, disables redirects, validates bounded JSON, and emits only `{model, input, conversation, stream: false}`. It never exposes an HA service callback or tool schema.

## Direct capability contract

The server must identify as Hermes, require bearer authentication, advertise `responses_api: true` and `chat_completions: true`, publish the fixed Responses route, and omit custom `security`. This is checked during configuration, setup, and immediately before every Responses dispatch. A Responses-only or custom gateway contract is rejected before POST.

Hermes owns the tool/MCP policy and can use the same configured abilities as its other channels. The Conversation entity therefore advertises Home Assistant control support, but that UI capability is not an authorization boundary.

The response parser skips Hermes tool records (`function_call`, `function_call_output`) and `reasoning` records, and succeeds only when final non-empty assistant `output_text` is also present. Reasoning text is never returned or spoken. Any other output item type is a protocol error, and a completed response without final assistant text cannot enter the Conversation entity's success path.

Once a POST has been dispatched, the bridge never retries it. A timeout, disconnect, malformed response, or response without final assistant text becomes an indeterminate result; the retained internal cause is sanitized while the Conversation entity returns only its fixed confirmation-failure message. HTTP 401/403 on the POST is a definite authentication rejection rather than an indeterminate result: the client raises its authentication error and the entity starts Home Assistant's reauthentication flow.

## Request timeout data flow

The option defaults (connect timeout, total timeout, maximum output) are defined once in `const.py`; the client, setup, reauthentication, and options form all read them from there. The total timeout defaults to 90 seconds, and the options UI accepts 1 to 120 seconds. An entry without a saved total timeout uses that default; an explicitly saved value is never migrated or overwritten.

The total timeout applies only to the Responses POST. `/health` and `/v1/capabilities` use a separate 5-second total timeout (capped at the total timeout), so a stalled check fails before dispatch instead of consuming the POST budget.

## Response and speech data flow

On success the entity stores Hermes' full reply in Home Assistant's ChatLog and sets the intent speech to a cleaned copy. The cleaning is a small local function: it removes only recognized Markdown delimiters (paired emphasis/code delimiters, headings, and bullet markers at the start of a line, joining lines as sentences), link targets, bare URLs, and emoji. It keeps numbers, signs, arithmetic, units, and negations: a line-start `-` or `+` followed by a number is a sign, and an unpaired, intraword, or spaced `*` or `_` is left alone. Nothing about the cleaning is sent to Hermes.

The `ConversationResult` carries Home Assistant's own `ChatLog.continue_conversation`, which is true when the last assistant message ends with a question mark. Assist satellites then reopen the microphone for the answer. Error turns add no assistant message and never continue.

## Diagnostics

The client emits one `DEBUG` log line per turn with the monotonic durations of the capabilities preflight and the POST, the outcome class name, and the reply length in characters. It contains no transcript, reply text, token, URL, or conversation key.

## Model data flow

Setup retains the capabilities-advertised model as the entry's validated default and separately stores an optional model alias. On each turn, the client revalidates the capabilities contract. Without an alias it also requires that the same default is still advertised; with an alias that comparison is skipped, because the alias route does not use the default. It then sends either the default model (blank alias) or the configured alias (nonblank alias) as the value of the existing `model` field and validates the response against that selected value.

The alias never appears as a separate HTTP field. The remaining DTO is the bounded utterance as `input`, an opaque entry-local Hermes named-conversation key as `conversation`, and `stream: false`.

Current Hermes does not honor per-route `reasoning_effort` in `platforms.api_server.extra.model_routes`: its route parser keeps only `model`, `provider`, `api_key`, and `base_url`, and silently drops other keys. An alias route can choose the model, but reasoning is resolved for the model that runs, from `agent.reasoning_overrides` for that model and otherwise the global `agent.reasoning_effort`. Operators set the voice model's effort with `agent.reasoning_overrides`; that setting applies to every channel that runs the same model. Reasoning configuration is owned by Hermes; the bridge sends no reasoning field.

Voice instructions are owned by Hermes as well. The bridge never sends instructions; an operator can add a server-side `platform_hints.api_server` hint, which applies to every client of the API server.

## Conversation continuity data flow

On a first turn without a Home Assistant `conversation_id`, the entity generates an opaque ID and returns it in `ConversationResult`. The entity keeps an entry-local mapping from each HA conversation ID to a separate opaque Hermes conversation key. Follow-up turns with the same HA ID reuse that Hermes key; distinct HA IDs receive distinct keys, so their Hermes contexts cannot mix. The mapping is a 256-item least-recently-used cache: touching an ID refreshes it, and an evicted ID receives a new Hermes key if it returns. The HA ID and inbound ChatLog never cross the HTTP boundary. Unloading or reloading the entry discards the in-memory mapping rather than sharing conversation state with another entity or config entry.
