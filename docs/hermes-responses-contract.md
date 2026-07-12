# Verified Hermes Responses API contract

## Verification baseline

The v0.1 adapter contract was live-verified on 2026-07-12 against a private, reachable Hermes Agent **0.18.2** instance. The test observed JSON success responses from `GET /health`, authenticated `GET /v1/capabilities`, and two authenticated, non-streaming `POST /v1/responses` turns. Both POSTs used the same synthetic opaque conversation name; the second response recalled a synthetic marker supplied only in the first turn.

Accordingly, the minimum Hermes version for this contract is **0.18.2**. Earlier versions are not claimed compatible. This is a contract-test floor, not a claim that every deployment of 0.18.2 has a usable model or identical tool configuration.

No private URL, token, request transcript, response text, session ID, or provider configuration was recorded.

## Required HTTP surface

| Request | Authentication | Observed success contract |
| --- | --- | --- |
| `GET /health` | None required | `200`, `application/json`; object with `status: "ok"`, `platform: "hermes-agent"`, and non-empty `version`. |
| `GET /v1/capabilities` | `Authorization: Bearer <token>` | `200`, `application/json`; `object: "hermes.api_server.capabilities"`, non-empty `model`, `auth.type: "bearer"`, `auth.required: true`, `features.responses_api: true`, and `endpoints.responses: {"method":"POST","path":"/v1/responses"}`. |
| `POST /v1/responses` | `Authorization: Bearer <token>` | `200`, `application/json`; `id`, `object: "response"`, `status: "completed"`, `created_at`, the advertised `model`, `output` array, and `usage` with `input_tokens`, `output_tokens`, and `total_tokens`. A message output has `type`, `role`, and `content`; an output-text content item has `type` and `text`. |

Requests send `Accept: application/json`; POST also sends `Content-Type: application/json`. The live POST response included `Content-Type`, `Content-Length`, and `X-Hermes-Session-Id`; the integration does not need to send or persist that session header because named `conversation` provides the selected state mechanism.

## v0.1 request allowlist

The contract test sends exactly:

```json
{
  "model": "<capabilities.model>",
  "input": "<bounded plain-text utterance>",
  "conversation": "<opaque integration-generated key>",
  "stream": false
}
```

Only these four fields are verified and allowed for v0.1. In particular, the bridge does not send `conversation_history`, `previous_response_id`, `instructions`, `tools`, Home Assistant `ChatLog`, HA identifiers, contexts, credentials, cookies, or copied headers. Named conversations and `previous_response_id` are mutually exclusive in the inspected 0.18.2 server implementation; v0.1 selects named conversations only.

The model is not a user-entered provider model ID. It is the opaque model name advertised by `/v1/capabilities`; the live instance advertised `hermes-agent`. Deployments may advertise a profile name or configured model-route alias, so clients must use the returned value rather than hard-code the observed name.

## Errors and limits

Live verification observed these JSON error envelopes:

- Missing/invalid bearer authentication on `/v1/capabilities`: HTTP `401`, root `error` object containing `message`, `type`, and `code`.
- Missing `input` on `/v1/responses`: HTTP `400`, root `error` object containing `message`, `type`, `param`, and `code`.

The Hermes 0.18.2 server source at the verified installation commit (`411d59976`) establishes additional server-side facts without requiring unsafe live payloads:

- Request bodies are capped at `10,000,000` bytes and return JSON HTTP `413` with code `body_too_large` when exceeded.
- Normalized text is capped at `65,536` characters and content arrays at `1,000` items. These are server normalization limits, not suitable integration input limits.
- Stored Responses entries are bounded to `100` on that server. Named conversation state can therefore be evicted; the component must handle lost server state safely.
- Invalid JSON/input and incompatible `conversation` plus `previous_response_id` return `400`; unknown previous response IDs return `404`; concurrency saturation can return `429`; an unhandled agent failure can return `500`.

There is no evidence-backed server limit for the named `conversation` string or final output length in this contract. The future client must impose its own tighter utterance, conversation-key, response-byte, deadline, and spoken-output limits. The verifier bounds each response to 1 MiB and never follows redirects; those are verifier safeguards, not claims about Hermes defaults.

## Automated verification

Deterministic tests use an in-process HTTP fixture and make no network calls:

```bash
python -m unittest discover -s tests -v
```

The live test is skipped unless all three variables are explicitly supplied:

```bash
HERMES_CONTRACT_LIVE=1 \
HERMES_CONTRACT_BASE_URL=https://private-hermes.example.invalid \
HERMES_CONTRACT_TOKEN="$API_SERVER_KEY" \
python -m unittest tests.test_hermes_contract.LiveContractTest -v
```

The standalone verifier uses the same gate:

```bash
HERMES_CONTRACT_LIVE=1 \
HERMES_CONTRACT_BASE_URL=https://private-hermes.example.invalid \
HERMES_CONTRACT_TOKEN="$API_SERVER_KEY" \
python -m tools.hermes_contract
```

Use only a private endpoint. Environment values are consumed at runtime and must not be written to shell history, test output, fixtures, or Git. Successful output contains only non-sensitive contract evidence; failures contain the method, fixed route, status/type, and never the response body or token.
