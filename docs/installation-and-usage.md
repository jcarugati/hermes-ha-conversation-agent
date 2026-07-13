# Installation and usage

Install through HACS or copy `custom_components/hermes_conversation/` into Home Assistant and restart Home Assistant. Configure it from **Settings → Devices & services → Add integration → Hermes Conversation Agent**.

## Endpoint modes

Enter a private root URL and bearer token. The integration validates `/health`, authenticated `/v1/capabilities`, and the fixed `/v1/responses` endpoint before saving.

### Direct Hermes API server

Use the standard API server of the running Hermes instance when Assist should use the same capabilities as other Hermes channels. It must advertise `responses_api: true`, `chat_completions: true`, bearer-required authentication, and no custom `security` object. This mode inherits the configured Hermes capability surface; it is not a home-only sandbox.

### Legacy no-tools gateway

A legacy private gateway remains supported only with the exact server-enforced no-tools policy. It is useful as a fallback while the direct endpoint is being verified.

The endpoint must be private. HTTPS is preferred; private HTTP requires explicit acknowledgement. Do not place credentials in URLs.

## Verify safely

1. Keep the existing Voice pipeline unchanged.
2. Create a separate direct config entry and pipeline.
3. Test a simple spoken text request.
4. Test a read-only Home Assistant question.
5. Only after an explicitly authorized harmless action succeeds, enable/control-route the direct agent and retire the fallback.

Every turn sends only a bounded utterance, validated model, and fresh opaque conversation key. HA ChatLog remains local and requests are not automatically retried after dispatch.