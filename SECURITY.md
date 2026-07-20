# Security policy

## Supported trust model

The integration accepts only a private, bearer-authenticated direct Hermes API server for the same running Hermes instance used by other channels. It must advertise `responses_api: true`, `chat_completions: true`, bearer authentication, and `POST /v1/responses`, with no custom `security` member.

The Hermes instance governs its own tools and MCP servers. A voice utterance is not proof of user identity, and this integration does not add a sandbox or authorization boundary. The connected instance may perform any operation it is configured to perform.

## Non-negotiable transport and data rules

- Keep Hermes private: LAN, Tailnet, or a private reverse proxy; never public Internet.
- Bearer authentication is sent only in the Authorization header; never in URLs or logs.
- HTTPS validates normally. Private HTTP requires explicit acknowledgement and a private-host allowlist.
- Redirects are disabled. The client uses an isolated cookie jar, so Home Assistant cookies never cross the boundary.
- The only request body is `{model, input, conversation, stream: false}`. It contains no HA context, user/device identifiers, ChatLog history, credentials, tools, actions, instructions, or prompt overrides.
- Home Assistant's `conversation_id` is retained locally and is never used as the wire value. Each entry maps it to a separate opaque Hermes key, reuses that key only for the same HA conversation, and assigns distinct keys to distinct IDs. A first turn without an HA ID receives a newly generated opaque ID in its result. The entry keeps a 256-item least-recently-used mapping; returning after eviction starts a fresh Hermes context and never reuses another conversation's key.
- A configured model alias replaces only the value of `model`; it is not an additional DTO field and cannot select another endpoint.
- After installing a Hermes runtime version/change that supports per-route `reasoning_effort`, operators may configure a `hermes-voice` API-server `model_routes` entry with the same provider/model as the default profile and `reasoning_effort: none`. This affects only requests sending `model: hermes-voice`; Discord, Telegram, CLI, and default API requests retain the global `agent.reasoning_effort`. Do not treat the reasoning isolation as active before the matching Hermes runtime support is installed.
- Tool records may precede final assistant output, but a completed tool-only response fails closed as a protocol error and is never spoken as success.
- Every dispatch revalidates direct capabilities. A dispatched request is never retried automatically; timeout, disconnect, malformed output, or tool-only output after dispatch is indeterminate. The retained causal diagnostic is sanitized, and the spoken response never claims success without final assistant text.
- New entries save a 90-second total timeout, within the 1–120 second supported range. Existing saved options are left unchanged; to adopt 90 seconds, open **Settings → Devices & services → Hermes Conversation Agent → Configure**, set **Total timeout** to `90`, and save.

## Rollout

Preserve the working Voice path while configuring and testing a new direct entry. Verify direct Assist text first, then a read-only Home Assistant request, then an explicitly authorized harmless action. Do not infer safety from prompt wording or from successful conversational replies.

## Reporting a vulnerability

Do not publish bearer tokens, transcripts, private addresses, model aliases that reveal private routing, or Home Assistant data. Use a private GitHub security advisory or contact the maintainer privately.
