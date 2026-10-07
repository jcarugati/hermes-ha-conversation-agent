# Voice speed and understanding fixes

Branch `fix/voice-speed-understanding`, based on `main` (`a82a8a2`). One commit per item. Not pushed or merged.

| # | Item | Status | Commit | Regression test |
|---|---|---|---|---|
| 1 | Parser skips Responses `reasoning` items, never speaks them, still requires final assistant text, still rejects unknown types | Fixed | `3fcd552` | `test_reasoning_records_are_skipped_and_never_spoken`, `test_rejects_completed_response_with_only_tool_records[reasoning]` |
| 2 | Return HA's own `ChatLog.continue_conversation` (homeassistant 2026.7.1: true when the last assistant message ends in `?`, `;` or `？`) | Fixed | `3932102` | `test_continue_conversation_follows_ha_chat_log` |
| 3 | Speak a cleaned copy (Markdown markers, headings, bullets to sentences, `[text](url)` to text, bare URLs removed, emoji removed); numbers, units and negations kept; full text kept in the ChatLog; stdlib `re` only, linear time | Fixed | `b49dcbb` | `test_speech_text_cleans_markup_but_keeps_meaning`, `test_speech_is_cleaned_while_chat_log_keeps_original_text`, `test_speech_text_stays_linear_on_pathological_replies` |
| 4 | Health and capabilities use an independent 5 s total timeout (capped at the total timeout); the POST keeps the configured timeout | Fixed | `44e99a4` | `test_preflight_uses_short_timeout_and_post_keeps_configured_timeout` |
| 5 | POST 401/403 raises `HermesAuthenticationError` (entity starts reauth) instead of being wrapped as indeterminate; timeouts and transport failures stay indeterminate | Fixed | `e53fefe` | `test_post_authentication_rejection_is_not_indeterminate` |
| 6 | Skip the advertised-default-model equality check when a model alias is configured; keep it otherwise | Fixed | `da7ac30` | `test_model_alias_ignores_a_changed_advertised_default_model` (existing `test_capability_model_mismatch_prevents_post` still covers the no-alias case) |
| 7 | One `_LOGGER.debug` line per turn: monotonic preflight and POST durations, outcome class name, reply length. No transcript, reply text, token, URL or conversation key | Fixed | `05a1da4` | `test_turn_debug_log_has_timings_and_outcome_without_private_data` |
| 8 | Single option-defaults source in `const.py` (total timeout 90 s); entries without a saved option now get 90 s like new entries, instead of the old 30 s client fallback. Explicitly saved values are unchanged | Fixed | `0e36a89` | `test_entry_without_saved_timeout_uses_new_entry_default` |
| 9 | Docs: README, installation, architecture and SECURITY updated. Each states plainly that Hermes ignores `reasoning_effort` in `model_routes` and documents `agent.reasoning_overrides` (all channels on that model). They also recommend "Prefer handling commands locally" with its tradeoff and include a `platform_hints.api_server` voice example | Fixed | `374724c` | Documentation only |

## Verification

- `uv run pytest -q`: 196 passed, 1 skipped, 18 subtests passed. Each commit was also checked out and passed on its own.
- Each new regression test was run against the pre-fix code and failed there.
- `python -m compileall` (custom_components, tools, tests), `ruff check`, `ruff format --check`, `mypy` (strict) and `git diff --check`: clean.
- The request DTO is still exactly `{model, input, conversation, stream: false}`. Nothing is retried after dispatch, and no dependencies were added.

## Environment notes

- `uv` was not on `PATH`. I used the existing `~/.hermes/bin/uv` (`PATH=$HOME/.hermes/bin:$PATH`) and changed nothing in the repo.
- Git had no identity configured. Commits use the author already in this repo's history (Javier Carugati), passed with `git -c`. No git config was modified.

## Audit claims checked and not acted on

- **Custom `?` heuristic for continue_conversation (Opus):** replaced by HA's own `ChatLog.continue_conversation`, as instructed. It reads the original reply, so a question followed by an emoji or Markdown does not reopen the mic. The docs ask for a plain-text Hermes hint.
- **Astra's suggestion to wait for an explicit clarification signal before reopening the mic:** not adopted; HA's built-in rule was requested instead.
- **Opus: with CONTROL, HA excludes `HassGetState` "and possibly timers" from local handling:** half wrong. The 2026.7.1 filter excludes `HassGetState` and media search/play only. The docs state that.
- **Replacing bare URLs with "un enlace" (Opus):** URLs are removed instead, which works in any language. The integration accepts every language.
- **Truncating long replies to about 600 characters (Opus, optional):** not requested. Cut speech would hide information that the ChatLog still has.
- **Hermes can return its error text as a completed message (Opus H9):** confirmed in `_extract_output_items`. Fixing it needs a Hermes change or a text heuristic; out of scope.
- **Hermes-side and HA-pipeline items (agent build time, context-window pin, tool_search, plugin name matching, STT/VAD/wake word, title generation, the 65 s poller):** out of scope for this repo. No poller exists in this integration.
- **Streaming and capability caching:** out of scope.

## Round 2

This round fixes the items from the Astra review of round 1: 3 blocking and 2 non-blocking. I checked each one against the code before fixing it; all five reproduced. One commit per item; each also updates README, installation, architecture and SECURITY. Not pushed or merged.

| # | Item | Status | Commit | Regression test |
|---|---|---|---|---|
| R1 | Blocking. The cleanup removed signs and operators: `- 5 °C` became `5 °C` and `2*3 W` became `23 W`. It now strips only recognized Markdown delimiters: emphasis/code pairs (`*`, `_`, `~~`, backticks, which must not touch a word character outside or a space inside), headings, and bullet markers at the start of a line. A line-start `-`/`+` followed by a number counts as a sign. | Fixed | `365b09e` | `test_speech_text_cleans_markup_but_keeps_meaning` (sign, arithmetic and emphasis-pair cases), `test_speech_text_stays_linear_on_pathological_replies[star-openers, underscore-openers]` |
| R2 | Blocking. Every line break became a sentence boundary (`No\nhay alarmas` turned into `No. hay alarmas`). Wrapped prose now joins with a space. A boundary goes only before a heading or list item (bullet, `1.`, `1)`) and after a heading. | Fixed | `58be3e9` | `test_speech_text_cleans_markup_but_keeps_meaning` (wrapped negation; heading, blank line, lazy list continuation) |
| R3 | Blocking. When cleanup removed everything, the raw reply was spoken. Now, if no letter or digit is left, the entity returns a fixed error ("La respuesta no se puede leer en voz alta. Revisa el estado antes de intentarlo de nuevo."). It does not claim success, keeps the original in the ChatLog and does not reopen the mic. | Fixed | `3b5ca29` | `test_unspeakable_reply_speaks_fixed_failure_and_keeps_original[emoji, url, question]`, plus `""` cases in `test_speech_text_cleans_markup_but_keeps_meaning` |
| R4 | Non-blocking. Validation failures logged no timing line. Validation and the request-size check now run inside the logging scope, so an empty, too-long or oversized request logs one line with `0.000 s` for both durations and outcome `ValueError`. | Fixed | `716d476` | `test_validation_failure_logs_one_turn_line_with_zero_network_time[empty, too-long, oversized-request]` |
| R5 | Non-blocking, pre-existing. Whitespace-only assistant output was accepted. The parser now rejects assembled assistant text with no non-whitespace character, so the POST failure is indeterminate, as before, and is not retried. | Fixed | `3fb5722` | `test_whitespace_only_assistant_output_is_indeterminate_and_not_retried[whitespace, reasoning]` |

### Decisions and behavior changes

- **Intraword `_` is no longer turned into a space.** Round 1 spoke `light.living_room` as `light.living room`. That is not a Markdown delimiter, so `_` is now stripped only as part of an emphasis pair (`__Ojo__`, `_nota_`). The existing test expectation was changed to `light.living_room`.
- **Only paired backticks are stripped.** A lone backtick or a fenced-code marker stays. Backticks carry no spoken meaning, but the rule is "recognized delimiters only".
- **A sign is not a bullet.** A line such as `- 5 luces` keeps its `-`, and is not treated as a list item for sentence boundaries. The cleaner cannot tell a bullet before a count from a negative value, and dropping a real minus sign changes meaning. `- -5 °C` and `- No hay` are still treated as bullets.
- **"Empty" means no letter or digit left,** not only `""`. For example, `¿🤔?` cleans to `¿?`. Because HA's own rule would reopen the mic for that reply's trailing `?`, the result also sets `continue_conversation` to false whenever the response is an error, which keeps the documented rule that error turns never continue.
- **Whitespace is checked on the assembled text.** A whitespace part next to real text is still accepted.
- Commit subjects start with "Fix …" as requested. Round 1 used `fix:`.

### Verification

- `~/.hermes/bin/uv run pytest -q`: 213 passed, 1 skipped, 18 subtests passed. Each round-2 commit was extracted with `git archive` and passed on its own (201, 203, 208, 211, 213 passed).
- Each new or changed regression case was run against the parent commit's code and failed there. The R3 `continue_conversation` guard was also checked by removing it: the `question` case then fails.
- `ruff check`, `ruff format --check`, `mypy` (strict) and `git diff --check`: clean.
- The cleanup stays linear: hostile 8 KiB inputs (runs of `*a `, `**a `, `_a `, `~~a `, backticks, `#`, `- `) each take about 1 ms.
- The request DTO is still exactly `{model, input, conversation, stream: false}`. Nothing is retried after dispatch, and no dependencies were added.
