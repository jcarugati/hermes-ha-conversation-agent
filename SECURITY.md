# Security policy

## Supported trust modes

The integration accepts only private, bearer-authenticated Hermes Responses API endpoints.

- **Direct Hermes API server:** the standard API server for the same running Hermes instance used by other channels. It advertises `responses_api: true`, `chat_completions: true`, bearer authentication, and `POST /v1/responses`, with no `security` member. Its tools and MCPs are governed by that Hermes instance. Voice is not identity proof and this mode may perform any operation that instance is configured to perform.
- **Legacy no-tools gateway:** accepted only when it advertises exactly `security: {"tool_policy":"none","mcp_policy":"none","server_enforced":true}`.

The modes are mutually exclusive. A direct server with any `security` member, or a legacy gateway that also advertises `chat_completions`, is rejected before dispatch.

## Non-negotiable transport and data rules

- Keep Hermes private: LAN, Tailnet, or a private reverse proxy; never public Internet.
- Bearer authentication is sent only in the Authorization header; never in URLs or logs.
- HTTPS validates normally. Private HTTP requires explicit acknowledgement and a private-host allowlist.
- Redirects are disabled. The client uses an isolated cookie jar, so Home Assistant cookies never cross the boundary.
- The only request body is `{model, input, conversation, stream: false}`. It contains no HA context, user/device identifiers, ChatLog history, credentials, tools, actions, instructions, or prompt overrides.
- Every dispatch revalidates capabilities. A dispatched request is never retried automatically; timeout or disconnect is indeterminate.

## Rollout

Keep a working legacy Voice gateway in place until direct text conversation has been verified through Assist. Then verify a read-only request and an explicitly authorized harmless action before advertising Home Assistant control capability or removing the fallback.

## Reporting a vulnerability

Do not publish bearer tokens, transcripts, private addresses, or Home Assistant data. Use a private GitHub security advisory or contact the maintainer privately.