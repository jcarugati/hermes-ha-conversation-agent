# Hermes Responses API Contract Validation Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:test-driven-development to implement this plan task-by-task. Steps use checkbox syntax for tracking.

**Goal:** Establish and continuously verify the narrow Hermes HTTP contract used by the planned v0.1 Home Assistant adapter.

**Architecture:** Add a dependency-free Python verifier for `GET /health`, authenticated `GET /v1/capabilities`, and non-streaming `POST /v1/responses`. Unit tests run against a local deterministic HTTP fixture; a separate test runs against a real Hermes server only when an explicit live-test flag, base URL, and token are all supplied.

**Tech Stack:** Python 3.11 standard library, `unittest`, Markdown.

## Global Constraints

- Validate only the Hermes API contract; do not implement Home Assistant component features.
- Never print, store, or commit bearer tokens, private endpoint URLs, or live utterances/responses.
- Live verification must be opt-in and must use a harmless request with `stream: false`.
- Pin a minimum Hermes version only when a real contract run supplies evidence for it.

---

### Task 1: Deterministic contract verifier

**Files:**
- Create: `tools/hermes_contract.py`
- Create: `tests/test_hermes_contract.py`

**Interfaces:**
- Produces: `verify_contract(base_url, token, timeout=...) -> ContractEvidence`
- Produces: `live_config_from_env() -> tuple[str, str] | None`

- [x] Write unit tests that define request methods, paths, headers, the allowlisted response request, response schemas, bounded reads, HTTP errors, and explicit live-test gating.
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

- [x] Run the verifier against the reachable local Hermes server using an in-process credential lookup that never emits the credential.
- [x] Record only observed status codes, content types, schema fields, advertised model/capability, safe request options, errors proven by deterministic tests or upstream source, limits proven by upstream source, and the observed Hermes version.
- [x] Mark the minimum supported Hermes version as the lowest live-verified version, without inferring compatibility with earlier tags.
- [x] Update user, setup, architecture, security-status, and implementation-plan statements affected by the evidence.
- [x] Run all available tests/checks, inspect `git diff --check`, the full diff, and repository status.
- [x] Commit only this task with `test: validate Hermes Responses API contract`.
