# Security policy

## Supported trust model

Operators must connect the integration only to a private, bearer-authenticated direct Hermes API server for the same running Hermes instance used by other channels. The server must advertise `responses_api: true`, `chat_completions: true`, bearer authentication, and `POST /v1/responses`, with no custom `security` member. The integration does not establish that an HTTPS host is private; only plaintext HTTP hosts are restricted to local names and private addresses.

The Hermes instance governs its own tools and MCP servers. A voice utterance is not proof of user identity, and this integration does not add a sandbox or authorization boundary. The connected instance may perform any operation it is configured to perform.

## Non-negotiable transport and data rules

- Keep Hermes private as an operator requirement: LAN, Tailnet, or a private reverse proxy; never public Internet. HTTPS certificate validation does not enforce private hosting.
- Bearer authentication is sent only in the Authorization header; never in URLs or logs. Enter the token through Home Assistant's configuration flow, which stores it in the config entry; do not manually copy it into documentation, logs, URLs, or ordinary files.
- HTTPS validates normally. Private HTTP requires explicit acknowledgement and a private-host allowlist.
- Redirects are disabled. The client uses an isolated cookie jar, so Home Assistant cookies never cross the boundary.
- The only request body is `{model, input, conversation, stream: false}`. It contains no HA context, user/device identifiers, ChatLog history, credentials, tools, actions, instructions, or prompt overrides.
- No ChatLog or cross-turn context is forwarded. Hermes may retain each one-turn named conversation, response, and tool records under its own policy; the integration makes no remote-retention or deletion guarantee.
- Setup and reload store the capabilities-advertised default model. An empty alias uses that stored model; if Hermes changes its default, reload or reconfigure the entry. A configured alias replaces only the value of `model`; it is forwarded without route pre-validation, must be accepted and echoed by Hermes, and cannot select another endpoint, isolated profile, or agent or change available tools.
- Tool records may precede final assistant output, but a completed tool-only response fails closed as a protocol error and is never spoken as success.
- Setup and reload validate health and authenticated direct capabilities. Every dispatch revalidates authenticated capabilities and then posts without another health check. A dispatched request is never retried automatically; timeout or disconnect is indeterminate.

## Rollout

Preserve the working Voice path while configuring and testing a new direct entry. First verify a written response through text Assist. Separately verify voice input and Home Assistant TTS output. Then test a read-only Home Assistant request and an explicitly authorized harmless action. Do not infer safety from prompt wording or from successful conversational replies.

## Reporting a vulnerability

Do not publish bearer tokens, transcripts, private addresses, model aliases that reveal private routing, or Home Assistant data. Use a private GitHub security advisory or contact the maintainer privately.
