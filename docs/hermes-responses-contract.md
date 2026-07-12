# Hermes Responses API contract verifier

## Verification baseline

The committed verifier checks `GET /health`, authenticated `GET /v1/capabilities`, and two authenticated, non-streaming `POST /v1/responses` turns. Each run generates a fresh opaque conversation key and a separate fresh marker. Both POSTs use that run-scoped key, and continuity passes only when the second response returns exactly that run's marker.

**Current evidence status:** no live-verifier environment was available during the rejected-review repair. A historical probe targeted Hermes Agent 0.18.2, but it used weaker schema and continuity checks and is not accepted as evidence for this strengthened contract. The minimum compatible Hermes version therefore remains unpinned until the committed verifier passes against a real instance. No Hermes version is currently claimed compatible.

The verifier does not print its base URL, token, prompts, response text, conversation key, marker, response ID, or headers. Successful output is limited to the validated version, advertised model, status/object/capability booleans, the three fixed validated security-policy values, and response media types.

## Required HTTP surface

| Request | Authentication | Required success contract |
| --- | --- | --- |
| `GET /health` | None required | `200`, `application/json`; object with `status: "ok"`, `platform: "hermes-agent"`, and non-empty `version`. |
| `GET /v1/capabilities` | `Authorization: Bearer <token>` | `200`, `application/json`; `object: "hermes.api_server.capabilities"`, non-empty `model`, `auth.type: "bearer"`, `auth.required: true`, `features.responses_api: true`, `endpoints.responses: {"method":"POST","path":"/v1/responses"}`, and exactly `security: {"tool_policy":"none","mcp_policy":"none","server_enforced":true}` for gateway-enforced home mode. |
| `POST /v1/responses` | `Authorization: Bearer <token>` | `200`, `application/json`; non-empty `id`, `object: "response"`, `status: "completed"`, non-negative integer `created_at`, the advertised `model`, and `usage` with non-negative integer `input_tokens`, `output_tokens`, and `total_tokens`. `output` must be a non-empty array containing only `type: "message"`, `role: "assistant"` items with non-empty `content`; every content item must have `type: "output_text"` and non-empty string `text`. The two turns must have distinct response IDs. |

Requests send `Accept: application/json`; POST also sends `Content-Type: application/json`. The verifier checks the response media type but makes no claim about `Content-Length`, session headers, or other response headers.

## v0.1 request allowlist

The contract test sends exactly:

```json
{
  "model": "<capabilities.model>",
  "input": "<inert run-scoped continuity probe>",
  "conversation": "<fresh opaque run-scoped key>",
  "stream": false
}
```

Only these four fields are sent by the verifier and allowed by the planned v0.1 DTO. In particular, it does not send `conversation_history`, `previous_response_id`, `instructions`, `tools`, Home Assistant `ChatLog`, HA identifiers, contexts, credentials, cookies, or copied headers. The verifier tests named conversations only; compatibility or mutual-exclusion behavior for other state mechanisms is unverified.

The Home Assistant client accepts only the gateway-enforced home mode above. A generic
remote Hermes server with `responses_api` but missing or different `security` policy is
not compatible and is rejected before any Responses POST.

The model is the opaque non-empty value returned by `/v1/capabilities`, and the verifier sends that exact value in both POSTs. It does not assert what that value represents and does not hard-code a model name.

## Errors and limits

The committed live verifier does not send negative, malformed, oversized, or action-bearing requests, so it establishes no Hermes error-envelope or server-limit behavior. Previous source-inspection claims have been removed because that inspection is not reproducible through the committed verifier.

The future client must impose its own utterance, conversation-key, response-byte, deadline, and spoken-output limits. The verifier bounds each response to 1 MiB and never follows redirects; those are verifier safeguards, not claims about Hermes defaults.

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
