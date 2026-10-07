# Security policy

## Supported trust model

The integration accepts only a private, bearer-authenticated direct Hermes API server for the same running Hermes instance used by other channels. It must advertise `responses_api: true`, `chat_completions: true`, bearer authentication, and `POST /v1/responses`, with no custom `security` member.

The Hermes instance governs its own tools and MCP servers. A voice utterance is not proof of user identity, and this integration does not add a sandbox or authorization boundary. The connected instance may perform any operation it is configured to perform.

## Non-negotiable transport and data rules

- Keep Hermes private: LAN, Tailnet, or a private reverse proxy; never public Internet.
- Bearer authentication is sent only in the Authorization header; never in URLs or logs.
- The only log output is one `DEBUG` line per turn with preflight/POST durations, the outcome class name, and the reply length. It never contains transcripts, reply text, tokens, URLs, or conversation keys.
- HTTPS validates normally. Private HTTP requires explicit acknowledgement and a private-host allowlist.
- Redirects are disabled. The client uses an isolated cookie jar, so Home Assistant cookies never cross the boundary.
- The only request body is `{model, input, conversation, stream: false}`. It contains no HA context, user/device identifiers, ChatLog history, credentials, tools, actions, instructions, or prompt overrides.
- Home Assistant's `conversation_id` is retained locally and is never used as the wire value. Each entry maps it to a separate opaque Hermes key, reuses that key only for the same HA conversation, and assigns distinct keys to distinct IDs. A first turn without an HA ID receives a newly generated opaque ID in its result. The entry keeps a 256-item least-recently-used mapping; returning after eviction starts a fresh Hermes context and never reuses another conversation's key.
- A configured model alias replaces only the value of `model`; it is not an additional DTO field and cannot select another endpoint.
- Current Hermes does not honor `reasoning_effort` inside API-server `model_routes`; the key is silently dropped. Reasoning for the voice model is set with Hermes `agent.reasoning_overrides`, which applies to every channel running that model. It is a latency setting, not an isolation or security boundary.
- Voice instructions live on the Hermes side (`platform_hints.api_server`) and apply to every API-server client. A prompt or hint is not a security boundary.
- Tool records and `reasoning` records may precede final assistant output. They are skipped, reasoning is never spoken, and a completed response without final assistant text fails closed as a protocol error and is never spoken as success.
- Every dispatch revalidates direct capabilities. Without a model alias it also requires the setup-time default model to still be advertised; with an alias that one comparison is skipped. A dispatched request is never retried automatically; timeout, disconnect, malformed output, or tool-only output after dispatch is indeterminate. HTTP 401/403 on the POST is treated as an authentication rejection and starts Home Assistant reauthentication. The retained causal diagnostic is sanitized, and the spoken response never claims success without final assistant text.
- Assist speaks a cleaned copy of the reply (no recognized Markdown delimiters, link targets, bare URLs, or emoji; signs and arithmetic such as `- 5 °C` or `2*3 W` are kept); the full reply stays only in Home Assistant's local ChatLog. When that reply ends with a question mark, Home Assistant's `continue_conversation` reopens the satellite microphone for one more utterance; that utterance is handled like any other turn.
- The total timeout defaults to 90 seconds (1–120 seconds) for every entry without a saved value; explicitly saved values are unchanged. Health and capabilities checks use a separate 5-second timeout.
- With **Prefer handling commands locally** enabled in the Assist pipeline, Home Assistant executes the commands it matches itself, with its own permissions on exposed entities, and those turns never reach Hermes. Only expose entities you are willing to control by unauthenticated voice.

## Rollout

Preserve the working Voice path while configuring and testing a new direct entry. Verify direct Assist text first, then a read-only Home Assistant request, then an explicitly authorized harmless action. Do not infer safety from prompt wording or from successful conversational replies.

## Reporting a vulnerability

Do not publish bearer tokens, transcripts, private addresses, model aliases that reveal private routing, or Home Assistant data. Use a private GitHub security advisory or contact the maintainer privately.
