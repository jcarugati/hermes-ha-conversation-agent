# Hermes Responses API contract verifier

## Verification baseline

The committed verifier checks `GET /health`, authenticated `GET /v1/capabilities`, and two authenticated, non-streaming `POST /v1/responses` turns. Each run generates a fresh opaque conversation key and a separate fresh marker. Both POSTs use that run-scoped key, and continuity passes only when the second response returns exactly that run's marker.

The current verifier targets the direct Hermes API-server contract. No live endpoint is contacted by the default test suite, and this repository records no claim that a particular private deployment currently passes it. A 2026-07-12 live result described an older gateway contract and does not constitute evidence for the current direct-only architecture.

The verifier does not print its base URL, token, prompts, response text, conversation key, marker, response ID, or headers. Successful output is limited to the validated version, advertised model, status/object/capability booleans, and response media types.

## Required HTTP surface

| Request | Authentication | Required success contract |
| --- | --- | --- |
| `GET /health` | None required | `200`, `application/json`; object with `status: "ok"`, `platform: "hermes-agent"`, and non-empty `version`. |
| `GET /v1/capabilities` | `Authorization: Bearer <token>` | `200`, `application/json`; `object: "hermes.api_server.capabilities"`, non-empty `model`, `auth.type: "bearer"`, `auth.required: true`, `features.responses_api: true`, `features.chat_completions: true`, `endpoints.responses: {"method":"POST","path":"/v1/responses"}`, and no custom `security` member. |
| `POST /v1/responses` | `Authorization: Bearer <token>` | `200`, `application/json`; non-empty `id`, `object: "response"`, `status: "completed"`, non-negative integer `created_at`, the requested `model`, and `usage` with non-negative integer token counts. `output` must contain assistant messages with non-empty `output_text`; the two turns must have distinct response IDs. |

Requests send `Accept: application/json`; POST also sends `Content-Type: application/json`. Redirects are never followed.

## Request allowlist

The contract test sends exactly:

```json
{
  "model": "<capabilities.model>",
  "input": "<inert run-scoped continuity probe>",
  "conversation": "<fresh opaque run-scoped key>",
  "stream": false
}
```

Only these four fields are sent by the verifier and allowed by the integration DTO. It does not send history, response IDs, instructions, prompt overrides, tools, MCP definitions, actions, Home Assistant ChatLog, HA identifiers, contexts, credentials, cookies, or copied headers.

The standalone verifier always tests the capabilities-advertised default model. The Home Assistant integration may instead place a configured alias in the same `model` field; this does not change the DTO or endpoint.

## Automated verification

Deterministic tests use an in-process HTTP fixture and make no external network calls:

```bash
uv run pytest -q tests/test_hermes_contract.py
```

The live test is skipped unless all three variables are explicitly supplied:

```bash
HERMES_CONTRACT_LIVE=1 \
HERMES_CONTRACT_BASE_URL=https://private-hermes.example.invalid \
HERMES_CONTRACT_TOKEN="$API_SERVER_KEY" \
uv run pytest -q tests/test_hermes_contract.py
```

Use only a private endpoint. Environment values are consumed at runtime and must not be written to shell history, test output, fixtures, or Git.
