# Hermes Conversation Bridge Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:test-driven-development to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Connect one official Home Assistant `ConversationEntity` per validated Hermes config entry to the existing allowlisted `HermesClient.async_respond` API.

**Architecture:** Setup retains the validated model with the entry-owned client, then forwards the entry to the conversation entity platform. Each entity sends only bounded input text, that model, and a fresh opaque conversation key to authenticated `POST /v1/responses`; it never uses chat completions, ignores inbound `ChatLog` and every other Home Assistant input field, adds only the bounded returned assistant text to HA's local `ChatLog` through its official no-tools completion method, and returns either final speech or a sanitized HA conversation error. Configuration, setup, and every turn require exactly `security: {"tool_policy":"none","mcp_policy":"none","server_enforced":true}`; there are no tool, MCP, action, instruction, or prompt-override fields.

**Tech Stack:** Python 3.14 and Home Assistant 2026.7.1 as the exercised development environment, the entity-based Conversation API, pytest-homeassistant-custom-component, Ruff, and mypy. These exercised versions are not a generic Hermes compatibility or minimum-version claim.

**Contract evidence:** The strengthened verifier passed on 2026-07-12 against the
deployed private home gateway with the exact server-enforced no-tools/no-MCP policy.
That live result is gateway-specific evidence only; it does not certify generic Hermes
servers or pin a minimum Hermes version.

---

### Task 1: Dispatcher-level bridge behavior

**Files:**
- Replace: `tests/test_conversation.py`
- Create: `custom_components/hermes_conversation/conversation.py`
- Modify: `custom_components/hermes_conversation/__init__.py`
- Modify: `custom_components/hermes_conversation/manifest.json`

- [x] Write failing tests that load real config entries and call `conversation.async_converse` against their registered entity IDs.
- [x] Prove the fake client's call contains only `model`, `utterance`, and opaque `conversation` keyword arguments and excludes ChatLog, context, device, user, credentials, tools, and actions.
- [x] Prove the real dispatcher completes HA's local `ChatLog` with only the bounded returned assistant text and that local content never enters the Hermes DTO.
- [x] Prove final speech, sanitized failure categories, no retry, authentication reauth, entry isolation, and unload/reload registration behavior.
- [x] Run `uv run pytest tests/test_conversation.py -q` and confirm failures are caused by the missing platform/entity bridge.
- [x] Implement the minimum runtime-data, platform forwarding, entity registration, request, and error mapping needed to pass.
- [x] Re-run the focused tests and refactor only while they remain green.

### Task 2: Lifecycle regression coverage

**Files:**
- Modify: `tests/test_init.py`

- [x] Update lifecycle assertions for runtime data containing both client and the setup-validated model.
- [x] Run `uv run pytest tests/test_init.py tests/test_config_flow.py -q` and fix only bridge-related regressions.

### Task 3: Required behavior documentation

**Files:**
- Modify: `README.md`
- Modify: `docs/installation-and-usage.md`
- Modify: `docs/architecture.md`
- Modify: `SECURITY.md`

- [x] Replace configuration-only status language with the exact implemented bridge behavior and exclusions.
- [x] State that v0.1 exposes no tools, MCP, actions, confirmation unlock, or prompt override and deliberately uses a fresh opaque key for every HA turn.

### Task 4: Verification and commit

**Files:**
- Verify all changed files.

- [x] Run the full local pytest, Ruff, mypy, package-layout, JSON, secret, lock, and
  shipped-runtime dependency gates. HACS remains a hosted CI action and hassfest has no
  locally callable gate in this custom-component repository.
- [x] Review the diff and repository status for scope and secret safety.
- [x] Commit all scoped changes without pushing or opening a pull request.

Gate note (2026-07-13): the shipped integration declares no runtime dependencies and
its runtime audit is clean. Auditing the complete development lock additionally reports
existing advisories in Home Assistant's transitive `pillow` and `pyjwt` packages; this
documentation-only task does not change dependencies.
