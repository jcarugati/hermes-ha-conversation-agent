# Hermes Responses API Contract Validation Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:test-driven-development to implement this plan task-by-task. Steps use checkbox syntax for tracking.

**Goal:** Establish and continuously verify the narrow Hermes HTTP contract used by the implemented v0.1 Home Assistant home-mode adapter.

**Architecture:** Add a dependency-free Python verifier for `GET /health`, authenticated `GET /v1/capabilities`, and non-streaming `POST /v1/responses`. Unit tests run against a local deterministic HTTP fixture; a separate test runs against a real Hermes server only when an explicit live-test flag, base URL, and token are all supplied.

**Tech Stack:** Python standard library (exercised in the project's Python 3.14 environment), `unittest`, Markdown.

## Global Constraints

- Validate only the private authenticated Hermes Responses API contract; never probe or
  document `/v1/chat/completions` as an alternative.
- Never print, store, or commit bearer tokens, private endpoint URLs, or live utterances/responses.
- Live verification must be opt-in and must use a harmless request with `stream: false`.
- Require exactly `security: {"tool_policy":"none","mcp_policy":"none",
  "server_enforced":true}` before either Responses POST.
- Treat live results as gateway-specific evidence; do not infer generic compatibility
  or pin a minimum Hermes version.

---

### Task 1: Deterministic contract verifier

**Files:**
- Create: `tools/hermes_contract.py`
- Create: `tests/test_hermes_contract.py`

**Interfaces:**
- Produces: `verify_contract(base_url, token, timeout=...) -> ContractEvidence`
- Produces: `live_config_from_env() -> tuple[str, str] | None`

- [x] Write unit tests that define request methods, paths, headers, the exact
  server-enforced no-tools security object, pre-POST rejection, the allowlisted response
  request, response schemas, bounded reads, HTTP errors, and explicit live-test gating.
- [x] Run the initial unit suite and confirm failure because `tools/hermes_contract.py` is absent.
- [x] Implement the smallest standard-library verifier that satisfies the tests without logging secrets or payload text.
- [x] Re-run the unit suite and confirm it passes.

### Task 2: Real-server evidence and documentation

**Files:**
- Modify: `README.md`
- Modify: `docs/installation-and-usage.md`
- Modify: `docs/architecture.md`
- Modify: `docs/plans/2026-07-12-initial-design.md`
- Create: `docs/hermes-responses-contract.md`

**Interfaces:**
- Consumes: `python -m tools.hermes_contract` with explicit live-test environment variables.
- Produces: evidence-backed contract matrix and documented unknowns.

- [x] Run the strengthened verifier without emitting the credential; it passed on
  2026-07-12 against the deployed private home gateway, including exact security-policy
  validation and two-turn continuity under one fresh verifier-run key.
- [x] Document only behavior exercised by the committed verifier; remove historical error, limit, header, model-value, and source-inspection assertions.
- [x] Record the result as gateway-specific evidence only, with no generic Hermes
  compatibility or minimum-version claim.
- [x] Update user, setup, architecture, security-status, and implementation-plan statements affected by the evidence.
- [x] Run all available tests/checks, inspect `git diff --check`, the full diff, and repository status.
- [x] Commit only this task with `test: validate Hermes Responses API contract`.
