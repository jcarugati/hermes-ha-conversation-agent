# Hermes Conversation Bridge Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:test-driven-development to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Connect one official Home Assistant `ConversationEntity` per validated Hermes config entry to the existing allowlisted `HermesClient.async_respond` API.

**Architecture:** Setup retains the validated model with the entry-owned client, then forwards the entry to the conversation entity platform. Each entity sends only bounded input text, that model, and a fresh opaque conversation key; it ignores `ChatLog` and every other Home Assistant input field and returns either final speech or a sanitized HA conversation error.

**Tech Stack:** Python 3.14, Home Assistant 2026.7 entity-based Conversation API, pytest-homeassistant-custom-component, Ruff, mypy.

---

### Task 1: Dispatcher-level bridge behavior

**Files:**
- Replace: `tests/test_conversation.py`
- Create: `custom_components/hermes_conversation/conversation.py`
- Modify: `custom_components/hermes_conversation/__init__.py`
- Modify: `custom_components/hermes_conversation/manifest.json`

- [ ] Write failing tests that load real config entries and call `conversation.async_converse` against their registered entity IDs.
- [ ] Prove the fake client's call contains only `model`, `utterance`, and opaque `conversation` keyword arguments and excludes ChatLog, context, device, user, credentials, tools, and actions.
- [ ] Prove final speech, sanitized failure categories, no retry, authentication reauth, entry isolation, and unload/reload registration behavior.
- [ ] Run `uv run pytest tests/test_conversation.py -q` and confirm failures are caused by the missing platform/entity bridge.
- [ ] Implement the minimum runtime-data, platform forwarding, entity registration, request, and error mapping needed to pass.
- [ ] Re-run the focused tests and refactor only while they remain green.

### Task 2: Lifecycle regression coverage

**Files:**
- Modify: `tests/test_init.py`

- [ ] Update lifecycle assertions for runtime data containing both client and the setup-validated model.
- [ ] Run `uv run pytest tests/test_init.py tests/test_config_flow.py -q` and fix only bridge-related regressions.

### Task 3: Required behavior documentation

**Files:**
- Modify: `README.md`
- Modify: `docs/installation-and-usage.md`
- Modify: `docs/architecture.md`
- Modify: `SECURITY.md`

- [ ] Replace configuration-only status language with the exact implemented bridge behavior and exclusions.
- [ ] State that the bridge exposes no tools/actions or confirmation unlock and that conversation lifecycle features remain separate tasks.

### Task 4: Verification and commit

**Files:**
- Verify all changed files.

- [ ] Run the full pytest, Ruff, mypy, package-layout, Home Assistant/hassfest, HACS, secret, and dependency gates available in the repository/CI configuration.
- [ ] Review the diff and repository status for scope and secret safety.
- [ ] Commit all scoped changes without pushing or opening a pull request.
