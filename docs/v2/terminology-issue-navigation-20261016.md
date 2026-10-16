# B05 saved terminology issue navigation

Baseline: `0b0bebc3cc4e2a978aa8ac4aea260cd258b55a6e`. The containing local commit identifies this increment. B05 remains **PARTIAL**.

## Original-owner audit and bounded gap

`MultilingualEditionsService` already captures exact saved manuscript paragraphs, maintains independent edition text and glossary revisions, and computes literal case-sensitive terminology issues in its authorized `_view`. Original segment save/review/preview/export use edition CAS and source validation; approved and locked rules remain independently reviewed. Translation coordinator already supports saved-source/approved-term request preview, original local executor receipts, explicit candidate adoption to DRAFT and separate human acceptance. Translation memory and history already exist. None of these owners or contracts were replaced.

The missing usability seam was edition-wide issue count → exact affected paragraph → corresponding saved rule evidence. Authors otherwise had to select every paragraph to discover where the errors were. Issues carry original rule IDs/versions but the UI discarded those details, and `LOCKED_TERM_VARIANT` was shown as an untranslated code.

## Implemented loop

1. Select an existing original language edition. The original list/GET supplies saved source version, glossary revision and per-segment issues; no new request or check engine is introduced.
2. Browse affected paragraphs, bounded to 20 rows per page. Each row identifies chapter, source version, original path and issue count.
3. Explicitly locate a paragraph. Exact unique segment ID selects the original bilingual editor and focuses its textarea, without changing any bytes, selecting guessed offsets, applying suggested text or issuing requests. Repeated identical source text, emoji, combining marks and RTL text do not affect identity.
4. Inspect issue rule evidence, including exact rule version when present, approved status, matching policy, aliases and lock state. Conflict rules use both original IDs from the same edition snapshot. A missing/ambiguous/version-mismatched rule remains unavailable rather than substituting another rule.
5. Author manually edits the original target textarea, saves through original versioned PUT, then uses existing submit → preview → explicit acceptance. Saved responses recalculate the issue navigation. Rule changes still use the original separate glossary review controls.

Dirty input, active IME composition (including before the first text change), and active edition mutations disable navigation; duplicate segment IDs are not guessed. Existing client-remount, late-request, unsaved preservation and acceptance invalidation behavior stays intact. Withheld content hides the editor, glossary and new evidence even when a response independently sets `content_withheld`. This is a consumer-side content fence, not a new permission decision.

## Verification

Exact commands, timestamps, exit codes, log hashes and source hashes are in the adjacent JSON receipt index.

- 41 mocked UI/component checks: exact duplicate Unicode paragraph navigation, focus, no navigation requests, original CAS save, saved issue removal, dirty blocking, changed-rule mismatch, independent withheld flag, bounded pagination, duplicate-ID rejection, stale omission, existing review/translation candidate/memory/export/late-scope behavior and PUBLIC disabled entry.
- Three original nonsecurity File owner tests: glossary aliases/forbidden/review trace, rule conflicts blocking acceptance/export, duplicate Unicode paragraph alignment. One original pure Unicode matching test. These confirm existing contracts, not a new backend implementation.
- 30 PUBLIC packaging checks; forced TypeScript, Vite, test-discovery, design tokens, scoped raw-color guard, diff check and 487-file source closure.
- Independent review additionally hardened incomplete segment/issue evidence, duplicate rule IDs, same-edition conflict labeling, IME continuity and page clamping after refreshed rows shrink. Initial UI/type run rejected an unsupported Vitest assertion matcher. It was corrected to existing matchers; failed receipts remain preserved. The deliberately malformed duplicate-rule fixture also triggers the unchanged glossary list’s React duplicate-key warning; it does not select rule evidence.

## Boundaries

No new backend/schema/store/authorization/queue/provider, no model calls or paid work, no manuscript write, automatic translation, automatic term replacement/unlock, approval, or quality score. Saved issues are not a live check of unsaved text, a freshness guarantee without refresh, or translation-quality acceptance. Word-position highlighting is deliberately absent because the owner supplies no target offsets; whole-editor focus is the supported exact action.

Browser/visual/native accessibility, real HTTP integration, PG/P0/security lifecycle, GPU/Windows/user-machine/model quality and full RC are NOT_RUN. Existing P0 BLOCKED / R3-GATE HOLD, disabled production Prompt Adoption and blocked DeliveryCenter entitlement producer are unchanged. Broader B05 quality, durable unsaved recovery and translation UNKNOWN/history UI still need separate original-owner audits. No push or hosted CI: costs remain unknown. Parent independent review is required before another tracked feature slice.
